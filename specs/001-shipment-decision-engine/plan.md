# Implementation Plan: Shipment Decision Engine

**Feature:** 001 — Shipment Decision Engine
**Plan version:** 1.0.0
**Created:** 2025-07-17
**Status:** Ready for tasking

---

## Technical Context

| Dimension | Decision |
|---|---|
| Language | Python 3.11 (backend), TypeScript/JSX via React 18 + Vite (frontend) |
| Backend framework | FastAPI with Pydantic v2 models |
| Config | PyYAML — loads `data/config.yaml` once at startup |
| Seed data | `data/seed.json` loaded into an in-memory store at startup |
| Engine package | `backend/engine/` — pure Python, zero I/O, zero LLM calls |
| API package | `backend/api/` — FastAPI routers, Pydantic request/response models |
| Frontend | React + Vite, plain CSS or Tailwind core utilities |
| Distance | Haversine formula (great-circle km) × road_factor from config |
| State | In-memory Python dict; reset via `POST /demo/reset` |
| Testing | pytest unit tests (engine), httpx contract tests (API), manual checklist (slider) |
| No database | In-memory only — constitution principle 10 |

---

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| P1 — Shipment First | Road plan always computed and compared even when water/hybrid win | ✅ Enforced in `options.py` — all three plans generated unconditionally |
| P2 — Deterministic Logic | Engine functions are pure; no LLM calls inside `engine/` | ✅ Architecture rule: `engine/` imports only stdlib + config |
| P3 — Honest Data | All constants in `data/config.yaml`; every value has `source_status` + `note` | ✅ `config.py` raises `ConfigError` on missing key |
| P3 — Tags visible | Every API response field that maps to a config value carries `source_status` | ✅ `assumptions` block in every plan response |
| P4 — Subsidy OFF | `subsidy_enabled` defaults to `false`; applied only to water-leg freight | ✅ Default in Pydantic request model |
| P5 — Test-first | Engine functions written with pytest tests covering the worked example | ✅ Tests required before task complete |
| P7 — Human in Loop | No booking in this feature; read-only comparison only | ✅ No booking endpoints in Feature 001 |
| P8 — Offline | No live API calls; OSRM optional and excluded | ✅ Haversine × factor requires no network |
| P9 — Privacy | Seed data uses simulated entities; no personal data | ✅ Seed data specification in data-model.md |
| P10 — Simplicity | One `backend/` folder, one `frontend/` folder; no DB | ✅ File layout enforced |

---

## Architecture

```
JalSetu/
├── backend/
│   ├── engine/
│   │   ├── config.py        # load_config() → Config; raises ConfigError on missing key
│   │   ├── options.py       # compute_options(shipment, config, seed) → OptionsResult
│   │   ├── reliability.py   # reliability_score(factors, config) → ReliabilityResult
│   │   └── tests/
│   │       ├── test_options.py
│   │       └── test_reliability.py
│   ├── api/
│   │   ├── main.py          # FastAPI app, lifespan loads config + seed
│   │   ├── routers/
│   │   │   ├── options.py   # POST /options
│   │   │   ├── demo.py      # POST /demo/reset
│   │   │   └── config.py    # GET /config/assumptions
│   │   └── models.py        # Pydantic v2 request/response models
│   ├── data_store.py        # InMemoryStore — holds seed snapshot + live state
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ShipmentForm.jsx
│   │   │   ├── OptionsComparison.jsx   # three PlanCard side by side
│   │   │   ├── PlanCard.jsx            # single option card (FR-9 fields)
│   │   │   ├── WhyPanel.jsx
│   │   │   ├── DeadlineSlider.jsx
│   │   │   ├── SourceBadge.jsx
│   │   │   ├── SubsidyToggle.jsx
│   │   │   └── DemoResetButton.jsx
│   │   ├── api.js                      # fetch wrappers
│   │   └── App.jsx
│   ├── index.html
│   └── vite.config.js
├── data/
│   ├── config.yaml
│   └── seed.json
└── specs/001-shipment-decision-engine/
    ├── plan.md  ← this file
    ├── research.md
    ├── data-model.md
    ├── contracts/
    │   └── openapi.yaml
    └── quickstart.md
```

---

## Phase 0 — Research (resolved)

All research items are resolved in `research.md`. Summary of decisions:

