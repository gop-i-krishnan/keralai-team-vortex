# Tasks: JalSetu Full Prototype

**Covers:** Feature 001 (Shipment Decision Engine) · Feature 002 (Capacity Matching,
Backhaul and Pooling) · Feature 003 (Intake, Operator Channel and Viability View)
**Generated:** 2025-07-17
**Build target:** 24-hour hackathon demo

**Terminology:** *plan* = a road/water/hybrid transport option (Feature 001); *sailing* = a scheduled vessel voyage (Feature 002).

---

## Implementation Strategy

**MVP scope (P1 stories only):** T001–T067
Tasks T068 onwards add P2/P3 stories (viability frontend, map, WhatsApp mock, demand
summary, demo hardening). Each phase is independently demonstrable.

**Cut list (drop first if time runs short):**
- `T076` CorridorMap Leaflet component
- `T071` WhatsAppMock scripted chat component
- `T068` ViabilityChart Recharts component
- `T072` Demand summary display
- `T082` Three consecutive clean-run demo script

The API and engine layers are **never cut**. Source badge audit (T052/T078) and grep
checks (T054/T055/T079/T080) are **never cut** — they verify constitution compliance.

---

## Phase 1 — Project Setup

- [ ] T001 Initialise repo: create `backend/`, `frontend/`, `data/` directories with empty `__init__.py` files; create `backend/requirements.txt` listing `fastapi>=0.111 uvicorn[standard]>=0.29 pydantic>=2.7 pyyaml>=6.0 pytest>=8.0 httpx>=0.27 rapidfuzz>=3.0 ibm-watsonx-ai>=1.0`
- [ ] T002 [P] Create `backend/.env.example` with `WATSONX_API_KEY`, `WATSONX_URL`, `WATSONX_PROJECT_ID`, `WATSONX_MODEL_ID`, `JALSETU_MOCK_LLM=0`; add `backend/.env` to `.gitignore`
- [ ] T003 [P] Scaffold frontend: `cd frontend && npm create vite@latest . -- --template react`; add `recharts leaflet react-leaflet` to `package.json`; verify `npm run dev` starts
- [ ] T004 Create `data/config.yaml` with all config keys from Features 001–003 data models (road_rate_per_tkm, road_speed_kmh, road_co2_per_tkm, road_reliability_baseline, water_freight_rate_per_t, water_speed_kmh, water_co2_per_tkm, loading_cost_per_t, unloading_cost_per_t, loading_time_h, unloading_time_h, jetty_search_radius_km, subsidy_pct, balanced_weight_*, reliability_weight_*, match_weight_*, proximity_max_km, slack_full_h, price_ref_inr, draft_safety_margin_m, backhaul_proximity_km, road_factor, confidence_threshold, fuzzy_match_cutoff, viability_chart_max_km, viability_green_margin_pct, viability_amber_margin_pct); every key MUST have `value`, `source_status: assumed`, `note`
- [ ] T005 Create `data/seed.json` with 8–10 Kerala nodes (site/jetty/hub with lat/lon/alternate_names), 6–8 vessels (capacity_t/draft_m/on_time_rate), 3 sailings (route_nodes/departure_time/capacity_total_t/capacity_used_t), 10–15 cargo requests including: reference (10 t sand, kochi-maradu→alappuzha-depot, 08:00, 18:00), 3 h deadline variant, overweight (weight > all vessel capacity_t), no-deadline-met, cargo-011 (4 t tiles poolable), cargo-012 (3 t hardware poolable), cargo-013 (7 t coir backhaul), 4–5 corridor objects with polyline arrays, operator_scripts array with scripted Vaikom message

---

## Phase 2 — Foundation (blocking all user stories)

- [ ] T006 [P] Write `backend/engine/config.py`: `load_config(path) → Config`; `Config` is a dataclass with typed accessors; raises `ConfigError(key)` on any missing required key; pure function, no I/O beyond the passed path; add `backend/engine/tests/test_config.py` with tests for happy path and missing-key error
- [ ] T007 [P] Write `backend/data_store.py`: `InMemoryStore` with `seed_snapshot` (deep copy on load, never mutated) and `live_state` (mutable); methods `reset()` → deep-copies snapshot to live_state; `get_sailings()`, `get_cargo_requests()`, `get_bookings()`, `get_nodes()`, `get_vessels()`; no I/O in constructor (takes parsed seed dict)
- [ ] T008 Write `backend/api/main.py`: FastAPI app with lifespan that loads config from `../data/config.yaml` and seed from `../data/seed.json`, stores both on `app.state`; selects `MockAdapter` when `JALSETU_MOCK_LLM=1` or `WATSONX_API_KEY` absent, else `WatsonxAdapter`; include `options`, `demo`, `config` routers (stubs OK at this stage); confirm `uvicorn api.main:app --reload` starts without error

