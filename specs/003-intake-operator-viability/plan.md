# Implementation Plan: Natural-Language Intake, Operator Channel and Viability View

**Feature:** 003 — Natural-Language Intake, Operator Channel and Viability View
**Plan version:** 1.0.0
**Created:** 2025-07-17
**Depends on:** Feature 001 (engine, config, seed, options API), Feature 002 (backhaul engine)
**Status:** Ready for tasking

---

## Technical Context

| Dimension | Decision |
|---|---|
| LLM provider | IBM watsonx.ai (primary); any provider via thin `LLMAdapter` interface |
| LLM adapter pattern | Abstract `LLMAdapter` with `WatsonxAdapter`, `MockAdapter` (tests + offline demo) |
| API key handling | Environment variables only (`WATSONX_API_KEY`, `WATSONX_URL`, `WATSONX_PROJECT_ID`); never committed |
| Regex fallback | `backend/engine/parser.py` — `regex_parse()`, pure Python, no I/O |
| Fuzzy node matching | Rapidfuzz `process.extractOne` with score cutoff from config; falls back to exact substring |
| New engine module | `backend/engine/viability.py` — pure Python, `breakeven()` + `classify_corridors()` |
| New API routers | `backend/api/routers/parse.py` (`POST /parse`), `backend/api/routers/viability.py` (`GET /viability`) |
| Frontend map | Leaflet + OpenStreetMap tiles; coloured polylines on corridors; static map layout; no live navigation |
| Frontend chart | Recharts `LineChart` (or plain SVG fallback); break-even curve + road/hybrid cost lines |
| New frontend components | `IntakeBox`, `WhatsAppMock`, `ViabilityChart`, `CorridorMap` |
| No keys in repo | `.env` file (gitignored); `.env.example` committed with placeholder values |

---

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| P1 — Shipment First | Parse produces structured input to Feature 001 engine; LLM never compares modes | ✅ |
| P2 — Deterministic Logic | LLM only extracts fields; viability calculations are pure deterministic Python | ✅ `viability.py` has no LLM calls |
| P3 — Honest Data | All break-even constants in `data/config.yaml`; viability figures tagged "estimated" | ✅ |
| P4 — Subsidy OFF | No subsidy logic in Feature 003 | ✅ Not applicable |
| P5 — Test-first | `viability.py` and `parser.py` have pytest tests; LLM path tested via `MockAdapter` | ✅ |
| P7 — Human in Loop | Low-confidence parses display warning + editable form before user can proceed | ✅ Confidence threshold in config |
| P8 — Graceful Degradation | LLM unavailable → `regex_parse()`; regex fails → blank form; demo works with `MockAdapter` | ✅ |
| P9 — Privacy | Input text scrubbed of personal data patterns before LLM call; seed is simulated | ✅ `scrub_pii()` function in `parser.py` |
| P10 — Simplicity | No real WhatsApp infra, no forecasting; Leaflet map uses static corridor lines from seed | ✅ |

---

## Architecture delta (additions to Features 001–002)

```
backend/
├── engine/
│   ├── parser.py          # regex_parse(), fuzzy_match_node(), scrub_pii()
│   ├── viability.py       # breakeven(), classify_corridors(), demand_summary()
│   └── tests/
│       ├── test_parser.py
│       └── test_viability.py
├── api/
│   ├── routers/
│   │   ├── parse.py       # POST /parse
│   │   └── viability.py   # GET /viability
│   └── llm/
│       ├── adapter.py     # LLMAdapter ABC
│       ├── watsonx.py     # WatsonxAdapter (uses WATSONX_* env vars)
│       └── mock.py        # MockAdapter (deterministic; used in tests + offline demo)
├── .env.example           # committed — placeholder keys
└── .env                   # gitignored — real keys

frontend/src/components/
├── IntakeBox.jsx           # free-text input + confidence badge + editable pre-fill form
├── WhatsAppMock.jsx        # scripted chat panel (operator view)
├── ViabilityChart.jsx      # Recharts LineChart — road vs hybrid cost/km + d* marker
└── CorridorMap.jsx         # Leaflet map with coloured polylines + text labels
```

---

## Phase 0 — Research (resolved)

See `research.md` for full write-up. Summary:

