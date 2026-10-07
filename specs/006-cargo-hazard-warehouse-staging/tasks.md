# Tasks: Feature 006 — Cargo Hazard Rules and Warehouse Staging

**Feature ID:** 006
**Generated:** 2026-10-07
**Design artifacts:** spec.md, plan.md, data-model.md, contracts/openapi.yaml, research.md, quickstart.md
**Constitution version:** 1.1.0

---

## Implementation Strategy

MVP scope: Phase 1–4 (data layer + engine + hazard filter + matching integration).
A passing `pytest backend/ -q` after each phase is the gate to proceed.

---

## Phase 1 — Setup: Data Layer

**Goal:** Extend config and seed. No code changes. All 54 existing tests still pass.

- [x] T001 Add `hazard_rules` section to `data/config.yaml`: 7 entries (`general`, `perishable`, `liquid_bulk`, `flammable`, `explosive`, `toxic_corrosive`, `oversized`), each with `class_id`, `allowed_modes`, `certification_required`, `human_review_required`, `notes` (must contain "verify with IWAI / PESO / state authority before production use"), `source_status: assumed`. `explosive` and `toxic_corrosive` have `allowed_modes: []`. `flammable` has `allowed_modes: ["road","water"]`, `certification_required: true`, `human_review_required: true`. (FR-1, P3, P11)

- [x] T002 Add `perishable` section to `data/config.yaml`: `schedule_buffer_h` (value: 1.0, source_status: assumed, note), `reliability_weight_override` (value: 0.25, source_status: assumed, note). Validate invariant: `reliability_weight_override` (0.25) > `scoring.weights.reliability` (0.10). (FR-9, P3)

- [x] T003 Add `warehouse` section to `data/config.yaml`: `proximity_radius_km` (value: 10.0, source_status: assumed, note), `staging_wait_threshold_h` (value: 4.0, source_status: assumed, note). (FR-8, P3)

- [x] T004 Add `warehouses` top-level key to `data/seed.json` with two warehouse records: `wh-001` near node-001 (50 t, general + liquid_bulk), `wh-002` near node-002 (30 t, general + perishable + flammable), both with non-zero costs and `source_status: "simulated"`. Set `capacity_used_t: 0` on both. (FR-4, FR-10, P13)

- [x] T005 Add `hazard_certs` field to both seed vessels in `data/seed.json`: `vessel-001` gets `hazard_certs: ["liquid_bulk"]`, `vessel-002` gets `hazard_certs: []`. Add a third vessel `vessel-003` with `hazard_certs: ["flammable","liquid_bulk"]` for positive hazmat-match tests. (FR-10, data-model.md §1.6)

- [x] T006 Add `cargo_class` field to all existing seed cargo records in `data/seed.json` (default `"general"` for backward compat), plus three new cargo records: `cargo-003` (`flammable`, 10 t, node-001→node-002), `cargo-004` (`explosive`, 5 t, node-001→node-002), `cargo-005` (`perishable`, 8 t, node-001→node-002). (FR-10, data-model.md §1.5)

- [x] T007 [P] Verify all 54 existing tests still pass after data-layer changes: `pytest backend/ -q` must exit 0. (P5)

---

## Phase 1b — Foundational: Config Accessor for Hazard Rules

**Goal:** Extend `backend/engine/config.py` with a typed accessor for the `hazard_rules` list. The existing `val(section, key)` only handles `{section: {key: {value: ...}}}` shape; the hazard rules are a list of dicts and need a dedicated function.

- [x] T001b [P] Add two functions to `backend/engine/config.py`:
  - `get_hazard_rules() -> list[dict]`: returns `CFG.get("hazard_rules", [])` as a plain list.
  - `get_hazard_rule(class_id: str) -> dict`: finds the rule whose `class_id` matches the argument; raises `ConfigError` (a `ValueError` subclass defined in this module) if not found. This is the authoritative `ConfigError` class — import it in `hazards.py` rather than redefining it. (C3, I2, FR-1, P3)

---

## Phase 2 — Foundational: Shared Geo Helper

**Goal:** Extract `haversine_km()` to a shared module so both `options.py` and `warehouse.py` can import it without code duplication.

