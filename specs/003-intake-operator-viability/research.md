# Research: Natural-Language Intake, Operator Channel and Viability View

**Feature:** 003 — Natural-Language Intake, Operator Channel and Viability View
**Created:** 2025-07-17

Resolves five research items: LLM provider integration, adapter pattern, prompt design,
fuzzy node matching, and viability formula implementation.

---

## R-1: IBM watsonx.ai SDK Integration

### Decision

Use the official `ibm-watsonx-ai` Python SDK. The relevant call path for chat-style
extraction is `ModelInference.chat()` with a system + user message pair.

```python
pip install ibm-watsonx-ai
```

**Required environment variables** (never committed):

| Variable | Purpose |
|---|---|
| `WATSONX_API_KEY` | IBM Cloud API key with watsonx.ai access |
| `WATSONX_URL` | Regional endpoint, e.g. `https://eu-de.ml.cloud.ibm.com` |
| `WATSONX_PROJECT_ID` | watsonx.ai project UUID |
| `WATSONX_MODEL_ID` | Model to use; default `ibm/granite-3-3-8b-instruct` |

**`.env.example`** (committed):
```
WATSONX_API_KEY=your-ibm-cloud-api-key-here
WATSONX_URL=https://eu-de.ml.cloud.ibm.com
WATSONX_PROJECT_ID=your-project-id-here
WATSONX_MODEL_ID=ibm/granite-3-3-8b-instruct
JALSETU_MOCK_LLM=0
```

**`.env`** — gitignored, holds real values locally.

**Minimal call:**
```python
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

client = APIClient(Credentials(api_key=os.environ["WATSONX_API_KEY"],
                               url=os.environ["WATSONX_URL"]))
model = ModelInference(
    model_id=os.environ.get("WATSONX_MODEL_ID", "ibm/granite-3-3-8b-instruct"),
    project_id=os.environ["WATSONX_PROJECT_ID"],
    api_client=client,
)
response = model.chat(
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": scrubbed_text},
    ],
    params={"temperature": 0, "max_new_tokens": 256},
)
raw_json = response["choices"][0]["message"]["content"]
```

Temperature 0 is critical — it makes the response deterministic for the same input,
which is required by Constitution P2.

### Rationale

- Official IBM SDK; `ibm-watsonx-ai` is the documented replacement for `ibm-watson-machine-learning`.
- Granite 3.3 8B Instruct follows instructions reliably and returns valid JSON with temperature 0.
- Configurable model id via env var means the team can substitute any watsonx-hosted model without a code change.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| OpenAI / Anthropic SDK | watsonx is the preferred IBM platform for this hackathon context |
| LangChain abstraction | Adds a large dependency for a single chat call; over-engineered |
| Direct HTTP requests | More brittle than the official SDK; no retry or auth handling |

---

## R-2: LLM Adapter Interface and MockAdapter

### Decision

Define an abstract base class `LLMAdapter` with a single method:

```python
class LLMAdapter(ABC):
    @abstractmethod
    def extract(self, text: str) -> ParseResult: ...
```

Two concrete implementations:

1. **`WatsonxAdapter`** — calls watsonx.ai via SDK (R-1 above)
2. **`MockAdapter`** — returns hardcoded `ParseResult` fixtures keyed by normalised
   input string; no network call

The `MockAdapter` is selected when either:
- `JALSETU_MOCK_LLM=1` env var is set, OR
- `WATSONX_API_KEY` env var is absent

This guarantees the demo and all pytest tests work offline with no API key.

**MockAdapter fixture keys** (normalised = stripped and lowercased):

| Key | Fixture |
|---|---|
| `"10 tonnes sand kochi to alappuzha by 6 pm"` | Full parse, confidence 0.97 |
| `"10 tonnes sand kochi to alappuzha by 6 pm tomorrow"` | Same + relative date |
| `"കൊച്ചിയിൽ നിന്ന് ആലപ്പുഴ 5 ടൺ"` (Malayalam) | Partial parse, confidence 0.72, `fallback_used=False` |
| `"8t gravel by tomorrow afternoon"` | origin_text=None, confidence 0.81 |
| Any unrecognised key | All fields None, confidence 0.50, `fallback_used=False` |

