# Quickstart & Validation Guide: Natural-Language Intake, Operator Channel and Viability View

**Feature:** 003 — Natural-Language Intake, Operator Channel and Viability View
**Created:** 2025-07-17
**Depends on:** Features 001 and 002 running; seed data loaded

This guide validates Feature 003. Refer to [`data-model.md`](data-model.md) and
[`contracts/openapi.yaml`](contracts/openapi.yaml) for schema details.

---

## Prerequisites

- Feature 001 + 002 backend running at `http://localhost:8000`
- All Feature 001 + 002 tests green
- Python packages added: `rapidfuzz`, `ibm-watsonx-ai` (optional for live LLM)

```bash
cd backend
pip install rapidfuzz ibm-watsonx-ai
```

---

## Environment setup

### Offline demo (no API key needed)

```bash
# In backend/.env or exported in your shell:
export JALSETU_MOCK_LLM=1
```

With `JALSETU_MOCK_LLM=1`, the `MockAdapter` is selected. No `WATSONX_*` variables are
needed. The demo runs fully offline.

### Live watsonx.ai (optional)

Copy `.env.example` to `.env` (gitignored) and fill in real values:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env:
#   WATSONX_API_KEY=<your key>
#   WATSONX_URL=https://eu-de.ml.cloud.ibm.com
#   WATSONX_PROJECT_ID=<your project id>
#   WATSONX_MODEL_ID=ibm/granite-3-3-8b-instruct
#   JALSETU_MOCK_LLM=0
```

**Never commit `.env`.** The `.gitignore` must include `backend/.env`.

---

## New engine modules

```
backend/engine/parser.py     # regex_parse, fuzzy_match_node, scrub_pii, resolve_deadline
backend/engine/viability.py  # breakeven, classify_corridors, demand_summary
backend/api/llm/adapter.py   # LLMAdapter ABC
backend/api/llm/watsonx.py   # WatsonxAdapter
backend/api/llm/mock.py      # MockAdapter
```

Restart backend after adding:

```bash
cd backend
JALSETU_MOCK_LLM=1 uvicorn api.main:app --reload --port 8000
```

---

## Run automated tests

All tests use `MockAdapter` (no network needed):

```bash
cd backend
JALSETU_MOCK_LLM=1 pytest engine/tests/test_parser.py    -v
JALSETU_MOCK_LLM=1 pytest engine/tests/test_viability.py -v
JALSETU_MOCK_LLM=1 pytest api/tests/test_parse.py         -v
JALSETU_MOCK_LLM=1 pytest api/tests/test_viability_api.py -v
JALSETU_MOCK_LLM=1 pytest -v   # all tests — must all pass
```

### Expected engine test outcomes

| Test | Expected result |
|---|---|
| `test_regex_reference` | `weight_t=10.0`, `origin_text` contains "Kochi", no exception |
| `test_regex_relative_date` | `deadline` resolved to HH:MM IST, ready_time defaults to 08:00 |
| `test_regex_no_match_malayalam` | All fields None, `fallback_used=True`, no exception |
| `test_fuzzy_match_hit` | "Alleppy" → `alappuzha-depot` id |
| `test_fuzzy_match_miss` | "XYZ123" → None, no exception |
| `test_scrub_pii_phone` | 10-digit number replaced with [PHONE] |
| `test_scrub_pii_email` | email replaced with [EMAIL] |
| `test_breakeven_normal` | `not_viable=False`, `breakeven_km ≈ 166`, chart_points non-empty |
| `test_breakeven_not_viable` | road_rate=0 → `not_viable=True`, reason set |
| `test_classify_green_red` | Seed corridors: ≥1 green, ≥1 red |
| `test_classify_unknown` | Corridor with distance_km=0 → `classification="unknown"` |
| `test_demand_sorted` | Corridor with most requests first |

---

## Verify endpoints via curl (offline — `JALSETU_MOCK_LLM=1`)

### Parse the reference sentence

```bash
curl -s -X POST http://localhost:8000/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "10 tonnes sand Kochi to Alappuzha by 6 PM tomorrow"}' \
  | python -m json.tool