- [x] T008 Create `backend/engine/geo.py` with a single public function `haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float`. Body is an exact copy of `_haversine_km()` currently in `backend/engine/options.py`. Module docstring: "Pure geographic helper. Constitution P2: no I/O." (research.md §7)

- [x] T009 Update `backend/engine/options.py`: import `haversine_km` from `backend.engine.geo` and replace the 2 calls to `_haversine_km(...)` (one in `_build_road_plan`, one in `_build_water_plan`) with `haversine_km(...)`. Remove the now-duplicate private function definition. No behaviour change. (plan.md §1.3, analysis I5)

- [x] T010 [P] Run `pytest backend/ -q` — must still pass all 54 tests with no failures after the refactor. (P5)

---

## Phase 3 — User Story P1: Hazard Hard Filter (SC-1, SC-5, SC-7)

**Story goal:** `apply_hazard_filters()` returns `(eligible_sailings, excluded_list)` with named reasons. A flammable request with no certified vessel returns an empty eligible list and a non-empty excluded list.

### Tests first (P5)

- [x] T011 Create `backend/engine/tests/test_hazards.py`. Write these failing tests before any implementation:
  - `test_general_cargo_passes_all_sailings` — `cargo_class="general"` with no `certification_required` rule; all sailings in eligible list; excluded list empty.
  - `test_mode_not_permitted_excludes_sailing` — `cargo_class="explosive"` with `allowed_modes: []`; every sailing excluded with reason `mode_not_permitted_for_class`.
  - `test_missing_hazmat_cert_excludes_sailing` — `cargo_class="flammable"`, `certification_required: true`; vessel without `flammable` in `hazard_certs` excluded with `missing_hazmat_cert`.
  - `test_certified_vessel_remains_eligible` — `cargo_class="flammable"`, vessel has `flammable` in `hazard_certs`; sailing remains in eligible list.
  - `test_unknown_cargo_class_raises_config_error` — `cargo_class="unknown"` not in hazard_rules; function raises `ConfigError` (SC-5).
  Note: tie-breaking belongs in `test_matching.py` (analysis C2 — `apply_hazard_filters()` does not rank; do not add a tie-break test here).
  (FR-2, P11, SC-1, SC-5)

### Implementation

- [x] T012 Create `backend/engine/hazards.py`. Implement `apply_hazard_filters(cargo_class: str, sailings: list[dict], vessels: list[dict], hazard_rules: list[dict]) -> tuple[list[dict], list[dict]]`. Logic: (1) look up rule for `cargo_class` by calling `get_hazard_rule(cargo_class)` from `backend.engine.config` — this raises `ConfigError` if not found; (2) for each sailing, resolve vessel by `vessel_id`; (3) if `water` not in rule's `allowed_modes`, add to excluded with reason `mode_not_permitted_for_class`; (4) if rule's `certification_required` is true and vessel's `hazard_certs` does not contain `cargo_class`, add to excluded with reason `missing_hazmat_cert`; (5) otherwise add to eligible. Import `ConfigError` from `backend.engine.config` (do NOT redefine it). No I/O, no LLM calls. (FR-2, P2, P11, analysis C3)

- [x] T013 [P] Run `pytest backend/engine/tests/test_hazards.py -q` — all 6 tests must pass.

---

## Phase 4 — User Story P1: Matching Integration

**Story goal:** `POST /api/match` gains `cargo_class` parameter, calls the hazard filter before `rank_sailings()`, and returns `{"ranked": [...], "excluded": [...]}`.

### Tests first (P5)

- [x] T014 Add to `backend/engine/tests/test_matching.py`:
  - `test_match_flammable_no_certs_returns_empty_ranked` — using seed vessels (vessel-001 has no flammable cert), ranked list is empty, excluded list non-empty with `missing_hazmat_cert`.
  - `test_match_liquid_bulk_with_cert_returns_ranked` — vessel-001 has `liquid_bulk` cert; cargo class `liquid_bulk`; ranked list non-empty.
  - `test_match_general_backward_compat` — no `cargo_class` param; defaults to `general`; ranked list unchanged from existing behaviour.
  - `test_tie_broken_by_lower_score_then_cost` — When two eligible sailings have the same score, the one with lower cost ranks first (spec clarification §session-2; analysis C2).
  (FR-2, P3, spec §session-2 backward compat)

