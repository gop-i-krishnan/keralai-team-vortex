# Feature Specification: Cargo Hazard Rules and Warehouse Staging

**Feature ID:** 006
**Short name:** cargo-hazard-warehouse-staging
**Status:** Draft
**Created:** 2026-10-07
**Last updated:** 2026-10-07

---

## Overview

Not all goods can move on all vessels or through all modes. A flammable liquid matched to
an uncertified barge is an unsafe recommendation; an explosive matched to a general-cargo
sailing is a legal problem. Equally, cargo that must wait for the next sailing or survive
a disruption needs somewhere to sit safely — a warehouse that can accept it, at a known
cost, with a new ETA. This feature adds two interlocking capabilities: a hazard-class
hard filter that gates vessel matching on certification and triggers a mandatory human
compliance review for restricted classes, and a warehouse registry that lets cargo owners
and operators stage goods with full cost transparency.

---

## Problem Statement

The existing matching engine has no knowledge of what a vessel is permitted to carry.
Any cargo, including hazardous goods, is currently matched to any vessel with spare
capacity. This creates an unsafe and legally non-compliant prototype. Separately, the
options engine and disruption re-planner (Feature 005) reference a "hold at warehouse"
alternative but there is no warehouse entity in the data model or registry. This feature
closes both gaps, keeping all rules in configuration and all decisions with humans.

---

## Clarifications

### Session 2026-10-07

- Q: What is the canonical source of hazard class rules for Indian inland waterways? →
  A: IWAI Regulations for Carriage of Dangerous Goods on National Waterways and PESO
  (Petroleum and Explosives Safety Organisation) rules. No authoritative published schedule
  was available at spec time; every entry in the hazard rules table is `source_status:
  assumed` with note "verify with IWAI / PESO / state authority before production use."
  The system MUST NOT present any rule as definitive.
- Q: Do road and water modes have different certification requirements? → A: Yes. The
  hazard rules table has a per-class `allowed_modes` list (e.g. `["road", "water"]` or
  `["road"]`). If `water` is not in the list, the vessel matching step is skipped for that
  cargo class and only road plans are offered. If `road` is not in the list, road plans
  are excluded.
- Q: What is the difference between `human_review_required: true` and a standard P7
  booking confirmation? → A: Standard P7 confirmation is always required. `human_review_
  required: true` adds a **separate, prior compliance review step**: a simulated reviewer
  action (`POST /api/compliance/review/{booking_id}/approve`) that MUST be recorded before
  the standard P7 confirm endpoint accepts the request. These are two distinct gates; both
  must be passed for hazardous classes.
- Q: Is the compliance reviewer a real role or a demo action? → A: Demo action only.
  A single endpoint marks the review as approved; no authentication is required. The UI
  labels it "Compliance review — simulated; production requires a qualified person."
- Q: How is warehouse capacity tracked — per booking or running total? → A: Running total
  of `capacity_used_t` across all accepted staging requests for that warehouse in the
  current session. On demo reset it reverts to the seed value (0 for all warehouses).
- Q: Should staging show a CO₂ figure? → A: Yes — the extra truck leg from origin to
  warehouse and from warehouse to destination uses the existing road CO₂ model. Storage
  itself is assigned CO₂ = 0 in this prototype (no refrigeration or fuel modelled).
  Scope caveat carried in the plan note.
- Q: Does the cargo class apply to a cargo record or to a booking request? → A: To the
  cargo record in `data/seed.json` / the registration form. A booking inherits the class
  from the cargo it references.
- Q: How are perishable schedule-buffer and reliability weights configured? → A: Two
  named overrides in `data/config.yaml` under a `perishable` key: `schedule_buffer_h`
  (tighter than the standard buffer) and `reliability_weight_override` (replaces the
  standard reliability weight in the scoring formula). Both `source_status: assumed`.
