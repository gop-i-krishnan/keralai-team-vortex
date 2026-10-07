# Implementation Plan: Feature 006 — Cargo Hazard Rules and Warehouse Staging

**Feature ID:** 006
**Phase:** Plan
**Date:** 2026-10-07
**Status:** Final

---

## 1. Technical Context

### 1.1 Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend runtime | Python 3.11+, FastAPI, Pydantic v2 | Existing; no new dependencies |
| Data | `data/config.yaml` (YAML), `data/seed.json` (JSON) | In-memory only (P10) |
| Engine | Pure Python modules in `backend/engine/` | No I/O, no LLM calls (P2) |
| Tests | pytest, no mocking required | Pure functions (P5) |
| Frontend | React + Vite (existing) | New components for hazard badge, compliance banner, warehouse UI |

### 1.2 New Files

| File | Purpose |
|---|---|
| `backend/engine/geo.py` | Extracted `haversine_km()` — shared by options and warehouse |
| `backend/engine/hazards.py` | Pure `apply_hazard_filters()` |
| `backend/engine/warehouse.py` | Pure `compute_staging_plan()`, `find_eligible_warehouses()` |
| `backend/engine/tests/test_hazards.py` | SC-1, SC-5, SC-7 scenarios |
| `backend/engine/tests/test_warehouse.py` | SC-3, SC-4, FR-6, FR-7, FR-8 scenarios |
| `backend/api/routers/compliance.py` | `POST /api/compliance/review/{id}/approve` |
| `backend/api/routers/warehouse_router.py` | Warehouse CRUD + stage endpoints |

### 1.3 Modified Files

| File | Change |
|---|---|
| `data/config.yaml` | Add `hazard_rules`, `perishable`, `warehouse` sections |
| `data/seed.json` | Add `warehouses`, new cargo records, vessel `hazard_certs` |
| `backend/engine/options.py` | Extract `_haversine_km` → `geo.py`; add `cargo_class` param + perishable overrides |
| `backend/engine/matching.py` | Call `apply_hazard_filters()` before `rank_sailings()` |
| `backend/data_store.py` | Add `warehouses`, `compliance_reviews`, `staging_proposals` collections |
| `backend/api/models.py` | New Pydantic models: Warehouse, StagingPlan, ComplianceReview, etc. |
| `backend/api/main.py` | Include new routers |
| `backend/api/routers/match.py` | Pass `cargo_class` through to hazard filter |
| `backend/api/routers/booking.py` | Handle `pending_review` state; guard confirm against it |
| `backend/api/routers/demo.py` | Extended reset: warehouses, compliance_reviews, proposals |
| `frontend/src/components/` | HazardBadge, ComplianceBanner, WarehouseForm, StagingPlanCard, WarehouseUtilisation |

---

## 2. Constitution Check

| Principle | Status | Notes |
|---|---|---|
| P1 — Shipment First | ✅ | Staging plan is an additional option; road is still always computed |
| P2 — Deterministic Logic | ✅ | All engine functions pure; no LLM in engine; `compute_staging_plan()` is pure |
| P3 — Honest Data | ✅ | All constants in `data/config.yaml` with `source_status: assumed`; no hardcoded values |
| P4 — Subsidy as What-If | ✅ | No change; subsidy defaults remain off |
| P5 — Test-First | ✅ | Tests written before implementation in tasks.md ordering |
| P6 — Layer, not Replace | ✅ | No claims about IWAI/PESO systems; FR-5 explicitly bans regulatory text |
| P7 — Human in the Loop | ✅ | Compliance review + P7 confirm = two separate gates for hazmat |
| P8 — Offline / Graceful Degradation | ✅ | No external calls; demo reset clears warehouses + reviews in < 1s |
| P9 — Privacy and Disclosure | ✅ | All seed data simulated; `reviewer_note` never sent to LLM |
| P10 — Simplicity | ✅ | In-memory only; no new external dependencies; no auth |
| P11 — Safety Before Convenience | ✅ | Hard filter mandatory; excluded list with named reasons; no regulatory text |
| P12 — Re-plan, Never Auto-Switch | ✅ | Two-step staging proposal → confirm; no auto-capacity change |
| P13 — Simulated Is Labelled | ✅ | All warehouse records `source_status: simulated`; compliance review same |
| P14 — Reputation Evidence-Based | ✅ | No change to reliability scoring |
| P15 — Privacy by Minimisation | ✅ | `reviewer_note` not sent to LLM; no new PII fields |

---

## 3. Architecture

### 3.1 Request Flow — Match with Hazard Filter

```
POST /api/match
  │
  ├─ Resolve cargo from data_store (get cargo_class, default "general")
  ├─ Load hazard_rules from config
  ├─ apply_hazard_filters(cargo_class, sailings, vessels, hazard_rules)
  │     returns (eligible_sailings, excluded_list)
  ├─ rank_sailings(cargo, eligible_sailings)   [existing, unchanged]
  └─ return {ranked: [...], excluded: [...]}
```