### Implementation

- [x] T015 Update `backend/engine/matching.py`: add `cargo_class: str = "general"`, `vessels: list[dict] = None`, and `hazard_rules: list[dict] = None` parameters to `rank_sailings()`. If `hazard_rules` is provided and non-empty, call `apply_hazard_filters()` first to split sailings into `eligible` and `excluded_list`; then rank only `eligible` sailings. Tie-breaking: when two ranked entries have equal score, sort by ascending cost. Return `{"ranked": [...], "excluded": [...]}` instead of plain list. Maintain backward compat: if no hazard_rules passed, `excluded` is `[]`. (FR-2, plan.md §3.1, analysis C2)

- [x] T016 Update `backend/api/routers/match.py`: read `cargo_class` from request body (default `"general"`); call `get_hazard_rules()` from `backend.engine.config` (not raw `CFG["hazard_rules"]`) to load validated rules; load `vessels` from `data_store.vessels`; use `cargo.get("cargo_class","general")` when reading cargo from data_store to enforce the default (analysis I3); pass all to `rank_sailings()`. Return `{"ranked": result["ranked"], "excluded": result["excluded"]}`. (FR-2, openapi.yaml §/api/match, analysis I3)

- [x] T017 [P] Run `pytest backend/ -q` — all tests (54 + new) must pass.

---

## Phase 5 — User Story P1: Warehouse Engine (SC-3, SC-4, FR-6, FR-7)

**Story goal:** `compute_staging_plan()` returns a fully itemised StagingPlan dict. `find_eligible_warehouses()` returns eligible and ineligible lists with named reasons.

### Tests first (P5)

- [x] T018 Create `backend/engine/tests/test_warehouse.py`. Write these failing tests:
  - `test_compute_staging_plan_cost_components` — hand-calculated total: `truck_to_cost + handling_in + storage + handling_out + truck_from` = expected sum; assert `total_cost_inr == sum_of_five` (SC-3).
  - `test_staging_plan_storage_days_ceil` — wait 25 h → storage_days = 2 (ceil(25/24)); wait 24 h → storage_days = 1.
  - `test_staging_plan_deadline_met_true` — total_time_h < deadline_h → `deadline_met: True`.
  - `test_staging_plan_deadline_met_false` — total_time_h > deadline_h → `deadline_met: False`.
  - `test_staging_plan_co2_scope` — `co2_scope` equals `"truck legs only; storage CO₂ not modelled"`.
  - `test_staging_plan_source_status_assumed` — `source_status == "assumed"`.
  - `test_find_eligible_excludes_class_mismatch` — warehouse's `allowed_cargo_classes` doesn't include cargo class → ineligible with `warehouse_class_mismatch` (FR-6).
  - `test_find_eligible_excludes_at_capacity` — `capacity_used_t == total_capacity_t` → ineligible with `warehouse_at_capacity` (FR-6, SC-4).
  - `test_find_eligible_no_warehouse_in_range` — all warehouses beyond `proximity_radius_km` → ineligible list contains `no_warehouse_in_range` entry (FR-6).
  - `test_perishable_adjustments_applied_flag` — `cargo_class="perishable"` → `perishable_adjustments_applied: True` in result (FR-9).
  (FR-6, FR-7, SC-3, SC-4)

### Implementation