- Q: Can a warehouse accept all cargo classes or only specific ones? → A: Only the classes
  in its `allowed_cargo_classes` list. A staging request for a class not on the list is
  rejected with reason `warehouse_class_mismatch`.
- Q: What accessibility requirements apply? → A: WCAG AA. Every hazard badge, compliance
  banner, and warehouse status indicator MUST have a text label; colour alone MUST NOT be
  the only indicator (P3, P11, P13).

### Session 2026-10-07 (edge-case clarifications from implementation brief)

- Q: What currency and units apply throughout? → A: INR (₹ in UI, "Rs." in text), tonnes,
  metres, IST. All constants in `data/config.yaml` tagged `assumed`. Simulated data labelled
  `[simulated]` in UI and `source_status: "simulated"` in API.
- Q: How are ties broken in the staging and hazard plan scoring? → A: Ties are broken by
  lower total cost, consistent with the rest of the options engine.
- Q: What fallback applies when the compliance review or staging endpoint cannot reach its
  dependency (e.g. node not found)? → A: Every external call has a documented fallback:
  missing node returns a named 404 error; missing warehouse returns `no_warehouse_in_range`;
  missing hazard rule raises `ConfigError`. No call is allowed to block the critical
  path or swallow errors silently.
- Q: What happens when a compliance review is submitted a second time for the same booking?
  → A: If the booking is already in `pending` or `confirmed` state (review already approved),
  the endpoint returns a structured error `compliance_already_reviewed` and makes no state
  change. It MUST NOT create a duplicate review record.
- Q: What happens when registration is submitted with an empty `allowed_cargo_classes` list?
  → A: Validation fails with error `{field: "allowed_cargo_classes", code: "required",
  message: "At least one cargo class must be selected"}`. No warehouse is created.
- Q: What happens when a staging plan is proposed against a warehouse with
  `capacity_used_t == total_capacity_t` (exactly full)? → A: The plan is not offered;
  the ineligibility reason is `warehouse_at_capacity`. The warehouse appears in the
  ineligibility list, not silently omitted.
- Q: What happens to existing confirmed bookings when a vessel is suspended? → A: Existing
  confirmed bookings are NOT cancelled or modified — they retain their current state. The
  vessel is excluded from all new matching and sailing publication requests. A suspended
  vessel's existing confirmed sailings remain in the schedule but cannot accept new capacity
  allocations. A UI notice states "This vessel is suspended — existing bookings unaffected;
  no new bookings can be made." This behaviour is added to FR-1 (vessel lifecycle) in Spec
  004 and to FR-2 (hazard hard filter) in this spec.
- Q: What happens when `allowed_cargo_classes` contains an invalid class id? → A: Validation
  returns `{field: "allowed_cargo_classes", code: "invalid_class", message: "Unknown cargo
  class: <id>"}` for each invalid entry. No warehouse is created.
- Q: What human confirmation step applies before any staging confirmation state change? →
  A: The same two-step pattern as P7 and P12: `POST /api/warehouse/stage` returns a
  `StagingProposal` (read-only, no capacity change); `POST /api/warehouse/stage/confirm`
  applies the capacity change and updates the booking. Setting any flag in step 1 MUST NOT
  skip step 2.

---

## Actors

| Actor | Role |
|---|---|
| Cargo owner | Specifies cargo class at booking time; receives hazard-gated match results; confirms staging plan |
| Boat operator | Declares certified cargo classes during vessel registration (Feature 004); sees class-filtered match results |
| Simulated compliance reviewer | Approves a compliance review for restricted cargo via a single demo action |
| Warehouse owner / operator with storage | Registers a warehouse node, sets capacity, storage rate, allowed classes |
| Planner | Views warehouse utilisation summary (simulated) |
| System | Applies hard filters, triggers compliance-review gate, computes staging costs |

---

## User Stories

### P1 — Cargo class selection and hazard matching