### 3.2 Request Flow — Hazmat Booking

```
POST /api/book
  │
  ├─ Resolve cargo_class from cargo record
  ├─ Look up hazard_rule for cargo_class
  ├─ if human_review_required → create booking in state "pending_review"
  │   else → create booking in state "pending" [existing flow]
  └─ return {booking_id, status, compliance_review_required}

POST /api/compliance/review/{id}/approve
  ├─ Check booking exists
  ├─ Check booking.status == "pending_review" (else error: compliance_already_reviewed)
  ├─ Check cargo_class.human_review_required (else error: review_not_required_for_class)
  ├─ Create ComplianceReview record
  ├─ Transition booking.status → "pending"
  └─ return ComplianceReview

POST /api/book/{id}/confirm
  ├─ Guard: if status == "pending_review" → return {error: "compliance_review_required"}
  └─ Existing P7 confirm logic [unchanged]
```

### 3.3 Request Flow — Staging

```
POST /api/warehouse/stage
  │
  ├─ Resolve cargo (class, weight, origin_node)
  ├─ find_eligible_warehouses(cargo, origin_node, warehouses, nodes, config)
  │     → (eligible_wh_list, ineligible_list_with_reasons)
  ├─ For each eligible warehouse:
  │     compute_staging_plan(cargo, wh, next_sailing_wait_h, destination_node, config)
  │     → StagingPlan dict with proposal_id (UUID)
  ├─ Store proposals in data_store.staging_proposals[proposal_id]
  └─ return {proposals, ineligible_warehouses, staging_threshold_h}

POST /api/warehouse/stage/confirm
  ├─ Look up proposal_id in staging_proposals
  ├─ Re-check capacity: capacity_used_t + weight_t <= total_capacity_t
  ├─ If capacity exceeded → return {error: "warehouse_at_capacity"}
  ├─ Update warehouse.capacity_used_t += weight_t
  └─ return {warehouse_id, capacity_used_t, available_capacity_t}
```

---

## 4. Data Constants (to be added to `data/config.yaml`)

All entries have `source_status: assumed` and include note "verify with IWAI / PESO / state authority before production use."

```yaml
hazard_rules:
  - class_id: general
    allowed_modes: ["road", "water"]
    certification_required: false
    human_review_required: false
  - class_id: perishable
    allowed_modes: ["road", "water"]
    certification_required: false
    human_review_required: false
  - class_id: liquid_bulk
    allowed_modes: ["road", "water"]
    certification_required: true
    human_review_required: false
  - class_id: flammable
    allowed_modes: ["road", "water"]
    certification_required: true
    human_review_required: true
  - class_id: explosive
    allowed_modes: []
    certification_required: true
    human_review_required: true
  - class_id: toxic_corrosive
    allowed_modes: []
    certification_required: true
    human_review_required: true
  - class_id: oversized
    allowed_modes: ["road", "water"]
    certification_required: false
    human_review_required: false

perishable:
  schedule_buffer_h:
    value: 1.0
    source_status: assumed
  reliability_weight_override:
    value: 0.25
    source_status: assumed

warehouse:
  proximity_radius_km:
    value: 10.0
    source_status: assumed
  staging_wait_threshold_h:
    value: 4.0
    source_status: assumed
```

---

## 5. Phase Breakdown

### Phase 1 — Data layer (config + seed)
Extend `data/config.yaml` and `data/seed.json`. No code changes.
**Gate:** `pytest backend/ -q` still passes all 54 existing tests.

### Phase 2 — Engine modules (tests first)
Write `test_hazards.py` and `test_warehouse.py` (all failing). Then implement
`geo.py`, `hazards.py`, `warehouse.py`. All tests pass.

### Phase 3 — Engine integration
Modify `options.py` (extract haversine, add `cargo_class` + perishable overrides),
modify `matching.py` (call hazard filter). Write/update tests. Full suite passes.

### Phase 4 — Data store extensions
Extend `data_store.py` with new collections, extend demo reset.

### Phase 5 — API layer
Add models, routers, wire into `main.py`. API checkpoint: curl every endpoint.

### Phase 6 — Frontend
HazardBadge, ComplianceBanner, WarehouseForm, StagingPlanCard, WarehouseUtilisation.

### Phase 7 — Final validation
Grep for hardcoded constants; grep for LLM calls in `engine/`; full test suite.

---

## 6. Cut List (out of scope)

- Actual regulatory compliance validation
- UN hazard number lookups or MSDS sheets
- Temperature-controlled storage tracking
- Authentication for the compliance reviewer
- Automatic compliance approval
- Multi-class cargo segregation rules
