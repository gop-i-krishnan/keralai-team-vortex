"""
backend/engine/tests/test_warehouse.py
Tests for warehouse engine: find_eligible_warehouses() and compute_staging_plan().
Constitution P5: tests written before / alongside implementation.
Constitution P2: pure functions — no mocking required.
"""
from __future__ import annotations
import math
import pytest
from backend.engine.warehouse import compute_staging_plan, find_eligible_warehouses
from backend.engine.config import val

# ── Fixtures ──────────────────────────────────────────────────────────────────

# Node coords: node-001 (Kochi) and node-002 (Alappuzha) from seed
NODE_001 = {"id": "node-001", "lat": 9.9312, "lon": 76.2673}
NODE_002 = {"id": "node-002", "lat": 9.4981, "lon": 76.3388}

# Warehouse at same location as node-001 (should be in proximity)
WH_AT_NODE1 = {
    "id": "wh-test",
    "name": "Test Warehouse",
    "location_node_id": "node-001",
    "total_capacity_t": 50.0,
    "capacity_used_t": 0.0,
    "storage_cost_per_t_per_day": 8.0,
    "handling_in_cost_per_t": 25.0,
    "handling_out_cost_per_t": 25.0,
    "allowed_cargo_classes": ["general", "liquid_bulk", "flammable"],
}

# Warehouse at node-002 (far from node-001, ~48km straight line — outside 10km radius)
WH_AT_NODE2 = {
    "id": "wh-far",
    "name": "Far Warehouse",
    "location_node_id": "node-002",
    "total_capacity_t": 30.0,
    "capacity_used_t": 0.0,
    "storage_cost_per_t_per_day": 6.0,
    "handling_in_cost_per_t": 20.0,
    "handling_out_cost_per_t": 20.0,
    "allowed_cargo_classes": ["general", "perishable"],
}

CARGO_GENERAL = {
    "id": "cargo-001",
    "weight_t": 10.0,
    "cargo_class": "general",
    "origin_node_id": "node-001",
    "destination_node_id": "node-002",
}

CARGO_TOXIC = {
    "id": "cargo-x",
    "weight_t": 5.0,
    "cargo_class": "toxic_corrosive",
    "origin_node_id": "node-001",
    "destination_node_id": "node-002",
}

CARGO_PERISHABLE = {
    "id": "cargo-005",
    "weight_t": 8.0,
    "cargo_class": "perishable",
    "origin_node_id": "node-001",
    "destination_node_id": "node-002",
}

ALL_NODES = [NODE_001, NODE_002]

# ── Hand-calculated expected values ──────────────────────────────────────────

def _hand_calc_staging_plan(weight_t: float, wait_h: float, wh: dict,
                             origin: dict, dest: dict, deadline_h: float) -> dict:
    """Compute expected cost components for test assertions."""
    from backend.engine.geo import haversine_km

    road_factor = val("road", "road_factor")
    rate_per_t_km = val("road", "rate_per_t_km")
    speed_kmh = val("road", "avg_speed_kmh")
    co2_per_t_km = val("road", "co2_kg_per_t_km")

    wh_node = next(n for n in ALL_NODES if n["id"] == wh["location_node_id"])

    straight_to_wh = haversine_km(origin["lat"], origin["lon"], wh_node["lat"], wh_node["lon"])
    road_km_to_wh = straight_to_wh * road_factor
    truck_to_wh_cost = weight_t * road_km_to_wh * rate_per_t_km
    truck_to_wh_time = road_km_to_wh / speed_kmh
    truck_to_wh_co2 = weight_t * road_km_to_wh * co2_per_t_km

    straight_from_wh = haversine_km(wh_node["lat"], wh_node["lon"], dest["lat"], dest["lon"])
    road_km_from_wh = straight_from_wh * road_factor
    truck_from_wh_cost = weight_t * road_km_from_wh * rate_per_t_km
    truck_from_wh_time = road_km_from_wh / speed_kmh
    truck_from_wh_co2 = weight_t * road_km_from_wh * co2_per_t_km

    storage_days = max(1, math.ceil(wait_h / 24))
    handling_in = weight_t * wh["handling_in_cost_per_t"]
    storage_cost = weight_t * storage_days * wh["storage_cost_per_t_per_day"]
    handling_out = weight_t * wh["handling_out_cost_per_t"]

    total_cost = truck_to_wh_cost + handling_in + storage_cost + handling_out + truck_from_wh_cost
    total_time = truck_to_wh_time + wait_h + truck_from_wh_time
    total_co2 = truck_to_wh_co2 + truck_from_wh_co2

    return {
        "truck_to_warehouse_cost_inr": round(truck_to_wh_cost, 2),
        "handling_in_cost_inr": round(handling_in, 2),
        "storage_cost_inr": round(storage_cost, 2),
        "handling_out_cost_inr": round(handling_out, 2),
        "truck_from_warehouse_cost_inr": round(truck_from_wh_cost, 2),
        "total_cost_inr": round(total_cost, 2),
        "total_time_h": round(total_time, 2),
        "co2_kg": round(total_co2, 2),
        "storage_days": storage_days,
        "deadline_met": total_time <= deadline_h,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_compute_staging_plan_cost_components():
    """SC-3: total_cost_inr == sum of 5 components (hand-calculated)."""
    plan = compute_staging_plan(
        cargo=CARGO_GENERAL,
        warehouse=WH_AT_NODE1,
        next_sailing_wait_h=8.0,
        destination_node=NODE_002,
        origin_node=NODE_001,
        deadline_h=48.0,
    )
    expected = _hand_calc_staging_plan(10.0, 8.0, WH_AT_NODE1, NODE_001, NODE_002, 48.0)

    # Each component matches
    assert plan["truck_to_warehouse_cost_inr"] == pytest.approx(expected["truck_to_warehouse_cost_inr"], abs=0.01)
    assert plan["handling_in_cost_inr"] == pytest.approx(expected["handling_in_cost_inr"], abs=0.01)
    assert plan["storage_cost_inr"] == pytest.approx(expected["storage_cost_inr"], abs=0.01)
    assert plan["handling_out_cost_inr"] == pytest.approx(expected["handling_out_cost_inr"], abs=0.01)
    assert plan["truck_from_warehouse_cost_inr"] == pytest.approx(expected["truck_from_warehouse_cost_inr"], abs=0.01)

    # Total == sum of 5
    computed_sum = round(
        plan["truck_to_warehouse_cost_inr"] + plan["handling_in_cost_inr"] +
        plan["storage_cost_inr"] + plan["handling_out_cost_inr"] +
        plan["truck_from_warehouse_cost_inr"], 2
    )
    assert plan["total_cost_inr"] == pytest.approx(computed_sum, abs=0.01)


def test_staging_plan_storage_days_ceil():
    """storage_days = ceil(wait_h / 24), minimum 1."""
    plan_25h = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 25.0, NODE_002, NODE_001, 48.0)
    assert plan_25h["storage_days"] == 2  # ceil(25/24) = 2

    plan_24h = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 24.0, NODE_002, NODE_001, 48.0)
    assert plan_24h["storage_days"] == 1  # ceil(24/24) = 1

    plan_0h = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 0.0, NODE_002, NODE_001, 48.0)
    assert plan_0h["storage_days"] == 1  # minimum 1 day


