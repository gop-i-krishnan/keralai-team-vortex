"""
backend/engine/viability.py
Corridor viability and break-even analysis.
Constitution P2: deterministic, pure.
Constitution P3: all constants from config.
Break-even formula: d* = F_total / road_rate_per_t_km
  where F_total = loading_per_t + unloading_per_t + water_freight_per_t
"""
from __future__ import annotations
from backend.engine.config import val


def breakeven_distance() -> float:
    """
    Return d* in km: minimum distance at which water transport costs less than road
    on a per-tonne basis.
    d* = (loading + unloading + water_freight) / road_rate_per_t_km
    """
    f_total = (
        val("water", "loading_cost_per_t")
        + val("water", "unloading_cost_per_t")
        + val("water", "water_freight_rate_per_t")
    )
    road_rate = val("road", "rate_per_t_km")
    return round(f_total / road_rate, 2)


def classify_corridors(corridors: list[dict]) -> list[dict]:
    """
    For each corridor, determine if it exceeds the break-even distance.
    Returns list of corridor dicts enriched with viable, d_star_km.
    """
    d_star = breakeven_distance()
    results = []
    for c in corridors:
        dist = c["distance_km"]
        results.append({
            **c,
            "d_star_km": d_star,
            "viable": dist >= d_star,
            "margin_km": round(dist - d_star, 2),
        })
    return results


def demand_summary(all_cargo: list[dict], corridors: list[dict]) -> list[dict]:
    """
    Aggregate total tonnage per corridor from cargo list.
    """
    results = []
    for corr in corridors:
        o, d = corr["origin_node_id"], corr["destination_node_id"]
        total = sum(
            c["weight_t"]
            for c in all_cargo
            if c["origin_node_id"] == o and c["destination_node_id"] == d
        )
        results.append({
            "corridor_id": corr["id"],
            "origin_node_id": o,
            "destination_node_id": d,
            "distance_km": corr["distance_km"],
            "total_t": total,
            "min_viable_t": val("viability", "min_demand_t_per_month"),
            "demand_viable": total >= val("viability", "min_demand_t_per_month"),
        })
    return results
