"""
backend/engine/tests/test_options.py
TDD: write failing tests first (Constitution P5).
Canonical scenario:
  - 10 t, Kochi→Alappuzha, ready 08:00 IST, deadline +10h → recommend hybrid
  - 10 t, Kochi→Alappuzha, ready 08:00 IST, deadline +3h  → recommend road
"""
import pytest
from backend.engine import options as eng


ORIGIN = {
    "id": "node-001",
    "name": "Kochi Thevara Jetty",
    "lat": 9.9312,
    "lon": 76.2673,
}
DESTINATION = {
    "id": "node-002",
    "name": "Alappuzha Boat Jetty",
    "lat": 9.4981,
    "lon": 76.3388,
}
SAILING = {
    "id": "sailing-001",
    "vessel_id": "vessel-001",
    "origin_node_id": "node-001",
    "destination_node_id": "node-002",
    "departure_time": "06:00",
    "days": ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],
    "available_capacity_t": 25,
}


# ── SC-1a: 10h deadline → hybrid ─────────────────────────────────────────────
def test_canonical_10h_recommends_hybrid():
    # ready_time 04:00 → sailing 06:00 same-day → wait 2h + sail ~6.3h = ~8.3h < 9.5h deadline
    plans = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="04:00",
        deadline_h=10,
        sailings=[SAILING],
        subsidy=False,
    )
    recommended = plans["recommended"]
    assert recommended == "hybrid", (
        f"Expected hybrid for 10h deadline, got {recommended}. Plans: {plans}"
    )


# ── SC-1b: 3h deadline → road ─────────────────────────────────────────────────
def test_canonical_3h_recommends_road():
    # road is ~2h; hybrid wait+sail ~8.3h > 2.5h effective deadline → road wins
    plans = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="04:00",
        deadline_h=3,
        sailings=[SAILING],
        subsidy=False,
    )
    recommended = plans["recommended"]
    assert recommended == "road", (
        f"Expected road for 3h deadline, got {recommended}. Plans: {plans}"
    )


# ── SC-2: road plan always present ────────────────────────────────────────────
def test_road_plan_always_present():
    plans = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="04:00",
        deadline_h=10,
        sailings=[SAILING],
        subsidy=False,
    )
    assert "road" in plans["plans"]
    road = plans["plans"]["road"]
    assert road["cost_inr"] > 0
    assert road["time_h"] > 0
    assert road["co2_kg"] > 0


# ── SC-3: hybrid plan fields ──────────────────────────────────────────────────
def test_hybrid_plan_has_required_fields():
    plans = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="04:00",
        deadline_h=10,
        sailings=[SAILING],
        subsidy=False,
    )
    hybrid = plans["plans"].get("hybrid")
    assert hybrid is not None, "Hybrid plan missing"
    for field in ("cost_inr", "time_h", "co2_kg", "source_status", "note"):
        assert field in hybrid, f"Field {field!r} missing from hybrid plan"


# ── SC-4: no sailings → no hybrid plan ───────────────────────────────────────
def test_no_sailings_no_hybrid():
    plans = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="04:00",
        deadline_h=10,
        sailings=[],
        subsidy=False,
    )
    assert "hybrid" not in plans["plans"]
    assert plans["recommended"] == "road"


# ── SC-5: why field present ───────────────────────────────────────────────────
def test_why_field_present():
    plans = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="04:00",
        deadline_h=10,
        sailings=[SAILING],
        subsidy=False,
    )
    assert "why" in plans
    assert isinstance(plans["why"], str)
    assert len(plans["why"]) > 10


# ── SC-6: subsidy reduces hybrid cost ─────────────────────────────────────────
def test_subsidy_reduces_hybrid_cost():
    plans_no = eng.build_plans(
        weight_t=10, origin=ORIGIN, destination=DESTINATION,
        ready_time="04:00", deadline_h=10, sailings=[SAILING], subsidy=False,
    )
    plans_yes = eng.build_plans(
        weight_t=10, origin=ORIGIN, destination=DESTINATION,
        ready_time="04:00", deadline_h=10, sailings=[SAILING], subsidy=True,
    )
    hybrid_no  = plans_no["plans"].get("hybrid", {}).get("cost_inr", 0)
    hybrid_yes = plans_yes["plans"].get("hybrid", {}).get("cost_inr", 0)
    assert hybrid_yes < hybrid_no, "Subsidy should reduce hybrid cost"
