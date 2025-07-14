# Data Model: Capacity Matching, Backhaul and Pooling

**Feature:** 002 — Capacity Matching, Backhaul and Pooling
**Created:** 2025-07-17
**Extends:** Feature 001 data model (`specs/001-shipment-decision-engine/data-model.md`)

All additions below layer on top of the Feature 001 model. Entities already defined there
(Node, Edge, Vessel, Sailing, ConfigRef, MetaBlock) are referenced, not duplicated.

---

## Config additions (`data/config.yaml`)

```yaml
# ── Matching ──────────────────────────────────────────────────────────────────

match_weight_capacity_fit:
  value: 0.30
  source_status: assumed
  note: "Fraction of vessel capacity available; higher = better fit"

match_weight_proximity:
  value: 0.25
  source_status: assumed
  note: "How close vessel's home jetty is to pickup jetty"

match_weight_schedule_slack:
  value: 0.25
  source_status: assumed
  note: "Slack hours between sailing arrival and cargo deadline"

match_weight_price:
  value: 0.15
  source_status: assumed
  note: "Lower water-leg cost relative to reference price = higher score"

match_weight_reliability:
  value: 0.05
  source_status: assumed
  note: "Vessel on-time rate (0–1 fraction)"

proximity_max_km:
  value: 50
  source_status: assumed
  note: "Distance at which proximity sub-score reaches 0"

slack_full_h:
  value: 6.0
  source_status: assumed
  note: "Deadline slack in hours that yields maximum schedule-slack sub-score"

price_ref_inr:
  value: 8000
  source_status: assumed
  note: "Reference water-leg cost (₹) at which price sub-score reaches 0"

draft_safety_margin_m:
  value: 0.3
  source_status: assumed
  note: "Minimum clearance (m) required between vessel draft and route depth"

# ── Backhaul ──────────────────────────────────────────────────────────────────

backhaul_proximity_km:
  value: 15
  source_status: assumed
  note: "Max straight-line distance (km) from candidate origin to arrival jetty (and dest to departure jetty)"
```

---

## Seed data additions (`data/seed.json`)

### Sailing — extended shape

Sailings from Feature 001 gain two mutable fields tracked in `live_state`:

```jsonc
{
  "id": "sailing-001",
  "vessel_id": "vessel-001",
  "route_nodes": ["kochi-thevara-jetty", "vaikom-jetty", "alappuzha-jetty"],
  "departure_time": "06:00",
  "frequency": "daily",
  "capacity_total_t": 25,      // NEW: required for matching and booking
  "capacity_used_t": 0         // seed value; mutable in live_state
}
```

### Cargo request — additions for pooling/backhaul seed

Two poolable small loads (must fit remaining capacity after 10 t hero booking):

```jsonc
{ "id": "cargo-011", "label": "Poolable load A",
  "cargo_type": "tiles", "weight_t": 4,
  "origin_node": "kochi-maradu", "destination_node": "alappuzha-depot",
  "ready_time": "08:00", "objective": "cheapest" },

{ "id": "cargo-012", "label": "Poolable load B",
  "cargo_type": "hardware", "weight_t": 3,
  "origin_node": "kochi-thevara-jetty", "destination_node": "alappuzha-jetty",
  "ready_time": "07:30", "objective": "cheapest" }
```

One backhaul load (origin near Alappuzha jetty, dest near Kochi Thevara jetty):

```jsonc
{ "id": "cargo-013", "label": "Backhaul candidate",
  "cargo_type": "coir_products", "weight_t": 7,
  "origin_node": "alappuzha-depot", "destination_node": "kochi-maradu",
  "ready_time": "14:00", "objective": "cheapest" }
```

Seed constraint: after hero booking (10 t), sailing-001 has 15 t remaining.
Poolable A (4 t) + Poolable B (3 t) = 7 t ≤ 15 t → both selected by greedy.
Backhaul (7 t): `haversine(alappuzha-depot, alappuzha-jetty) < backhaul_proximity_km` ✓
              `haversine(kochi-maradu, kochi-thevara-jetty) < backhaul_proximity_km` ✓

---

## Engine models (`backend/engine/`)

### `FilterResult`
```python
@dataclass
class FilterResult:
    passed: bool
    reason: str | None   # None when passed=True
    # reason codes: "capacity_exceeded" | "draft_too_deep" |
    #               "route_not_permitted" | "deadline_not_met"
```

### `SubScore`
```python
@dataclass
class SubScore:
    factor: str       # "capacity_fit" | "proximity" | "schedule_slack" | "price" | "reliability"
    raw: float        # 0.0–1.0
    reason: str       # human-readable explanation
```

### `MatchResult`
```python
@dataclass
class MatchResult:
    vessel_id: str
    sailing_id: str
    score: int              # 0–100
    sub_scores: list[SubScore]
    excluded: bool = False
    exclusion_reason: str | None = None
```

