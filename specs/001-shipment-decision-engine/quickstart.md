# Quickstart & Validation Guide: Shipment Decision Engine

**Feature:** 001 — Shipment Decision Engine
**Created:** 2025-07-17

This guide walks through setting up the project and validating that Feature 001 works
end-to-end. It covers prerequisites, startup, automated tests, and the manual slider
checklist. It does **not** duplicate the data model or OpenAPI contract — refer to
[`data-model.md`](data-model.md) and [`contracts/openapi.yaml`](contracts/openapi.yaml).

---

## Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Python | 3.11 | `pyenv install 3.11` or system package manager |
| pip / venv | bundled with Python | — |
| Node.js | 18 LTS | `nvm install 18` or system package manager |
| npm | 9+ | bundled with Node.js |

No database, no Docker, no internet connection required during the demo.

---

## Project layout

```
JalSetu/
├── backend/
│   ├── engine/          # pure Python engine — no I/O
│   ├── api/             # FastAPI routers and Pydantic models
│   ├── data_store.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   └── vite.config.js
└── data/
    ├── config.yaml      # all numeric constants
    └── seed.json        # nodes, edges, vessels, sailings, cargo requests
```

---

## Backend setup

```bash
# From the project root
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

`requirements.txt` must include:
```
fastapi>=0.111
uvicorn[standard]>=0.29
pydantic>=2.7
pyyaml>=6.0
pytest>=8.0
httpx>=0.27        # for contract tests
```

---

## Start the backend

```bash
cd backend
uvicorn api.main:app --reload --port 8000
```

Expected startup output:
```
INFO: Loading config from ../data/config.yaml
INFO: Loading seed from ../data/seed.json
INFO: Application startup complete.
```

If you see `ConfigError: Missing required config key: <key>`, a required value is absent
from `data/config.yaml`. Add the missing key before proceeding.

---

## Run the automated tests

All tests run offline. From `backend/`:

```bash
pytest engine/tests/ -v                   # engine unit tests
pytest api/tests/  -v                     # contract tests (requires running server OR test client)
pytest -v                                 # all tests
```

### Expected engine test outcomes

| Test | Expected result |
|---|---|
| `test_reference_10h` | `plans[mode=hybrid].recommended == True` |
| `test_reference_3h` | `plans[mode=road].recommended == True` |
| `test_no_sailing` | `plans[mode=water].not_viable == True`, reason `no_sailing_available` |
| `test_cargo_overweight` | `plans[mode=water].not_viable == True`, reason `cargo_exceeds_all_vessel_capacity` |
| `test_no_jetty_in_radius` | `plans[mode=hybrid].not_viable == True`, reason contains `no_jetty_within_radius` |
| `test_all_miss_deadline` | `result.no_plan_meets_deadline == True` |
| `test_subsidy_only_water_leg` | `effective_cost_inr` set on water/hybrid plans, null on road |
| `test_reliability_score` | Deterministic integer; same inputs → same output |
| `test_config_missing_key` | `ConfigError` raised with key name in message |
| `test_tie_broken_by_cost` | Lower-cost plan selected when metrics equal |

All 10 tests must pass (green) before any engine task is considered done.

### Expected contract test outcomes

| Test | Expected result |
|---|---|
| `test_post_options_200` | HTTP 200 |
| `test_post_options_reference` | `plans` has 3 items; hybrid plan `recommended=true` |
| `test_post_options_bad_node` | HTTP 422 |
| `test_demo_reset` | HTTP 200, `{"status": "reset"}` |
| `test_config_assumptions` | HTTP 200, list with at least 15 items, each has `source_status` |
| `test_meta_block` | `response.meta.model == "deterministic\|simulated"` |

---

## Verify the reference scenario via curl

**10 h deadline (expect hybrid recommended):**
```bash
curl -s -X POST http://localhost:8000/options \
  -H "Content-Type: application/json" \
  -d '{
    "cargo_type": "construction_sand",
    "weight_t": 10,
    "origin_node": "kochi-maradu",
    "destination_node": "alappuzha-depot",
    "ready_time": "08:00",
    "deadline": "18:00",
    "objective": "cheapest",
    "subsidy_enabled": false
  }' | python -m json.tool | grep -A2 '"mode_label": "hybrid"'
