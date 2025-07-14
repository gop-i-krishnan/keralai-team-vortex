"""
backend/engine/backhaul.py
Pure backhaul opportunity finder.
Constitution P2: deterministic, no I/O.
"""
from __future__ import annotations


def find_backhaul(sailing: dict, all_cargo: list[dict], booked_weight_t: float) -> list[dict]:
    """
    Find cargo that can fill the return leg of the given sailing.
    Return cargo must travel in the opposite direction (dest→origin of sailing).
    Capacity available = vessel capacity - booked_weight_t.
    """
    reverse_origin = sailing["destination_node_id"]
    reverse_dest = sailing["origin_node_id"]
    remaining_capacity = sailing["available_capacity_t"] - booked_weight_t

    results = []
    used = 0.0
    for cargo in all_cargo:
        if cargo["origin_node_id"] != reverse_origin:
            continue
        if cargo["destination_node_id"] != reverse_dest:
            continue
        if used + cargo["weight_t"] > remaining_capacity:
            continue
        results.append({
            "cargo_id": cargo["id"],
            "weight_t": cargo["weight_t"],
            "direction": "backhaul",
        })
        used += cargo["weight_t"]

    return results
