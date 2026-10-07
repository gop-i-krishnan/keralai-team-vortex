# Research: Feature 006 — Cargo Hazard Rules and Warehouse Staging

**Feature ID:** 006
**Phase:** Plan — Phase 0 Research
**Date:** 2026-10-07
**Status:** Complete

---

## Topic 1 — Hazard classification for Indian inland waterways

**Decision:** Use a project-defined 7-class taxonomy
(`general`, `perishable`, `liquid_bulk`, `flammable`, `explosive`, `toxic_corrosive`,
`oversized`) stored entirely in `data/config.yaml`.

**Rationale:** No authoritative, publicly available IWAI or PESO schedule of cargo classes
for NW-3 could be found at spec time. Adopting a simplified taxonomy avoids invented
regulatory detail while providing a working demo abstraction. Every rule is tagged
`source_status: assumed` with note "verify with IWAI / PESO / state authority before
production use" (P11, FR-1).

**Alternatives considered:**
- IMDG-class numbering (1–9): too fine-grained for a demo; implies specific UN regulations
  not verified for NW-3. Rejected — P11 prohibits presenting unverified rules as definitive.
- A single boolean `hazardous: true/false`: insufficient to model `flammable` vs `explosive`
  vs `perishable` with different certification and review requirements. Rejected.

---

## Topic 2 — Hazard filter placement in the existing codebase

**Decision:** New pure module `backend/engine/hazards.py` — `apply_hazard_filters()` —
called from the `match` router before the existing `rank_sailings()`. Returns two lists:
`eligible` and `excluded` (with named reasons).

**Rationale:** `rank_sailings()` currently has no knowledge of cargo class. Injecting the
filter upstream keeps both functions small and pure, and avoids modifying a passing test suite.

**Alternatives considered:**
- Extending `rank_sailings()` directly: contaminates a small, tested function with a new
  concern. Rejected.
- Filtering inside the router: logic in a router is not testable as a pure function. Rejected.

---

## Topic 3 — Compliance review state machine

**Decision:** Add a new `pending_review` booking state that precedes the existing
`pending → confirmed` P7 flow. Store compliance review records in a new
`data_store.compliance_reviews` dict keyed by booking id.

**Rationale:** Minimum-change approach: the existing two-step booking flow is unchanged.
`pending_review` is simply a new state that blocks the confirm endpoint until
`POST /api/compliance/review/{id}/approve` transitions it to `pending`.

**State machine:**
```
pending_review ──(approve)──► pending ──(confirm)──► confirmed
```
For non-hazmat classes the flow starts directly at `pending` (no change to existing code).

---

## Topic 4 — Warehouse entity design

**Decision:** A `warehouses` list in `data_store` seeded from `data/seed.json` top-level
`warehouses` key. Runtime registrations appended in memory; all cleared on demo reset.
No separate file or database.

**Rationale:** Consistent with the in-memory-only P10 constraint. The `data_store.py`
pattern (lists seeded from JSON, cleared on reset) is already used for vessels, sailings,
and cargo.

---

## Topic 5 — `compute_staging_plan()` pure function shape

**Decision:** Takes `(cargo: dict, warehouse: dict, next_sailing_wait_h: float,
destination_node: dict, config: dict)` and returns a typed dict `StagingPlan`. All five
cost components are computed inline from config values; no I/O. `storage_days =
max(1, ceil(next_sailing_wait_h / 24))`.

**Rationale:** Pure function is easily unit-tested (SC-3, SC-4). Five named components give
full cost transparency to the cargo owner (P2).

---

## Topic 6 — Perishable scoring override

**Decision:** `build_plans()` receives an optional `cargo_class` parameter. When
`cargo_class == "perishable"`, the deadline buffer and reliability weight are replaced by
the `perishable.*` config values before scoring. Remaining weights are scaled
proportionally to sum to 1.0.

**Rationale:** Minimal extension to `build_plans()` — no new scoring function needed.
Config-driven, deterministic, no hardcoded values.

---

## Topic 7 — Proximity calculation for warehouse matching

**Decision:** Reuse `_haversine_km()` from `options.py`. Extract it into a shared
`backend/engine/geo.py` helper. Both `options.py` and `warehouse.py` import from there.

**Rationale:** `_haversine_km()` already exists and is tested implicitly. Extracting it
avoids code duplication. `warehouse_proximity_radius_km` stored in `data/config.yaml`.

**Alternatives considered:**
- Copy the function into `warehouse.py`: duplication, divergence risk. Rejected.
- Keep it private in `options.py` and call it from there: cross-module coupling to a private
  function. Rejected.

---

## Topic 8 — Demo reset extension

**Decision:** Extend the existing `POST /api/demo/reset` handler to:
1. Reset `capacity_used_t` to 0 for all seed warehouses.
2. Remove all runtime-registered warehouses (retain only seed warehouses).
3. Clear all compliance review records.

**Rationale:** Minimal change; existing reset already reloads sailings and bookings from
seed. Same pattern extended to warehouses and compliance records.

---

## All NEEDS CLARIFICATION resolved

No open questions remain. All items from spec clarification sessions 2026-10-07 are
encoded in `spec.md`. Constants will be written to `data/config.yaml` with `source_status:
assumed`. Simulated runtime data will carry `source_status: "simulated"` in seed and API.