### `RankResult`
```python
@dataclass
class RankResult:
    ranked: list[MatchResult]    # passed filter, sorted descending by score
    excluded: list[MatchResult]  # failed filter, with exclusion_reason set
```

### `Booking`
```python
@dataclass
class Booking:
    id: str                   # uuid4().hex
    shipment_id: str          # cargo_request.id or ad-hoc label
    sailing_id: str
    weight_t: float
    confirmed: bool
    created_at: str           # ISO datetime, IST
    # Derived at creation time (not stored, computed on GET):
    arrival_jetty: str        # last node in sailing.route_nodes
    departure_jetty: str      # first node in sailing.route_nodes
```

### `BackhaulSuggestion`
```python
@dataclass
class BackhaulSuggestion:
    cargo_request_id: str
    weight_t: float
    backhaul_cost_inr: float
    detour_km: float           # always 0.0 for same-route return
    price_effect_owner_inr: float      # cost to the backhaul cargo owner
    price_effect_requester_inr: float  # revenue gain for the vessel operator (negative cost)
    source_status: str         # "assumed"
```

### `PoolingSuggestion`
```python
@dataclass
class PoolingSuggestion:
    cargo_request_id: str
    weight_t: float
    utilisation_pct: float     # rounded to 1 decimal place
    cost_per_tonne_inr: float  # rounded to 2 decimal places
    source_status: str         # "assumed"
```

---

## API models (`backend/api/models.py` additions)

### Request: `MatchRequest`
```python
class MatchRequest(BaseModel):
    # Inherits all fields from ShipmentRequest (Feature 001)
    cargo_type: str
    weight_t: float = Field(gt=0)
    origin_node: str
    destination_node: str
    ready_time: str = "08:00"
    deadline: str = "18:00"
    objective: Literal["cheapest","fastest","greenest","most_reliable","balanced"] = "cheapest"
    subsidy_enabled: bool = False
    plan_mode: Literal["water", "hybrid"] = "water"
```

### Request: `BookRequest`
```python
class BookRequest(BaseModel):
    sailing_id: str
    cargo_type: str
    weight_t: float = Field(gt=0)
    origin_node: str
    destination_node: str
    ready_time: str = "08:00"
    deadline: str = "18:00"
    human_confirmed: bool = False    # MUST be True for booking to be recorded
```

### Response: `SubScoreOut`
```python
class SubScoreOut(BaseModel):
    factor: str
    raw: float
    reason: str
```

### Response: `MatchResultOut`
```python
class MatchResultOut(BaseModel):
    vessel_id: str
    sailing_id: str
    vessel_name: str
    departure_time: str       # HH:MM IST
    capacity_available_t: float
    capacity_total_t: float
    score: int
    sub_scores: list[SubScoreOut]
    excluded: bool
    exclusion_reason: str | None
```

### Response: `BookPreviewResponse`
```python
class BookPreviewResponse(BaseModel):
    preview: bool = True
    sailing_id: str
    vessel_name: str
    departure_time: str
    weight_t: float
    estimated_cost_inr: float
    meta: MetaBlock
```

### Response: `BackhaulSuggestionOut`
```python
class BackhaulSuggestionOut(BaseModel):
    cargo_request_id: str
    weight_t: float
    backhaul_cost_inr: float
    detour_km: float
    price_effect_owner_inr: float
    price_effect_requester_inr: float
    source_status: str
```

### Response: `PoolingSuggestionOut`
```python
class PoolingSuggestionOut(BaseModel):
    cargo_request_id: str
    weight_t: float
    utilisation_pct: float
    cost_per_tonne_inr: float
    source_status: str
```

### Response: `BookConfirmedResponse`
```python
class BookConfirmedResponse(BaseModel):
    booking_id: str
    sailing_id: str
    vessel_name: str
    departure_time: str
    weight_t: float
    confirmed_cost_inr: float
    backhaul_suggestions: list[BackhaulSuggestionOut]
    pooling_suggestions: list[PoolingSuggestionOut]
    meta: MetaBlock
```

### Response: `MatchResponse`
```python
class MatchResponse(BaseModel):
    ranked: list[MatchResultOut]
    excluded: list[MatchResultOut]
    meta: MetaBlock
```

---

## State mutation summary

| Operation | State change |
|---|---|
| `POST /match` | None — read-only |
| `POST /book` with `human_confirmed=false` | None — preview only |
| `POST /book` with `human_confirmed=true` | `live_state.sailings[id].capacity_used_t += weight_t`; append to `live_state.bookings` |
| `POST /demo/reset` | `live_state.bookings = {}`; restore all `capacity_used_t` from `seed_snapshot` |
| `GET /backhaul/{id}` | None — read-only re-computation |