- [x] T019 Create `backend/engine/warehouse.py`. Implement two public functions (no `config: dict` parameter — use `val()` and `get_hazard_rule()` from `backend.engine.config` directly per P3/P2 pattern; analysis C1, I4):
  1. `find_eligible_warehouses(cargo: dict, origin_node: dict, warehouses: list[dict], nodes: list[dict]) -> tuple[list[dict], list[dict]]` — uses `val("warehouse","proximity_radius_km")` for radius; imports `haversine_km` from `backend.engine.geo`; filters by proximity, cargo class membership, and available capacity; returns `(eligible, ineligible_with_reasons)`. Add warehouse `_is_seed` flag check: flag is set at data_store load time (analysis G2).
  2. `compute_staging_plan(cargo: dict, warehouse: dict, next_sailing_wait_h: float, destination_node: dict, origin_node: dict, deadline_h: float) -> dict` — reads road constants via `val("road",...)` directly; computes truck legs using `haversine_km` × `val("road","road_factor")` × `val("road","rate_per_t_km")`; sets `storage_days = max(1, ceil(wait_h / 24))`; generates `proposal_id = str(uuid.uuid4())`; returns all 5 cost components plus totals, `co2_scope`, `source_status: "assumed"`, `note` including "storage CO₂ not modelled in this prototype [assumed]", `perishable_adjustments_applied` flag. Import `ConfigError` from `backend.engine.config`. No I/O, no LLM calls. (FR-6, P2, P3, analysis C1, I4)

- [x] T020 [P] Run `pytest backend/engine/tests/test_warehouse.py -q` — all 10 tests must pass.

---

## Phase 6 — User Story P1: Booking State Machine Extension (SC-2)

**Story goal:** Hazmat booking is created in `pending_review` state. Confirm endpoint rejects `compliance_review_required`. Approve endpoint transitions to `pending`. Idempotency guards work.

### Tests first (P5)

- [x] T021 Add to `backend/api/tests/test_api.py` (or new file `test_compliance_api.py`):
  - `test_explosive_booking_created_pending_review` — POST /api/book with cargo-004 (explosive) → status `pending_review`, `compliance_review_required: true`.
  - `test_confirm_rejected_while_pending_review` — POST /api/book/{id}/confirm on a `pending_review` booking → error `compliance_review_required`.
  - `test_approve_compliance_transitions_to_pending` — POST /api/compliance/review/{id}/approve → status 200, booking status becomes `pending`.
  - `test_compliance_already_reviewed_error` — Approve same booking twice → error `compliance_already_reviewed`, no duplicate record.
  - `test_review_not_required_for_general` — POST /api/compliance/review/{id}/approve on a `general` cargo booking → error `review_not_required_for_class` (SC-7).
  - `test_full_hazmat_flow_sc2` — 3-step sequence: book → approve → confirm → status `confirmed` (SC-2).
  (FR-3, SC-2, SC-7, P7, P11)

### Implementation

- [x] T022 Extend `backend/data_store.py`:
  - Add `compliance_reviews: dict[str, dict]` keyed by `booking_id` (initially `{}`).
  - Add `staging_proposals: dict[str, dict]` keyed by `proposal_id` (initially `{}`).
  - Add `warehouses: list[dict]` seeded from `seed.json["warehouses"]`; when loading seed warehouses set `_is_seed: True` on each dict so `reset()` can distinguish them from runtime-registered ones.
  - Extend `reset()` to: remove all warehouses where `_is_seed` is False; reset `capacity_used_t = 0` on remaining seed warehouses; clear `compliance_reviews`; clear `staging_proposals`. (FR-11, P8, P10, analysis G2)

- [x] T023 Update `backend/api/routers/booking.py`:
  - In `POST /api/book`: after creating booking record, look up `hazard_rules` from CFG; if the cargo's class has `human_review_required: true`, set `booking.status = "pending_review"`; include `compliance_review_required: True` in response.
  - In `POST /api/book/{id}/confirm`: add guard — if `booking.status == "pending_review"`, return HTTP 400 `{"error": "compliance_review_required"}`. (FR-3, P7, P11)

- [x] T024 Create `backend/api/routers/compliance.py` with endpoint `POST /api/compliance/review/{booking_id}/approve`. Logic: (1) fetch booking — 404 if not found; (2) if booking.status != "pending_review" → return `{"error": "compliance_already_reviewed"}`; (3) look up hazard rule — if `human_review_required: false` → return `{"error": "review_not_required_for_class"}`; (4) create ComplianceReview record in `data_store.compliance_reviews[booking_id]`; (5) transition `booking.status = "pending"`; (6) return ComplianceReview dict with `source_status: "simulated"`. (FR-3, P11, P13)

