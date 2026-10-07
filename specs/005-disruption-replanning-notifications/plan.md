# Implementation Plan: Feature 005 — Disruption Re-planning, Notifications and Milestone Tracking

**Feature ID:** 005 · **Phase:** Plan · **Date:** 2026-10-07 · **Constitution:** v1.1.0
**Depends on:** 004 (vessel status, delivery), 006 (`hazards.py`, `warehouse.py`, compliance gate)

## 1. Technical Context

Existing stack, no new dependencies. INR, tonnes, IST. State in-memory with `reset()`.
LLM involvement: **none** in this feature. (Operator-message parsing for registration is Feature 004;
the re-plan engine never touches an adapter.)

### 1.1 New files

| File | Purpose |
|---|---|
| `backend/engine/tracking.py` | Pure: `MILESTONES`, `milestone_schedule()`, `advance_milestone()`, `current_node()`, `elapsed_h()`, `format_hhmm()` |
| `backend/engine/replan.py` | Pure: `classify_severity()`, `replan()`, `render_notification()` |
| `backend/api/routers/replan.py` | `POST /api/replan/{id}`, `/confirm`, `POST /api/booking/{id}/notify`, `GET /api/disruptions/summary`, `POST /api/compliance/replan-review/{proposal_id}/approve` |
| `backend/api/routers/tracking.py` | `GET /api/booking/{id}`, `POST /api/demo/booking/{id}/advance`, `POST /api/demo/booking/{id}/disrupt`, `GET /api/demo/disruption-scenarios` |
| `backend/engine/tests/test_tracking.py`, `test_replan.py` | tests first |
| `backend/api/tests/test_replan_api.py` | SC-3, SC-5…SC-8 at API level |
| `frontend/src/components/MilestoneTimeline.jsx`, `DisruptionPanel.jsx`, `ReplanAlternatives.jsx`, `NotificationPreview.jsx`, `DisruptionSummary.jsx` | UI |

### 1.2 Modified files

| File | Change |
|---|---|
| `data/config.yaml` | `replan` (severity thresholds, wait cost, road-blocked delay, weather reliability penalty, max alternatives), `tracking` (loading lead, unloading time), `notifications` (5 templates) — all `assumed` |
| `data/seed.json` | Vaikom as intermediate node (from 004); `sailing-001.route_node_ids = [node-001, node-004, node-002]`; `disruption_scenarios` (2, `simulated`) |
| `backend/data_store.py` | `_disruptions`, `_replan_proposals`, `_replan_reviews`; reset clears; booking extensions |
| `backend/api/routers/booking.py` | booking stores `weight_t`, `deadline_h`, `ready_time`, `planned_cost_inr`, `planned_time_h`, `milestone_index`, `event_log`, `vessel_id`, `mode` |
| `backend/engine/config.py` | `get_scoring_weights()` shared accessor (also removes the `.get(…, 0.40)` literal fallbacks in options.py — separate cleanup task) |
| `backend/api/models.py`, `main.py`, `routers/demo.py` | models, routers, reset |
| `specs/005-…/contracts/openapi.yaml` | contract (new) |

## 2. Constitution Check

| Principle | Status | Note |
|---|---|---|
| P2 | ✅ | `replan()` pure; `now_hhmm` passed as arg; ids minted in router |
| P3 | ✅ | thresholds, penalties, waiting cost, templates in config (`assumed`) |
| P5 | ✅ | tests precede implementation |
| P8 | ✅ | no network; `now_hhmm` override; reset < 1 s |
| P11 | ✅ | hazard filters apply to alternatives; replan confirm needs a review for review-required classes |
| P12 | ✅ | propose = read-only; confirm = explicit; `replan_proposed` event written only at confirm |
| P13 | ✅ | every milestone/disruption/event/preview carries `source_status: "simulated"` |

## 3. Design decisions

1. **Current node** (assumption 1 refined): `Booked`/`Loading` → route[0]; `In Transit` → the route node
   before the destination (spec FR-10 "last waterway node before destination"), or route[0] on a
   two-node route; `Arrived`/`Delivered` → route[-1].
2. **Elapsed time**: `(now − ready_time) mod 24 h`; remaining = `deadline_h − elapsed`.
3. **Alternatives** — all costs ₹, all from config:
   - `wait_and_continue`: extra = `W × wait_cost_per_t_h × expected_duration_h`; new total = planned + duration.
   - `truck_from_jetty`: road plan from current node to destination via `build_plans(...).plans["road"]`
     (reuses road model; `sailings=[]`); `road_blocked` adds `road_blocked_delay_h`.
   - `alternative_vessel`: `build_plans` from current node with candidate sailings (disruption filters,
     hazard filters, vessel status) → hybrid plan.
   - `return_to_origin`: extra = road cost current→origin (SC-4); also reports `distance_already_travelled_km`
     and `already_travelled_cost_inr` separately (sunk, informational). Feasible only if current ≠ origin.
   - `hold_warehouse`: eligible warehouse via Feature 006 `find_eligible_warehouses`; extra =
     handling_in + storage (`ceil(duration/24)` days, min 1) + handling_out; requires known duration.
4. **Ranking**: weights from `scoring.weights` (config); normalised across alternatives on
   `extra_cost`, `new_total_time_h`, CO₂, reliability; ties → lower extra cost. Max 5 returned.
5. **Fallback** (FR-4): none meets deadline → all `deadline_met:false`, `fastest_fallback_id` set.
6. **Severity**: pure; `duration null` → `severe` (conservative, assumed); thresholds in config.
7. **Proposal id**: deterministic `"{booking_id}:{disruption_id}"`; one live proposal per booking.
8. **Notifications**: template render only; `delivered:false` always; Malayalam placeholder not rendered.
9. **Confirm** applies chosen alternative to the booking (`status: replanned`, plan fields, event log:
   `replan_proposed`, `replan_confirmed`, `notification_preview`), closes disruption. No sailing capacity change.

## 4. Error codes

`booking_not_disruptable`, `disruption_already_open`, `no_proposal`, `proposal_stale`, `unknown_alternative`,
`replan_already_confirmed`, `compliance_review_required`, `booking_not_active`, `booking_disrupted`,
`final_milestone`, `invalid_duration`.

## 5. Known weaknesses (reported with every task batch)

- Seed corridors are tiny; most alternatives collapse to road/wait on the hero route.
- Sunk-cost treatment is a simplification; CO₂ for non-road alternatives is carried or 0.
- Replan never frees or consumes sailing capacity.
