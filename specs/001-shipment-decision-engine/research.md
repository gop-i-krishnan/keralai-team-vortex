# Research: Shipment Decision Engine

**Feature:** 001 — Shipment Decision Engine
**Created:** 2025-07-17

This document resolves the three research items identified in the plan and records the
decisions made, rationale, and alternatives evaluated.

---

## R-1: Haversine + Road Factor Distance

### Decision

Use the standard haversine formula (great-circle distance in km) implemented in pure
Python with no external dependencies, multiplied by a configurable `road_factor` constant
(default `1.3`, `source_status: assumed`) stored in `data/config.yaml`.

```python
import math

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Earth radius, km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def road_distance_km(lat1, lon1, lat2, lon2, road_factor: float) -> float:
    return haversine_km(lat1, lon1, lat2, lon2) * road_factor
```

Water-edge distances are stored explicitly in `data/seed.json` as
`distance_km` on each edge; haversine is not used for water legs.

### Rationale

- Pure Python, zero dependencies, no network call → satisfies offline requirement.
- Haversine is accurate to < 0.5% for distances up to ~1000 km; Kerala spans ~600 km —
  well within the acceptable range for prototype estimates.
- Road factor of 1.3 is a common Kerala-terrain assumption; tagging it `assumed` makes
  its status clear.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| OSRM / Google Maps routing | Requires live API; violates offline constraint (Constitution P8) |
| Vincenty formula | More accurate but complex; difference < 0.003% for Kerala distances |
| Pre-computed distance table | Would hardcode values; violates Constitution P3 |

---

## R-2: Objective Normalisation

### Decision

Use **min-max normalisation** across the three plans for each dimension. Lower is better
for cost, time, and CO₂; higher is better for reliability. The normalised value for
`cheapest`/`fastest`/`greenest`/`most_reliable` is the plan's rank on that single metric.
For `balanced`, the four normalised dimensions are combined as a weighted sum.

```python
def normalise(values: list[float]) -> list[float]:
    """Min-max normalise; returns 0.0 for best, 1.0 for worst.
    If all values equal, returns 0.0 for all (no distinction)."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]

def balanced_score(plan, norms: dict, weights: BalancedWeights) -> float:
    # norms keys: cost_norm, time_norm, co2_norm, reliability_norm
    # For reliability: lower norm = better (already inverted by normalise on reversed list)
    return (
        weights.cost        * norms["cost"]
      + weights.time        * norms["time"]
      + weights.co2         * norms["co2"]
      + weights.reliability * (1.0 - norms["reliability"])  # higher reliability = better
    )
```

Defaults (from `data/config.yaml`, `source_status: assumed`):
- `balanced_weight_cost: 0.4`
- `balanced_weight_time: 0.3`
- `balanced_weight_reliability: 0.2`
- `balanced_weight_co2: 0.1`

Tie-breaking rule: when two plans produce the same normalised score (or the same raw
metric for single-objective comparisons), the plan with the lower `total_cost_₹` wins.
If costs are also equal, the first plan in the canonical order (road < water < hybrid)
is chosen — this is deterministic and testable.

Only plans where `deadline_ok = True` are eligible for recommendation. Not-viable plans
(`not_viable = True`) are never eligible regardless of deadline.

### Rationale

- Min-max is simple, deterministic, and produces values in [0, 1] with no outlier
  sensitivity for exactly three plans.
- Using the same normalisation for all objectives makes the balanced objective consistent
  with single-objective rankings.
- Explicit tie-breaking makes the output deterministic for identical inputs.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Z-score normalisation | Requires mean/std; undefined for 2 plans (one not_viable) |
| Rank-based scoring (1/2/3) | Loses magnitude information; balanced score would ignore how much better |
| Equal weights (0.25 each) | Spec explicitly requires 0.4/0.3/0.2/0.1 from config |

---

## R-3: Data Model for Legs and Handling

### Decision

A `Leg` is the atomic unit of a plan. There are four leg subtypes identified by the
`mode` field:

| Mode value | Meaning |
|---|---|
| `road` | Truck movement between two nodes |
| `water` | Barge movement between two jetties |
| `handling` | Loading or unloading at a jetty (zero distance, non-zero time + cost) |
| `waiting` | Time waiting for the next scheduled sailing (zero distance, zero cost, non-zero time) |

`handling` and `waiting` legs carry `distance_km = 0`. Their time and cost come directly
from config. This keeps the plan response consistent — every second of door-to-door time
and every rupee of cost is accounted for by a leg, making the total trivially verifiable.

**Hybrid plan leg order:**

```
Leg 1: road  (origin → origin_jetty)
Leg 2: handling  (loading at origin_jetty)
Leg 3: waiting   (origin_jetty, wait for sailing)
Leg 4: water     (origin_jetty → dest_jetty)
Leg 5: handling  (unloading at dest_jetty)
Leg 6: road      (dest_jetty → destination)
```

**Water-only plan leg order:**

```
Leg 1: handling  (loading at origin_jetty)
Leg 2: waiting   (wait for sailing)
Leg 3: water     (origin_jetty → dest_jetty)
Leg 4: handling  (unloading at dest_jetty)
```

**Road plan leg order:**

```
Leg 1: road  (origin → destination)
```

Each leg records the config values it used in `config_values_used: list[ConfigRef]`
where `ConfigRef = {key, value, source_status, note}`. This is how the `assumptions`
block is assembled at the plan level (union of all legs' `config_values_used`).

### Rationale

- Explicit `handling` and `waiting` legs mean `sum(leg.time_h) == plan.total_time_h`
  without hidden adjustments — testable with a simple assertion.
- `config_values_used` on each leg traces every number to its config source, fulfilling
  FR-7 and Constitution P3 without needing a separate lookup.
- Four fixed mode strings are exhaustive for this feature; no open-ended enum needed.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| Separate `handling_time_h` field on Plan | Hides the accounting; can't verify total = sum of legs |
| Handling baked into water leg | Same problem; also mixes two distinct cost drivers |
| Polymorphic leg subclasses | Over-engineering for a prototype; a `mode` discriminator field is sufficient |

---

## R-4: Reliability Score Sub-weights

### Decision

Three factors, weights read from `data/config.yaml`:

| Factor | Config key | Default | Meaning |
|---|---|---|---|
| Schedule buffer | `reliability_weight_buffer` | `0.4` | Slack between estimated arrival and deadline, normalised by `reliability_buffer_full_h` |
| Draft margin | `reliability_weight_depth` | `0.35` | `(route_depth_m - vessel_draft_m) / reliability_depth_safe_m`, clamped 0–1 |
| On-time rate | `reliability_weight_ontime` | `0.25` | Vessel's historical on-time rate (0–1 float in seed data) |

Weights must sum to 1.0; the engine raises `ConfigError` if they do not. Each factor
produces a `sub_score` (float 0–1) and a human-readable `reason` string describing what
drove it up or down. The final integer score = `round(raw × 100)`.

Road reliability is not computed — it is a fixed constant
(`reliability_road_baseline: 0.92`, `source_status: assumed`) returned directly.

All six config keys carry `source_status: assumed` and notes in `data/config.yaml`.

### Rationale

- Three-factor model covers the three primary water-transport risk dimensions without
  requiring data that doesn't exist for a prototype (weather, mechanical failure, etc.).
- Storing weights in config means the judge can tweak them live without a code change.
- Explicit `reason` strings per factor fulfil FR-4's human-readable reason requirement.