| Research item | Decision |
|---|---|
| Haversine + road factor | Standard haversine formula (pure Python, no deps); road_factor ≈ 1.3 (assumed, in config) |
| Objective normalisation | Min-max across the three plans; score = 0 when best, 1 when worst; balanced = weighted sum |
| Leg data model | Flat list of `Leg` objects; `Handling` is a special leg with mode=`handling` |
| Reliability sub-weights | Three factors: schedule_buffer (weight from config), draft_margin (from config), on_time_rate (from config); sum must = 1.0 |
| Waiting time | `wait_h = max(0, sailing.departure_iso - ready_time_iso)` in hours; added as a `waiting` pseudo-leg |

---

## Phase 1 — Design

### Engine design: `backend/engine/options.py`

**Input:** `ShipmentInput` (pure data, no I/O) + `Config` + `SeedData`

**Algorithm:**

```
1. Validate config — raise ConfigError on missing key
2. Build road plan:
   a. distance_km = haversine(origin, dest) × road_factor
   b. cost = distance_km × weight_t × road_rate_per_tkm
   c. time_h = distance_km / road_speed_kmh
   d. co2_kg = distance_km × weight_t × road_co2_per_tkm
   e. reliability = road_reliability_constant (from config)
3. Build water plan:
   a. Find best sailing (departure ≥ ready_time, route covers origin→dest jetties)
   b. wait_h = sailing.departure - ready_time
   c. water_distance = sum of water edge distances on route
   d. transit_h = water_distance / water_speed_kmh
   e. loading_h, unloading_h from config
   f. total_time = wait_h + loading_h + transit_h + unloading_h
   g. cost = weight_t × (water_freight_rate + loading_cost + unloading_cost)
   h. co2_kg = water_distance × weight_t × water_co2_per_tkm
   i. reliability = reliability_score(schedule_buffer, draft_margin, on_time_rate)
   j. If no sailing → not_viable("no_sailing_available")
   k. If weight > vessel.capacity_t → not_viable("cargo_exceeds_all_vessel_capacity")
4. Build hybrid plan:
   a. Find origin-side jetty within jetty_search_radius_km of origin
   b. Find dest-side jetty within jetty_search_radius_km of destination
   c. If either missing → not_viable("no_jetty_within_radius:<side>")
   d. truck_leg_1: origin → origin_jetty (road calculation)
   e. water_leg:  origin_jetty → dest_jetty (water calculation)
   f. truck_leg_2: dest_jetty → destination (road calculation)
   g. total = sum of legs; reliability = weighted min of components
5. Apply subsidy if subsidy_enabled:
   a. effective_water_cost = water_cost × (1 - subsidy_pct/100)
   b. Store as effective_cost_₹; original cost_₹ unchanged
6. Score and recommend:
   a. Filter to plans where deadline_ok = True
   b. For each objective, pick winner; ties → lowest total_cost
   c. FR-3: if no plans meet deadline, mark fastest as fallback
7. Collect assumptions: all config values used, with source_status + note
8. Return OptionsResult
```

### Engine design: `backend/engine/reliability.py`

```
reliability_score(schedule_buffer_h, draft_margin_m, on_time_rate,
                  weights: ReliabilityWeights) → ReliabilityResult

  buffer_score  = min(1.0, schedule_buffer_h / weights.buffer_full_h)
  depth_score   = min(1.0, draft_margin_m / weights.depth_safe_m)
  ontime_score  = on_time_rate  # already 0-1

  raw = (buffer_score × weights.w_buffer
       + depth_score  × weights.w_depth
       + ontime_score × weights.w_ontime)

  score = round(raw × 100)  # integer 0-100
  reasons = [human-readable string per factor]
  return ReliabilityResult(score, reasons, label="simulated model")
```

### Objective normalisation

For each objective among the three plans:

```python
values = [p.metric for p in plans if not p.not_viable]
lo, hi = min(values), max(values)
if lo == hi:
    norm = {p.mode: 0.0 for p in plans}
else:
    norm = {p.mode: (p.metric - lo) / (hi - lo) for p in plans}
# For maximise objectives (reliability), invert: 1 - norm
```

Balanced score = `0.4×cost_norm + 0.3×time_norm + 0.2×(1-reliability_norm) + 0.1×co2_norm` (weights from config).