| Research item | Decision |
|---|---|
| watsonx.ai API | `ibm-watsonx-ai` Python SDK; `TextChatParameters`; model `ibm/granite-3-3-8b-instruct` (configurable via env) |
| Adapter interface | Abstract base class `LLMAdapter` with single method `extract(text) → ParseResult`; `MockAdapter` returns hardcoded fixture responses keyed by input hash |
| LLM prompt structure | System prompt (JSON schema + field rules) + 3 few-shot examples (English, Malayalam, relative date) + user message; temperature 0, max tokens 256 |
| Fuzzy node matching | `rapidfuzz.process.extractOne(query, node_names, scorer=fuzz.WRatio, score_cutoff=70)` — cutoff in config |
| Viability formula | `d* = F / (r - w)` pure Python; F is `water_freight_rate_per_t × weight_ref_t` from config |
| Corridor map | Leaflet `L.polyline` per corridor with colour from classification; `L.tooltip` for text label |
| Recharts chart | `LineChart` with two `Line` series (road, hybrid) + `ReferenceLine` at d* |

---

## Phase 1 — Design

### LLM Adapter interface

```python
# backend/api/llm/adapter.py
from abc import ABC, abstractmethod
from engine.parser import ParseResult

class LLMAdapter(ABC):
    @abstractmethod
    def extract(self, text: str) -> ParseResult:
        """
        Accept raw user text; return ParseResult.
        MUST NOT price, rank, score, or recommend.
        MUST be called only after scrub_pii(text).
        """
```

```python
# backend/api/llm/watsonx.py
import os
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

class WatsonxAdapter(LLMAdapter):
    def __init__(self):
        self.client = APIClient(Credentials(
            api_key=os.environ["WATSONX_API_KEY"],
            url=os.environ["WATSONX_URL"],
        ))
        self.model = ModelInference(
            model_id=os.environ.get("WATSONX_MODEL_ID", "ibm/granite-3-3-8b-instruct"),
            project_id=os.environ["WATSONX_PROJECT_ID"],
            api_client=self.client,
        )
        self._prompt = _build_prompt()   # system + few-shots loaded once

    def extract(self, text: str) -> ParseResult:
        scrubbed = scrub_pii(text)
        response = self.model.chat(
            messages=[
                {"role": "system", "content": self._prompt},
                {"role": "user",   "content": scrubbed},
            ],
            params={"temperature": 0, "max_new_tokens": 256},
        )
        raw_json = response["choices"][0]["message"]["content"]
        return _parse_llm_response(raw_json)   # JSON → ParseResult; handles malformed JSON
```

```python
# backend/api/llm/mock.py
class MockAdapter(LLMAdapter):
    """
    Returns fixture ParseResults keyed by normalised input string.
    Used in all pytest tests and when JALSETU_MOCK_LLM=1 env var is set.
    No network call; deterministic.
    """
    FIXTURES = {
        "10 tonnes sand kochi to alappuzha by 6 pm tomorrow": ParseResult(
            cargo_type="construction_sand", weight_t=10.0,
            origin_text="Kochi", destination_text="Alappuzha",
            deadline_text="18:00 tomorrow", confidence=0.97, fallback_used=False, ...
        ),
        # Malayalam fixture, relative-date fixture — see research.md
    }
    def extract(self, text: str) -> ParseResult:
        key = text.strip().lower()
        return self.FIXTURES.get(key, _low_confidence_fixture(text))
```

**Adapter selection** (in `api/main.py` lifespan):
```python
if os.environ.get("JALSETU_MOCK_LLM") == "1" or not os.environ.get("WATSONX_API_KEY"):
    app.state.llm = MockAdapter()
else:
    app.state.llm = WatsonxAdapter()
```

### LLM prompt design

```
System:
  You are a shipment data extractor for a Kerala logistics system.
  Extract ONLY these fields from the user message. Do NOT price, rank, or recommend.
  Return JSON matching this schema exactly:
  {
    "cargo_type": string | null,
    "weight_t": number | null,
    "origin_text": string | null,
    "destination_text": string | null,
    "deadline_text": string | null,
    "confidence": number (0.0–1.0)
  }
  Rules:
  - weight_t must be in tonnes. Convert kg to tonnes if needed.
  - deadline_text must be a time string ("HH:MM" or relative like "by 6 PM tomorrow").
    Do NOT resolve relative dates — return them as-is.
  - If a field cannot be extracted, return null for that field.
  - confidence reflects your certainty across all fields (not per-field).
  - Return ONLY valid JSON. No prose, no explanation.

Few-shot examples:

User: "Send 10 tonnes of sand from Kochi to Alappuzha by 6 PM"
Assistant: {"cargo_type":"construction_sand","weight_t":10,"origin_text":"Kochi",
            "destination_text":"Alappuzha","deadline_text":"18:00","confidence":0.98}

User: "കൊച്ചിയിൽ നിന്ന് ആലപ്പുഴയിലേക്ക് 5 ടൺ തടി നാളെ 3 മണിക്കൂർ ഉള്ളിൽ"
Assistant: {"cargo_type":"timber","weight_t":5,"origin_text":"Kochi",
            "destination_text":"Alappuzha","deadline_text":"by 3 hours tomorrow",
            "confidence":0.72}

User: "Need to move 8t gravel to Vaikom by tomorrow afternoon"
Assistant: {"cargo_type":"gravel","weight_t":8,"origin_text":null,
            "destination_text":"Vaikom","deadline_text":"by afternoon tomorrow",
            "confidence":0.81}
```

