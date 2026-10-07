# Tasks: Feature 005 — Disruption Re-planning, Notifications and Milestone Tracking

**Constitution:** v1.1.0 · **Prerequisite:** Feature 004 Phase 1 (Vaikom node) and the 006 backend already in tree.
Every phase ends with the full suite (`pytest backend/ -q`; baseline 100 passed). `[P]` = parallel-safe.

## Phase 1 — Config and seed

- [x] T501 [P] `data/config.yaml`: `replan.severity_minor_max_h` (2), `severity_moderate_max_h` (6), `wait_cost_per_t_h` (20), `road_blocked_delay_h` (2), `weather_reliability_penalty` (0.10), `max_alternatives` (5); `tracking.loading_lead_h` (0.5), `tracking.unloading_h` (0.5). All `assumed` + note. (FR-1, FR-2, FR-3)
- [x] T502 [P] `data/config.yaml`: `notifications` list — 5 templates (`type`, `subject_en`, `body_en` with `{cargo_id} {location} {deadline}`, `body_ml_placeholder` marked "requires professional translation", `source_status: assumed`). (FR-5)
- [x] T503 `data/seed.json`: `sailing-001.route_node_ids` through Vaikom; `disruption_scenarios` (breakdown at `node-004`; jetty_closed at `node-002`), `source_status:"simulated"`. (FR-10)
- [x] T504 `backend/engine/config.py`: `get_scoring_weights()`; no behaviour change. (P3)
- [x] T505 Regression: full suite green.

## Phase 2 — Tests first

- [x] T510 [P] `backend/engine/tests/test_tracking.py`: milestone order; advance from Delivered → structured `final_milestone`; `current_node` for each milestone incl. two-node route; schedule times derive from departure + sail time; `format_hhmm` wraparound; `elapsed_h` across midnight.
- [x] T511 [P] `backend/engine/tests/test_replan.py`: severity boundaries (1.99/2/6/6.01/null/deadline-missed); each alternative type feasibility + omission; `vessel_breakdown` removes booking vessel; `low_depth` removes sailings through node; `jetty_closed` removes origin/destination sailings; `road_blocked` adds delay; `weather_delay` lowers water reliability; SC-1 (≥2 types, different trade-offs); SC-2 (remaining 1.5 h → top is `truck_from_jetty`); SC-4 (return cost == hand-calculated road cost; `distance_already_travelled_km` present); SC-5 (no alternatives → empty, flag, no exception); FR-4 fallback id = min time; tie → lower cost; max 5; input not mutated (deep-equal before/after); determinism; hazardous cargo filters uncertified/unverified/suspended vessels; hold_warehouse omitted with no eligible warehouse.
- [x] T512 [P] `backend/engine/tests/test_replan.py` (notifications): all five types render non-empty, no unresolved `{}` placeholders, `delivered` false (SC-7).
- [x] T513 [P] `backend/api/tests/test_replan_api.py`: booking snapshot fields; advance ×4 then error (SC-6); advance on disrupted/unconfirmed; trigger disruption (invalid type/duration/node/duplicate/unconfirmed); propose leaves booking deep-equal (SC-3), repeat returns same id; confirm happy path; confirm twice; stale; unknown alternative; no proposal; hazardous class needs replan review; notify for all types (SC-7); summary empty + populated; full cycle then reset restores Booked/confirmed (SC-8); disruption on suspended-vessel booking works (suspension does not block disruption handling).

## Phase 3 — Engine

- [x] T520 `backend/engine/tracking.py`. T510 passes.
- [x] T521 `backend/engine/replan.py` (imports only `options`, `hazards`, `warehouse`, `geo`, `config`, `tracking`; no adapter import). T511–T512 pass.
- [x] T522 Regression: full suite green.

## Phase 4 — State and API

- [x] T530 `backend/data_store.py`: disruption, proposal and replan-review stores; reset clears (P8: < 1 s).
- [x] T531 `backend/api/routers/booking.py`: booking snapshot fields; `GET /api/booking/{id}`; `deliver` interplay with 004 (milestone set to Delivered).
- [x] T532 `backend/api/models.py`: request/response models (extra fields forbidden on trigger/confirm bodies; `human_confirmed` in proposal body ignored per P12).
- [x] T533 `backend/api/routers/tracking.py` (advance, disrupt, scenarios) and `backend/api/routers/replan.py` (propose, confirm, notify, summary, replan-review). Event ids deterministic.
- [x] T534 `backend/api/main.py` registration; `specs/005-…/contracts/openapi.yaml`.
- [x] T535 T513 passes; full suite green.

## Phase 5 — CHECKPOINT: curl every endpoint

- [x] T540 Start server; curl every 005 endpoint (happy + one error each), full hero cycle: book → confirm → advance → disrupt → replan → confirm → notify → summary → reset. Paste outputs into `specs/005-…/quickstart.md`. **STOP for user review.**

## Phase 6 — Frontend

- [x] T550 [P] `MilestoneTimeline.jsx`, [P] `DisruptionPanel.jsx` ("Demo control — simulated disruption"), [P] `ReplanAlternatives.jsx` (side-by-side; explicit "Accept this plan"; dismiss accepts nothing; deadline text label + colour), [P] `NotificationPreview.jsx` ("message preview — not sent [simulated]"), [P] `DisruptionSummary.jsx`.
- [x] T551 Wire into `frontend/src/App.jsx`; every number shows `[assumed]`/`[simulated]` badge via `SourceBadge`.

## Phase 7 — Final validation

- [x] T560 Full suite exit 0; original 100 tests still present (additions only in test-file diffs).
- [ ] T561 Grep hardcoded constants in `backend/engine/` and routers (`[0-9]+\.[0-9]+` and bare thresholds); resolve or justify each.
- [x] T562 Grep LLM use in engine: `grep -rniE "llm|adapter|watsonx|granite|openai" backend/engine/ --include=*.py` → 0 matches.
- [ ] T563 Verify `POST /api/replan/{id}` leaves booking byte-identical (covered by SC-3 test) and no code path sets `replanned` outside confirm: `grep -rn "replanned" backend/` reviewed.

## Dependencies

T501–T505 → T510–T513 → T520–T522 → T530–T535 → **T540 checkpoint** → T550–T551 → T560–T563.
Feature 004 T402/T403 (Vaikom, vessel fields) must land first.

## Cut list (in order)

1. `DisruptionSummary` UI (keep endpoint). 2. `hold_warehouse` alternative. 3. `low_depth`/`weather_delay` variants (keep enums, treat as delay).
4. Operator-side disruption view. Never cut: confirm gate, labels, SC-3, reset.

## Progress note (2026-10-07)

Backend T501-T535 complete; checkpoint T540 run against a live server (hero cycle: book, confirm, advance, disrupt, replan, confirm, summary, reset). Frontend delivered as role-based screens in `MyShipments.jsx` (timeline, simulate-disruption, notification card, alternatives, confirm dialog) rather than the five separate component files planned. Deviations from the plan: `replan_proposed` is logged at confirm; hazardous re-plans need `POST /api/compliance/replan-review/{proposal_id}/approve`; the disruption trigger is `POST /api/demo/booking/{id}/disrupt`; `POST /api/cargo` and `GET /api/bookings` were added for the UI. Not done: T561 numeric-literal review is partial (only unit conversions and rounding remain in the new engine files); T563 manually reviewed.