---

## Phase 3 — P1: Side-by-side plan comparison (US1)

*Goal: cargo owner submits a shipment and sees road/water/hybrid cards. Independent test: `test_reference_10h` and `test_reference_3h` pass.*

- [ ] T009 [US1] Write failing test `backend/engine/tests/test_options.py::test_reference_10h`: assert `result.plans[mode=hybrid].recommended == True` for 10 t sand, kochi-maradu→alappuzha-depot, ready 08:00, deadline 18:00, objective cheapest — test must FAIL before implementation
- [ ] T010 [US1] Write failing test `test_options.py::test_reference_3h`: assert `result.plans[mode=road].recommended == True`, deadline 11:00 — must FAIL
- [ ] T011 [US1] Write failing test `test_options.py::test_three_plans_always_returned`: assert `len(result.plans) == 3` for any valid input — must FAIL
- [ ] T012 [P] [US1] Write failing tests for edge cases in `test_options.py`: `test_no_sailing` (water/hybrid not_viable=True, reason no_sailing_available), `test_cargo_overweight` (water/hybrid not_viable=True, reason cargo_exceeds_all_vessel_capacity), `test_no_jetty_in_radius` (hybrid not_viable=True, reason no_jetty_within_radius:origin), `test_all_miss_deadline` (no_plan_meets_deadline=True) — all must FAIL
- [ ] T013 [P] [US1] Write failing test `test_options.py::test_config_missing_key`: remove required key from config fixture → assert `ConfigError` raised with key name — must FAIL
- [ ] T014 [US1] Write `backend/engine/options.py`: `haversine_km(lat1,lon1,lat2,lon2) → float` and `road_distance_km(lat1,lon1,lat2,lon2,road_factor) → float`; implement `_build_road_plan`, `_build_water_plan` (find best sailing with departure ≥ ready_time on the same day IST; if no same-day departure qualifies advance to the next calendar day at the same departure time; compute `wait_h = sailing_departure_h - ready_time_h` adjusting for midnight crossings; return not_viable on no sailing or overweight), `_build_hybrid_plan` (find jetties within jetty_search_radius_km; not_viable with reason `no_jetty_within_radius:origin` or `:destination` if absent); `compute_options(shipment, config, seed) → OptionsResult` calling all three; `why_text` generation is in T018b; run `pytest engine/tests/test_options.py -x` — T009–T013 must go green (T018a/b handled separately)
- [ ] T015 [P] [US1] Write failing test `backend/engine/tests/test_reliability.py::test_reliability_deterministic`: given fixed buffer_h=2.0, margin_m=0.9, ontime=0.87 → assert same integer score returned on two identical calls — must FAIL
- [ ] T016 [P] [US1] Write failing test `test_reliability.py::test_road_reliability_constant`: assert road plan reliability score == `round(config.road_reliability_baseline * 100)` — must FAIL
- [ ] T017 [US1] Write `backend/engine/reliability.py`: `reliability_score(schedule_buffer_h, draft_margin_m, on_time_rate, config) → ReliabilityResult`; three weighted sub-scores; assert weights sum to 1.0 (raise ConfigError if not); road path returns fixed constant; all `test_reliability.py` tests must go green
- [ ] T018a [US1] Write failing test `test_options.py::test_balanced_objective`: verify balanced score uses weights from config (cost 0.4/time 0.3/reliability 0.2/co2 0.1); verify tie broken by lower total_cost — test MUST FAIL before implementation
- [ ] T018b [US1] Implement balanced scoring in `backend/engine/options.py`: weighted sum of min-max normalised cost/time/co2/reliability; tie-break by lower total_cost_inr; generate deterministic `why_text` string for the recommended plan (e.g. "Hybrid is X% cheaper than road and meets your deadline"); run `pytest engine/tests/test_options.py -x` — all must go green
- [ ] T019 [US1] Write `backend/api/models.py`: Pydantic v2 `ShipmentRequest` (with defaults: ready_time="08:00", deadline="18:00", objective="cheapest", subsidy_enabled=False), `LegOut`, `ReliabilityOut`, `PlanOut`, `OptionsResponse`, `MetaBlock`, `ConfigRefOut`; all fields as per `specs/001-shipment-decision-engine/data-model.md`
- [ ] T020 [US1] Write `backend/api/routers/options.py`: `POST /options` calls `compute_options`; assembles `OptionsResponse` with `plans`, `no_plan_meets_deadline`, `meta`; write contract test `backend/api/tests/test_options_api.py::test_post_options_reference` (HTTP 200, hybrid recommended); `test_post_options_bad_node` (HTTP 422); `test_meta_block` (meta.model == "deterministic|simulated"); all must pass
- [ ] T021 [US1] Write `backend/api/routers/demo.py`: `POST /demo/reset` calls `app.state.store.reset()`, returns `{"status":"reset","message":"Demo state restored to seed."}`; write `test_demo_reset` contract test — must pass
- [ ] T022 [US1] Write `backend/api/routers/config_router.py`: `GET /config/assumptions` returns all config values with source_status; write contract test asserting ≥15 items each with source_status field — must pass
- [ ] T023 [US1] Write `frontend/src/components/ShipmentForm.jsx`: controlled form with fields cargo_type, weight_t, origin_node (select from nodes), destination_node (select), ready_time, deadline, objective (select), submit button; calls `POST /options` on submit; passes result to parent via `onResult` prop
- [ ] T024 [P] [US1] Write `frontend/src/components/SourceBadge.jsx`: renders `<span className="source-badge" title={note}>[{source_status}]</span>` with visible text label; `source_status` prop "assumed" → amber background, "sourced" → green background; colour is secondary to text
- [ ] T025 [P] [US1] Write `frontend/src/components/PlanCard.jsx`: renders all FR-9 fields (mode_label, total_cost_inr + SourceBadge, effective_cost_inr if subsidy_enabled, total_time_h, total_co2_kg + SourceBadge, reliability score + expandable reasons, deadline_ok as Yes/No text + colour, recommended badge with objective text, why_text, not_viable_reason, collapsible legs table); no information conveyed by colour alone
- [ ] T026 [US1] Write `frontend/src/components/OptionsComparison.jsx`: renders three `PlanCard` side by side (or stacked mobile); receives `plans` array and `subsidy_enabled` prop
- [ ] T027 [US1] Write `frontend/src/App.jsx`: compose `ShipmentForm` + `OptionsComparison`; wire `onResult`; confirm three plan cards render for reference shipment

