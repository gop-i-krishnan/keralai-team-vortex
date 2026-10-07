# Data Model: Feature 006 — Cargo Hazard Rules and Warehouse Staging

**Feature ID:** 006
**Phase:** Plan — Phase 1 Design
**Date:** 2026-10-07
**Status:** Final

---

## 1. Entities

### 1.1 HazardRule (config-only; not stored at runtime)

Lives in `data/config.yaml` under the `hazard_rules` key. Loaded at startup by
`backend/engine/config.py`. Immutable during a session.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `class_id` | string enum | One of 7 canonical ids | Key into all cargo and vessel records |
| `allowed_modes` | list\[string\] | Subset of `["road","water"]`; may be `[]` | `[]` means no mode is offered without a special permit |
| `certification_required` | bool | — | True ⇒ vessel must carry `class_id` in `hazard_certs` |
| `human_review_required` | bool | — | True ⇒ booking starts in `pending_review` state |
| `notes` | string | Must contain "verify with IWAI / PESO / state authority" | P11 compliance |
| `source_status` | string | Must be `"assumed"` | Every row — P3, P11 |

**Canonical class ids:** `general`, `perishable`, `liquid_bulk`, `flammable`, `explosive`,
`toxic_corrosive`, `oversized`

**ConfigError** is raised at startup if any cargo request references an unknown class id.

---

### 1.2 Warehouse

Stored in `data_store.warehouses` (list). Seeded from `data/seed.json["warehouses"]`.
Runtime-registered warehouses are appended and cleared on demo reset.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | string | Unique | Generated (e.g. `wh-001`) |
| `name` | string | Non-empty | Free text |
| `location_node_id` | string | Must exist in node list | Used for proximity calculation |
| `total_capacity_t` | float | > 0 | |
| `capacity_used_t` | float | 0 ≤ used ≤ total | Mutated only on staging confirmation |
| `storage_cost_per_t_per_day` | float | ≥ 0 | INR |
| `handling_in_cost_per_t` | float | ≥ 0 | INR |
| `handling_out_cost_per_t` | float | ≥ 0 | INR |
| `allowed_cargo_classes` | list\[string\] | Non-empty; each element a valid class id | |
| `source_status` | string | `"simulated"` | All warehouses — P13 |

**Validation errors** (returned as `{field, code, message}` list):
- `total_capacity_t ≤ 0` → `{field:"total_capacity_t", code:"invalid_value"}`
- Any cost field `< 0` → `{field:"<field>", code:"invalid_value"}`
- `location_node_id` not in nodes → `{field:"location_node_id", code:"not_found"}`
- `allowed_cargo_classes` empty → `{field:"allowed_cargo_classes", code:"required"}`
- Unknown class in `allowed_cargo_classes` → `{field:"allowed_cargo_classes", code:"invalid_class", message:"Unknown cargo class: <id>"}`

---

### 1.3 StagingPlan

Read-only output of `compute_staging_plan()`. Never stored; returned directly by the
`POST /api/warehouse/stage` endpoint. Stored transiently in a staging proposal store
keyed by a `proposal_id` (UUID) for the confirm step.

| Field | Type | Notes |
|---|---|---|
| `proposal_id` | string | UUID; used to call confirm endpoint |
| `warehouse_id` | string | |
| `cargo_class` | string | |
| `weight_t` | float | |
| `storage_days` | int | `max(1, ceil(wait_h / 24))` |
| `truck_to_warehouse_cost_inr` | float | Road cost origin → warehouse node |
| `handling_in_cost_inr` | float | `weight_t × handling_in_cost_per_t` |
| `storage_cost_inr` | float | `weight_t × storage_days × storage_cost_per_t_per_day` |
| `handling_out_cost_inr` | float | `weight_t × handling_out_cost_per_t` |
| `truck_from_warehouse_cost_inr` | float | Road cost warehouse node → destination |
| `total_cost_inr` | float | Sum of all five above |
| `total_time_h` | float | Truck to warehouse + wait + truck from warehouse |
| `co2_kg` | float | Road CO₂ for both truck legs only |
| `co2_scope` | string | `"truck legs only; storage CO₂ not modelled"` |
| `deadline_met` | bool | |
| `perishable_adjustments_applied` | bool | |
| `source_status` | string | `"assumed"` |
| `note` | string | Includes "storage CO₂ not modelled in this prototype [assumed]" |

