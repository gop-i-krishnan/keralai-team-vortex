# Implementation Plan: Feature 004 — Vessel Registration and Delivery History

**Feature ID:** 004 · **Phase:** Plan · **Date:** 2026-10-07 · **Constitution:** v1.1.0
**Depends on:** 001–003 (existing), 006 (`hazards.py`, hazard rules, compliance gate)

## 1. Technical Context

Existing stack, no new dependencies: FastAPI, pydantic v2, React + Vite, in-memory
`backend/data_store.py` with `reset()`. Units: INR, tonnes, metres, IST (HH:MM strings).

### 1.1 New files

| File | Purpose |
|---|---|
| `backend/engine/registry.py` | Pure: `validate_registration()`, `validate_sailing()`, `transition_status()`, `vessel_effective_status()` |
| `backend/engine/history.py` | Pure: `build_delivery_record()`, `compute_reliability()` (Bayesian), `reliability_trend()` |
| `backend/api/routers/vessel.py` | `POST /api/vessel/register`, `GET /api/vessel/list`, `POST /api/sailing/publish`, admin verify/suspend/reinstate, `POST /api/vessel/parse-message` |
| `backend/engine/tests/test_registry.py`, `test_history.py` | Tests first (P5) |
| `backend/api/tests/test_vessel_api.py` | API tests SC-1, SC-5…SC-7 |
| `frontend/src/components/VesselForm.jsx`, `OperatorProfile.jsx`, `VesselStatusBadge.jsx` | UI |

### 1.2 Modified files

| File | Change |
|---|---|
| `data/config.yaml` | `history` (prior k, prior_rate, midnight_wrap_h), `registry` (unverified_reliability_penalty), `meta.ist_offset_min` |
| `data/seed.json` | Vaikom node; 7 vessels with draft/home jetty/status/contact; `delivery_history`; vessel/operator/sailing `source_status: simulated` |
| `backend/data_store.py` | `delivery_history` list in `_state` (auto-reset); add/get helpers for vessels, sailings, deliveries |
| `backend/engine/hazards.py` | vessel-status filters: `vessel_suspended`, `unverified_vessel_for_hazmat` (before mode/cert) |
| `backend/engine/matching.py` | unverified penalty, `cost_inr` from `price_per_t`, suspended exclusion for non-hazard path |
| `backend/engine/parser.py` | `parse_vessel_message()` regex helper (pure; `scrub_pii` first) |
| `backend/api/routers/booking.py` | `POST /api/booking/{id}/deliver`; confirm guard `vessel_suspended` |
| `backend/api/routers/operator.py` | `GET /api/operator/{id}/profile` |
| `backend/api/models.py`, `backend/api/main.py` | models, router registration |
| `specs/004-…/contracts/openapi.yaml` | contract (new) |

## 2. Constitution Check

| Principle | Status | Note |
|---|---|---|
| P2 | ✅ | registry/history pure; times passed in; no uuid/clock in engine (ids minted in router) |
| P3 | ✅ | `k`, `prior_rate`, penalty, wrap constant in config, `assumed` |
| P5 | ✅ | test tasks precede implementation tasks |
| P7 | ✅ | message-parsed registration needs explicit Confirm (registration call) |
| P10 | ⚠ | admin endpoints unauthenticated (demo-only, labelled); spec-sanctioned |
| P11 | ✅ | `unverified_vessel_for_hazmat` hard filter; appears in `excluded` |
| P12 | ✅ | suspension never alters or switches confirmed bookings |
| P13 | ✅ | seed vessel/operator/history `source_status: simulated`; runtime deliveries `recorded` |
| P14 | ✅ | label `"N trips [simulated]"` always paired with %; no subjective input |
| P15 | ✅ | `scrub_pii` before adapter; contact is fictional |

## 3. Design decisions

1. **Reliability** `(on_time + k·prior)/(total + k)` — pure, 4-dp rounded. Zero records → `prior_rate`.
2. **Vessel status** default `verified` when the field is absent (legacy fixtures keep passing).
3. **Matching order**: suspended → (hazard filters incl. unverified-for-hazmat) → capacity/route → score
   (`− penalty` if pending_verification, floor 0) → sort (−score, cost).
4. **Sailing record** keeps existing keys + `route_node_ids`, `price_per_t`, `source_status:"recorded"`.
5. **Ids** minted in routers (`vessel-<n>`, `sailing-<n>`, `del-<n>` via counters from store length) so
   engine stays pure and ids are deterministic after reset.
6. **Deliver** is the only writer of delivery records (see 005 clarification).
7. **Operator id** required on registration (needed for the profile view; spec FR-4 omits it — see analysis).
8. **Fallbacks (P8)**: LLM unavailable → regex helper; no network on any path.

## 4. Error codes

`invalid_transition`, `duplicate_vessel`, `vessel_suspended`, `already_delivered`,
`booking_not_deliverable`, `invalid_time`, field errors `{field, code, message}` with codes
`required`, `not_positive`, `not_found`, `exceeds_vessel_capacity`, `too_few_stops`.

## 5. Risks / known weaknesses

- Reliability stats do not affect ranking (only the unverified penalty does).
- Verification is a one-click simulated action with no identity check.
- Vaikom node coordinates are approximate and `assumed`.
