# Implementation Plan: Capacity Matching, Backhaul and Pooling

**Feature:** 002 — Capacity Matching, Backhaul and Pooling
**Plan version:** 1.0.0
**Created:** 2025-07-17
**Depends on:** Feature 001 (engine package, config loader, seed store, API skeleton)
**Status:** Ready for tasking

---

## Technical Context

| Dimension | Decision |
|---|---|
| Language | Python 3.11 (extends Feature 001 backend) |
| New engine modules | `backend/engine/matching.py`, `backend/engine/backhaul.py`, `backend/engine/pooling.py` |
| New API routers | `backend/api/routers/match.py`, `backend/api/routers/booking.py`, `backend/api/routers/backhaul.py` |
| New endpoints | `POST /match`, `POST /book`, `GET /backhaul/{booking_id}` |
| Pooling strategy | Greedy knapsack by value-per-tonne (descending) — no LP, no combinatorial search |
| State | In-memory store (from Feature 001); bookings + capacity mutations live in `live_state` |
| Distance | Haversine × road_factor (same helper as Feature 001) for proximity checks |
| Reset | `POST /demo/reset` (Feature 001) clears bookings and restores capacity_used_t to seed values |
| New frontend components | `RankedSailings`, `BookingConfirm`, `BackhaulPopup` |
| Testing | pytest unit tests (pure engine functions), contract tests (endpoints), seed-pinned scenario |

---

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| P1 — Shipment First | Matching ranks sailings for a water/hybrid plan already chosen; road is still available from Feature 001 | ✅ Matching never replaces the three-plan comparison |
| P2 — Deterministic Logic | Scoring, filtering, backhaul, pooling are pure deterministic functions; no LLM | ✅ All three engine modules are pure Python |
| P3 — Honest Data | Scoring weights, radii, safety margin in `data/config.yaml` with source_status | ✅ ConfigError on any missing key |
| P4 — Subsidy OFF | Subsidy is a Feature 001 concern; Feature 002 uses cost_inr from Feature 001 leg model | ✅ No new subsidy logic introduced |
| P5 — Test-first | Engine functions have pytest tests; seeded demo scenario is the canonical test | ✅ SC-3 is a pytest requirement |
| P7 — Human in Loop | `POST /book` requires `human_confirmed=true` in the request body; preview returned otherwise | ✅ Enforced in Pydantic model default |
| P8 — Offline | Proximity uses haversine (same as Feature 001); no live APIs | ✅ |
| P9 — Privacy | Seed data uses simulated cargo owners and operators | ✅ |
| P10 — Simplicity | Three new engine modules, three new routers; greedy only, no optimisation infrastructure | ✅ |

---

## Architecture delta (additions to Feature 001 layout)

```
backend/
├── engine/
│   ├── matching.py     # hard_filter() + match_score() → MatchResult list
│   ├── backhaul.py     # find_backhaul(booking, seed, config) → BackhaulSuggestion list
│   ├── pooling.py      # find_pooling(booking, seed, config) → PoolingSuggestion list
│   └── tests/
│       ├── test_matching.py
│       ├── test_backhaul.py
│       └── test_pooling.py
├── api/
│   └── routers/
│       ├── match.py    # POST /match
│       ├── booking.py  # POST /book
│       └── backhaul.py # GET /backhaul/{booking_id}
└── data_store.py       # extended: bookings list, capacity mutation, reset covers bookings

frontend/src/components/
├── RankedSailings.jsx   # ranked list + excluded accordion
├── BookingConfirm.jsx   # summary modal + explicit confirm button
└── BackhaulPopup.jsx    # backhaul + pooling suggestions panel
```

---

## Phase 0 — Research (resolved)

See `research.md` for full write-up. Summary:

| Research item | Decision |
|---|---|
| Proximity metric | Haversine km between node lat/lon (same helper as Feature 001); no road routing |
| Score normalisation | Per-factor raw score 0–1; weighted sum → 0–1 → ×100 integer. Factors are independent; no cross-factor normalisation. |
| Greedy knapsack for pooling | Sort open requests descending by `weight_t / total_cost_inr` (value-per-tonne); iterate, add if remaining capacity allows; stop when capacity exhausted |
| Backhaul proximity | Two separate radius checks: `origin_near_arrival` and `destination_near_departure`; both must pass |
| Booking id | `uuid4()` hex string, generated at confirmation time, stored in `live_state.bookings` |

---

## Phase 1 — Design

### Engine: `backend/engine/matching.py`

**Pure function signatures:**