As a cargo owner, when I submit a shipment I choose a cargo class from a fixed list:
**General, Perishable, Liquid bulk, Flammable, Explosive, Toxic/corrosive, Oversized**.
The matching engine hard-filters sailings so only vessels certified for that class are
ranked. Vessels excluded by the filter appear in a collapsible "Excluded vessels" section
with the reason (e.g. "not certified for: flammable"). If no vessel passes the filter, the
ranked list is empty and I see "No certified vessels available for this cargo class."
All hazard filter reasons carry a text label; no information is conveyed by colour alone.

### P1 — Compliance review gate for restricted classes

As a cargo owner booking explosive, flammable, or toxic/corrosive cargo, I see a
"Compliance review required" banner on the booking detail page immediately after creating
a preview booking. The standard "Confirm booking" button is disabled until a compliance
review is recorded for that booking. In the demo, a presenter clicks "Mark review
approved" (labelled "Compliance review — simulated; production requires a qualified
person") to unblock the confirm button. After approval the booking proceeds through the
normal P7 two-step confirmation. Both the review approval and the booking confirmation
are recorded in the event log.

### P1 — Warehouse registration

As a warehouse owner (or cargo owner with storage), I register a warehouse by providing:
location (select from node list, or "near" a node within a configured radius), total
capacity in tonnes, storage cost per tonne per day (₹/t/day), handling-in cost per tonne
(₹/t), handling-out cost per tonne (₹/t), and the cargo classes the facility accepts
(multi-select from the same fixed list). Required fields are validated (capacity > 0, all
costs ≥ 0, at least one cargo class, location node must exist). On success the warehouse
appears in the warehouse list with `available_capacity_t = total_capacity_t` and
`source_status: "simulated"` on all runtime-registered warehouses.

### P1 — Stage-at-warehouse plan option

As a cargo owner, when the wait for the next sailing exceeds a configured threshold, or
when a disruption re-plan (Feature 005) is running, the options engine includes a
"Stage at warehouse" plan alongside road and hybrid plans. The staging plan shows:
total cost (truck leg to warehouse + storage cost for estimated wait days + handling-in
+ handling-out + truck leg from warehouse to destination), ETA, CO₂ from truck legs
(storage CO₂ = 0, labelled), and whether the original deadline is met. The plan is
rejected and not shown if no compatible, non-full warehouse exists within the configured
proximity radius.

### P2 — Perishable cargo adjustments

As a cargo owner shipping perishable cargo, the scoring formula uses a tighter schedule-
buffer requirement and an elevated reliability weighting read from configuration. These
adjustments are visible in the plan detail as "Perishable cargo adjustments applied
[assumed]" with the configured values shown alongside.

### P2 — Operator declares certified classes

As a boat operator registering a vessel (Feature 004), the `hazard_certs` field accepts a
multi-select from the same fixed cargo class list. Vessels with no certification receive
only general cargo (the default). This field is already part of Feature 004's vessel
entity; this feature specifies the matching behaviour that consumes it.

### P2 — Warehouse utilisation view

As a planner, I see a warehouse utilisation table on the analytics panel showing each
registered warehouse: total capacity, used capacity, available capacity, and utilisation
percentage. All figures carry a `[simulated]` tag. Utilisation resets on demo reset.

---

## Functional Requirements

**FR-1 — Hazard rules table in configuration**

`data/config.yaml` MUST contain a `hazard_rules` section with one entry per cargo class.
Each entry MUST have:

| Field | Type | Requirement |
|---|---|---|
| `class_id` | string | Matches the enum used in cargo records and vessel certs |
| `allowed_modes` | list of string | Subset of `["road", "water"]`; modes not listed are excluded |
| `certification_required` | bool | If true, vessel must have this class in `hazard_certs` |
| `human_review_required` | bool | If true, compliance review gate applies (P11) |
| `notes` | string | MUST include "verify with IWAI / PESO / state authority before production use" |
| `source_status` | string | MUST be `"assumed"` for every row |

