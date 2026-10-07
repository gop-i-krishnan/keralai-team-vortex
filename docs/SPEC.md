# JalSetu — what runs (status specification)

*Written 7 Oct 2026 from the code and test run in this repository. Every claim below was checked
against the running system or the test suite; anything not demonstrable is marked ROADMAP.*

JalSetu is a prototype shipment decision and orchestration engine for Kerala inland waterways. It
compares road and hybrid (road + water) door-to-door plans for a shipment, recommends one with a
plain-English reason, matches the shipment to vessel sailings, and lets a person confirm bookings,
handle simulated disruptions, and register vessels and warehouses. Governing rules are in
`.specify/memory/constitution.md` (v1.1.0); per-feature specs are in `specs/`.

## 1. Status legend

| Label | Meaning |
|---|---|
| **BUILT AND TESTED** | Implemented and covered by automated pytest tests that pass today |
| **BUILT, MOCKED** | Implemented and runs, but the data, actor or integration is simulated; labelled `[simulated]` in the UI |
| **ROADMAP** | Not built, or code exists but has never been run. Do not treat as a capability |

Note on the UI: where a row says BUILT AND TESTED, the backend behaviour is covered by pytest. The React
UI on top has **no automated tests**; its evidence is the screenshots in `docs/screenshots/`, captured
from the running app by `docs/screenshots/capture.py`.