```python
def hard_filter(
    sailing: Sailing,
    shipment: ShipmentInput,
    config: Config,
    seed: SeedData,
) -> FilterResult:
    """
    Returns FilterResult(passed=True) or FilterResult(passed=False, reason=<code>).
    Applies checks in order:
      1. capacity_exceeded  — sailing.capacity_available_t < shipment.weight_t
      2. draft_too_deep     — vessel.draft_m > edge_min_depth_m - config.draft_safety_margin_m
      3. route_not_permitted — neither origin nor dest jetty appears in sailing.route_nodes
      4. deadline_not_met   — (sailing.departure_h + transit_h + loading_h + unloading_h)
                               > (deadline_h - ready_h)
    """

def score_sailing(
    sailing: Sailing,
    shipment: ShipmentInput,
    config: Config,
    seed: SeedData,
) -> MatchResult:
    """
    Computes five sub-scores (each 0.0–1.0) and returns weighted sum × 100 as integer.
    Sub-scores:
      capacity_fit   = sailing.capacity_available_t / sailing.capacity_total_t
                       clamped 0–1; best = 1.0 (fully available)
      proximity      = max(0, 1 - haversine(vessel_pos, pickup_jetty) / config.proximity_max_km)
      schedule_slack = min(1, slack_h / config.slack_full_h)
      price          = max(0, 1 - water_cost / config.price_ref_inr)  [lower = better]
      reliability    = sailing.vessel.on_time_rate  (already 0–1)
    Each sub-score returns a human-readable reason string.
    """

def rank_sailings(
    shipment: ShipmentInput,
    config: Config,
    seed: SeedData,
) -> RankResult:
    """
    Applies hard_filter to every sailing.
    Passed → score_sailing → sort descending by score → ranked list.
    Failed → excluded list with reason.
    Returns RankResult(ranked, excluded).
    """
```

**Weight validation:** at module load, asserts
`sum([w_capacity_fit, w_proximity, w_schedule_slack, w_price, w_reliability]) == 1.0`
(with float tolerance `abs(sum - 1.0) < 1e-9`); raises `ConfigError` if not.

### Engine: `backend/engine/backhaul.py`

```python
def find_backhaul(
    booking: Booking,
    config: Config,
    seed: SeedData,
) -> list[BackhaulSuggestion]:
    """
    Scans open cargo requests (not in seed.bookings).
    For each candidate:
      1. origin_near_arrival:   haversine(candidate.origin, booking.arrival_jetty)
                                 <= config.backhaul_proximity_km
      2. destination_near_departure: haversine(candidate.dest, booking.departure_jetty)
                                 <= config.backhaul_proximity_km
      3. weight fits remaining capacity:
         remaining = booking.sailing.capacity_total_t
                     - booking.sailing.capacity_used_t   # after this booking
         candidate.weight_t <= remaining
      4. No hard-filter failure against the same vessel + sailing
    For each passing candidate, compute:
      backhaul_cost_inr = candidate.weight_t * config.water_freight_rate_per_t
      detour_km = 0  (return journey uses same route in reverse; no detour)
      price_effect_requester_inr = 0 - backhaul_cost_inr  (additional revenue for operator
                                    passed as negative cost change; UI shows as saving)
      price_effect_owner_inr     = backhaul_cost_inr (what the candidate owner would pay)
    Returns list sorted by weight_t descending (heaviest first).
    """
```

`arrival_jetty` = last node in `sailing.route_nodes`.
`departure_jetty` = first node in `sailing.route_nodes`.
Detour is always 0 for a standard return on the same route; the field is kept for
extensibility in future features.

### Engine: `backend/engine/pooling.py`

```python
def find_pooling(
    booking: Booking,
    config: Config,
    seed: SeedData,
) -> list[PoolingSuggestion]:
    """
    Greedy knapsack by value-per-tonne descending.

    Candidates: open cargo requests whose route overlaps the same sailing's route_nodes
                (at minimum: request.origin in route AND request.dest in route,
                 both appear after the current load's origin_jetty stop).

    Sort candidates by (weight_t / water_cost_inr) descending  [value-per-tonne proxy].

    Iterate:
      remaining = sailing.capacity_total_t - sailing.capacity_used_t
      for each candidate (sorted):
        if candidate.weight_t <= remaining:
          add to result
          remaining -= candidate.weight_t

    For each selected candidate compute:
      combined_weight = booking.weight_t + sum(selected so far).weight_t
      utilisation_pct = (sailing.capacity_used_t + combined_weight)
                        / sailing.capacity_total_t * 100
      cost_per_tonne_inr = (booking_water_cost + candidate_water_cost) / combined_weight

    Returns list in greedy selection order (highest value-per-tonne first).
    """
```

### API: `POST /match`

- **Input:** `MatchRequest` — same fields as `ShipmentRequest` (re-uses Pydantic model)
  plus `plan_mode: Literal["water", "hybrid"]`
- **Action:** calls `rank_sailings(shipment, config, seed)` — **read-only**, no state change
- **Output:** `MatchResponse` — `ranked: list[MatchResultOut]`, `excluded: list[ExcludedOut]`,
  `meta: MetaBlock`

### API: `POST /book`

- **Input:** `BookRequest` — `sailing_id`, `shipment` (ShipmentRequest fields), `human_confirmed: bool = False`
- **Guard:** if `human_confirmed is False` → return `BookPreviewResponse` (no state change)
- **Guard:** re-check capacity at confirmation time; if `capacity_available_t < weight_t`
  → HTTP 409 `"Insufficient capacity — please select another sailing."`