The seven classes are: `general`, `perishable`, `liquid_bulk`, `flammable`, `explosive`,
`toxic_corrosive`, `oversized`. The engine MUST raise a named `ConfigError` if a cargo
class in a request is not found in this table.

The `human_review_required` flag MUST be `true` for at minimum `explosive`, `flammable`,
and `toxic_corrosive`. The spec does not set it for `general`, `perishable`, `liquid_bulk`,
or `oversized`; those defaults are recorded in configuration and tagged `assumed`.

**FR-2 — Hazard hard filter in matching**

Before any scoring, the matching engine applies two hard filters for each candidate sailing:

1. **Mode filter**: if the cargo class's `allowed_modes` does not include `water`, the
   sailing is excluded with reason `mode_not_permitted_for_class`.
2. **Certification filter**: if `certification_required` is true and the vessel's
   `hazard_certs` list does not contain the cargo class, the sailing is excluded with
   reason `missing_hazmat_cert`.

Excluded sailings MUST appear in the response's `excluded` list with their reason. They
MUST NOT be silently dropped (P11). Road plans are unaffected by the certification filter
(road certification is not modelled in this prototype) but ARE excluded if `road` is not
in `allowed_modes`.

The engine MUST NOT produce, quote, or paraphrase any regulatory or safety handling text.
Exclusion reasons are eligibility codes only (P11, FR-5).

**FR-3 — Compliance review gate**

For cargo classes where `human_review_required` is `true`:

1. `POST /api/book` creates the booking in `pending_review` state (not `pending` — a new
   state that precedes the existing two-step P7 flow).
2. `POST /api/compliance/review/{booking_id}/approve` transitions to `pending` state and
   appends a `compliance_review_approved` event log entry. The request body MUST include
   `{"reviewer_note": "<string>"}` (free text, not validated for content).
3. `POST /api/book/{id}/confirm` MUST reject with error `compliance_review_required` if
   the booking is still in `pending_review` state.
4. Once in `pending` state, the normal P7 two-step flow proceeds as defined in the
   constitution. The compliance review does not substitute for P7 confirmation.

The demo UI labels the approve action "Compliance review — simulated; production requires
a qualified person [simulated]." A text banner on the booking shows review status.

**FR-4 — Warehouse entity**

A warehouse record has:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique |
| `name` | string | Free text |
| `location_node_id` | string | Must exist in node list |
| `total_capacity_t` | float | > 0 |
| `capacity_used_t` | float | 0 ≤ used ≤ total; updated on staging acceptance |
| `storage_cost_per_t_per_day` | float | ≥ 0 |
| `handling_in_cost_per_t` | float | ≥ 0 |
| `handling_out_cost_per_t` | float | ≥ 0 |
| `allowed_cargo_classes` | list | Subset of the seven class ids; at least one |
| `source_status` | string | `"simulated"` for seed and runtime-registered warehouses |

Validation on registration: all numeric fields checked against the constraints above;
`location_node_id` must exist; `allowed_cargo_classes` must be non-empty and each element
must be a valid class id. Each failing field returns a structured error `{field, code,
message}` (pattern from Feature 004 FR-4). The warehouse MUST NOT be created if any
required validation fails.

**FR-5 — No regulatory or safety instructions (P11)**

The engine, API, and UI MUST NOT emit text that:
- Quotes or paraphrases specific regulations, threshold concentrations, flash points, or
  UN hazard numbers.
- Gives handling, stowage, segregation, or emergency response instructions.
- Claims a particular route, vessel type, or configuration is "safe" or "compliant."

If a user asks a question in this territory, the UI MUST display: "For regulatory and
safety guidance on hazardous goods transport, contact IWAI, PESO, or the relevant state
authority." No further information is given by the system.

**FR-6 — Staging plan computation**