### Engine: `backend/engine/parser.py`

```python
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def scrub_pii(text: str) -> str:
    """Remove patterns that look like phone numbers or email addresses."""
    text = re.sub(r'\b\d{10}\b', '[PHONE]', text)
    text = re.sub(r'\S+@\S+\.\S+', '[EMAIL]', text)
    return text

def regex_parse(text: str) -> ParseResult:
    """
    English-only pattern extraction. Returns ParseResult with fallback_used=True.
    Patterns:
      weight:      r'(\d+(?:\.\d+)?)\s*(?:t(?:onne)?s?|ton(?:ne)?s?)'
      cargo_type:  r'(?:of\s+)?(\w+(?:\s+\w+)?)\s+from'  (word(s) before "from")
      origin:      r'from\s+([A-Za-z][A-Za-z\s]+?)(?:\s+to\b)'
      destination: r'to\s+([A-Za-z][A-Za-z\s]+?)(?:\s+by\b|$)'
      deadline:    r'by\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?(?:\s+\w+)?)'
    Unmatched fields → None. Never raises.
    """

def fuzzy_match_node(text: str, nodes: list[Node], cutoff: int) -> str | None:
    """
    Uses rapidfuzz WRatio scorer. Returns node.id if score >= cutoff, else None.
    Falls back to case-insensitive substring match first (faster, exact).
    """

def resolve_deadline(deadline_text: str | None) -> str:
    """
    Resolve relative strings ("by 6 PM tomorrow", "by afternoon tomorrow") to HH:MM IST.
    "tomorrow" → now(IST) + 1 day; time part parsed; defaults to 18:00 if only date.
    Returns HH:MM string. Never raises.
    """
```

### Engine: `backend/engine/viability.py`

```python
@dataclass
class BreakevenResult:
    F_inr: float                   # fixed water leg cost used
    r_per_tkm: float               # road rate ₹/tonne-km
    w_per_tkm: float               # effective water rate ₹/tonne-km (freight/avg_distance)
    breakeven_km: float | None     # None when not_viable
    not_viable: bool
    not_viable_reason: str | None
    source_status: str             # "assumed" for all values in prototype

def breakeven(config: Config) -> BreakevenResult:
    """
    d* = F / (r - w)
    F   = config.water_freight_rate_per_t × config.viability_ref_weight_t
    r   = config.road_rate_per_tkm
    w   = config.water_rate_per_tkm_effective   # new config key: F/avg_water_distance_km
    If r <= w: return BreakevenResult(not_viable=True, reason="road rate not greater than water rate")
    """

@dataclass
class CorridorViability:
    corridor_id: str
    label: str
    from_node: str
    to_node: str
    distance_km: float
    polyline: list[tuple[float, float]]  # [(lat, lon), ...] for Leaflet
    hybrid_cost_inr: float
    road_cost_inr: float
    cost_saving_per_t: float
    co2_saving_kg_per_t: float
    classification: str   # "green" | "amber" | "red" | "unknown"
    source_status: str

def classify_corridors(config: Config, seed: SeedData) -> list[CorridorViability]:
    """
    For each corridor in seed.corridors:
      1. Compute road_cost using Feature 001 road model (distance × rate)
      2. Compute hybrid_cost using Feature 001 hybrid model
      3. saving_pct = (road_cost - hybrid_cost) / road_cost × 100
      4. if saving_pct > config.viability_green_margin_pct  → "green"
         if saving_pct > 0 and saving_pct <= green_margin   → "amber"
         if saving_pct <= 0                                  → "red"
         if seed data insufficient                           → "unknown"
    """

def demand_summary(seed: SeedData) -> list[DemandSummary]:
    """
    Count open cargo requests per corridor_id. Sort descending by count.
    """
```

### API: `POST /parse`

- Calls `scrub_pii(text)` first
- Tries `app.state.llm.extract(scrubbed)` — if any exception → `fallback_used=True`, calls `regex_parse(text)`
- Runs `fuzzy_match_node` on `origin_text` and `destination_text` against `seed.nodes`
- Resolves `deadline_text` with `resolve_deadline()`
- Returns `ParseResponse` — never raises to client; errors become `fallback_used=True`

