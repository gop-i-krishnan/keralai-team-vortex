# Research: Capacity Matching, Backhaul and Pooling

**Feature:** 002 — Capacity Matching, Backhaul and Pooling
**Created:** 2025-07-17

Resolves four research items identified in the plan. All items have decisions and rationale.

---

## R-1: Proximity Metric for Vessel Position and Backhaul Matching

### Decision

Use the same haversine helper introduced in Feature 001 (`engine/options.py`). No
additional dependency or routing API is required.

```python
# Reuse from Feature 001:
from engine.options import haversine_km

# Vessel's current position ≈ departure jetty of its next scheduled sailing
vessel_pos_node = seed.nodes[sailing.route_nodes[0]]

proximity_km = haversine_km(
    vessel_pos_node.lat, vessel_pos_node.lon,
    pickup_jetty.lat,    pickup_jetty.lon,
)
```

The proximity sub-score for matching:
```python
proximity_score = max(0.0, 1.0 - proximity_km / config.proximity_max_km)
# proximity_max_km: configured threshold beyond which score = 0 (default 50 km, assumed)
```

Backhaul proximity uses the same function with a separate radius:
```python
origin_near = haversine_km(candidate_origin, arrival_jetty) <= config.backhaul_proximity_km
dest_near   = haversine_km(candidate_dest,   departure_jetty) <= config.backhaul_proximity_km
```

Both conditions must be true for a backhaul candidate to qualify.

### Rationale

- Reuses proven code — no new dependency, no new test surface.
- Great-circle distance is a conservative lower bound; using it as a proximity filter
  means candidates that pass are genuinely close, not over-estimated.
- `proximity_max_km` and `backhaul_proximity_km` in config allow the team to tune the
  demo without a code change.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Road routing API (OSRM) for proximity | Violates offline constraint (Constitution P8); out of scope per spec |
| Fixed 10 km hard cutoff in code | Violates Constitution P3 (no constants in code) |
| Using seed edge distance for proximity | Edges only exist for pre-defined pairs; new node combos would break |

---

## R-2: Per-Factor Score Normalisation

### Decision

Each of the five scoring factors produces an **independent raw score** in [0.0, 1.0].
These are combined with a weighted sum — **no cross-factor min-max normalisation**.
This differs from Feature 001's objective normalisation (which normalises across plans).
Here each factor has a natural scale that makes it self-contained:

| Factor | Raw score formula | Scale anchor |
|---|---|---|
| `capacity_fit` | `available_t / total_t` | 1.0 = fully empty vessel |
| `proximity` | `max(0, 1 - km / proximity_max_km)` | 1.0 = vessel already at jetty |
| `schedule_slack` | `min(1, slack_h / slack_full_h)` | 1.0 = deadline slack ≥ `slack_full_h` |
| `price` | `max(0, 1 - water_cost / price_ref_inr)` | 1.0 = free; 0 = at or above reference price |
| `reliability` | `vessel.on_time_rate` | 1.0 = perfect on-time history |

`price_ref_inr` (the cost at which price score hits 0) and `slack_full_h` (the slack that
yields a full score) are both in `data/config.yaml` with `source_status: assumed`.

Final: `score = round((Σ weight_i × raw_i) × 100)` — integer 0–100.

### Rationale

- Independent normalisation means adding or removing a sailing does not change the scores
  of existing sailings — the ranking is stable and testable against seed data.
- Cross-factor min-max (as in Feature 001's objectives) would mean a single very cheap
  sailing could distort the price sub-score of all others — undesirable for matching.
- The formula is deterministic over fixed config values, satisfying Constitution P2.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Min-max across sailings (like Feature 001 objectives) | Rankings shift when new sailings added to seed; unstable for seeded demo test |
| Rank scoring (1st = 1.0, 2nd = 0.5 …) | Non-linear; magnitude lost; two 95-score sailings become 1.0 / 0.5 |

---

## R-3: Greedy Knapsack Algorithm for Pooling

### Decision

Sort candidate open cargo requests by **value-per-tonne** descending, then iterate once
adding items while remaining capacity allows. This is the classic greedy fractional
knapsack applied to integer items.

**Value-per-tonne** proxy = `weight_t / water_cost_inr` for the candidate.
This favours heavier, cheaper cargoes that fill the vessel efficiently.

```python
def find_pooling(booking, config, seed):
    remaining = sailing.capacity_total_t - sailing.capacity_used_t  # post-booking
    candidates = [r for r in seed.cargo_requests
                  if r.id != booking.shipment_id
                  and r.id not in live_bookings
                  and r.origin_node in sailing.route_nodes
                  and r.dest_node   in sailing.route_nodes]

    # Sort: highest weight/cost first (most weight per rupee → fills vessel best)
    candidates.sort(key=lambda r: r.weight_t / water_cost(r, config), reverse=True)

    result, cumulative_weight = [], 0.0
    for c in candidates:
        if c.weight_t <= remaining:
            cumulative_weight += c.weight_t
            remaining -= c.weight_t
            combined = booking.weight_t + cumulative_weight
            utilisation_pct = (sailing.capacity_used_t + combined) / sailing.capacity_total_t * 100
            cost_per_tonne  = (booking_cost + water_cost(c, config)) / combined
            result.append(PoolingSuggestion(
                cargo_request_id=c.id,
                weight_t=c.weight_t,
                utilisation_pct=round(utilisation_pct, 1),
                cost_per_tonne_inr=round(cost_per_tonne, 2),
                source_status="assumed",
            ))
    return result
```

The seed data is crafted so that exactly two requests qualify and both fit; this pins
the demo output deterministically.

### Rationale

- Greedy knapsack is O(n log n) — fast enough for demo-scale data (< 20 requests).
- It is deterministic over a fixed sorted input, making the seeded demo test reliable.
- The spec explicitly out-scopes combinatorial optimisation (FR spec: "greedy only").
- Value-per-tonne sorts by utilisation efficiency, matching the real-world priority of
  filling remaining capacity with the most weight.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Optimal 0/1 knapsack (DP) | O(n × W) complexity; overkill for prototype; out of scope per spec |
| Sort by weight descending | Ignores cost; could select expensive small cargoes over cheap heavy ones |
| Sort by cost ascending | Favours cheap cargo regardless of fill; utilisation metric would suffer |

---

## R-4: Booking ID Generation and State Mutation

### Decision

Booking IDs are `uuid.uuid4().hex` (32-character lowercase hex string) generated at
confirmation time. They are stored in `live_state.bookings` as a dict keyed by
`booking_id`. This allows O(1) lookup for `GET /backhaul/{booking_id}`.

```python
import uuid

booking_id = uuid.uuid4().hex   # e.g. "a3f1c2d4e5b6..."

live_state.bookings[booking_id] = Booking(
    id=booking_id,
    shipment_id=request.shipment_id,
    sailing_id=request.sailing_id,
    weight_t=request.weight_t,
    confirmed=True,
    created_at=datetime.now(tz=IST).isoformat(),
)
live_state.sailings[request.sailing_id].capacity_used_t += request.weight_t
```

`POST /demo/reset` clears `live_state.bookings = {}` and restores all
`capacity_used_t` to the values in `seed_snapshot`.

### Rationale

- UUID hex strings are unique enough for a single-process in-memory prototype.
- Dict keyed by id gives fast lookup without a database.
- The reset procedure is explicit and testable: a booking that existed before reset must
  return HTTP 404 after reset.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Sequential integer ids ("B001") | Not unique if demo is run multiple times without reset |
| Full UUID with dashes | Functionally identical; hex is shorter in URLs |
| Storing bookings in a list | O(n) lookup; dict is simpler and faster |
