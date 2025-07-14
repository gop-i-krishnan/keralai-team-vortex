# Data Model: Shipment Decision Engine

**Feature:** 001 — Shipment Decision Engine
**Created:** 2025-07-17

All entities below are represented as Pydantic v2 models in `backend/api/models.py`
(request/response shapes) and as plain Python dataclasses or TypedDicts in
`backend/engine/` (pure computation shapes). Seed data lives in `data/seed.json`.
Config values live in `data/config.yaml`.

---

## Config entities (`data/config.yaml`)

```yaml
# Every value carries source_status and note.

# ── Distance ──────────────────────────────────────────────────────────────────
road_factor:
  value: 1.3
  source_status: assumed
  note: "Typical India road-to-straight-line ratio for Kerala terrain"

# ── Road transport ────────────────────────────────────────────────────────────
road_rate_per_tkm:        # ₹ per tonne-km
  value: 3.5
  source_status: assumed
  note: "Placeholder; tuned to produce ~Rs.9,000 for 10t × ~257km road"
road_speed_kmh:
  value: 45
  source_status: assumed
  note: "Average truck speed including stops, Kerala NH/SH"
road_co2_per_tkm:         # kg CO₂ per tonne-km
  value: 0.195
  source_status: assumed
  note: "IPCC AR5 default for medium truck"
road_reliability_baseline:
  value: 0.92
  source_status: assumed
  note: "Assumed road on-time fraction; no Kerala-specific data available"

# ── Water transport ───────────────────────────────────────────────────────────
water_freight_rate_per_t: # ₹ per tonne (water leg, fixed charge)
  value: 420
  source_status: assumed
  note: "Placeholder; tuned for reference scenario water leg ~Rs.4,200 for 10t"
water_speed_kmh:
  value: 12
  source_status: assumed
  note: "Typical barge speed on Kerala backwaters"
water_co2_per_tkm:        # kg CO₂ per tonne-km
  value: 0.031
  source_status: assumed
  note: "Approx. IWT emission factor; significantly lower than road"
loading_cost_per_t:       # ₹ per tonne
  value: 80
  source_status: assumed
  note: "Estimated jetty loading charge"
unloading_cost_per_t:     # ₹ per tonne
  value: 80
  source_status: assumed
  note: "Estimated jetty unloading charge"
loading_time_h:
  value: 0.5
  source_status: assumed
  note: "Estimated barge loading time for general cargo"
unloading_time_h:
  value: 0.5
  source_status: assumed
  note: "Estimated barge unloading time"

# ── Hybrid feasibility ────────────────────────────────────────────────────────
jetty_search_radius_km:
  value: 10
  source_status: assumed
  note: "Max road distance from cargo origin/dest to nearest jetty"

# ── Subsidy what-if ───────────────────────────────────────────────────────────
subsidy_pct:
  value: 20
  source_status: assumed
  note: "Hypothetical Kerala IWT subsidy on water-leg freight; not confirmed for short routes"

# ── Balanced objective weights ────────────────────────────────────────────────
balanced_weight_cost:         { value: 0.4, source_status: assumed, note: "Equal-priority composite" }
balanced_weight_time:         { value: 0.3, source_status: assumed, note: "Equal-priority composite" }
balanced_weight_reliability:  { value: 0.2, source_status: assumed, note: "Equal-priority composite" }
balanced_weight_co2:          { value: 0.1, source_status: assumed, note: "Equal-priority composite" }

# ── Reliability model ─────────────────────────────────────────────────────────
reliability_weight_buffer:    { value: 0.40, source_status: assumed, note: "Schedule slack factor" }
reliability_weight_depth:     { value: 0.35, source_status: assumed, note: "Draft safety margin factor" }
reliability_weight_ontime:    { value: 0.25, source_status: assumed, note: "Vessel historical on-time factor" }
reliability_buffer_full_h:    { value: 4.0,  source_status: assumed, note: "Hours of slack that give max buffer score" }
reliability_depth_safe_m:     { value: 1.0,  source_status: assumed, note: "Depth margin (m) above draft that gives max depth score" }
```