`compute_staging_plan(cargo, warehouse, next_sailing_wait_h, destination_node, config)`
MUST be a pure deterministic function. It returns a `StagingPlan` with:

- `truck_to_warehouse_cost_inr`: road cost from cargo origin to warehouse location node.
- `handling_in_cost_inr`: `weight_t × warehouse.handling_in_cost_per_t`.
- `storage_cost_inr`: `weight_t × storage_days × warehouse.storage_cost_per_t_per_day`,
  where `storage_days = ceil(next_sailing_wait_h / 24)`.
- `handling_out_cost_inr`: `weight_t × warehouse.handling_out_cost_per_t`.
- `truck_from_warehouse_cost_inr`: road cost from warehouse location node to destination.
- `total_cost_inr`: sum of all five above.
- `total_time_h`: truck leg to warehouse + storage wait (= `next_sailing_wait_h`) + truck
  leg from warehouse.
- `co2_kg`: road CO₂ for both truck legs only; storage CO₂ = 0.
- `co2_scope`: `"truck legs only; storage CO₂ not modelled"`.
- `deadline_met`: bool.
- `source_status`: `"assumed"`.
- `note`: includes "storage CO₂ not modelled in this prototype [assumed]."

A staging plan is not offered if:
- The warehouse's `allowed_cargo_classes` does not include the cargo class
  (reason: `warehouse_class_mismatch`).
- `capacity_used_t + weight_t > total_capacity_t`
  (reason: `warehouse_at_capacity`).
- No warehouse exists within the configured `warehouse_proximity_radius_km`
  (reason: `no_warehouse_in_range`).

**FR-7 — Warehouse capacity guard**

When a staging plan is **confirmed** (not merely proposed):
- `capacity_used_t` increases by `weight_t`.
- If at the moment of confirmation `capacity_used_t + weight_t > total_capacity_t`, the
  confirmation is rejected with reason `warehouse_at_capacity` and the booking is not
  updated. The capacity check at confirmation is authoritative; a passing check at
  proposal time does not guarantee confirmation will succeed (concurrent staging is not
  modelled — first confirmation wins in the in-memory store).

**FR-8 — Staging threshold for options engine integration**

The options engine includes a staging plan in its response when
`next_sailing_wait_h ≥ staging_wait_threshold_h` (read from `data/config.yaml`,
`source_status: assumed`, default 4 h). Below the threshold, staging is not offered
(the wait is short enough that it is not worth the extra handling cost). The threshold
is visible in the options response as `staging_threshold_h` alongside the plan.

**FR-9 — Perishable cargo scoring adjustments**

When `cargo_class == "perishable"`, the options and staging engines apply two config
overrides before scoring:

1. `deadline_buffer_h` is replaced by `perishable.schedule_buffer_h` (must be ≥ standard
   buffer; config validates this at startup).
2. The reliability weight in the scoring formula is replaced by
   `perishable.reliability_weight_override`. The remaining weights (cost, time, CO₂) are
   scaled proportionally so they still sum to 1.0.

Both values are `source_status: assumed`. The plan response includes a
`perishable_adjustments_applied: true` flag and a human-readable note listing the
override values.

**FR-10 — Seed data requirements**

`data/seed.json` MUST be extended with:

- At least two warehouse records under a `warehouses` top-level key:
  - One near node-001 (Kochi area) accepting `general` and `liquid_bulk`.
  - One near node-002 (Alappuzha area) accepting `general`, `perishable`, and `flammable`.
  - Both with realistic seed capacity (e.g. 50 t, 30 t) and non-zero costs.
  - Both `source_status: "simulated"`.
- Three additional cargo records covering: one `flammable` shipment on the hero corridor
  with all vessels uncertified (SC-1 scenario), one `explosive` shipment (triggers
  compliance review, SC-2), one `perishable` shipment (triggers perishable adjustments).
- Seed vessels updated (or two new vessels added) so that at least one vessel is certified
  for `flammable` and one for `liquid_bulk`, enabling a positive hazmat match test.