- [x] T025 [P] Run `pytest backend/ -q` — all tests must pass.

---

## Phase 7 — User Story P1: Warehouse API (FR-4, FR-7, FR-8, FR-11)

**Story goal:** Warehouse CRUD endpoints and staging proposal/confirm flow. Demo reset extended.

### Tests first (P5)

- [x] T026 Add API tests for warehouse endpoints:
  - `test_warehouse_list_returns_seed_warehouses` — GET /api/warehouse/list → 2 seed warehouses, all `source_status: "simulated"`.
  - `test_warehouse_register_valid` — POST /api/warehouse/register with valid payload → 201, warehouse in list.
  - `test_warehouse_register_empty_classes_fails` — POST /api/warehouse/register with `allowed_cargo_classes: []` → 422 with `{field:"allowed_cargo_classes", code:"required"}`.
  - `test_warehouse_register_invalid_class_fails` — POST /api/warehouse/register with `allowed_cargo_classes: ["radioactive"]` → 422 with `{code:"invalid_class"}`.
  - `test_warehouse_register_unknown_node_fails` — `location_node_id: "node-999"` → 422 with `{field:"location_node_id", code:"not_found"}`.
  - `test_staging_proposal_sc3` — cargo-001 (10 t), wait 8 h (> threshold 4 h) → proposals non-empty; total_cost_inr == sum of five components (SC-3).
  - `test_staging_below_threshold_returns_empty` — wait 2 h (< 4 h threshold) → proposals empty.
  - `test_staging_confirm_updates_capacity` — propose + confirm → `capacity_used_t` increases by weight.
  - `test_staging_confirm_capacity_guard_sc4` — fill warehouse to capacity, then confirm another proposal → 409 `warehouse_at_capacity` (SC-4).
  - `test_warehouse_utilisation_source_status` — GET /api/warehouse/utilisation → top-level `source_status: "simulated"` and each row has `source_status: "simulated"`.
  - `test_demo_reset_clears_capacity` — stage → confirm → reset → utilisation shows 0 capacity used (SC-8).
  (FR-4, FR-7, FR-8, FR-11, SC-3, SC-4, SC-8, P8, P12, P13)

### Implementation

- [x] T027 Add Pydantic v2 models to `backend/api/models.py`: `WarehouseIn`, `WarehouseOut`, `StagingProposalRequest`, `StagingConfirmRequest`, `StagingPlanOut`, `IneligibleWarehouse`, `WarehouseUtilisationRow`, `WarehouseUtilisationResponse`. (data-model.md §1.2–1.3, openapi.yaml)

- [x] T028 Create `backend/api/routers/warehouse_router.py` with 5 endpoints:
  - `GET /api/warehouse/list`: return all `data_store.warehouses` with computed `available_capacity_t` and `utilisation_pct`.
  - `POST /api/warehouse/register`: validate all fields (see data-model.md §1.2 validation errors), generate uuid id, append to `data_store.warehouses`, return 201. Return 422 with `{"errors": [...]}` on validation failure.
  - `POST /api/warehouse/stage`: resolve cargo; if `next_sailing_wait_h < staging_wait_threshold_h` from config → return empty proposals; otherwise call `find_eligible_warehouses()` + `compute_staging_plan()` for each; store proposals in `data_store.staging_proposals`; return proposals + ineligible list + threshold value.
  - `POST /api/warehouse/stage/confirm`: look up proposal; re-check capacity; update `capacity_used_t`; remove proposal from store; return updated warehouse capacity fields. Return 404 on unknown proposal_id. Return 409 on capacity conflict.
  - `GET /api/warehouse/utilisation`: return all warehouses with utilisation metrics and top-level `source_status: "simulated"`.
  (FR-4, FR-7, FR-8, P12, P13, openapi.yaml)

- [x] T029 [P] Register `warehouse_router` and `compliance_router` in `backend/api/main.py`. (plan.md §1.3)

- [x] T030 [P] Run `pytest backend/ -q` — all tests must pass.

---

## Phase 8 — User Story P2: Perishable Scoring Adjustments (SC-6, FR-9)

