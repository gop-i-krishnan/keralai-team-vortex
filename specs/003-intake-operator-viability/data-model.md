# Data Model: Natural-Language Intake, Operator Channel and Viability View

**Feature:** 003 — Natural-Language Intake, Operator Channel and Viability View
**Created:** 2025-07-17
**Extends:** Feature 001 data model + Feature 002 data model

All additions below layer on top of the existing models. Entities already defined in
Features 001–002 are referenced, not duplicated.

---

## Config additions (`data/config.yaml`)

```yaml
# ── Parse / LLM ───────────────────────────────────────────────────────────────

confidence_threshold:
  value: 0.75
  source_status: assumed
  note: "Parse confidence below this threshold triggers a low-confidence warning in the UI"

fuzzy_match_cutoff:
  value: 70
  source_status: assumed
  note: "Rapidfuzz WRatio score cutoff for node name matching (0–100)"

# ── Viability chart ───────────────────────────────────────────────────────────

viability_chart_max_km:
  value: 300
  source_status: assumed
  note: "Maximum x-axis distance (km) for the break-even chart"

viability_green_margin_pct:
  value: 10
  source_status: assumed
  note: "Hybrid saving % above which a corridor is classified green"

viability_amber_margin_pct:
  value: 0
  source_status: assumed
  note: "Hybrid saving % above which a corridor is amber (below green threshold)"
```

---

## Seed data additions (`data/seed.json`)

### Node — extended shape (alternate names for fuzzy matching)

```jsonc
{
  "id": "kochi-maradu",
  "name": "Kochi (Maradu)",
  "type": "site",
  "lat": 9.9312,
  "lon": 76.2673,
  "alternate_names": ["Kochi", "Cochin", "Cochin Maradu"]  // NEW
}
```

All 8–10 nodes gain an `alternate_names` list. Common English aliases and known
transliteration variants are included. No phonetic matching needed.

### Corridor — new seed entity

```jsonc
{
  "id": "corridor-kochi-alappuzha",
  "label": "Kochi–Alappuzha",
  "from_node": "kochi-thevara-jetty",
  "to_node": "alappuzha-jetty",
  "distance_km": 63,
  "polyline": [
    [9.9312, 76.2673],
    [9.8500, 76.3200],
    [9.4981, 76.3388]
  ]
}
```

`polyline` is a list of `[lat, lon]` pairs for Leaflet to draw.

**Seed corridors (4–5):** include at least one that classifies green, one amber, one red,
to satisfy SC-3 and the map requirement.

| id | label | distance_km | Expected classification |
|---|---|---|---|
| `corridor-kochi-alappuzha` | Kochi–Alappuzha | 63 | green (hybrid ~12% cheaper) |
| `corridor-kochi-kollam` | Kochi–Kollam | 142 | green |
| `corridor-vaikom-changanacherry` | Vaikom–Changanacherry | 28 | amber (marginal saving) |
| `corridor-kottayam-kochi` | Kottayam–Kochi | 48 | red (road faster, similar cost) |
| `corridor-kollam-alappuzha` | Kollam–Alappuzha | 85 | green |

### Operator scripts — new seed entity

```jsonc
{
  "operator_scripts": [
    {
      "trigger": "12 ton barge, vaikom, free tomorrow, going alappuzha",
      "structured_listing": {
        "capacity_t": 12,
        "home_port": "Vaikom Jetty",
        "availability_date": "tomorrow",
        "destination": "Alappuzha Jetty"
      },
      "reply_text": "Got it! Your 12t barge from Vaikom to Alappuzha has been noted. We'll match you with available cargo.",
      "backhaul_query": {
        "arrival_jetty": "alappuzha-jetty",
        "departure_jetty": "vaikom-jetty",
        "capacity_t": 12
      }
    }
  ]
}
```

The `backhaul_query` is used by FR-5 to run Feature 002's `find_backhaul()` against open
cargo. The scripted map is stored here in seed data, never in application source.

---

## Engine models (`backend/engine/`)

### `ParseResult`
```python
@dataclass
class ParseResult:
    raw_text: str
    cargo_type: str | None
    weight_t: float | None
    origin_text: str | None
    destination_text: str | None
    deadline_text: str | None        # raw relative string, not yet resolved
    origin_node_id: str | None       # set by fuzzy_match_node
    destination_node_id: str | None
    ready_time: str | None           # HH:MM IST, set by resolve_deadline
    deadline: str | None             # HH:MM IST, set by resolve_deadline
    confidence: float                # 0.0–1.0
    warnings: list[str]              # e.g. ["origin not matched to known node"]
    fallback_used: bool              # True = regex parser was used
```