**FR-11 — Demo reset**

`POST /api/demo/reset` MUST reset `capacity_used_t` to 0 for all warehouses, clear all
runtime-registered warehouses, and clear all compliance review records. Resets in under
1 second (P8).

---

## Reference Scenarios

| Scenario | Setup | Expected outcome |
|---|---|---|
| SC-1: flammable, no certified vessel | `cargo_class = flammable`, all seed vessels lack flammable cert | Ranked list empty; excluded list shows all vessels with `missing_hazmat_cert` |
| SC-2: explosive, compliance gate | `cargo_class = explosive` | Booking created in `pending_review`; confirm rejected until `POST /api/compliance/review/{id}/approve` |
| SC-3: staging for long wait | `cargo_class = general`, next sailing wait ≥ threshold | Options response includes a `stage_at_warehouse` plan with itemised cost and ETA |
| SC-4: warehouse full | Warehouse `capacity_used_t = total_capacity_t` | Staging confirmation rejected with `warehouse_at_capacity`; no booking update |

---

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-1 | A flammable cargo request with only uncertified vessels in seed returns an empty ranked list and a non-empty excluded list with reason `missing_hazmat_cert` for every vessel | Automated pytest |
| SC-2 | A booking for explosive cargo is created in `pending_review` state; `POST /api/book/{id}/confirm` returns `compliance_review_required`; after `POST /api/compliance/review/{id}/approve` the confirm endpoint succeeds | Automated pytest — three-step sequence |
| SC-3 | When sailing wait ≥ `staging_wait_threshold_h`, the options response includes a `stage_at_warehouse` plan whose `total_cost_inr` equals the sum of the five cost components computed by hand | Automated pytest with hand-calculated expected value |
| SC-4 | Confirming a staging plan against a warehouse where `capacity_used_t + weight_t > total_capacity_t` returns `warehouse_at_capacity` and leaves the booking and warehouse state unchanged | Automated pytest |
| SC-5 | A cargo class not found in the hazard rules table raises a named `ConfigError`, not a generic exception | Automated pytest |
| SC-6 | Perishable cargo: the options response includes `perishable_adjustments_applied: true` and the reliability weight in `scores` metadata matches the override value from config | Automated pytest |
| SC-7 | The compliance review endpoint returns a structured error if called on a booking whose class does not require review | Automated pytest |
| SC-8 | Demo reset sets `capacity_used_t` to 0 for all warehouses and clears all runtime compliance records | Automated pytest: stage → reset → assert |

---

## Key Entities

| Entity | Attributes |
|---|---|
| HazardRule | `class_id`, `allowed_modes` (list), `certification_required` (bool), `human_review_required` (bool), `notes`, `source_status` |
| Warehouse | `id`, `name`, `location_node_id`, `total_capacity_t`, `capacity_used_t`, `storage_cost_per_t_per_day`, `handling_in_cost_per_t`, `handling_out_cost_per_t`, `allowed_cargo_classes` (list), `source_status` |
| StagingPlan | `warehouse_id`, `cargo_class`, `weight_t`, `storage_days`, `truck_to_warehouse_cost_inr`, `handling_in_cost_inr`, `storage_cost_inr`, `handling_out_cost_inr`, `truck_from_warehouse_cost_inr`, `total_cost_inr`, `total_time_h`, `co2_kg`, `co2_scope`, `deadline_met`, `perishable_adjustments_applied`, `source_status`, `note` |
| ComplianceReview | `id`, `booking_id`, `cargo_class`, `reviewer_note`, `approved_at`, `source_status` |
| CargoRecord (extended) | adds `cargo_class` (enum, default `general`) to existing cargo entity |
| VesselRecord (extended) | `hazard_certs` (list of class ids) already in Feature 004; this feature specifies the matching behaviour |

---

## Out of Scope