**Story goal:** When `cargo_class == "perishable"`, `build_plans()` uses tighter buffer and elevated reliability weight. Response includes `perishable_adjustments_applied: true`.

### Tests first (P5)

- [x] T031 Add to `backend/engine/tests/test_options.py`:
  - `test_perishable_adjustments_applied_flag` — call `build_plans()` with `cargo_class="perishable"`; response includes `perishable_adjustments_applied: True` (SC-6).
  - `test_perishable_reliability_weight_override` — in the scores metadata, reliability component reflects `reliability_weight_override: 0.25` not the standard `0.10` (SC-6).
  - `test_non_perishable_no_adjustment_flag` — `cargo_class="general"`; `perishable_adjustments_applied: False` (or absent).
  - `test_config_error_if_override_lt_standard` — if config has `reliability_weight_override <= scoring.weights.reliability`, `val()` call raises `ConfigError` at startup. (FR-9)

### Implementation

- [x] T032 Update `backend/engine/options.py`:
  - Add `cargo_class: str = "general"` parameter to `build_plans()`.
  - If `cargo_class == "perishable"`: load `perishable.schedule_buffer_h` from config (replace `buffer_h`); load `perishable.reliability_weight_override` from config; scale remaining weights (cost, time, co2) proportionally so all 4 weights sum to 1.0; pass adjusted weights to `_score_plans()`.
  - At startup (module load), assert `val("perishable","reliability_weight_override") > val("scoring","weights",...)`; raise `ConfigError` on violation.
  - Add `perishable_adjustments_applied: bool` to the returned dict.
  (FR-9, P3)

- [x] T033 [P] Run `pytest backend/ -q` — all tests must pass.

---

## Phase 9 — Checkpoint: API smoke test

**Goal:** Every Feature 006 endpoint responds correctly from a running server. Reference the `quickstart.md` scenarios B.1–B.7.

- [ ] T034 [P] Start the API server and run curl/Invoke-RestMethod for all 7 quickstart scenarios from `quickstart.md` (B.1 through B.7). Document each result inline. All must match expected responses. This is a manual checkpoint; it does not replace automated tests. (quickstart.md)

---

## Phase 10 — Regression Gate

**Goal:** Confirm that Feature 006 implementation has not broken any of the 54 pre-existing tests.

- [x] T035 Run `pytest backend/ -q --tb=short`. Must show: 0 failures, 0 errors, 0 unexpected skips. The total test count must equal 54 + (all new Feature 006 tests). Record the count. (P5, constitution §Quality Gates)

---

## Phase 11 — User Story P2: Frontend Components

**Story goal:** Hazard badge, compliance banner, warehouse form, staging plan card, and utilisation table are visible in the UI with correct text labels and `[simulated]` tags.

- [ ] T036 [P] Create `frontend/src/components/HazardBadge.jsx`: displays cargo class name as text (e.g. "Flammable") with a visible colour-coded badge. Colour alone MUST NOT be the only indicator — text label is mandatory (P11). Carries `[assumed]` badge for source_status. (P3, P11, FR-2)

- [ ] T037 [P] Create `frontend/src/components/ComplianceBanner.jsx`: shown when booking status is `pending_review`. Text: "Compliance review required — hazardous cargo [simulated]". Includes a "Mark review approved" button labelled "Compliance review — simulated; production requires a qualified person". Confirm booking button is disabled until `compliance_review_required` is false. (FR-3, P7, P11, P13)

- [ ] T038 [P] Create `frontend/src/components/WarehouseForm.jsx`: registration form with all fields from FR-4. Multi-select for `allowed_cargo_classes` using fixed enum list. Validates required fields client-side; displays server-side `{field, code, message}` errors inline per field. (FR-4, spec §P1 Warehouse registration)

- [x] T039 [P] Create `frontend/src/components/StagingPlanCard.jsx`: displays itemised staging plan with all 5 cost components, ETA, CO₂ (with `co2_scope` text), deadline met/not met, `perishable_adjustments_applied` note, and `[assumed]` badge. Includes "Confirm staging" button that calls `POST /api/warehouse/stage/confirm`. (FR-6, FR-8, P2, P3, P12, P13)