### API design: `POST /options`

- Validates request with Pydantic v2 `ShipmentRequest`
- Calls `compute_options(shipment, app.state.config, app.state.seed)`
- Returns `OptionsResponse` with `plans[]`, `meta` block, `no_plan_meets_deadline` flag
- Pure engine call — no writes to state

### API design: `POST /demo/reset`

- Calls `app.state.store.reset()` — copies the original seed snapshot back into live state
- Returns `{"status": "reset", "message": "Demo state restored to seed."}`

### API design: `GET /config/assumptions`

- Returns the full list of config values used by the engine, each with `key`, `value`, `source_status`, `note`
- Read-only; no state change

### Frontend flow

```
App
├── ShipmentForm   → onChange → POST /options → store result
├── DeadlineSlider → onChange → POST /options (re-submit same form) → update result
├── SubsidyToggle  → onChange → POST /options → update result
├── OptionsComparison
│   └── PlanCard ×3
│       ├── mode label, cost (₹ + SourceBadge), time, CO₂ + SourceBadge
│       ├── ReliabilityBadge (score + expandable reasons)
│       ├── DeadlineBadge (Yes/No text + colour)
│       ├── RecommendedBadge (if recommended)
│       └── WhyPanel (why text)
│           └── collapsible LegsTable
└── DemoResetButton → POST /demo/reset → clear result + reset form
```

`SourceBadge` renders `[assumed]` or `[sourced]` as a `<span>` with visible text and a
title attribute. Colour is used as a secondary cue only; the text label is always present.

---

## Testing Plan

### Engine unit tests (`pytest`)

| Test | Input | Expected |
|---|---|---|
| `test_reference_10h` | 10 t, Kochi→Alappuzha, deadline 18:00 | hybrid recommended, deadline_ok=True |
| `test_reference_3h` | 10 t, Kochi→Alappuzha, deadline 11:00 | road recommended, hybrid deadline_ok=False |
| `test_no_sailing` | origin with no sailings | water/hybrid not_viable="no_sailing_available" |
| `test_cargo_overweight` | weight > all vessel capacity_t | water/hybrid not_viable="cargo_exceeds_all_vessel_capacity" |
| `test_no_jetty_in_radius` | origin far from any jetty | hybrid not_viable="no_jetty_within_radius:origin" |
| `test_all_miss_deadline` | deadline < fastest road time | no_plan_meets_deadline=True, fallback=fastest |
| `test_subsidy_only_water_leg` | subsidy_enabled=True | effective_cost < cost only on water/hybrid plans |
| `test_reliability_score` | known buffer, margin, ontime | deterministic integer score + reasons |
| `test_config_missing_key` | config with required key removed | ConfigError with key name |
| `test_tie_broken_by_cost` | two plans equal on objective | lower cost plan recommended |

### Contract tests (`httpx`, `pytest`)

| Test | Endpoint | Assertion |
|---|---|---|
| `test_post_options_200` | `POST /options` with valid body | HTTP 200, response matches OpenAPI schema |
| `test_post_options_reference` | reference shipment, 10 h deadline | `plans[mode=hybrid].recommended == true` |
| `test_post_options_bad_node` | unknown origin node id | HTTP 422, error detail |
| `test_demo_reset` | `POST /demo/reset` | HTTP 200, `{"status": "reset"}` |
| `test_config_assumptions` | `GET /config/assumptions` | HTTP 200, list of items with source_status |
| `test_meta_block` | any `POST /options` | response.meta.model == "deterministic\|simulated" |

### Manual checklist (slider flip)

1. Load demo with reference shipment, deadline = 18:00 → confirm hybrid recommended.
2. Drag slider to 11:00 → confirm road recommended (update < 1 s visually).
3. Enable subsidy toggle → confirm effective cost appears on hybrid card only.
4. Disable subsidy toggle → confirm effective cost disappears.
5. Press Demo Reset → confirm form returns to seed defaults.

---

## Deliverables checklist

- [x] `plan.md` — this file
- [ ] `research.md`
- [ ] `data-model.md`
- [ ] `contracts/openapi.yaml`
- [ ] `quickstart.md`
- [ ] Engine functions with passing pytest
- [ ] API endpoints with contract tests
- [ ] Frontend components