Any `Exception` raised by `WatsonxAdapter.extract()` is caught in `POST /parse` and
triggers `regex_parse()` with `fallback_used=True`.

### Rationale

- The adapter pattern satisfies Constitution P8 (graceful degradation) without coupling
  the engine or API router to any specific LLM SDK.
- `MockAdapter` makes every pytest test deterministic and offline, satisfying Constitution P5.
- Selecting mock via env var means switching between live and offline requires only a one-line
  environment change — no code change.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Always try LLM, skip tests if no key | Tests would be non-deterministic and skip-dependent |
| Pytest monkeypatch per test | More boilerplate; env var is simpler and applies globally |

---

## R-3: LLM Prompt Design (Few-shot JSON Schema)

### Decision

System prompt specifies the output JSON schema, extraction rules, and three few-shot
examples. The prompt is built once at adapter construction and cached.

**Key rules in system prompt:**

1. Return ONLY valid JSON matching the schema — no prose.
2. `weight_t` in tonnes; convert from kg if the user says "kg".
3. `deadline_text`: return the raw relative string ("by 6 PM tomorrow") — do NOT resolve dates.
   Resolution is done deterministically in `resolve_deadline()` in `parser.py`.
4. `confidence` is a single float across all fields (not per-field).
5. If a field cannot be extracted, return `null` for that field.
6. Do NOT price, rank, score, or recommend anything.

**Three few-shot examples chosen to cover:**

- **Example 1 (English, full):** "Send 10 tonnes of sand from Kochi to Alappuzha by 6 PM"
  → all fields present, high confidence
- **Example 2 (Malayalam, partial):** "കൊച്ചിയിൽ നിന്ന് ആലപ്പുഴ 5 ടൺ നാളെ"
  → cargo and weight extracted, place names partially found, lower confidence, deadline relative
- **Example 3 (English, relative date only):** "Need to move 8t gravel to Vaikom by tomorrow afternoon"
  → origin null, destination present, deadline relative

The Malayalam example is included to:
1. Teach the model that Malayalam text is valid input.
2. Demonstrate expected partial-parse behaviour (not all fields always extractable).
3. Prevent the model from refusing Malayalam input.

**Response validation:** after receiving the raw JSON string from the model, the adapter
runs `json.loads()` in a `try/except`. If parsing fails, it falls back to regex as if the
LLM were unavailable. This ensures a malformed LLM response never propagates as an error.

### Rationale

- Zero-temperature + structured schema prompt produces highly consistent JSON from Granite 3.3.
- Keeping `deadline_text` as raw string (not resolved) means the LLM never needs to know the
  current date — the deterministic `resolve_deadline()` function handles it.
- Three examples cover the three highest-risk input types identified in SC-1 and the spec.

---

## R-4: Fuzzy Node Matching

### Decision

Two-stage matching: exact substring first (O(n), fast), then `rapidfuzz` WRatio if no
exact match found.

```python
pip install rapidfuzz   # add to requirements.txt
```

```python
from rapidfuzz import process, fuzz

def fuzzy_match_node(text: str, nodes: list[Node], cutoff: int = 70) -> str | None:
    if not text:
        return None

    # Stage 1: exact case-insensitive substring
    t_lower = text.strip().lower()
    for node in nodes:
        if t_lower in node.name.lower() or node.name.lower() in t_lower:
            return node.id

    # Stage 2: fuzzy
    names = [n.name for n in nodes]
    result = process.extractOne(text, names, scorer=fuzz.WRatio,
                                score_cutoff=cutoff)
    if result:
        matched_name, score, idx = result
        return nodes[idx].id

    return None
```

`cutoff` (default 70) is stored in `data/config.yaml` as `fuzzy_match_cutoff` with
`source_status: assumed`. The demo seed node names include common English and partial
Malayalam transliterations ("Aleppey" → "Alappuzha", "Cochin" → "Kochi").

**Known mappings to include in seed node names (alternate_names field):**

| Canonical id | alt names in seed |
|---|---|
| `kochi-maradu` | Kochi, Cochin, Cochin Maradu |
| `alappuzha-depot` | Alappuzha, Alleppey, Aleppey |
| `vaikom-jetty` | Vaikom, Vaikam |
| `kollam-jetty` | Kollam, Quilon |

