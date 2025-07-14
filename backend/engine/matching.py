"""
backend/engine/matching.py
Pure capacity-matching engine.
Constitution P2: deterministic, no I/O.
"""
from __future__ import annotations
from backend.engine.config import val


def rank_sailings(cargo: dict, sailings: list[dict]) -> list[dict]:
    """
    Return sailings that can carry `cargo`, ranked by a simple score.
    Score factors: capacity utilisation, departure time proximity (not implemented — placeholder 0.5).
    Returns list of {"sailing_id", "score", "available_capacity_t"}.
    """
    weight = cargo["weight_t"]
    origin = cargo["origin_node_id"]
    destination = cargo["destination_node_id"]

    results = []
    for s in sailings:
        if s["origin_node_id"] != origin:
            continue
        if s["destination_node_id"] != destination:
            continue
        cap = s.get("available_capacity_t", 0)
        if cap < weight:
            continue
        # Score: utilisation ratio (how well cargo fills vessel)
        utilisation = min(weight / cap, 1.0)
        score = round(0.5 * utilisation + 0.5 * 0.5, 4)  # 50% utilisation + 50% placeholder
        results.append({
            "sailing_id": s["id"],
            "vessel_id": s["vessel_id"],
            "departure_time": s["departure_time"],
            "available_capacity_t": cap,
            "score": score,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
