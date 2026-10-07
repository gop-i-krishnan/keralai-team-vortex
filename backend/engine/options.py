"""
backend/engine/options.py
Pure shipment-decision engine.
Constitution P2: deterministic, no I/O, no LLM calls.
Constitution P3: all constants via engine/config.py → data/config.yaml.
Constitution P1: compares road, water, hybrid — recommends road when road wins.
"""
from __future__ import annotations
from typing import Optional

from backend.engine.config import val, ConfigError, get_scoring_weights
from backend.engine.geo import haversine_km
from backend.engine.reliability import score_reliability

# ── Perishable config validation (P5, FR-9) ────────────────────────────────
# Verified at module import; raises ConfigError if invariant violated.
def _check_perishable_invariant() -> None:
    try:
        rel_override = val("perishable", "reliability_weight_override")
    except Exception:
        return  # Config not yet fully populated; skip at import time
    # Must read from the nested dict structure
    rel_standard = get_scoring_weights()["reliability"]
    if float(rel_override) <= rel_standard:
        raise ConfigError(
            f"perishable.reliability_weight_override ({rel_override}) must be > "
            f"scoring.weights.reliability ({rel_standard}). Fix data/config.yaml."
        )

_check_perishable_invariant()


# ── Road plan ─────────────────────────────────────────────────────────────────

def _build_road_plan(weight_t: float, origin: dict, destination: dict) -> dict:
    straight_km = haversine_km(
        origin["lat"], origin["lon"],
        destination["lat"], destination["lon"],
    )
    road_km = straight_km * val("road", "road_factor")
    cost_inr = weight_t * road_km * val("road", "rate_per_t_km")
    time_h = road_km / val("road", "avg_speed_kmh")
    co2_kg = weight_t * road_km * val("road", "co2_kg_per_t_km")
    return {
        "mode": "road",
        "cost_inr": round(cost_inr, 2),
        "time_h": round(time_h, 2),
        "co2_kg": round(co2_kg, 2),
        "distance_km": round(road_km, 2),
        "source_status": "assumed",
        "note": "Haversine × road_factor fallback (no live routing API).",
    }


# ── Next-sailing logic ────────────────────────────────────────────────────────