- **Action (confirmed only):**
  1. Generate `booking_id = uuid4().hex`
  2. Mutate `live_state`: increment `sailing.capacity_used_t` by `weight_t`
  3. Append `Booking` to `live_state.bookings`
  4. Call `find_backhaul(booking, config, seed)` and `find_pooling(booking, config, seed)`
- **Output:** `BookConfirmedResponse` — `booking_id`, `booking_summary`, `backhaul_suggestions`,
  `pooling_suggestions`, `meta`

### API: `GET /backhaul/{booking_id}`

- **Action:** looks up booking in `live_state.bookings`; re-runs `find_backhaul` +
  `find_pooling` against current state
- **Output:** same shape as the suggestions portion of `BookConfirmedResponse`
- **Error:** HTTP 404 if `booking_id` not found

### Frontend components

**`RankedSailings`**
- Props: `ranked: MatchResultOut[]`, `excluded: ExcludedOut[]`, `onSelect(sailing_id)`
- Renders a sorted list of `SailingCard` items (score badge with text label, sub-scores
  expandable, capacity bar, departure time IST, price estimate ₹)
- Below the ranked list: collapsible "Excluded sailings" accordion; each item shows
  exclusion reason as text badge with colour as secondary cue only

**`BookingConfirm`**
- Props: `sailing: MatchResultOut`, `shipment: ShipmentFormData`, `onConfirm()`, `onCancel()`
- Renders a modal/panel summary: vessel name, departure time, load, cost estimate
- Single "Confirm Booking" button; button disabled until user sees the summary (300 ms
  minimum display time enforced by `setTimeout` in component)
- Posts `POST /book` with `human_confirmed: true` only when button pressed
- On HTTP 409: shows inline error "Capacity filled — please choose another sailing"

**`BackhaulPopup`**
- Props: `backhaul: BackhaulSuggestion[]`, `pooling: PoolingSuggestion[]`, `booking_id`
- Appears automatically after a confirmed booking
- Each backhaul card: cargo id, weight (t), cost (₹ with assumed tag), detour (km)
- Each pooling card: cargo id, weight (t), utilisation (%), cost-per-tonne (₹/t with assumed tag)
- "Accept" and "Decline" buttons on each suggestion (accept/decline is UI-only in this
  prototype; no booking mutation for backhaul acceptance in Feature 002)

---

## Testing Plan

### Engine unit tests (`pytest`)

| Test | Module | Input | Expected |
|---|---|---|---|
| `test_rank_hero` | matching | Reference 10 t, 18:00 deadline | ≥1 ranked sailing with `sailing-001` |
| `test_hard_filter_draft` | matching | Vessel draft > route depth − margin | `excluded` contains reason `draft_too_deep` |
| `test_hard_filter_capacity` | matching | Shipment weight > all vessels | All excluded `capacity_exceeded`, ranked empty |
| `test_hard_filter_deadline` | matching | Deadline before soonest arrival | All excluded `deadline_not_met` |
| `test_weight_sum_1` | matching | Weights from config | `abs(sum - 1.0) < 1e-9` |
| `test_backhaul_seeded` | backhaul | Hero booking confirmed | Exactly 1 suggestion: 7 t, Alappuzha→Kochi |
| `test_backhaul_none` | backhaul | Booking with no open return cargo | Empty list, no exception |
| `test_pooling_seeded` | pooling | Hero booking confirmed | Exactly 2 suggestions |
| `test_pooling_greedy_order` | pooling | 3 candidates, 2 fit | Highest value-per-tonne selected first |
| `test_pooling_none` | pooling | No open cargo on same route | Empty list, no exception |

### Contract tests (`httpx`, `pytest`)

| Test | Endpoint | Assertion |
|---|---|---|
| `test_match_200` | `POST /match` | HTTP 200, response schema valid |
| `test_match_hero` | `POST /match` | `ranked` non-empty, `sailing-001` present |
| `test_book_preview` | `POST /book` `human_confirmed=false` | HTTP 200, no `booking_id` in response |
| `test_book_confirmed` | `POST /book` `human_confirmed=true` | HTTP 200, `booking_id` present, backhaul + pooling lists returned |
| `test_book_409` | `POST /book` on over-capacity sailing | HTTP 409, error message |
| `test_backhaul_get` | `GET /backhaul/{booking_id}` | HTTP 200, lists match post-booking response |
| `test_backhaul_404` | `GET /backhaul/unknown` | HTTP 404 |
| `test_reset_clears_booking` | `POST /demo/reset` after booking | Capacity restored; `GET /backhaul/{id}` → HTTP 404 |

### Manual checks

1. Post-booking: `BackhaulPopup` appears immediately with 1 backhaul and 2 pooling cards.
2. All monetary figures on pooling/backhaul cards show `[assumed]` badge text.
3. `BookingConfirm` "Confirm" button only submits on explicit click (not auto-submitted).
4. After reset: repeat booking flow from scratch — same results as first run.

---

## Deliverables checklist

- [x] `plan.md` — this file
- [ ] `research.md`
- [ ] `data-model.md`
- [ ] `contracts/openapi.yaml`
- [ ] `quickstart.md`
- [ ] Engine modules with passing pytest
- [ ] API routers with contract tests
- [ ] Frontend components