## 2. Feature status

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Road vs hybrid comparison, recommendation with a reason, subsidy what-if (OFF by default) | **BUILT AND TESTED** | `test_options.py` (13), `test_api.py`; screenshots 01, 02 | 10 t Kochi→Alappuzha: 10 h deadline → hybrid, 3 h → road. Hybrid cost is port-to-port only |
| Sailing matching: capacity, ranking, excluded vessels listed with reasons | **BUILT AND TESTED** | `test_matching.py` (15), `test_hazards.py` (10); screenshot 04 | Schedule part of the score is a fixed neutral 0.5 |
| Backhaul and pooling opportunities (counts shown after booking) | **BUILT AND TESTED** | `test_matching.py` | Shown as counts only |
| Booking with explicit two-step human confirmation | **BUILT AND TESTED** | `test_api.py`, `test_compliance_api.py` | `human_confirmed` in the request body is ignored |
| Free-text intake (`/api/parse`, `/api/operator/message`) with offline parser | **BUILT AND TESTED** | `test_parser.py` (11), `test_api.py` | Regex / mock adapter. Low confidence (< 0.8) asks a person to review |
| Live IBM watsonx.ai Granite parsing | **ROADMAP** | — | `backend/api/llm/watsonx.py` exists but was never run; `ibm-watsonx-ai` is not installed |
| Simulated WhatsApp-style chat | **BUILT, MOCKED** | `WhatsAppChat.jsx` | No WhatsApp integration; uses the offline parser |
| Corridor viability (break-even distance) | **BUILT AND TESTED** | `test_viability.py` (5); screenshot 12 | Planner tab. Demand is summed from simulated seed cargo and tagged `[simulated]` |
| Demo reset to seed state | **BUILT AND TESTED** | reset fixtures in all API tests | Measured: median 7 ms, worst 310 ms over 20 resets (in-process) |
| Vessel registration by form, per-field validation, duplicate guard | **BUILT AND TESTED** | `test_registry.py` (34), `test_vessel_api.py` (26); screenshot 08 | Registration number is a placeholder, not validated |
| Vessel registration from a pasted message | **BUILT AND TESTED** | `test_parser.py`, `test_vessel_api.py`; screenshot 08 | Regex only, English only. Needs an explicit Register click |
| Recurring sailing publication | **BUILT AND TESTED** | `test_vessel_api.py` | Only first and last stop used for matching; weekdays stored but not used by the engine |
| Vessel verification, suspension, reinstatement | **BUILT, MOCKED** | `test_vessel_api.py` | Demo-admin buttons, no identity check, no authentication. Suspension never alters confirmed bookings |
| Bayesian reliability from delivery history (always shown with trip count) | **BUILT AND TESTED** | `test_history.py` (11), `test_vessel_api.py`; screenshot 09 | Affects ranking only through the unverified-vessel penalty |
| Delivery history data | **BUILT, MOCKED** | `data/seed.json` | 31 simulated records; records created at runtime are tagged `recorded` |
| Milestone timeline and advance | **BUILT, MOCKED** | `test_tracking.py` (14), `test_replan_api.py`; screenshot 05 | Demo control. No live tracking or GPS |
| Disruption trigger (5 types) and severity | **BUILT, MOCKED** | `test_replan_api.py`; screenshot 05 | Demo control labelled "simulated" |
| Re-plan: ranked alternatives, deadline fallback, no auto-switch | **BUILT AND TESTED** | `test_replan.py` (31), `test_replan_api.py` (25); screenshots 05, 06 | Booking unchanged until explicit confirm; cost basis treats earlier payments as sunk |
| Notification preview | **BUILT, MOCKED** | `test_replan.py`, `test_replan_api.py`; screenshot 05 | Template text only. Nothing is sent, `delivered` is always false |
| Disruption summary (by type and corridor) | **BUILT AND TESTED** | `test_replan_api.py`; screenshot 07 | Simulated counts for this session |
| Cargo classes and hazard hard filter (named exclusion reasons) | **BUILT AND TESTED** | `test_hazards.py`, `test_matching.py`; screenshots 03, 04 | Rules are all `assumed` placeholders, not regulations |
| Compliance-review gate (bookings and re-plans of hazardous cargo) | **BUILT, MOCKED** | `test_compliance_api.py` (6), `test_replan_api.py`; screenshots 03 | Gate logic is tested; the reviewer is a demo button |
| Warehouse registry and utilisation | **BUILT AND TESTED** | `test_warehouse.py` (13), `test_warehouse_api.py` (19); screenshot 10 | Warehouse data is simulated |
| Warehouse staging plan, confirm, attach to a booking | **BUILT AND TESTED** | `test_warehouse_api.py`; screenshot 11 | Recorded on the booking; does not change its plan time |
| Perishable-cargo scoring adjustments | **BUILT AND TESTED** | `test_options.py` | No dedicated UI; visible only as a note on staging plans |
| Four-role UI: Shipper, Boat owner, Warehouse, Planner | **BUILT, MOCKED** | screenshots 01–11 | No automated UI tests; many panels show simulated data |
| Documentation tables kept in sync with `data/config.yaml` and `data/seed.json` | **BUILT AND TESTED** | `test_docs_sync.py` (4) | Fails if section 5 below is stale |
| Live GPS / vessel tracking | **ROADMAP** | — | Out of scope (constitution P10) |
| Payments, invoicing | **ROADMAP** | — | Out of scope (P10) |
| Authentication and roles (admin, compliance reviewer) | **ROADMAP** | — | Demo controls are unauthenticated |
| Real WhatsApp / SMS / email notifications | **ROADMAP** | — | Previews only |
| Real vessel-registry verification, real hazard regulations | **ROADMAP** | — | Verify with IWAI / PESO / state authority |
| Road routing API, map tiles, real waterway chart distances | **ROADMAP** | — | Straight-line × factor is used |
| Malayalam message parsing | **ROADMAP** | — | Regex parser handles English only |
| Persistent database | **ROADMAP** | — | State is in memory; lost on restart |

## 3. Test evidence

Command: `python -m pytest backend/ -q` → **261 passed** (7 Oct 2026, Python 3.14.5, pytest 9.1.1).
The 100 tests present before Features 004–006 were added are all still there; one assertion in them was changed (see below).

| Test file | Tests |
|---|---|
| `backend/engine/tests/test_options.py` | 13 |
| `backend/engine/tests/test_matching.py` | 15 |
| `backend/engine/tests/test_hazards.py` | 10 |
| `backend/engine/tests/test_warehouse.py` | 13 |
| `backend/engine/tests/test_history.py` | 11 |
| `backend/engine/tests/test_registry.py` | 34 |
| `backend/engine/tests/test_replan.py` | 31 |
| `backend/engine/tests/test_tracking.py` | 14 |
| `backend/engine/tests/test_parser.py` | 11 |
| `backend/engine/tests/test_reliability.py` | 7 |
| `backend/engine/tests/test_viability.py` | 5 |
| `backend/engine/tests/test_docs_sync.py` | 4 |
| `backend/api/tests/test_api.py` | 17 |
| `backend/api/tests/test_vessel_api.py` | 26 |
| `backend/api/tests/test_replan_api.py` | 25 |
| `backend/api/tests/test_warehouse_api.py` | 19 |
| `backend/api/tests/test_compliance_api.py` | 6 |
| **Total** | **261** |