---

## Seed data entities (`data/seed.json`)

### Node

```jsonc
{
  "id": "kochi-maradu",
  "name": "Kochi (Maradu)",
  "type": "site",          // "site" | "jetty" | "hub"
  "lat": 9.9312,
  "lon": 76.2673
}
```

**Seed nodes (8–10):**

| id | name | type |
|---|---|---|
| `kochi-maradu` | Kochi (Maradu) | site |
| `kochi-thevara-jetty` | Kochi Thevara Jetty | jetty |
| `kochi-willingdon-jetty` | Kochi Willingdon Island Jetty | jetty |
| `vaikom-jetty` | Vaikom Jetty | jetty |
| `alappuzha-jetty` | Alappuzha Jetty | jetty |
| `alappuzha-depot` | Alappuzha (Depot Rd) | site |
| `changanacherry-hub` | Changanacherry Hub | hub |
| `kollam-jetty` | Kollam Jetty | jetty |
| `kottayam-site` | Kottayam (NH516) | site |
| `ernakulam-hub` | Ernakulam Hub | hub |

---

### Edge

```jsonc
{
  "id": "kochi-maradu__kochi-thevara-jetty__road",
  "from_node": "kochi-maradu",
  "to_node":   "kochi-thevara-jetty",
  "mode":      "road",          // "road" | "water"
  "distance_km": 6.2,
  "depth_m": null               // null for road edges
}
```

Water edges carry `depth_m` (minimum navigable depth in metres). Road edges carry
`distance_km` for the seed-defined legs; haversine is the fallback when no edge exists.

---

### Vessel

```jsonc
{
  "id": "vessel-001",
  "name": "MV Vembanad Star",
  "capacity_t": 25,
  "draft_m": 1.4,
  "on_time_rate": 0.87
}
```

**Seed vessels (6–8):** capacity range 8–50 t; draft range 0.8–2.0 m;
on_time_rate range 0.75–0.95. One vessel intentionally has capacity < 5 t (for the
overweight edge-case test).

---

### Sailing

```jsonc
{
  "id": "sailing-001",
  "vessel_id": "vessel-001",
  "route_nodes": ["kochi-thevara-jetty", "vaikom-jetty", "alappuzha-jetty"],
  "departure_time": "06:00",    // HH:MM IST, daily
  "frequency": "daily"          // "daily" | "weekdays" | "once"
}
```

**Seed sailings (2–3):**
- `sailing-001`: Kochi Thevara → Alappuzha (daily 06:00) — covers reference scenario
- `sailing-002`: Kochi Willingdon → Kollam (daily 07:30)
- `sailing-003`: Vaikom → Changanacherry (weekdays 08:00)

---

### Cargo request

```jsonc
{
  "id": "cargo-001",
  "label": "Reference scenario",
  "cargo_type": "construction_sand",
  "weight_t": 10,
  "origin_node": "kochi-maradu",
  "destination_node": "alappuzha-depot",
  "ready_time": "08:00",        // HH:MM IST
  "objective": "cheapest"
}
```

**Seed cargo requests (10–15):** includes the reference scenario, a 3 h deadline variant,
an overweight scenario (weight > all vessel capacity_t), a no-deadline-met scenario
(deadline < fastest road time), and requests for other corridors.

---

## Engine models (`backend/engine/`)

### `ConfigRef`
```python
@dataclass
class ConfigRef:
    key: str
    value: float | str | int
    source_status: str   # "sourced" | "assumed"
    note: str
```

### `Leg`
```python
@dataclass
class Leg:
    mode: str             # "road" | "water" | "handling" | "waiting"
    from_node: str        # node id
    to_node: str          # node id (same as from_node for handling/waiting)
    distance_km: float    # 0.0 for handling and waiting legs
    cost_inr: float
    time_h: float
    co2_kg: float
    config_values_used: list[ConfigRef]
```