---

## Phase 4 — P1: Deadline slider flips recommendation (US2)

*Goal: dragging the slider from 18:00 to 11:00 changes recommended plan from hybrid to road in < 1 s. Independent test: slider manual checklist steps 3–4 pass.*

- [ ] T028 [US2] Write `frontend/src/components/DeadlineSlider.jsx`: range input spanning from the current `ready_time` value (minimum) to 23:59 IST (maximum), mapped to HH:MM strings; the deadline MUST always be ≥ ready_time; `onChange` prop fires debounced (300 ms) with new deadline string; label shows current selected time value in HH:MM IST
- [ ] T029 [US2] Wire `DeadlineSlider` into `App.jsx`: on change, re-submit `ShipmentForm` state with new deadline to `POST /options`; update `OptionsComparison` result
- [ ] T030 [US2] **CHECKPOINT — curl every endpoint**: run curl commands from `specs/001-shipment-decision-engine/quickstart.md` for `POST /options` (10 h deadline → hybrid, 3 h → road), `POST /demo/reset`, `GET /config/assumptions`; all must return expected shapes; paste results into a file `backend/api/tests/checkpoint_001.txt`
- [ ] T031 [US2] **CHECKPOINT — slider hero screen**: open frontend, submit reference shipment with 18:00 deadline → confirm hybrid recommended; drag slider to 11:00 → confirm road recommended within 1 second; record pass/fail in `specs/001-shipment-decision-engine/checklists/requirements.md` SC-2

---

## Phase 5 — P1: Vessel ranking and explicit booking (US3)