### `BreakevenResult`
```python
@dataclass
class BreakevenResult:
    F_total_inr: float              # total fixed hybrid overhead per tonne
    road_rate_per_tkm: float
    breakeven_km: float | None      # None when not_viable
    not_viable: bool
    not_viable_reason: str | None
    chart_points: list[ChartPoint]  # pre-computed for x = 0..viability_chart_max_km
    source_status: str              # "assumed"

@dataclass
class ChartPoint:
    distance_km: float
    road_cost_per_t: float
    hybrid_cost_per_t: float
```

### `CorridorViability`
```python
@dataclass
class CorridorViability:
    corridor_id: str
    label: str
    from_node: str
    to_node: str
    distance_km: float
    polyline: list[tuple[float, float]]
    hybrid_cost_inr: float          # total hybrid cost for ref weight
    road_cost_inr: float            # total road cost for ref weight
    saving_pct: float               # (road - hybrid) / road * 100
    cost_saving_per_t: float        # ₹/t
    co2_saving_kg_per_t: float
    classification: str             # "green" | "amber" | "red" | "unknown"
    source_status: str              # "assumed"
```

### `DemandSummary`
```python
@dataclass
class DemandSummary:
    corridor_label: str
    request_count: int
```

### `OperatorMessageResult`
```python
@dataclass
class OperatorMessageResult:
    raw_text: str
    matched: bool
    structured_listing: dict | None
    reply_text: str
    backhaul_offer: BackhaulSuggestion | None   # from Feature 002 backhaul engine
```

---

## API models (`backend/api/models.py` additions)

### Request: `ParseRequest`
```python
class ParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
```

### Request: `OperatorMessageRequest`
```python
class OperatorMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
```

### Response: `ParseResponse`
```python
class ParseResponse(BaseModel):
    cargo_type: str | None
    weight_t: float | None
    origin_text: str | None
    destination_text: str | None
    deadline_text: str | None
    origin_node_id: str | None
    destination_node_id: str | None
    ready_time: str | None           # HH:MM IST
    deadline: str | None             # HH:MM IST
    confidence: float
    warnings: list[str]
    fallback_used: bool
    meta: MetaBlock
```

### Response: `ChartPointOut`
```python
class ChartPointOut(BaseModel):
    distance_km: float
    road_cost_per_t: float
    hybrid_cost_per_t: float
```

### Response: `BreakevenOut`
```python
class BreakevenOut(BaseModel):
    F_total_inr: float
    road_rate_per_tkm: float
    breakeven_km: float | None
    not_viable: bool
    not_viable_reason: str | None
    chart_points: list[ChartPointOut]
    source_status: str
    disclaimer: str
```

### Response: `CorridorViabilityOut`
```python
class CorridorViabilityOut(BaseModel):
    corridor_id: str
    label: str
    from_node: str
    to_node: str
    distance_km: float
    polyline: list[list[float]]    # [[lat, lon], ...]
    hybrid_cost_inr: float
    road_cost_inr: float
    saving_pct: float
    cost_saving_per_t: float
    co2_saving_kg_per_t: float
    classification: str
    source_status: str
```

### Response: `DemandSummaryOut`
```python
class DemandSummaryOut(BaseModel):
    corridor_label: str
    request_count: int
```

### Response: `ViabilityResponse`
```python
class ViabilityResponse(BaseModel):
    breakeven: BreakevenOut
    corridors: list[CorridorViabilityOut]
    demand: list[DemandSummaryOut]
    meta: MetaBlock
```

### Response: `OperatorMessageResponse`
```python
class OperatorMessageResponse(BaseModel):
    matched: bool
    structured_listing: dict | None
    reply_text: str
    backhaul_offer: BackhaulSuggestionOut | None
    meta: MetaBlock
```

---

## LLM adapter models (`backend/api/llm/`)

These are internal Python dataclasses, not exposed in the OpenAPI contract directly
(they are mapped to `ParseResponse` by the router).

### `LLMRawResponse`
```python
@dataclass
class LLMRawResponse:
    raw_json: str
    model_id: str
    tokens_used: int | None
```

---

## Environment variables

| Variable | Required for live LLM | Default / fallback |
|---|---|---|
| `WATSONX_API_KEY` | Yes | Absence → MockAdapter selected |
| `WATSONX_URL` | Yes | — |
| `WATSONX_PROJECT_ID` | Yes | — |
| `WATSONX_MODEL_ID` | No | `ibm/granite-3-3-8b-instruct` |
| `JALSETU_MOCK_LLM` | No | `0`; set to `1` for offline demo / tests |

All are loaded in `api/main.py` lifespan; none are read inside `engine/`.