Additional checks run for this document:

| Check | Result |
|---|---|
| Suite run with every non-loopback socket connect and DNS lookup blocked | 261 passed (`JALSETU_MOCK_LLM=1`, in-process client; real network was not available to the tests) |
| `grep` for LLM / adapter imports in `backend/engine/` | 0 matches (engine has no LLM calls) |
| `grep` for `uuid`, `random`, `datetime` in `backend/engine/` | 0 matches (engine is deterministic) |
| Every `config.yaml` entry tagged `sourced` or `assumed` with a note | enforced by `test_docs_sync.py` |
| Frontend `npm run build` | succeeds; `oxlint` reports 10 warnings, 0 errors |
| README demo script (post cargo, match, book, confirm, disrupt, alternatives, confirm re-plan, reset) driven in headless Chrome | every step succeeded |

One existing test was modified: `test_staging_plan_has_proposal_id` asserted a UUID-format id, which made the
engine non-deterministic; it now asserts a non-empty deterministic id.

## 4. Screenshots (real, from the running app)

Captured 7 Oct 2026 by `docs/screenshots/capture.py` against the backend on :8000 and the Vite dev server on :5173.

| # | File | Shows |
|---|---|---|
| 1 | `docs/screenshots/01-hero-deadline-10h-hybrid.png` | Landing screen: 10 h deadline → HYBRID |
| 2 | `docs/screenshots/02-hero-deadline-3h-road.png` | Same screen, slider at 3 h → ROAD |
| 3 | `docs/screenshots/03-post-cargo-flammable-compliance-banner.png` | Hazard class selector and compliance banner |
| 4 | `docs/screenshots/04-matches-excluded-vessels-with-reasons.png` | Flammable cargo: no certified vessels, exclusions with reasons |
| 5 | `docs/screenshots/05-shipment-disruption-ranked-alternatives.png` | Timeline, disruption, notification preview, ranked alternatives |
| 6 | `docs/screenshots/06-replan-confirm-dialog.png` | Explicit "Confirm re-plan" step |
| 7 | `docs/screenshots/07-planner-disruption-summary-simulated.png` | Planner: disruption summary |
| 8 | `docs/screenshots/08-owner-register-from-message.png` | Vessel registration from a pasted message |
| 9 | `docs/screenshots/09-owner-history-trips-simulated.png` | History with "NN% — N trips [simulated]" |
| 10 | `docs/screenshots/10-warehouse-utilisation-simulated.png` | Warehouse utilisation |
| 11 | `docs/screenshots/11-staging-plan-itemised.png` | Itemised staging plan |
| 12 | `docs/screenshots/12-planner-corridor-viability.png` | Planner: corridor viability with tags |

## 5. Data honesty: sourced, assumed, simulated

Rules: every constant lives in `data/config.yaml` tagged `sourced` or `assumed` with a note;
`simulated` is used only for fictional records in `data/seed.json`. The two tables below are
**generated** by `python docs/sync_tables.py` and checked by `test_docs_sync.py`.

Only four values are `sourced`: the IST offset (UTC+05:30), the road and water CO₂ factors (cited to IPCC
AR6 WG3 Table 10.1) and the IBM model id. **The team has not re-checked the two CO₂ values against the
IPCC table**; treat them as unverified until someone does. Everything else, including every rate, speed,
weight, hazard rule and threshold, is an assumption to be verified with the relevant authority.

### 5.1 `data/config.yaml`

<!-- CONFIG-TABLE:START -->
Config entries: **67** total — 63 assumed, 4 sourced.