### `ReliabilityResult`
```python
@dataclass
class ReliabilityResult:
    score: int                    # 0–100
    sub_scores: dict[str, float]  # {"buffer": 0.8, "depth": 0.9, "ontime": 0.87}
    reasons: list[str]
    label: str = "simulated model"
```

### `Plan`
```python
@dataclass
class Plan:
    mode_label: str               # "road" | "water" | "hybrid"
    legs: list[Leg]
    total_cost_inr: float
    effective_cost_inr: float | None   # set when subsidy_enabled=True, water/hybrid only
    total_time_h: float
    total_co2_kg: float
    reliability: ReliabilityResult
    deadline_ok: bool
    recommended: bool
    objective: str | None          # which objective this plan was recommended for
    why_text: str | None
    not_viable: bool
    not_viable_reason: str | None
    assumptions: list[ConfigRef]   # union of all legs' config_values_used
```

### `OptionsResult`
```python
@dataclass
class OptionsResult:
    plans: list[Plan]               # always 3 items (road, water, hybrid)
    no_plan_meets_deadline: bool
    fallback_plan_mode: str | None  # fastest plan mode when no_plan_meets_deadline
    objective: str
    subsidy_enabled: bool
```

---

## API models (`backend/api/models.py`)

### Request: `ShipmentRequest`
```python
class ShipmentRequest(BaseModel):
    cargo_type: str
    weight_t: float = Field(gt=0)
    origin_node: str
    destination_node: str
    ready_time: str = "08:00"      # HH:MM IST; defaults applied before engine call
    deadline: str = "18:00"        # HH:MM IST
    objective: Literal["cheapest", "fastest", "greenest",
                        "most_reliable", "balanced"] = "cheapest"
    subsidy_enabled: bool = False
```

### Response: `ConfigRefOut`
```python
class ConfigRefOut(BaseModel):
    key: str
    value: float | str | int
    source_status: str
    note: str
```

### Response: `LegOut`
```python
class LegOut(BaseModel):
    mode: str
    from_node: str
    to_node: str
    distance_km: float
    cost_inr: float
    time_h: float
    co2_kg: float
    config_values_used: list[ConfigRefOut]
```

### Response: `ReliabilityOut`
```python
class ReliabilityOut(BaseModel):
    score: int
    sub_scores: dict[str, float]
    reasons: list[str]
    label: str
```

### Response: `PlanOut`
```python
class PlanOut(BaseModel):
    mode_label: str
    legs: list[LegOut]
    total_cost_inr: float
    effective_cost_inr: float | None
    total_time_h: float
    total_co2_kg: float
    reliability: ReliabilityOut
    deadline_ok: bool
    recommended: bool
    objective: str | None
    why_text: str | None
    not_viable: bool
    not_viable_reason: str | None
    assumptions: list[ConfigRefOut]
```

### Response: `MetaBlock`
```python
class MetaBlock(BaseModel):
    model: str = "deterministic|simulated"
    assumptions: list[ConfigRefOut]
    disclaimer: str = "All rates are assumed placeholder values, not real market quotes."
```

### Response: `OptionsResponse`
```python
class OptionsResponse(BaseModel):
    plans: list[PlanOut]           # always 3 items
    no_plan_meets_deadline: bool
    fallback_plan_mode: str | None
    objective: str
    subsidy_enabled: bool
    meta: MetaBlock
```

---

## State & reset

`InMemoryStore` in `backend/data_store.py` holds:
- `seed_snapshot`: deep copy of `seed.json` loaded at startup (never mutated)
- `live_state`: mutable copy, reset by `POST /demo/reset`

Feature 001 never writes to `live_state`. The reset endpoint replaces `live_state`
with a fresh deep copy of `seed_snapshot`.
