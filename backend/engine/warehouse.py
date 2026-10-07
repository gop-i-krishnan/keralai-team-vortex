"""
backend/engine/warehouse.py
Pure warehouse staging engine.
Constitution P2: deterministic, no I/O, no LLM calls.
Constitution P3: all constants via val() from data/config.yaml.
Constitution P12: compute_staging_plan() is read-only; no capacity mutation here.
"""
from __future__ import annotations
import math

from backend.engine.config import val, ConfigError
from backend.engine.geo import haversine_km

_VALID_CLASSES = {
    "general", "perishable", "liquid_bulk",
    "flammable", "explosive", "toxic_corrosive", "oversized",
}


def find_eligible_warehouses(
    cargo: dict,
    origin_node: dict,
    warehouses: list[dict],
    nodes: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Filter warehouses against three criteria:
    1. Proximity: warehouse location node must be within warehouse.proximity_radius_km
       (Haversine) of origin_node.
    2. Class match: cargo's cargo_class must be in warehouse.allowed_cargo_classes.
    3. Capacity: capacity_used_t + cargo.weight_t <= total_capacity_t.

    Returns (eligible_warehouses, ineligible_with_reasons).
    Ineligible items: {warehouse_id, reason}.
    reason codes: 'no_warehouse_in_range', 'warehouse_class_mismatch', 'warehouse_at_capacity'.

    P11: reasons are always returned, never silently dropped.
    """
    radius_km: float = val("warehouse", "proximity_radius_km")
    cargo_class: str = cargo.get("cargo_class", "general")
    weight_t: float = cargo.get("weight_t", 0.0)

    # Build node lookup
    node_map: dict[str, dict] = {n["id"]: n for n in nodes}

    eligible: list[dict] = []
    ineligible: list[dict] = []
    any_in_range = False

    for wh in warehouses:
        wh_node = node_map.get(wh.get("location_node_id", ""))
        if wh_node is None:
            # Unknown location node → treat as out of range
            ineligible.append({"warehouse_id": wh["id"], "reason": "no_warehouse_in_range"})
            continue

        distance = haversine_km(
            origin_node["lat"], origin_node["lon"],
            wh_node["lat"], wh_node["lon"],
        )

        if distance > radius_km:
            ineligible.append({"warehouse_id": wh["id"], "reason": "no_warehouse_in_range"})
            continue

        any_in_range = True

        # Class mismatch check
        if cargo_class not in wh.get("allowed_cargo_classes", []):
            ineligible.append({"warehouse_id": wh["id"], "reason": "warehouse_class_mismatch"})
            continue

        # Capacity check
        used = wh.get("capacity_used_t", 0.0)
        total = wh.get("total_capacity_t", 0.0)
        if used + weight_t > total:
            ineligible.append({"warehouse_id": wh["id"], "reason": "warehouse_at_capacity"})
            continue

        eligible.append(wh)

    # If no warehouse was within range at all, add a synthetic sentinel entry
    if not any_in_range and not ineligible:
        ineligible.append({"warehouse_id": "__none__", "reason": "no_warehouse_in_range"})
    elif not any_in_range and all(e["reason"] != "no_warehouse_in_range" for e in ineligible):
        ineligible.append({"warehouse_id": "__none__", "reason": "no_warehouse_in_range"})

    return eligible, ineligible


def compute_staging_plan(
    cargo: dict,
    warehouse: dict,
    next_sailing_wait_h: float,
    destination_node: dict,
    origin_node: dict,
    deadline_h: float,
    cargo_origin_node: dict | None = None,
) -> dict:
    """
    Compute a read-only staging plan for one warehouse.

    Parameters
    ----------
    cargo             : cargo record dict (weight_t, cargo_class)
    warehouse         : warehouse record dict
    next_sailing_wait_h : time until next suitable sailing (h)
    destination_node  : the final destination node (for truck leg 2: wh → dest)
    origin_node       : the warehouse's location node (for truck leg 2 start;
                        truck leg 1 is from cargo_origin_node → this node)
    deadline_h        : overall deadline for the shipment
    cargo_origin_node : the cargo's actual origin node (for truck leg 1).
                        If None, origin_node is used for both legs (leg 1 = 0 km).

    Five cost components (all from config via val()):
    1. truck_to_warehouse_cost_inr  — road leg: cargo_origin → warehouse node
    2. handling_in_cost_inr         — weight × handling_in_cost_per_t
    3. storage_cost_inr             — weight × storage_days × storage_cost_per_t_per_day
    4. handling_out_cost_inr        — weight × handling_out_cost_per_t
    5. truck_from_warehouse_cost_inr — road leg: warehouse node → destination

    storage_days = max(1, ceil(wait_h / 24))
    CO₂ = road truck legs only; storage phase CO₂ = 0.

    Does NOT modify warehouse capacity (P12).
    """
    cargo_class: str = cargo.get("cargo_class", "general")
    weight_t: float = cargo.get("weight_t", 0.0)

    road_factor: float = val("road", "road_factor")
    rate_per_t_km: float = val("road", "rate_per_t_km")
    speed_kmh: float = val("road", "avg_speed_kmh")
    co2_per_t_km: float = val("road", "co2_kg_per_t_km")

    # warehouse_node = origin_node (the warehouse is at this node)
    warehouse_node = origin_node
    # cargo's actual origin for leg 1; if not specified, assume cargo is already at wh node
    actual_origin = cargo_origin_node if cargo_origin_node is not None else origin_node

    # Truck leg 1: cargo origin → warehouse node
    straight_to_wh = haversine_km(
        actual_origin["lat"], actual_origin["lon"],
        warehouse_node["lat"], warehouse_node["lon"],
    )
    road_km_to_wh = straight_to_wh * road_factor
    truck_to_wh_cost = round(weight_t * road_km_to_wh * rate_per_t_km, 2)
    truck_to_wh_time = road_km_to_wh / speed_kmh
    truck_to_wh_co2 = weight_t * road_km_to_wh * co2_per_t_km

    # Truck leg 2: warehouse node → destination
    straight_from_wh = haversine_km(
        warehouse_node["lat"], warehouse_node["lon"],
        destination_node["lat"], destination_node["lon"],
    )
    road_km_from_wh = straight_from_wh * road_factor
    truck_from_wh_cost = round(weight_t * road_km_from_wh * rate_per_t_km, 2)
    truck_from_wh_time = road_km_from_wh / speed_kmh
    truck_from_wh_co2 = weight_t * road_km_from_wh * co2_per_t_km

    # Storage
    storage_days = max(1, math.ceil(next_sailing_wait_h / 24))
    handling_in = round(weight_t * warehouse["handling_in_cost_per_t"], 2)
    storage_cost = round(weight_t * storage_days * warehouse["storage_cost_per_t_per_day"], 2)
    handling_out = round(weight_t * warehouse["handling_out_cost_per_t"], 2)

    # Totals
    total_cost = round(
        truck_to_wh_cost + handling_in + storage_cost + handling_out + truck_from_wh_cost, 2
    )
    total_time = round(truck_to_wh_time + next_sailing_wait_h + truck_from_wh_time, 2)
    total_co2 = round(truck_to_wh_co2 + truck_from_wh_co2, 2)
    deadline_met = total_time <= deadline_h

    perishable_adjustments_applied = (cargo_class == "perishable")

    return {
        "proposal_id": f"stg-{cargo.get('id', 'cargo')}-{warehouse['id']}",
        "warehouse_id": warehouse["id"],
        "cargo_class": cargo_class,
        "weight_t": weight_t,
        "storage_days": storage_days,
        "truck_to_warehouse_cost_inr": truck_to_wh_cost,
        "handling_in_cost_inr": handling_in,
        "storage_cost_inr": storage_cost,
        "handling_out_cost_inr": handling_out,
        "truck_from_warehouse_cost_inr": truck_from_wh_cost,
        "total_cost_inr": total_cost,
        "total_time_h": total_time,
        "co2_kg": total_co2,
        "co2_scope": "truck legs only; storage CO₂ not modelled",
        "deadline_met": deadline_met,
        "perishable_adjustments_applied": perishable_adjustments_applied,
        "source_status": "assumed",
        "note": (
            "Road truck leg costs and CO₂ only. "
            "storage CO₂ not modelled in this prototype [assumed]. "
            "verify with IWAI / PESO / state authority before production use."
        ),
    }
