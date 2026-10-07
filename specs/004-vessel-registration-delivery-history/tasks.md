# Tasks: Feature 004 — Vessel Registration and Delivery History

**Constitution:** v1.1.0 · **Baseline:** `pytest backend/ -q` = 100 passed (2026-10-07). Every phase
ends with the full suite; no existing test may be removed or weakened.
`[P]` = independent of other tasks in the same phase (different files).

## Phase 1 — Data layer (no code logic)

- [x] T401 [P] `data/config.yaml`: add `history.prior_trip_count` (5), `history.prior_on_time_rate` (0.80), `history.midnight_wrap_h` (12), `registry.unverified_reliability_penalty` (0.10), `meta.ist_offset_min` (330, sourced: UTC+05:30). All `assumed` except the offset; each with `note`. (FR-2, FR-7, P3)
- [x] T402 [P] `data/seed.json`: add `node-004` Vaikom (`assumed`, note "verify with IWAI / Kerala State Water Transport Dept."). **User review required.** (SC-2)
- [x] T403 `data/seed.json`: expand to 7 vessels (existing 3 + 4 new, all fictional names) with `draft_m`, `home_jetty_id`, `status`, `contact` (`simulated@…example`), `type`, `registration_number` ("placeholder"), `source_status:"simulated"`. One `pending_verification`; one with zero history; one verified with ≥10 records. Existing ids/capacities/certs unchanged. (FR-6, P13, P15)
- [x] T404 `data/seed.json`: add `delivery_history` array (6–12 records for others, ≥10 for the mature vessel, 0 for the zero-history vessel), all `source_status:"simulated"`. (FR-6)
- [x] T405 `backend/data_store.py`: ensure `delivery_history` is part of `_state` (reset-safe); helpers `get_delivery_history()`, `add_delivery(record)`, `add_vessel()`, `add_sailing()`, `get_vessel_by_id()`. (FR-11)
- [x] T406 Regression: `pytest backend/ -q` → 100 passed.

## Phase 2 — Tests first (all must fail before implementation)

- [x] T410 [P] `backend/engine/tests/test_history.py`: zero records → prior_rate/0 trips (SC-3); hand-calculated 5-trip example; `on_time` +1 changes rate to expected value (SC-4); trend length == records; `late`/`incident` status taken from caller not delay; `delay_min` negative = early; midnight wrap; determinism (same input twice); no subjective inputs accepted.
- [x] T411 [P] `backend/engine/tests/test_registry.py`: each required field missing/zero/negative → its own `{field,code}` (SC-6); unknown jetty `not_found`; sailing `exceeds_vessel_capacity`, `too_few_stops`, empty weekdays, price ≤ 0; transitions table incl. every invalid transition → `invalid_transition`; legacy vessel without status → `verified`.
- [x] T412 [P] `backend/engine/tests/test_hazards.py` (append): suspended → `vessel_suspended`; pending vessel + flammable → `unverified_vessel_for_hazmat` (SC-5); pending vessel + general → eligible.
- [x] T413 [P] `backend/engine/tests/test_matching.py` (append): pending vessel score = verified score − penalty; suspended excluded with reason (not silently dropped); equal scores ordered by lower `cost_inr` (real values from `price_per_t`).
- [x] T414 [P] `backend/engine/tests/test_parser.py` (append): hero message → capacity 12, type "barge", home "Vaikom", route hint "Alappuzha" (SC-2); PII scrubbed first; malformed text → low confidence, no exception.
- [x] T415 [P] `backend/api/tests/test_vessel_api.py`: register → publish → `/api/match` shows sailing (SC-1); validation errors; duplicate; verify/suspend/reinstate + invalid transitions; suspended vessel with confirmed booking leaves booking unchanged and blocks confirm of a pending one; deliver happy path, repeat → `already_delivered`, bad time, bad status, unconfirmed booking; profile with zero history; unknown operator 404; reset removes runtime vessels/sailings/records (SC-7).