*Goal: cargo owner selects a sailing and confirms booking; seeded backhaul and pooling appear. Independent test: `test_rank_hero`, `test_backhaul_seeded`, `test_pooling_seeded` pass.*

- [ ] T032 [US3] Write failing test `backend/engine/tests/test_matching.py::test_rank_hero`: assert ranked list non-empty with sailing-001 present — must FAIL
- [ ] T033 [P] [US3] Write failing tests `test_matching.py`: `test_hard_filter_draft` (draft_too_deep), `test_hard_filter_capacity` (all excluded capacity_exceeded, ranked empty), `test_hard_filter_deadline` (all excluded deadline_not_met), `test_weight_sum_1` (abs(sum-1.0) < 1e-9) — all must FAIL
- [ ] T034 [US3] Write `backend/engine/matching.py`: `hard_filter(sailing, shipment, config, seed) → FilterResult`; `score_sailing(sailing, shipment, config, seed) → MatchResult` (five independent sub-scores per research.md R-2); `rank_sailings(shipment, config, seed) → RankResult`; weights-sum validation; run all `test_matching.py` tests to green
- [ ] T035 [US3] Write failing test `backend/engine/tests/test_backhaul.py::test_backhaul_seeded`: confirm booking of cargo-001 → exactly 1 suggestion (cargo-013, 7 t) — must FAIL
- [ ] T036 [P] [US3] Write failing test `test_backhaul.py::test_backhaul_none`: booking with no open return cargo → empty list, no exception — must FAIL
- [ ] T037 [US3] Write `backend/engine/backhaul.py`: `find_backhaul(booking, config, seed) → list[BackhaulSuggestion]`; two-radius proximity check (haversine); weight-fits-remaining check; same hard-filter check; all `test_backhaul.py` tests must go green
- [ ] T038 [US3] Write failing test `backend/engine/tests/test_pooling.py::test_pooling_seeded`: hero booking confirmed → exactly 2 suggestions (cargo-011 4 t, cargo-012 3 t) — must FAIL
- [ ] T039 [P] [US3] Write failing tests `test_pooling.py`: `test_pooling_greedy_order` (cargo-011 before cargo-012), `test_pooling_none` (no matching requests → empty list) — must FAIL
- [ ] T040 [US3] Write `backend/engine/pooling.py`: `find_pooling(booking, config, seed) → list[PoolingSuggestion]`; greedy knapsack sort by weight_t/water_cost descending; iterate remaining capacity; compute utilisation_pct and cost_per_tonne_inr; all `test_pooling.py` tests must go green
- [ ] T041 [US3] Extend `backend/api/models.py` with `MatchRequest`, `BookRequest`, `MatchResultOut`, `SubScoreOut`, `BookPreviewResponse`, `BookConfirmedResponse`, `BackhaulSuggestionOut`, `PoolingSuggestionOut`, `BackhaulResponse` per `specs/002-capacity-matching-backhaul-pooling/data-model.md`
- [ ] T042 [US3] Write `backend/api/routers/match.py`: `POST /match` calls `rank_sailings`; returns `MatchResponse`; write contract tests `test_match_200`, `test_match_hero` (sailing-001 in ranked), `test_match_overweight` (all excluded) — all must pass
- [ ] T043 [US3] Write `backend/api/routers/booking.py`: `POST /book`; request body uses `human_confirmed: bool = False` (field name matches 002/spec FR-3 and `BookRequest` model); if `human_confirmed=False` return `BookPreviewResponse` (no state change); if `True` check capacity (409 if full), generate `uuid4().hex` booking_id, mutate `live_state.sailings[id].capacity_used_t`, append to `live_state.bookings`, call `find_backhaul` + `find_pooling`, return `BookConfirmedResponse`; write contract tests `test_book_preview` (no booking_id in response), `test_book_confirmed` (booking_id present), `test_book_409`, `test_reset_clears_booking` — all must pass
- [ ] T044 [US3] Write `backend/api/routers/backhaul.py`: `GET /backhaul/{booking_id}`; 404 if not found; re-run find_backhaul + find_pooling; write contract tests `test_backhaul_get`, `test_backhaul_404` — must pass
- [ ] T045 [US3] Write `frontend/src/components/RankedSailings.jsx`: sorted sailing cards (score badge text + sub-scores expandable, capacity, departure time IST, price ₹); collapsed "Excluded sailings" accordion; each exclusion reason as text badge; no colour-only information
- [ ] T046 [US3] Write `frontend/src/components/BookingConfirm.jsx`: modal summary (vessel, departure, load t, cost ₹); "Confirm Booking" button disabled for 300 ms; on click: POST /book with `human_confirmed: true`; shows inline HTTP 409 error "Capacity filled"
- [ ] T047 [US3] Write `frontend/src/components/BackhaulPopup.jsx`: appears after confirmed booking; 1 backhaul card (weight t, cost ₹ + [assumed] badge, detour km); 2 pooling cards (weight t, utilisation %, cost/tonne ₹/t + [assumed] badge); Accept/Decline buttons (UI-only)
- [ ] T048 [US3] **CHECKPOINT — curl Feature 002 endpoints**: run all curl commands from `specs/002-capacity-matching-backhaul-pooling/quickstart.md` (match, preview, confirm, backhaul fetch, 409, reset + 404); paste results into `backend/api/tests/checkpoint_002.txt`