| Key | Value | Status | Note |
|---|---|---|---|
| `meta.ist_offset_min` | 330 | sourced | India Standard Time is UTC+05:30 (330 minutes). Fixed offset; no tz database needed. |
| `road.rate_per_t_km` | 10.2 | assumed | Kerala door-to-door road freight ~Rs 9,000 for 10t over ~88km Kochi–Alappuzha (Rs 10.2/t·km). No primary tariff survey. |
| `road.avg_speed_kmh` | 40.0 | assumed | NH/SH average including town congestion for Kerala corridors. |
| `road.co2_kg_per_t_km` | 0.062 | sourced | IPCC AR6 WG3 Table 10.1 median for road freight (diesel HGV), 2022. |
| `road.road_factor` | 1.3 | assumed | Straight-line to road-distance multiplier. NH66 Kochi–Alappuzha is approximately 55–62 km; 1.3× on 48.8 km crow-fly gives ~63 km. Previous value of 1.8 (→88 km) overstated road distance by ~38%. Verify against NH66 mileage before production use. |
| `water.tortuosity_factor` | 1.05 | assumed | Water-route distance = straight-line × 1.05; NW-3 is relatively straight. Verify with IWAI charts. |
| `water.speed_kmh` | 12.0 | assumed | Typical Kerala inland vessel cruising speed on National Waterway 3. |
| `water.loading_cost_per_t` | 80.0 | assumed | Jetty loading charge estimate; no published tariff found for minor jetties. |
| `water.unloading_cost_per_t` | 80.0 | assumed | Jetty unloading charge estimate; same assumption as loading. |
| `water.water_freight_rate_per_t` | 420.0 | assumed | Estimated inland water freight Rs 420/t for ~80 km Kochi–Alappuzha corridor. |
| `water.co2_kg_per_t_km` | 0.019 | sourced | IPCC AR6 WG3 Table 10.1 median for inland waterway freight, 2022. |
| `water.min_viable_weight_t` | 2.0 | assumed | Minimum commercial shipment weight for inland vessel operations. |
| `water.subsidy_fraction` | 0.2 | assumed | Hypothetical 20% subsidy on water-leg freight; no confirmed Kerala scheme for short routes. |
| `reliability.road_base_score` | 0.85 | assumed | Road reliability score; accounts for traffic variability on Kerala roads. |
| `reliability.water_base_score` | 0.78 | assumed | Water reliability score; lower due to tidal/seasonal factors on NW-3. |
| `reliability.monsoon_penalty` | 0.1 | assumed | Reliability reduction for water mode during June–September monsoon months. |
| `reliability.night_sailing_penalty` | 0.05 | assumed | Small reliability reduction for sailings departing after 20:00 IST. |
| `scoring.weights.cost` | 0.4 | assumed | Scoring weight for cost. Team choice; the four weights sum to 1.0. |
| `scoring.weights.time` | 0.35 | assumed | Scoring weight for time. Team choice. |
| `scoring.weights.co2` | 0.15 | assumed | Scoring weight for CO2. Team choice. |
| `scoring.weights.reliability` | 0.1 | assumed | Scoring weight for reliability. Team choice; perishable cargo overrides this (perishable.reliability_weight_override). |
| `scoring.deadline_buffer_h` | 0.5 | assumed | Safety buffer subtracted from deadline before checking time feasibility. |
| `matching.score_weight_utilisation` | 0.5 | assumed | Weight given to capacity utilisation in sailing rank score. |
| `matching.score_weight_schedule` | 0.5 | assumed | Weight given to schedule proximity in sailing rank score (currently a neutral 0.5 placeholder; improve when schedule data is richer). |
| `matching.fuzzy_match_cutoff` | 70 | assumed | RapidFuzz WRatio threshold for node name fuzzy matching (0–100). |
| `matching.proximity_radius_km` | 5.0 | assumed | Max crow-fly distance between a cargo origin and a vessel jetty to be considered nearby. |
| `matching.max_pool_weight_fraction` | 0.3 | assumed | Max fraction of vessel capacity that any single pooled cargo may occupy. |
| `viability.min_demand_t_per_month` | 50.0 | assumed | Minimum monthly tonnage for a corridor to be considered commercially viable. |
| `llm.confidence_threshold` | 0.8 | assumed | Parse confidence below this value triggers human review prompt. Set to 0.8 to match constitution P7 (was 0.75). |
| `llm.model_id` | ibm/granite-13b-chat-v2 | sourced | IBM watsonx.ai Granite chat model; used only when JALSETU_MOCK_LLM=0. |
| `demo.reference_weight_t` | 10 | assumed | Reference demo shipment weight (hero scenario). |
| `demo.reference_origin` | Kochi Thevara Jetty | assumed | Reference demo origin; illustrative terminal name. |
| `demo.reference_destination` | Alappuzha Boat Jetty | assumed | Reference demo destination; illustrative terminal name. |
| `demo.deadline_hybrid_h` | 10 | assumed | Hero scenario deadline at which hybrid is recommended; also the default booking deadline. |
| `demo.deadline_road_h` | 3 | assumed | Hero scenario deadline at which road is recommended. |
| `hazard_rules.general` | modes=['road', 'water'], cert_required=False, review_required=False | assumed | Standard general cargo; no special cert required. verify with IWAI / PESO / state authority before production use. |
| `hazard_rules.perishable` | modes=['road', 'water'], cert_required=False, review_required=False | assumed | Perishable goods (fresh produce, chilled); no hazmat cert required but time-sensitive. verify with IWAI / PESO / state authority before production use. |
| `hazard_rules.liquid_bulk` | modes=['road', 'water'], cert_required=True, review_required=False | assumed | Liquid bulk (edible oils, chemicals); vessel must carry liquid_bulk cert. verify with IWAI / PESO / state authority before production use. |
| `hazard_rules.flammable` | modes=['road', 'water'], cert_required=True, review_required=True | assumed | Flammable liquids and solids; vessel must be certified; compliance review required. verify with IWAI / PESO / state authority before production use. |
| `hazard_rules.explosive` | modes=[], cert_required=True, review_required=True | assumed | Explosives; no mode offered by default — special permit required. verify with IWAI / PESO / state authority before production use. |
| `hazard_rules.toxic_corrosive` | modes=[], cert_required=True, review_required=True | assumed | Toxic or corrosive substances; no mode offered by default — special permit required. verify with IWAI / PESO / state authority before production use. |
| `hazard_rules.oversized` | modes=['road', 'water'], cert_required=False, review_required=False | assumed | Oversized or out-of-gauge cargo; no hazmat cert required; route may need special clearance not modelled here. verify with IWAI / PESO / state authority before production use. |
| `perishable.schedule_buffer_h` | 1.0 | assumed | Tighter schedule buffer for perishable cargo (standard is 0.5 h). Assumed; verify with cold-chain logistics standards. |
| `perishable.reliability_weight_override` | 0.25 | assumed | Elevated reliability weight for perishable cargo scoring (standard is 0.10). Must be > scoring.weights.reliability. Assumed; verify with supply-chain experts. |
| `warehouse.proximity_radius_km` | 10.0 | assumed | Maximum Haversine distance from cargo origin node to warehouse location node for staging eligibility. Assumed default. |
| `warehouse.staging_wait_threshold_h` | 4.0 | assumed | Minimum sailing wait before a staging plan is offered (FR-8). Below this threshold, staging is not worth the extra handling cost. Assumed default. |
| `history.prior_trip_count` | 5 | assumed | Bayesian prior weight k: a new vessel is treated as having 5 virtual trips. Chosen so one late trip does not dominate early history. Assumed. |
| `history.prior_on_time_rate` | 0.8 | assumed | Prior on-time rate for vessels with little or no history (P14). Assumed; replace with corridor data when available. |
| `history.midnight_wrap_h` | 12 | assumed | If actual arrival is earlier than planned by more than this many hours, it is treated as next-day arrival (HH:MM strings carry no date). |
| `registry.unverified_reliability_penalty` | 0.1 | assumed | Subtracted from the match score of pending_verification vessels. Assumed; verified vessels are unaffected. |
| `vessel_parse.weight_capacity` | 0.35 | assumed | Structural confidence contribution when capacity is found in an operator message. Not a model score. |
| `vessel_parse.weight_type` | 0.15 | assumed | Contribution when a vessel type keyword is found. |
| `vessel_parse.weight_home` | 0.3 | assumed | Contribution when a home jetty phrase is found. |
| `vessel_parse.weight_route` | 0.1 | assumed | Contribution when a route hint is found. |
| `tracking.loading_lead_h` | 0.5 | assumed | Loading starts this many hours before sailing departure. Simulated milestone timing; no live tracking. |
| `tracking.unloading_h` | 0.5 | assumed | Unloading time between Arrived and Delivered milestones. |
| `replan.severity_minor_max_h` | 2 | assumed | Expected disruption below this many hours is 'minor'. |
| `replan.severity_moderate_max_h` | 6 | assumed | Up to this many hours is 'moderate'; above is 'severe'. Unknown duration or a missed deadline is also 'severe'. |
| `replan.wait_cost_per_t_h` | 20 | assumed | Rs per tonne per hour of waiting for the original plan to resume. Verify with operators. |
| `replan.road_blocked_delay_h` | 2 | assumed | Extra hours added to road alternatives that start at a node where the road is blocked. |
| `replan.weather_reliability_penalty` | 0.1 | assumed | Reliability reduction applied to water-mode alternatives under a weather delay. |
| `replan.max_alternatives` | 5 | assumed | Maximum number of ranked alternatives returned. |
| `notifications.vessel_breakdown` | message template (English) | assumed | Template text is an assumption; message preview only, never sent. |
| `notifications.low_depth` | message template (English) | assumed | Template text is an assumption; message preview only, never sent. |
| `notifications.jetty_closed` | message template (English) | assumed | Template text is an assumption; message preview only, never sent. |
| `notifications.road_blocked` | message template (English) | assumed | Template text is an assumption; message preview only, never sent. |
| `notifications.weather_delay` | message template (English) | assumed | Template text is an assumption; message preview only, never sent. |
<!-- CONFIG-TABLE:END -->

