"""
backend/engine/pooling.py
Pure cargo pooling (same-direction co-load) engine.
Constitution P2: deterministic, no I/O.
Constitution P3: max_pool_weight_fraction from config.
"""
from __future__ import annotations
from backend.engine.config import val


def find_pooling(sailing: dict, booked_weight_t: float, all_cargo: list[dict]) -> list[dict]:
    """
    Find same-direction cargo that can share the remaining vessel capacity.
    Each pooled cargo must not exceed max_pool_weight_fraction of total vessel capacity.
    """
    origin = sailing["origin_node_id"]
    destination = sailing["destination_node_id"]
    vessel_cap = sailing["available_capacity_t"]
    remaining = vessel_cap - booked_weight_t
    max_single = vessel_cap * val("matching", "max_pool_weight_fraction")

    results = []
    used = 0.0
    for cargo in all_cargo:
        if cargo["origin_node_id"] != origin:
            continue
        if cargo["destination_node_id"] != destination:
            continue
        w = cargo["weight_t"]
        if w > max_single:
            continue
        if used + w > remaining:
            continue
        results.append({
            "cargo_id": cargo["id"],
            "weight_t": w,
            "direction": "pooling",
        })
        used += w

    return results