---

## Phase 6 — P2: Subsidy what-if toggle (US4)

*Goal: enabling subsidy toggle shows effective cost on hybrid/water cards only; disabling hides it. Independent test: `test_subsidy_only_water_leg` passes.*

- [ ] T049a [US4] Write failing test `test_options.py::test_subsidy_only_water_leg`: `subsidy_enabled=True` → `effective_cost_inr` set on water/hybrid plans, `None` on road plan; `subsidy_pct` read from config, never hardcoded — test MUST FAIL before implementation
- [ ] T049b [US4] Implement subsidy logic in `backend/engine/options.py`: in `_build_water_plan` and the water leg of `_build_hybrid_plan`, when `subsidy_enabled=True` compute `effective_cost_inr = water_freight_cost × (1 - config.subsidy_pct/100)`; handling and truck-leg costs unchanged; run `pytest engine/tests/test_options.py::test_subsidy_only_water_leg` — must go green
- [ ] T050 [US4] Write `frontend/src/components/SubsidyToggle.jsx`: labelled checkbox "What-if policy subsidy (OFF by default)"; shows tooltip "This is a hypothetical scenario — subsidy availability for short Kerala routes is unconfirmed"; `onChange` triggers re-submit of shipment form with `subsidy_enabled` toggled
- [ ] T051 [US4] Wire `SubsidyToggle` into `App.jsx`; confirm effective cost row appears on hybrid card when enabled and disappears when disabled

---

## Phase 7 — P2: Source badge on every displayed number (US5)

*Goal: 100% of numbers in the UI carry [assumed] or [sourced] text badge. Independent test: manual checklist SC-3.*

- [ ] T052 [US5] Audit `PlanCard.jsx`, `BackhaulPopup.jsx`, `RankedSailings.jsx`: wrap every displayed numeric value (cost, time, CO₂, score, rate, weight) in `<SourceBadge source_status={...} note={...} />`; check that no raw number renders without a badge
- [ ] T053 [US5] Add visible prototype disclaimer banner to `App.jsx`: "All rates are assumed placeholder values — not real market quotes" rendered in a `<aside>` above the plan cards
- [ ] T054 [US5] **CONFIG STRUCTURE CHECK**: verify `data/config.yaml` contains all required keys (road_rate_per_tkm, water_freight_rate_per_t, road_reliability_baseline, subsidy_pct, balanced_weight_*, reliability_weight_*, match_weight_*, etc.); assert every key has `source_status` and `note` fields; run `python -c "import yaml; c=yaml.safe_load(open('data/config.yaml')); [assert 'source_status' in v and 'note' in v for v in c.values()]"` — must pass; record in `backend/api/tests/checkpoint_config_structure.txt`
- [ ] T055 [US5] **LLM BOUNDARY CHECK**: confirm `backend/api/llm/` directory exists with `adapter.py`, `watsonx.py`, `mock.py`; run `grep -rn "from api.llm\|import.*Adapter\|import.*watsonx\|ibm_watsonx" backend/engine/` — must return zero matches; record in `backend/api/tests/checkpoint_llm_boundary.txt`

---

## Phase 8 — P1: Natural-language intake (US6)