### 5.2 `data/seed.json`

<!-- SEED-TABLE:START -->
| Seed collection | Records | source_status |
|---|---|---|
| `nodes` | 4 | 4 assumed |
| `vessels` | 7 | 7 simulated |
| `operators` | 2 | 2 simulated |
| `sailings` | 2 | 2 simulated |
| `corridors` | 2 | 2 assumed |
| `cargo` | 7 | 7 simulated |
| `shippers` | 4 | 4 simulated |
| `warehouses` | 2 | 2 simulated |
| `delivery_history` | 31 | 31 simulated |
| `disruption_scenarios` | 2 | 2 simulated |
<!-- SEED-TABLE:END -->

All shipper, operator, vessel, contact and registration data is fictional (contacts use `simulated@…example`).
Jetty names and coordinates are illustrative and approximate and must be verified with IWAI or the Kerala
State Water Transport Department. The Vaikom node is an approximate placement on the Kochi–Alappuzha route.

## 6. Limitations

**Prototype scope**
- State is in memory in one process: restarting or resetting loses everything; not safe for concurrent users.
- No authentication. Admin verify/suspend, compliance-review, milestone-advance and disruption endpoints are
  open demo controls.
- No live GPS, payments, real messaging, database, or vessel-registry check. These are labelled `[simulated]`
  wherever shown.