Stage 1 substring match checks both `node.name` and each entry in `node.alternate_names`.

### Rationale

- Two-stage avoids the overhead of rapidfuzz on every call when an exact match is sufficient.
- WRatio handles transpositions ("Allepey" vs "Alleppey") and length differences.
- Cutoff 70 is intentionally permissive for a demo; real deployment would raise it.
- Alternate names in seed data are the correct mechanism for known aliases — no phonetic
  or transliteration engine required (per spec out-of-scope).

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Levenshtein distance only | Less accurate for substring-like matches ("Kochi" in "Kochi Maradu") |
| Soundex / phonetic | Requires additional library; transliteration quality varies for Malayalam |
| LLM for place resolution | Constitutionally prohibited from making decisions; would also be slow |

---

## R-5: Viability Formula and `d*` Implementation

### Decision

The break-even formula `d* = F / (r - w)` uses three values from config:

```
F = config.water_freight_rate_per_t × config.viability_ref_weight_t
r = config.road_rate_per_tkm          (₹ per tonne-km, from Feature 001 config)
w = config.water_rate_per_tkm_effective
      = config.water_freight_rate_per_t / config.viability_avg_water_km
```

`water_rate_per_tkm_effective` converts the fixed-per-tonne water freight charge into
a per-tonne-km rate for the formula by dividing by a representative average corridor
distance. This is labelled `assumed` in config.

Example with seed values:
```
water_freight_rate_per_t    = 420 ₹/t
viability_ref_weight_t      = 1 t  (unit basis for the formula)
road_rate_per_tkm           = 3.5 ₹/t-km
viability_avg_water_km      = 60 km  (assumed average Kerala IWT corridor)

F = 420 × 1 = 420 ₹
w = 420 / 60 = 7.0 ₹/t-km
d* = 420 / (3.5 - 7.0) → r < w → not_viable (water rate exceeds road per km)
```

Wait — this is the expected edge case. The break-even is only meaningful for longer
distances. For the chart to show a useful crossing, we represent the hybrid plan where
the water leg replaces only a fraction of the total road distance. The chart plots:

```
road_cost_per_t(d)   = road_rate × d
hybrid_cost_per_t(d) = F_handling + water_rate × d
                     = (loading + unloading costs per t) + water_freight_rate_per_t
                       (flat charge, independent of distance for the demo)
```

`d*` is the distance at which the two lines cross. For the demo:
```
hybrid_cost = loading_cost_per_t + unloading_cost_per_t + water_freight_rate_per_t
            = 80 + 80 + 420 = 580 ₹/t (flat)
road_cost(d) = 3.5 × d

d* = 580 / 3.5 ≈ 166 km
```

This is the formula used in `viability.py`:
```python
F_total = config.loading_cost_per_t + config.unloading_cost_per_t + config.water_freight_rate_per_t
d_star  = F_total / config.road_rate_per_tkm   # km where road equals hybrid
```

If `road_rate_per_tkm == 0` → `not_viable("road rate is zero")`.

The chart x-axis spans 0 to `viability_chart_max_km` (from config, default 300 km).
The corridor map uses the same `classify_corridors()` to colour each seeded corridor.

### Rationale

- Using total hybrid flat cost (handling + freight) divided by road rate gives the most
  intuitive break-even: "beyond X km, hybrid is cheaper per tonne."
- This is consistent with the original spec formula `d* = F / (r - w)` when F is the
  fixed hybrid overhead and `r` is the road rate, w = 0 (water variable cost is treated
  as ~0 for backwaters).
- The approach avoids the degenerate case where water rate > road rate prevents any
  break-even from existing, since handling is the dominant fixed cost.

All config values used in the formula carry `source_status: assumed` and are displayed
with that tag in the viability view.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Per-km water rate as in original formula | Produces not_viable for most realistic Kerala rates; unhelpful for demo |
| Hardcode the example in the chart | Violates Constitution P3 |
| Separate viability config file | Adds complexity; existing `data/config.yaml` is sufficient |