*Goal: typing reference sentence pre-fills the shipment form; offline fallback never crashes. Independent test: `test_regex_reference`, `test_parse_reference` pass.*

- [ ] T056 [US6] Write `backend/api/llm/adapter.py`: `LLMAdapter` abstract base class with `extract(text: str) → ParseResult`
- [ ] T057 [P] [US6] Write `backend/api/llm/mock.py`: `MockAdapter(LLMAdapter)` with FIXTURES dict keyed by normalised text; returns deterministic `ParseResult`; includes fixtures for English reference, partial Malayalam, relative-date-only inputs; unrecognised keys return all-None result with confidence 0.50
- [ ] T058 [P] [US6] Write `backend/api/llm/watsonx.py`: `WatsonxAdapter(LLMAdapter)`; reads `WATSONX_API_KEY/URL/PROJECT_ID/MODEL_ID` from env; calls `ModelInference.chat()` with system prompt + 3 few-shot examples (English full, Malayalam partial, relative-date-only) at temperature 0; wraps response JSON parse in try/except → fallback to `regex_parse` on failure; `scrub_pii(text)` called before any LLM call
- [ ] T059 [US6] Write failing tests `backend/engine/tests/test_parser.py`: `test_regex_reference` (weight_t=10, origin has "Kochi", no exception), `test_regex_relative_date` (deadline resolved to HH:MM IST), `test_regex_no_match_malayalam` (all fields None, fallback_used=True, no exception), `test_fuzzy_match_hit` ("Alleppy" → alappuzha-depot), `test_fuzzy_match_miss` ("XYZ123" → None), `test_scrub_pii_phone` ([PHONE] in output), `test_scrub_pii_email` ([EMAIL] in output) — all must FAIL
- [ ] T060 [US6] Write `backend/engine/parser.py`: `scrub_pii(text)`, `regex_parse(text) → ParseResult` (English patterns, never raises), `fuzzy_match_node(text, nodes, cutoff) → str|None` (exact substring first, then rapidfuzz WRatio), `resolve_deadline(deadline_text) → str` (HH:MM IST; "tomorrow" → now+1 day; default 18:00); all `test_parser.py` tests must go green
- [ ] T061 [US6] Extend `backend/api/models.py` with `ParseRequest`, `ParseResponse`, `OperatorMessageRequest`, `OperatorMessageResponse` per `specs/003-intake-operator-viability/data-model.md`
- [ ] T062 [US6] Write `backend/api/routers/parse.py`: `POST /parse`; call `scrub_pii`; try `app.state.llm.extract(scrubbed)` → on any exception fall back to `regex_parse` with `fallback_used=True`; run `fuzzy_match_node` on origin/dest texts; run `resolve_deadline`; return `ParseResponse`; write contract tests `JALSETU_MOCK_LLM=1`: `test_parse_reference`, `test_parse_llm_unavailable` (force exception → fallback_used=True), `test_parse_empty` (422), `test_parse_no_pii_in_logs` — all must pass
- [ ] T063 [US6] Write `frontend/src/components/IntakeBox.jsx`: `<textarea>` + "Parse" button; on response: pre-fill `ShipmentForm` fields; show `ConfidenceBadge` (text "[High]"/[Low]"); show "[offline parser]" badge when `fallback_used=true`; yellow banner when confidence < threshold; all fields editable after parse

---

## Phase 9 — P1: Viability engine and endpoint (US7)

*Goal: GET /viability returns break-even + classified corridors; at least one green and one red in seed. Independent test: `test_breakeven_normal`, `test_classify_green_red` pass.*

- [ ] T064 [US7] Write failing tests `backend/engine/tests/test_viability.py`: `test_breakeven_normal` (not_viable=False, breakeven_km > 0, chart_points non-empty), `test_breakeven_not_viable` (road_rate=0 → not_viable=True), `test_classify_green_red` (seed → ≥1 green, ≥1 red), `test_classify_unknown` (zero distance → unknown), `test_demand_sorted` (descending order) — all must FAIL
- [ ] T065 [US7] Write `backend/engine/viability.py`: `breakeven(config) → BreakevenResult` using `F_total = loading + unloading + water_freight_rate_per_t`, `d* = F_total / road_rate_per_tkm`; pre-compute `chart_points` for x in 0..viability_chart_max_km; `classify_corridors(config, seed) → list[CorridorViability]` reusing Feature 001 cost model; `demand_summary(seed) → list[DemandSummary]`; all tests must go green
- [ ] T066 [US7] Write `backend/api/routers/viability.py`: `GET /viability` returns `ViabilityResponse` with breakeven, corridors, demand, meta; write contract tests `test_viability_200`, `test_viability_schema` (all corridor source_status=="assumed") — must pass
- [ ] T067 [US7] **CHECKPOINT — curl Feature 003 endpoints**: run all curl commands from `specs/003-intake-operator-viability/quickstart.md` (parse reference, parse fallback, viability, scripted operator, unrecognised operator); paste results into `backend/api/tests/checkpoint_003.txt`

---

## Phase 10 — P2: Viability frontend (US8)

*Goal: planner sees break-even chart and coloured corridor map.*

- [ ] T068 [US8] Write `frontend/src/components/ViabilityChart.jsx`: Recharts `LineChart`; x = distance 0..viability_chart_max_km, y = cost per tonne ₹/t; two `Line` series (Road, Hybrid) from `breakeven.chart_points`; `ReferenceLine` at `breakeven_km` labelled "Break-even [estimated]"; series identified by text labels, not colour only; if `not_viable`, show text "Break-even distance undefined — [reason]"
- [ ] T069 [P] [US8] Write `frontend/src/components/CorridorMap.jsx`: Leaflet map centred on Kerala (9.5°N, 76.5°E); `L.polyline` per corridor with colour from classification; `L.tooltip` permanent with text label e.g. "Kochi–Alappuzha — Green: water competitive"; map legend with text labels for green/amber/red/unknown; note: OSM tiles require internet; polylines render on blank background offline

---

## Phase 11 — P2/P3: Operator channel and demand (US9)

- [ ] T070 [US9] Write `backend/api/routers/operator.py`: `POST /operator/message`; normalise input (strip, lower); look up in `seed.operator_scripts`; if matched: assemble `OperatorMessageResponse` with structured_listing, scripted reply, run `find_backhaul` for top suggestion; if not matched: return `reply_text="Not recognised — please use the manual form."`; write contract tests `test_operator_scripted` (matched=True, reply non-empty), `test_operator_unrecognised` (matched=False, reply equals fallback string) — must pass; also add `test_empty_ranked_list_messages` to `test_match.py` asserting the three specific human-readable messages for capacity_exceeded ("Your load exceeds…"), deadline_not_met ("No sailing can meet…"), and all-filters-fail ("No vessels available…") — must pass
- [ ] T071 [P] [US9] Write `frontend/src/components/WhatsAppMock.jsx`: chat-bubble panel; operator types message, hits Send; POST /operator/message; renders scripted reply + structured listing + backhaul offer in chat bubbles; unrecognised → fallback message bubble
- [ ] T072 [P] [US9] Write demand summary display in the Planner tab: table or bar chart of corridor_label vs request_count from `viability.demand`; fetch on tab open
- [ ] T073 [US3] Write `frontend/src/components/DemoResetButton.jsx`: button "Reset Demo"; calls `POST /demo/reset`; on success clears all frontend state (plan result, booking state, parse state) to defaults — **moved here from Phase 11: the reset button is required for every demo run, not P2/P3 polish**

---

## Phase 12 — Polish and cross-cutting

- [ ] T074 Accessibility audit: tab through all interactive elements; confirm focus indicators visible; verify every badge/indicator has text label and WCAG AA contrast; fix any missing `aria-label` attributes on icon-only elements
- [ ] T075 Write `frontend/src/api.js`: centralise all fetch calls; add error boundary in `App.jsx` that catches unhandled errors and shows "Something went wrong — please reset the demo" rather than a crash screen
- [ ] T076 Add `pytest` CI sanity check: create `backend/Makefile` with `test` target `JALSETU_MOCK_LLM=1 pytest -v --tb=short`; confirm exits 0 from a clean install

---

## Phase 13 — Demo hardening

- [ ] T077 **FULL pytest run**: `JALSETU_MOCK_LLM=1 pytest -v` from `backend/`; all tests must pass (0 failures, 0 errors); record output in `backend/api/tests/pytest_final.txt`
- [ ] T078 **Full source badge audit** (constitution P3 — never cut): manually load the UI; open browser dev tools → search DOM for any number rendered without a `source-badge` sibling; fix each one found; record pass in checklist 001/SC-3 and 003/SC-4
- [ ] T079 **GREP CHECK — hardcoded constants (final)**: `grep -rn "[0-9]\.[0-9]" backend/engine/ backend/api/routers/ --include="*.py" --exclude-dir=tests`; each match must trace to a config read, not a literal; record in `backend/api/tests/checkpoint_constants_final.txt`
- [ ] T080 **GREP CHECK — LLM calls inside engine/ (final)**: `grep -rn "watsonx\|llm\|adapter\|ibm_watsonx" backend/engine/ --include="*.py"`; must return zero matches; record in `backend/api/tests/checkpoint_llm_final.txt`
- [ ] T081 Demo reset validation: confirm booking → POST /demo/reset → re-run reference match → assert `capacity_available_t` back to seed value; automate as `backend/api/tests/test_demo_reset_full.py`; must pass
- [ ] T082 **THREE CONSECUTIVE CLEAN RUNS**: restart backend (`JALSETU_MOCK_LLM=1 uvicorn api.main:app --port 8000`); run `JALSETU_MOCK_LLM=1 pytest -v` three times in a row; all must pass each time; record run 1/2/3 exit codes in `backend/api/tests/clean_runs.txt`
- [ ] T082a **10-run manual parse test** (003/SC-1): type the reference sentence "10 tonnes sand Kochi to Alappuzha by 6 PM tomorrow" into `IntakeBox` 10 times using the live LLM (or MockAdapter if LLM unavailable); assert all 10 fields extracted correctly on at least 9 of 10 attempts; record pass/fail count per run in `backend/api/tests/checkpoint_parse_sc1.txt`
- [ ] T082b **Usability check** (001/SC-4): demonstrate the recommended option and why-text to 3 observers without coaching; all 3 must identify the recommended plan within 10 seconds; record pass/fail per observer in `specs/001-shipment-decision-engine/checklists/requirements.md` SC-4

---

## Dependency graph

```
T001–T005 (Setup)
    └── T006–T008 (Foundation)
            ├── T009–T031 (US1 + US2: plan comparison + slider) ← MVP gate
            │       ├── T032–T048 (US3: vessel ranking + booking)
            │       │       └── T049a/b–T051 (US4: subsidy toggle)
            │       │               └── T052–T055 (US5: source badges + checks)
            │       └── T073 (DemoResetButton) ← same phase as US3 API done
            ├── T032–T040 (matching/backhaul/pooling engine) ← ALSO parallel with T009–T018 after T008
            ├── T056–T063 (US6: NL intake) ← parallel with US3 after T008
            └── T064–T067 (US7: viability engine + endpoint) ← parallel after T008
                    └── T068–T069 (US8: viability frontend)
                            └── T070–T072 (US9: operator channel + demand)

T074–T082b (Polish + demo hardening) ← after all user stories
```

## Parallel execution opportunities

| Parallelisable group | Tasks |
|---|---|
| After T008: engine work | T009–T018a (options engine) + T032–T040 (matching/backhaul/pooling engine) + T056–T060 (parser engine) + T064–T065 (viability engine) |
| After T019: API and frontend models | T020–T022 (API routers) + T023–T027 (frontend components) |
| After T034: backhaul + pooling | T035–T037 (backhaul) + T038–T040 (pooling) — different files |
| After T066: frontend P2 | T068 (chart) + T069 (map) |

---

## Cut list (drop in this order if time runs short)

| Task | Story | Effort | Impact if cut |
|---|---|---|---|
| T069 CorridorMap Leaflet | US8 | High | Planner map absent; chart still shows |
| T071 WhatsAppMock | US9 | Medium | Operator channel tab absent |
| T068 ViabilityChart | US8 | Medium | Viability tab is text-only |
| T072 Demand summary display | US9 | Low | No bar chart; data available via API |
| T082 Three consecutive runs | Hardening | Low | Demo quality check skipped |
| T082b Usability check | Hardening | Low | SC-4 unchecked; low risk |

**Never cut:** T009–T031 (P1 engine + API), T073 (DemoResetButton), T077 (full pytest
run), T078 (source badge audit — constitution P3), T054–T055, T079–T080 (grep/boundary
checks — constitution P2/P3), T082a (manual parse test — 003/SC-1).