### API: `GET /viability`

- Calls `breakeven(config)` + `classify_corridors(config, seed)` + `demand_summary(seed)`
- Read-only; no state change
- Returns `ViabilityResponse`

### Frontend components

**`IntakeBox`**
- `<textarea>` for free-text input + "Parse" button
- On submit: `POST /parse` → pre-fill `ShipmentForm` fields
- Shows `ConfidenceBadge`: `[High]` / `[Low]` with text label; colour secondary
- Low confidence (< threshold) → yellow banner: "Low confidence — please review all fields"
- Shows `[offline parser]` badge when `fallback_used=true`
- All fields remain editable; user must explicitly submit the form to proceed

**`WhatsAppMock`**
- Chat-bubble UI panel (no real messaging)
- Operator types → matches against `seed.operator_scripts`
- Shows structured listing + scripted reply + backhaul offer
- Unrecognised input → "Not recognised — please use the manual form."

**`ViabilityChart`**
- Recharts `LineChart`; x-axis = distance (km), y-axis = cost per tonne (₹/t)
- Two `Line` series: Road (straight line) and Hybrid (fixed+variable)
- `ReferenceLine` at `x = d*` labelled "Break-even [estimated]"
- All series labels include text; no information conveyed by colour alone
- Chart legend always visible

**`CorridorMap`**
- Leaflet map with OpenStreetMap tiles; `useEffect` initialises map once
- One `L.polyline` per corridor; colour from classification (`green`/`amber`/`red`/`unknown`)
- `L.tooltip` permanent on each polyline: "Label — Green: water competitive" (text, not colour only)
- `L.control` legend in corner with text labels for each colour class
- Offline note: OSM tiles require internet; map still renders without tiles (polylines on blank background)

---

## Testing Plan

### Engine unit tests (`pytest`)

| Test | Module | Input | Expected |
|---|---|---|---|
| `test_regex_reference` | parser | "10 tonnes sand Kochi to Alappuzha by 6 PM" | `weight_t=10`, `origin_text="Kochi"`, `destination_text="Alappuzha"`, no exception |
| `test_regex_relative_date` | parser | "8t gravel by tomorrow afternoon" | `deadline_text not None`, resolved to 18:00 |
| `test_regex_no_match` | parser | "ഇതൊരു മലയാളം വാക്യം" (Malayalam) | All fields None, no exception |
| `test_fuzzy_match_hit` | parser | "Alleppy" → nodes | Returns `alappuzha-depot` node id |
| `test_fuzzy_match_miss` | parser | "XYZ123" → nodes | Returns None, no exception |
| `test_scrub_pii` | parser | text with phone + email | Neither present in output |
| `test_breakeven_normal` | viability | config with r > w | `not_viable=False`, `breakeven_km > 0` |
| `test_breakeven_not_viable` | viability | config with r <= w | `not_viable=True`, reason set |
| `test_classify_at_least_one_green_one_red` | viability | seed corridors | ≥1 green, ≥1 red |
| `test_classify_unknown` | viability | corridor with missing distance | classification="unknown" |
| `test_demand_summary_sorted` | viability | seed cargo requests | Sorted descending by count |

### Contract tests (`httpx`, `pytest`) — run with `JALSETU_MOCK_LLM=1`

| Test | Endpoint | Assertion |
|---|---|---|
| `test_parse_reference` | `POST /parse` | HTTP 200, `weight_t=10.0`, `origin_node_id="kochi-maradu"` |
| `test_parse_llm_unavailable` | `POST /parse` with LLM exception | HTTP 200, `fallback_used=True`, no exception propagated |
| `test_parse_empty` | `POST /parse` `text=""` | HTTP 422 |
| `test_parse_no_pii_in_logs` | `POST /parse` with phone in input | Scrubbed text in response warnings, not raw phone |
| `test_viability_200` | `GET /viability` | HTTP 200, `corridors` list non-empty, `breakeven` present |
| `test_viability_schema` | `GET /viability` | All `corridor.source_status == "assumed"` |

### Offline demo validation

With `JALSETU_MOCK_LLM=1` (no LLM key needed):
1. `POST /parse` with reference text → correct parse from MockAdapter fixture
2. `GET /viability` → corridors classified, break-even computed — no network call

---

## Deliverables checklist

- [x] `plan.md` — this file
- [ ] `research.md`
- [ ] `data-model.md`
- [ ] `contracts/openapi.yaml`
- [ ] `quickstart.md`
- [ ] Engine modules with passing pytest
- [ ] LLM adapter + mock with passing tests
- [ ] API routers
- [ ] Frontend components