- [ ] T040 [P] Create `frontend/src/components/WarehouseUtilisation.jsx`: table showing all warehouses with capacity, used, available, utilisation%. Every row and the table header carry `[simulated]` text label. (FR-11, spec §P2 Utilisation, P3, P13)

- [x] T041 Wire new components into existing routing/pages in `frontend/src/` (booking detail page gets ComplianceBanner; options results page gets StagingPlanCard; analytics panel gets WarehouseUtilisation; a new "Warehouses" tab or section gets WarehouseForm + list). Exact file: `frontend/src/App.jsx` or equivalent top-level router. (plan.md §1.3)

---

## Phase 12 — Final Validation

- [x] T042 Run `pytest backend/ -q` — must exit 0 with 0 failures. Record total test count. (constitution §Quality Gates)

- [x] T043 Grep for hardcoded numeric constants in engine/ and routers/: `grep -rn "[0-9]\+\.[0-9]\+" backend/engine/ backend/api/routers/ --include="*.py"`. Review each match — any rate, threshold, radius, or weight not delegated to `val()` or `CFG` is a P3 violation; fix before marking complete. (P3, constitution §Quality Gates)

- [x] T044 Grep for LLM calls inside `backend/engine/`: `grep -rn "llm\|adapter\|watsonx\|granite\|LLM" backend/engine/ --include="*.py"`. Expected: 0 matches. Any match is a P2 violation; fix before marking complete. (P2, constitution §Quality Gates)

- [x] T045 Verify WCAG AA compliance for all new UI components: each HazardBadge, ComplianceBanner, and WarehouseUtilisation row has a text label (not colour alone). Check in browser developer tools or by code review. (P11, spec §Accessibility)

---

## Dependencies

```
T001–T006 (data layer) → T007 (regression check)
T008–T009 (geo helper) → T010 (regression check)
T011 (hazard tests) → T012 (hazards.py) → T013 (tests pass)
T014 (matching tests) → T015–T016 (matching integration) → T017
T018 (warehouse tests) → T019 (warehouse.py) → T020
T021 (compliance tests) → T022–T024 (data_store + routers) → T025
T026 (warehouse API tests) → T027–T029 (models + router + main) → T030
T031 (perishable tests) → T032 (options.py) → T033
T034 (checkpoint) depends on T030 + T033
T035 (regression gate) depends on T034
T036–T041 (frontend) can start after T030 [P]
T042–T045 (final) depend on T041
```

## Parallel Opportunities

- T001, T002, T003, T004, T005, T006 — all data-only changes, no code deps (within Phase 1)
- T008, T011, T014, T018, T021, T026, T031 — test files all independent [P]
- T036, T037, T038, T039, T040 — frontend components all independent [P]
- T042, T043, T044, T045 — independent validation checks [P]

---

## Cut List (explicitly out of scope)

- Actual regulatory compliance validation or legal advice
- UN hazard number lookups or MSDS/SDS sheets
- Temperature-controlled storage or cold-chain tracking
- Authentication or role-based access for the compliance reviewer
- Automatic compliance approval based on any rules
- Multi-class cargo segregation rules
- Custom `[P]` dependency graph tooling

## Progress note (2026-10-07)

Backend phases 1-10 verified by the test suite (251 passing overall; the 54 in this document's header is stale, the baseline is now 100 original tests). T034 (curl checkpoint) was covered by the 004/005 live-server runs for shared endpoints but the warehouse quickstart B.1-B.7 was not re-run. Open: T036-T041 and T045 - hazard badge, compliance banner (delivered as `ClassBadge`, `Banner` and the Confirm screen), warehouse form and utilisation (delivered in `WarehousePanels.jsx`); the staging plan card (T039) is NOT built. P2 fix: `proposal_id` is now deterministic (no uuid in `engine/`).

Update: T039 delivered as `frontend/src/components/StagingPanel.jsx` (inside Shipper → Matches): itemised five-part cost, ETA, CO₂ with scope, deadline label, explicit Confirm staging dialog. Confidence threshold set to 0.8 in `data/config.yaml` to match constitution P7.