**Ineligibility reasons** (returned in `ineligible_warehouses` list, not silently dropped):
- `warehouse_class_mismatch` — cargo class not in warehouse's `allowed_cargo_classes`
- `warehouse_at_capacity` — `capacity_used_t + weight_t > total_capacity_t`
- `no_warehouse_in_range` — no warehouse within `warehouse_proximity_radius_km`

---

### 1.4 ComplianceReview

Stored in `data_store.compliance_reviews` (dict keyed by `booking_id`). Cleared on
demo reset.

| Field | Type | Notes |
|---|---|---|
| `id` | string | UUID |
| `booking_id` | string | FK to booking |
| `cargo_class` | string | Inherited from booking |
| `reviewer_note` | string | Free text; not sent to any LLM (P15) |
| `approved_at` | string | ISO 8601 timestamp (IST) |
| `source_status` | string | `"simulated"` |

**Errors:**
- Review already recorded for this booking → `compliance_already_reviewed`
- Booking's cargo class does not require review → `review_not_required_for_class`

---

### 1.5 CargoRecord (extended)

Adds one field to the existing cargo entity in `data/seed.json` and API requests:

| New Field | Type | Default | Notes |
|---|---|---|---|
| `cargo_class` | string enum | `"general"` | Backward-compatible; existing records without this field default to `general` |

---

### 1.6 VesselRecord (extended)

Adds one field consumed by the hazard filter (already spec'd in Feature 004):

| New Field | Type | Default | Notes |
|---|---|---|---|
| `hazard_certs` | list\[string\] | `[]` | Class ids the vessel is certified to carry |

---

## 2. Booking State Machine (extended)

```
                ┌─────────────────────────────────────┐
                │         POST /api/book               │
                ▼                                       │
   [hazmat class]     [non-hazmat class]                │
        │                    │                          │
        ▼                    ▼                          │
  pending_review          pending                       │
        │                    │                          │
  POST /api/compliance/       │                          │
  review/{id}/approve         │                          │
        │                    │                          │
        ▼                    │                          │
      pending ◄──────────────┘                          │
        │                                               │
  POST /api/book/{id}/confirm                           │
        │                                               │
        ▼                                               │
    confirmed                                           │
        │                                               │
  POST /api/book/{id}/cancel ──────────────────────────►
        │
        ▼
    cancelled
```

**Guard:** `POST /api/book/{id}/confirm` MUST reject with `compliance_review_required`
if booking is still in `pending_review` state.

---

## 3. Staging Proposal State Machine

```
POST /api/warehouse/stage     POST /api/warehouse/stage/confirm
─────────────────────────►   ──────────────────────────────────►
  StagingProposal (read-only)   Capacity updated + booking linked
  stored by proposal_id
```

No capacity change at proposal time (P12 pattern).

---

## 4. New Engine Modules

| Module | Public functions | Pure? |
|---|---|---|
| `backend/engine/geo.py` | `haversine_km(lat1, lon1, lat2, lon2) → float` | ✅ |
| `backend/engine/hazards.py` | `apply_hazard_filters(cargo_class, sailings, vessels, hazard_rules) → (eligible, excluded)` | ✅ |
| `backend/engine/warehouse.py` | `compute_staging_plan(cargo, warehouse, next_sailing_wait_h, destination_node, config) → dict`, `find_eligible_warehouses(cargo, origin_node, warehouses, nodes, config) → (eligible, ineligible)` | ✅ |

---

## 5. Extended `data_store.py` Collections

| Collection | Seed source | Reset behaviour |
|---|---|---|
| `warehouses` | `data/seed.json["warehouses"]` | Seed warehouses reset to 0 capacity_used_t; runtime warehouses cleared |
| `compliance_reviews` | None (empty) | Cleared entirely |

---

## 6. Invariants

1. `capacity_used_t ≤ total_capacity_t` at all times.
2. No booking transitions from `pending_review` → `confirmed` without an intermediate
   `compliance_review_approved` event.
3. `perishable.reliability_weight_override > scoring.weights.reliability` — engine raises
   `ConfigError` at startup if violated.
4. All hazard rules have `source_status: "assumed"` — engine raises `ConfigError` at
   startup for any row where this is not the case.
5. No warehouse is created with an empty `allowed_cargo_classes` list.