```

Expected fragment: `"recommended": true`

**3 h deadline (expect road recommended):**
```bash
curl -s -X POST http://localhost:8000/options \
  -H "Content-Type: application/json" \
  -d '{
    "cargo_type": "construction_sand",
    "weight_t": 10,
    "origin_node": "kochi-maradu",
    "destination_node": "alappuzha-depot",
    "ready_time": "08:00",
    "deadline": "11:00",
    "objective": "cheapest",
    "subsidy_enabled": false
  }' | python -m json.tool | grep -A2 '"mode_label": "road"'
```

Expected fragment: `"recommended": true`

---

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Vite dev server starts at `http://localhost:5173`.
API calls target `http://localhost:8000` (configure in `frontend/src/api.js`).

---

## Manual slider checklist (SC-2, SC-3, SC-4, SC-6)

Perform this check with both backend and frontend running.

| Step | Action | Expected |
|---|---|---|
| 1 | Open `http://localhost:5173`. Fill form: 10 t, Kochi Maradu → Alappuzha Depot, 08:00 ready, 18:00 deadline, objective = cheapest. Submit. | Three plan cards appear. Hybrid card shows "Recommended" badge. |
| 2 | Inspect any numeric figure (cost, time, CO₂). | An `[assumed]` or `[sourced]` text badge is visible next to the number. |
| 3 | Drag deadline slider to 11:00. | Road card shows "Recommended" badge within 1 second. Hybrid card loses badge. |
| 4 | Drag slider back to 18:00. | Hybrid card shows "Recommended" badge again within 1 second. |
| 5 | Enable "What-if subsidy" toggle. | Hybrid card shows a second cost line "Effective cost (with subsidy): ₹ N,NNN". Road card shows no effective cost line. |
| 6 | Disable subsidy toggle. | Effective cost line disappears from hybrid card. |
| 7 | Inspect a not-viable plan card (change origin to a node far from any jetty to force hybrid infeasibility). | Card shows "Not viable: no_jetty_within_radius:origin" text. No cost or time figures shown. |
| 8 | Press "Reset Demo" button. | Form returns to default values; plan cards clear. |
| 9 | Tab through all interactive elements. | Focus indicators visible on all buttons, slider, toggle, and form fields. |
| 10 | View "Deadline met" badge on each card. | Both text ("Yes"/"No") and colour are present on the badge. Colour is not the only indicator. |

All 10 steps must pass before Feature 001 is considered done.

---

## Demo reset verification

```bash
curl -s -X POST http://localhost:8000/demo/reset | python -m json.tool
```

Expected:
```json
{
  "status": "reset",
  "message": "Demo state restored to seed."
}
```

---

## Config assumptions endpoint

```bash
curl -s http://localhost:8000/config/assumptions | python -m json.tool | head -40
```

Expected: a JSON object with an `assumptions` array. Every item has `key`, `value`,
`source_status` (`"sourced"` or `"assumed"`), and `note`. All values for this prototype
should have `source_status: "assumed"`.

---

## Acceptance gate summary

| Gate | How verified |
|---|---|
| SC-1: 10 h → hybrid, 3 h → road | `test_reference_10h` + `test_reference_3h` pytest (green) |
| SC-2: update < 1 s | Manual slider checklist steps 3–4 |
| SC-3: 100% numbers tagged | Manual checklist step 2 + visual review of all cards |
| SC-4: viewer identifies recommendation in < 10 s | 3-person quick check during demo |
| SC-5: edge cases return structured results | pytest edge-case tests all green |
| SC-6: text label on every badge | Manual checklist step 10 |
| Constitution P3: no hardcoded constants | `grep -r "3.5\|0.92\|420" backend/engine/` returns nothing |
| Constitution P5: pytest green | `pytest -v` exits 0 |