def test_staging_plan_deadline_met_true():
    """total_time_h <= deadline_h → deadline_met: True."""
    plan = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 8.0, NODE_002, NODE_001, 48.0)
    # 48h deadline is very generous for a short Kochi→Alappuzha staging plan
    assert plan["deadline_met"] is True


def test_staging_plan_deadline_met_false():
    """total_time_h > deadline_h → deadline_met: False."""
    plan = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 8.0, NODE_002, NODE_001, 1.0)
    # 1h deadline is too tight for any staging plan
    assert plan["deadline_met"] is False


def test_staging_plan_co2_scope():
    """co2_scope == 'truck legs only; storage CO₂ not modelled'."""
    plan = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 8.0, NODE_002, NODE_001, 48.0)
    assert plan["co2_scope"] == "truck legs only; storage CO₂ not modelled"


def test_staging_plan_source_status_assumed():
    """source_status == 'assumed'."""
    plan = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 8.0, NODE_002, NODE_001, 48.0)
    assert plan["source_status"] == "assumed"


def test_staging_plan_has_proposal_id():
    """plan includes a non-empty, deterministic proposal_id (P2: no uuid in engine)."""
    plan = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 8.0, NODE_002, NODE_001, 48.0)
    again = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 8.0, NODE_002, NODE_001, 48.0)
    assert plan["proposal_id"]
    assert plan["proposal_id"] == again["proposal_id"]


def test_find_eligible_excludes_class_mismatch():
    """Warehouse doesn't accept cargo class → ineligible with warehouse_class_mismatch."""
    wh = {**WH_AT_NODE1, "allowed_cargo_classes": ["general"]}
    eligible, ineligible = find_eligible_warehouses(CARGO_TOXIC, NODE_001, [wh], ALL_NODES)
    assert eligible == []
    assert len(ineligible) == 1
    assert ineligible[0]["reason"] == "warehouse_class_mismatch"


def test_find_eligible_excludes_at_capacity():
    """Full warehouse → ineligible with warehouse_at_capacity (SC-4)."""
    wh = {**WH_AT_NODE1, "capacity_used_t": 50.0, "total_capacity_t": 50.0}
    eligible, ineligible = find_eligible_warehouses(CARGO_GENERAL, NODE_001, [wh], ALL_NODES)
    assert eligible == []
    assert len(ineligible) == 1
    assert ineligible[0]["reason"] == "warehouse_at_capacity"


def test_find_eligible_no_warehouse_in_range():
    """All warehouses beyond proximity_radius_km → no_warehouse_in_range in ineligible."""
    # WH_AT_NODE2 is ~48km from node-001, beyond 10km radius
    eligible, ineligible = find_eligible_warehouses(CARGO_GENERAL, NODE_001, [WH_AT_NODE2], ALL_NODES)
    assert eligible == []
    reasons = [e["reason"] for e in ineligible]
    assert "no_warehouse_in_range" in reasons


def test_find_eligible_warehouse_in_range_and_class_match():
    """WH_AT_NODE1 is at same node as origin → eligible for general cargo."""
    eligible, ineligible = find_eligible_warehouses(CARGO_GENERAL, NODE_001, [WH_AT_NODE1], ALL_NODES)
    assert len(eligible) == 1
    assert eligible[0]["id"] == "wh-test"


def test_perishable_adjustments_applied_flag():
    """cargo_class='perishable' → perishable_adjustments_applied: True."""
    wh = {**WH_AT_NODE1, "allowed_cargo_classes": ["perishable", "general"]}
    plan = compute_staging_plan(CARGO_PERISHABLE, wh, 8.0, NODE_002, NODE_001, 48.0)
    assert plan["perishable_adjustments_applied"] is True


def test_non_perishable_adjustments_not_applied():
    """cargo_class='general' → perishable_adjustments_applied: False."""
    plan = compute_staging_plan(CARGO_GENERAL, WH_AT_NODE1, 8.0, NODE_002, NODE_001, 48.0)
    assert plan["perishable_adjustments_applied"] is False