```

Expected:
```json
{
  "cargo_type": "construction_sand",
  "weight_t": 10.0,
  "origin_node_id": "kochi-maradu",
  "destination_node_id": "alappuzha-depot",
  "deadline": "18:00",
  "confidence": 0.97,
  "fallback_used": false
}
```

### Parse with no LLM key (regex fallback)

```bash
JALSETU_MOCK_LLM=0 WATSONX_API_KEY="" \
curl -s -X POST http://localhost:8000/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "10 tonnes sand from Kochi to Alappuzha by 6 PM"}' \
  | python -m json.tool | grep fallback_used
```

Expected: `"fallback_used": true`

### Get viability data

```bash
curl -s http://localhost:8000/viability | python -m json.tool | head -60
```

Expected:
- `breakeven.breakeven_km` is a positive number (≈ 166)
- `corridors` has ≥ 1 entry with `classification: "green"` and ≥ 1 with `classification: "red"`
- `corridors[*].source_status` all equal `"assumed"`
- `demand` is a non-empty list sorted descending by `request_count`

### Operator scripted chat

```bash
curl -s -X POST http://localhost:8000/operator/message \
  -H "Content-Type: application/json" \
  -d '{"text": "12 ton barge, vaikom, free tomorrow, going alappuzha"}' \
  | python -m json.tool
```

Expected:
```json
{
  "matched": true,
  "structured_listing": {
    "capacity_t": 12,
    "home_port": "Vaikom Jetty",
    "availability_date": "tomorrow",
    "destination": "Alappuzha Jetty"
  },
  "reply_text": "Got it! Your 12t barge from Vaikom..."
}
```

### Unrecognised operator message

```bash
curl -s -X POST http://localhost:8000/operator/message \
  -H "Content-Type: application/json" \
  -d '{"text": "hello is anyone there"}' \
  | python -m json.tool | grep reply_text
```

Expected: `"reply_text": "Not recognised — please use the manual form."`

---

## Frontend manual checks

With backend and frontend both running:

| Step | Action | Expected |
|---|---|---|
| 1 | Open app → "Intake" tab. Type reference sentence. Click "Parse". | `ShipmentForm` pre-fills with parsed fields. `confidence` badge shows text "[High confidence]". |
| 2 | Type a low-confidence sentence (e.g. "gravel somewhere tomorrow"). Click "Parse". | Yellow banner "Low confidence — please review all fields" appears. All fields editable. |
| 3 | Set `JALSETU_MOCK_LLM=0` + no key; restart; type reference sentence. | `[offline parser]` badge appears. Fields partially filled. No crash. |
| 4 | Open "Planner" tab → Viability section. | `ViabilityChart` renders two lines (Road, Hybrid) with a vertical "Break-even [estimated]" marker. |
| 5 | Check chart legend. | Text labels for each series; colour is not the only differentiator. |
| 6 | Check `CorridorMap`. | Coloured polylines visible on map. Each polyline has a permanent tooltip with text label (not colour only). Map legend shows text labels for green/amber/red/unknown. |
| 7 | Open "Operator" tab → `WhatsAppMock`. Type scripted message. | Structured listing, reply, and backhaul offer appear in chat bubbles. |
| 8 | Type unrecognised message. | "Not recognised — please use the manual form." appears. No crash. |
| 9 | Press Demo Reset. | Parse form clears; all state restored. Re-run steps 1 and 4 — identical results. |

---

## Acceptance gate summary

| Gate | How verified |
|---|---|
| SC-1: reference sentence parses correctly ≥ 9/10 | 10-run manual test; both LLM and regex paths |
| SC-2: regex fallback never raises | `test_regex_no_match_malayalam` + all 10 edge-case inputs in pytest |
| SC-3: ≥ 1 green + ≥ 1 red corridor | `test_classify_green_red` pytest |
| SC-4: all viability figures tagged estimated/assumed | Visual review step 5–6; `test_viability_schema` contract test |
| SC-5: all FR-10 edge cases return structured results | pytest edge-case suite |
| SC-6: text labels on every badge + colour indicator | Manual steps 2, 5, 6 |
| Constitution P2: LLM never ranks/recommends | Code review: `parser.py` + `viability.py` contain zero LLM calls |
| Constitution P3: no hardcoded constants | `grep -r "3.5\|0.75\|166\|70" backend/engine/` returns nothing |
| Constitution P5: pytest green | `JALSETU_MOCK_LLM=1 pytest -v` exits 0 |
| Constitution P8: offline demo works | `JALSETU_MOCK_LLM=1` + no WATSONX keys → full demo runs |
| No API keys committed | `git log --all -- "**/.env"` returns nothing; `.gitignore` covers `backend/.env` |