## Phase 3 — Engine implementation

- [x] T420 `backend/engine/history.py` (pure; constants via `val`). Makes T410 pass.
- [x] T421 `backend/engine/registry.py` (pure). Makes T411 pass.
- [x] T422 `backend/engine/hazards.py`: add vessel-status filters ahead of mode/cert filters. T412 pass.
- [x] T423 `backend/engine/matching.py`: penalty, `cost_inr`, tie-break. T413 pass; legacy list return path unchanged.
- [x] T424 `backend/engine/parser.py`: `parse_vessel_message()` (regex fallback only; no LLM import). T414 pass.
- [x] T425 Regression: full suite green.

## Phase 4 — API

- [x] T430 `backend/api/models.py`: `VesselRegisterRequest`, `SailingPublishRequest`, `DeliverRequest`, response models; `BookingRequest` unchanged.
- [x] T431 `backend/api/routers/vessel.py` (register, list, publish, admin transitions, parse-message). Parse-message calls `scrub_pii` then the existing adapter pattern; fallback regex (P8).
- [x] T432 `backend/api/routers/booking.py`: `deliver` endpoint; confirm guard `vessel_suspended`. `backend/api/routers/operator.py`: profile endpoint.
- [x] T433 `backend/api/main.py`: register router. `specs/004-…/contracts/openapi.yaml`: document every endpoint.
- [x] T434 Run T415; full suite green.

## Phase 5 — CHECKPOINT: curl every endpoint

- [x] T440 Start server (`JALSETU_MOCK_LLM=1`), curl each 004 endpoint (happy path + one error each), paste results into `specs/004-…/quickstart.md`. Includes reset-then-verify. **STOP for user review.**

## Phase 6 — Frontend (after checkpoint approval)

- [x] T450 [P] `VesselStatusBadge.jsx` (text label + `[simulated]`), [P] `VesselForm.jsx` (field-level errors; message-parse editable preview; Confirm button), [P] `OperatorProfile.jsx` ("NN% — N trips [simulated]", trend, history list).
- [x] T451 Wire into `frontend/src/App.jsx`; "Mark Verified" with simulated notice; suspended notice text.

## Phase 7 — Final validation

- [x] T460 `pytest backend/ -q` exits 0; record count; confirm the original 100 still present (no deletions: `git diff --stat` on test files shows additions only).
- [x] T461 Grep engine for hardcoded constants: `grep -rnE "[0-9]+\.[0-9]+" backend/engine/*.py` — each match justified or moved to config.
- [x] T462 Grep for LLM use in engine: `grep -rniE "llm|adapter|watsonx|granite|openai" backend/engine/ --include=*.py` → 0 matches.
- [ ] T463 Update `docs/disclosures.md` if any dependency/tool changed (expected: none).

## Dependencies

T401–T405 → T406 → T410–T415 → T420–T424 → T425 → T430–T434 → **T440 checkpoint** → T450–T451 → T460–T463.

## Cut list (drop in this order if time runs out)

1. Reliability trend chart (keep JSON field). 2. Message-based registration UI (keep endpoint).
3. `reinstate` endpoint. 4. Vessel list filters. Never cut: validation, hazmat/unverified filter, tags, tests.

## Progress note (2026-10-07)

T401–T440 complete: `pytest backend/ -q` = 181 passed (100 original + 81 new). T433 contract `openapi.yaml` and T461/T462 greps: grep done (no LLM imports in engine; only unit-conversion literals), `contracts/openapi.yaml` NOT yet written. Phase 6 (frontend) awaits checkpoint approval.

Contracts generated 2026-10-07: `contracts/openapi.yaml`. Frontend delivered as `VesselRegister.jsx`, `MySailings.jsx`, `MyHistory.jsx` (status badges are rendered through `StatusBadge` in `ui.jsx`). T463: `docs/disclosures.md` not changed because no new dependency or AI tool was added.