**Modelling**
- Road distance is straight-line × a factor; water distance is straight-line × a tortuosity factor. Neither is a
  routed or charted distance. Only four nodes exist.
- The hybrid plan's cost and CO₂ are port-to-port: first- and last-mile truck legs are not included.
- The monsoon reliability penalty exists in the engine but is never switched on by the API.
- Sailing weekdays are stored but the options engine assumes a daily sailing. Times are HH:MM strings with no dates.
- The schedule component of the match score is a fixed neutral value (0.5). Reliability statistics affect
  ranking only through the unverified-vessel penalty.
- Matching uses only the first and last stop of a route; intermediate stops are display-only.
- Hazard rules are placeholders. `explosive` and `toxic_corrosive` offer no transport mode by default.
  The system gives eligibility guidance only and never handling or safety instructions.

**Disruptions and re-planning**
- Position is a node, not a coordinate; "In Transit" is the last waterway node. The demo clock uses the planned
  time of the current milestone, so results are deterministic rather than real-time.
- Alternatives treat earlier payments as sunk. Re-plans and staging do not change sailing capacity, and staging
  does not change a booking's plan time. Alternatives that meet the deadline are ranked ahead of better-scoring
  ones that miss it.
- With the seed data the hero disruption yields three alternatives (wait, truck, return to origin). "Alternative
  vessel" and "hold at warehouse" appear only when a suitable sailing or warehouse exists; they are covered by
  tests, not by the screenshots.

**Parsing and AI**
- The demo never calls an LLM. The IBM watsonx.ai adapter has never been run in this repository.
- The message parsers are regex-based, English-only and brittle outside the demo phrasing.

**Quality**
- No automated UI tests; the UI was checked only in headless Chrome at 1280 px. No mobile or contrast audit.
- `oxlint` reports 10 warnings.
- Wherever a number is displayed it carries a text badge, but badge placement was reviewed by eye only.

## 7. Roadmap (not built)

Live positions from vessels; real notifications; vessel-registry integration; verified hazard regulations
from IWAI / PESO / state authorities; routed road and chart-based waterway distances; Malayalam intake;
persistent storage; authentication; UI test suite.

## 8. Disclosures

AI tools, LLM provider, specification tooling and every library are listed in `docs/disclosures.md`
and `ATTRIBUTIONS.md`.