def _parse_hhmm(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def _find_next_sailing(
    ready_time: str,
    sailings: list[dict],
    origin_id: str,
    destination_id: str,
    weight_t: float,
) -> Optional[dict]:
    """
    Return the sailing with the earliest departure >= ready_time that has
    sufficient capacity.  If no same-day departure qualifies, advance to the
    next calendar day (simulating a daily schedule).
    Returns None when sailings list is empty or none qualify.
    """
    rh, rm = _parse_hhmm(ready_time)
    ready_mins = rh * 60 + rm

    candidates = [
        s for s in sailings
        if s["origin_node_id"] == origin_id
        and s["destination_node_id"] == destination_id
        and s.get("available_capacity_t", 0) >= weight_t
    ]
    if not candidates:
        return None

    # Same-day candidates first
    same_day = [s for s in candidates if _parse_hhmm(s["departure_time"])[0] * 60 + _parse_hhmm(s["departure_time"])[1] >= ready_mins]
    if same_day:
        best = min(same_day, key=lambda s: _parse_hhmm(s["departure_time"])[0] * 60 + _parse_hhmm(s["departure_time"])[1])
        dep_h, dep_m = _parse_hhmm(best["departure_time"])
        wait_h = (dep_h * 60 + dep_m - ready_mins) / 60.0
        return {**best, "_wait_h": wait_h}

    # Next-day: pick the earliest departure overall (adds 24h wait from ready)
    best = min(candidates, key=lambda s: _parse_hhmm(s["departure_time"])[0] * 60 + _parse_hhmm(s["departure_time"])[1])
    dep_h, dep_m = _parse_hhmm(best["departure_time"])
    next_day_dep_mins = dep_h * 60 + dep_m + 24 * 60
    wait_h = (next_day_dep_mins - ready_mins) / 60.0
    return {**best, "_wait_h": wait_h}


# ── Water / hybrid plan ───────────────────────────────────────────────────────

def _build_water_plan(
    weight_t: float,
    origin: dict,
    destination: dict,
    sailings: list[dict],
    ready_time: str,
    subsidy: bool,
) -> Optional[dict]:
    sailing = _find_next_sailing(
        ready_time, sailings, origin["id"], destination["id"], weight_t
    )
    if sailing is None:
        return None

    straight_km = haversine_km(
        origin["lat"], origin["lon"],
        destination["lat"], destination["lon"],
    )
    # Water distance slightly longer than straight line (P3: factor from config)
    water_km = straight_km * val("water", "tortuosity_factor")

    sail_time_h = water_km / val("water", "speed_kmh")
    wait_h: float = sailing["_wait_h"]

    loading = weight_t * val("water", "loading_cost_per_t")
    unloading = weight_t * val("water", "unloading_cost_per_t")
    freight = weight_t * val("water", "water_freight_rate_per_t")

    if subsidy:
        freight = freight * (1.0 - val("water", "subsidy_fraction"))

    cost_inr = loading + unloading + freight
    total_time_h = wait_h + sail_time_h
    # CO2 computed for barge leg only (water_km = straight × tortuosity).
    # First/last-mile truck CO2 is NOT included, consistent with the cost scope.
    co2_kg = weight_t * water_km * val("water", "co2_kg_per_t_km")

    return {
        "mode": "hybrid",
        "cost_inr": round(cost_inr, 2),
        "time_h": round(total_time_h, 2),
        "sail_time_h": round(sail_time_h, 2),
        "wait_h": round(wait_h, 2),
        "co2_kg": round(co2_kg, 2),
        "distance_km": round(water_km, 2),
        "sailing_id": sailing["id"],
        "subsidy_applied": subsidy,
        "source_status": "assumed",
        "co2_scope": "barge-leg only",
        "note": (
            "Port-to-port cost and CO₂ only: jetty loading + barge freight + jetty unloading (±subsidy). "
            "First-mile and last-mile truck legs are NOT included in cost or CO₂. "
            "Add first/last-mile road costs and emissions for a full door-to-door comparison. [assumed]"
        ),
    }


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score_plans(
    plans: dict,
    monsoon: bool = False,
    weights_override: dict | None = None,
) -> dict[str, float]:
    """
    Min-max normalise cost, time, co2 across available plans, then add reliability.
    Lower cost/time/co2 is better (inverted normalisation). Reliability is [0,1] higher=better.
    Weighted sum → final score (higher = better).
    Constitution P3: weights from CFG dict (scoring.weights is a plain sub-dict, not {value:…}).
    weights_override: if provided, use these weights instead of config (for perishable FR-9).
    """
    keys = list(plans.keys())

    # Resolve weights (from override or config)
    if weights_override:
        w_cost = weights_override["cost"]
        w_time = weights_override["time"]
        w_co2  = weights_override["co2"]
        w_rel  = weights_override["reliability"]
    else:
        _w = get_scoring_weights()
        w_cost, w_time, w_co2, w_rel = _w["cost"], _w["time"], _w["co2"], _w["reliability"]

    if len(keys) == 1:
        # Single plan: score reliability only, no normalisation needed
        mode = keys[0]
        night = plans[mode].get("_night", False)
        rel = score_reliability(mode, monsoon=monsoon, night=night)
        return {mode: round(1.0 - w_rel + w_rel * rel, 4)}

    costs = [plans[k]["cost_inr"] for k in keys]
    times = [plans[k]["time_h"]   for k in keys]
    co2s  = [plans[k]["co2_kg"]   for k in keys]

    def norm(values: list[float]) -> list[float]:
        mn, mx = min(values), max(values)
        if mx == mn:
            return [1.0] * len(values)
        return [(mx - v) / (mx - mn) for v in values]  # inverted: lower raw → higher score

    nc = norm(costs)
    nt = norm(times)
    ne = norm(co2s)

    scores = {}
    for i, k in enumerate(keys):
        night = plans[k].get("_night", False)
        rel = score_reliability(k, monsoon=monsoon, night=night)
        scores[k] = round(w_cost * nc[i] + w_time * nt[i] + w_co2 * ne[i] + w_rel * rel, 4)
    return scores


# ── Public API ────────────────────────────────────────────────────────────────

def build_plans(
    weight_t: float,
    origin: dict,
    destination: dict,
    ready_time: str,
    deadline_h: float,
    sailings: list[dict],
    subsidy: bool = False,
    monsoon: bool = False,
    cargo_class: str = "general",
) -> dict:
    """
    Compare road, water/hybrid door-to-door plans.
    Returns:
      {
        "plans": {"road": {...}, "hybrid": {...}},
        "recommended": "road"|"hybrid",
        "why": "<plain English>",
        "scores": {"road": 0.6, "hybrid": 0.8},
        "perishable_adjustments_applied": bool,
        "weights_applied": {"cost": ..., "time": ..., "co2": ..., "reliability": ...},
      }
    Constitution P1: road wins when road is better.
    Constitution P2: pure function, deterministic, human-readable why.
    monsoon: pass True during June–September to apply reliability penalty (P3).
    cargo_class: when "perishable", uses tighter buffer and elevated reliability weight (FR-9).
    """
    # ── Perishable overrides (FR-9, P3) ──────────────────────────────────────
    perishable_adjustments_applied = False
    if cargo_class == "perishable":
        buffer_h = val("perishable", "schedule_buffer_h")
        perishable_adjustments_applied = True
    else:
        buffer_h = val("scoring", "deadline_buffer_h")
    effective_deadline_h = deadline_h - buffer_h

    road = _build_road_plan(weight_t, origin, destination)
    plans: dict = {}

    # Road is always viable
    if road["time_h"] <= effective_deadline_h:
        plans["road"] = road

    water = _build_water_plan(weight_t, origin, destination, sailings, ready_time, subsidy)
    if water is not None and water["time_h"] <= effective_deadline_h:
        # Tag night sailing for reliability scoring (departure after 20:00)
        dep_time = water.get("sailing_id")  # sailing_id present
        # Find departure hour from the matched sailing record
        matched = next((s for s in sailings if s["id"] == water.get("sailing_id")), None)
        if matched:
            dep_h, _ = _parse_hhmm(matched["departure_time"])
            water["_night"] = dep_h >= 20
        plans["hybrid"] = water

    # If deadline too tight for road even, still include road (best effort)
    if not plans:
        plans["road"] = road

    # ── Scoring weights: apply perishable override (FR-9, P3) ────────────────
    if cargo_class == "perishable":
        _w = get_scoring_weights()
        w_cost_base, w_time_base, w_co2_base = _w["cost"], _w["time"], _w["co2"]
        w_rel_override = float(val("perishable", "reliability_weight_override"))
        # Scale remaining three weights proportionally so sum = 1.0
        remaining_base = w_cost_base + w_time_base + w_co2_base
        scale = (1.0 - w_rel_override) / remaining_base
        adjusted_weights = {
            "cost":        round(w_cost_base * scale, 6),
            "time":        round(w_time_base * scale, 6),
            "co2":         round(w_co2_base  * scale, 6),
            "reliability": w_rel_override,
        }
    else:
        adjusted_weights = get_scoring_weights()

    scores = _score_plans(plans, monsoon=monsoon, weights_override=adjusted_weights)
    recommended = max(scores, key=lambda k: scores[k])

    # Build why text (Constitution P2: must be a plain-English sentence with numbers)
    rec_plan = plans[recommended]
    why = (
        f"Recommended {recommended}: "
        f"Rs {rec_plan['cost_inr']:,.0f}, "
        f"{rec_plan['time_h']:.1f} h, "
        f"{rec_plan['co2_kg']:.1f} kg CO₂"
    )
    if recommended == "hybrid":
        why += " (water-leg cost only — first/last-mile truck not included)"
    if len(plans) > 1:
        other = [k for k in plans if k != recommended][0]
        other_plan = plans[other]
        why += (
            f" vs {other} "
            f"Rs {other_plan['cost_inr']:,.0f} "
            f"{other_plan['time_h']:.1f} h"
        )
    if recommended == "road" and water is not None and water["time_h"] > effective_deadline_h:
        why += f" (hybrid excluded: {water['time_h']:.1f} h > {effective_deadline_h:.1f} h deadline)"

    return {
        "plans": plans,
        "recommended": recommended,
        "scores": scores,
        "why": why,
        "perishable_adjustments_applied": perishable_adjustments_applied,
        "weights_applied": adjusted_weights,
    }