- Actual regulatory compliance validation or legal advice
- UN hazard number lookups, MSDS / SDS sheets, or flash-point data
- Temperature-controlled storage or cold-chain tracking
- Customs or excise duties
- Insurance or liability assignment
- Multi-class segregation rules (a cargo record has one class; mixed loads are out of scope)
- Authentication or role-based access for the compliance reviewer
- Automatic compliance approval based on any rules or thresholds

---

## Assumptions

1. All hazard rule entries are assumed values; none are sourced from an authoritative
   published schedule. Every entry carries `source_status: assumed` and note "verify with
   IWAI / PESO / state authority before production use." This is non-negotiable (P11, FR-5).
2. `human_review_required` defaults: `explosive = true`, `flammable = true`,
   `toxic_corrosive = true`, `liquid_bulk = false`, `oversized = false`, `perishable =
   false`, `general = false`. All `assumed`; actual requirements must be verified.
3. Road mode is always available for `general`, `perishable`, `oversized`, and
   `liquid_bulk` classes (standard road tanker assumed). `explosive` and `toxic_corrosive`
   require special road permits not modelled here — their `allowed_modes` is `[]` by
   default (no mode offered) with note "special permit required; verify with state
   authority." This means SC-1 flammable scenario must have `allowed_modes: ["water"]` or
   `["road", "water"]` so that the match path is reached and the cert filter fires.
   Flammable default: `allowed_modes: ["road", "water"]`, `certification_required: true`.
4. Storage days is computed as `ceil(next_sailing_wait_h / 24)` with a minimum of 1 day.
   This is a simplification; actual charging could be per-hour. Tagged `assumed`.
5. Proximity of a warehouse to a cargo origin or disruption node is measured as straight-
   line Haversine distance (consistent with the rest of the codebase). The search radius
   `warehouse_proximity_radius_km` is stored in `data/config.yaml`, default 10 km,
   `source_status: assumed`.
6. Staging CO₂ is computed for truck legs only using the existing road CO₂ model.
   Storage-phase CO₂ (diesel-powered warehousing, refrigeration, etc.) is set to 0 with
   an explicit caveat in the plan note.
7. Perishable `reliability_weight_override` must be > standard `reliability` weight in
   the scoring config. The engine raises `ConfigError` at startup if this invariant fails.
8. The `cargo_class` field defaults to `general` if omitted in a cargo record or request.
   This ensures backward compatibility with existing seed data that has no `cargo_class`
   field.
9. The compliance review `reviewer_note` is free text stored verbatim; it is not sent to
   any LLM or external service (P15).
10. Runtime-registered warehouses are held in memory and cleared on demo reset, consistent
    with P10 (no persistent database).

---

## Constraints (from Constitution)

- **P2**: `compute_staging_plan()` and the hazard filter logic MUST be pure deterministic
  functions. Tests require no mocking of I/O.
- **P3**: Every hazard rule, threshold, and cost constant MUST be in `data/config.yaml`
  with `source_status: assumed`. No numeric constant MAY be hardcoded in Python or
  JavaScript.
- **P5**: SC-1 through SC-8 are mandatory automated pytest targets. No engine function is
  complete until all pass.
- **P8**: All computation is offline-capable. Demo reset clears warehouses and compliance
  records within 1 second.
- **P10**: No new external dependencies, database, or authentication. In-memory state only.
- **P11**: Hard filter exclusions MUST appear in the excluded list with named reasons.
  The engine MUST NOT emit regulatory or safety handling text. `human_review_required`
  classes MUST NOT reach `confirmed` state without a recorded compliance review.
- **P12**: Staging confirmation follows the same two-step pattern as P7. A proposal does
  not change warehouse capacity; only confirmation does.
- **P13**: All warehouse records, compliance reviews, and utilisation figures carry
  `source_status: "simulated"` in the API and `[simulated]` tags in the UI.
- **P15**: Compliance review notes are never sent to any LLM or external service.
