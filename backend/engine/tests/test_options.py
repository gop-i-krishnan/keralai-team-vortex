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


# ── Fix-1: road distance uses corrected factor 1.3, not over-stated 1.8 ─────
def test_road_distance_factor_is_corrected():
    """
    Straight-line Kochi(9.9312,76.2673)→Alappuzha(9.4981,76.3388) ≈ 48.8 km.
    Factor 1.8 gave ~88 km (NH66 is ~55-62 km — overstated by ~38%).
    Factor 1.3 gives ~63.4 km — closer to actual NH66 distance.
    Verify: road plan distance_km < 70 km.
    """
    plans = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="04:00",
        deadline_h=10,
        sailings=[SAILING],
        subsidy=False,
    )
    road = plans["plans"]["road"]
    assert road["distance_km"] < 70.0, (
        f"Road distance {road['distance_km']} km exceeds 70 km — road_factor may still be over-stated"
    )
    # Also assert it isn't too short (sanity lower bound ~50 km)
    assert road["distance_km"] > 50.0, (
        f"Road distance {road['distance_km']} km is implausibly short"
    )


# ── Fix-3: CO2 is consistent with each plan's own distance_km ────────────────
def test_co2_consistent_with_distance():
    """
    For each plan, verify:
        co2_kg ≈ weight_t × distance_km × emission_factor
    Road uses road_km, hybrid uses water_km (barge leg only).
    This ensures no cross-mode distance confusion.
    """
    from backend.engine.config import val as cfg_val
    plans = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="04:00",
        deadline_h=10,
        sailings=[SAILING],
        subsidy=False,
    )
    road = plans["plans"]["road"]
    road_factor = cfg_val("road", "co2_kg_per_t_km")
    expected_road_co2 = 10 * road["distance_km"] * road_factor
    assert abs(road["co2_kg"] - expected_road_co2) < 0.1, (
        f"Road CO2 mismatch: got {road['co2_kg']}, expected {expected_road_co2:.2f}"
    )

    hybrid = plans["plans"].get("hybrid")
    if hybrid:
        water_factor = cfg_val("water", "co2_kg_per_t_km")
        expected_hybrid_co2 = 10 * hybrid["distance_km"] * water_factor
        assert abs(hybrid["co2_kg"] - expected_hybrid_co2) < 0.1, (
            f"Hybrid CO2 mismatch: got {hybrid['co2_kg']}, expected {expected_hybrid_co2:.2f}"
        )
        # Confirm scope field is present
        assert hybrid.get("co2_scope") == "barge-leg only", (
            "Hybrid plan must declare co2_scope to warn about missing truck-leg emissions"
        )


# ── Perishable scoring (T031) ─────────────────────────────────────────────────

def test_perishable_adjustments_applied_flag():
    """SC-6: build_plans with cargo_class='perishable' → perishable_adjustments_applied: True."""
    result = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="08:00",
        deadline_h=10,
        sailings=[SAILING],
        cargo_class="perishable",
    )
    assert result.get("perishable_adjustments_applied") is True


def test_non_perishable_no_adjustment_flag():
    """build_plans with cargo_class='general' → perishable_adjustments_applied: False."""
    result = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="08:00",
        deadline_h=10,
        sailings=[SAILING],
        cargo_class="general",
    )
    assert result.get("perishable_adjustments_applied") is False


def test_perishable_reliability_weight_override():
    """SC-6: perishable result includes weights_applied with override reliability weight."""
    result = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="08:00",
        deadline_h=10,
        sailings=[SAILING],
        cargo_class="perishable",
    )
    from backend.engine.config import val
    expected_rel_weight = val("perishable", "reliability_weight_override")
    weights = result.get("weights_applied", {})
    assert "reliability" in weights
    assert abs(weights["reliability"] - expected_rel_weight) < 0.001


def test_perishable_weights_sum_to_one():
    """Perishable scoring: all four weights sum to 1.0."""
    result = eng.build_plans(
        weight_t=10,
        origin=ORIGIN,
        destination=DESTINATION,
        ready_time="08:00",
        deadline_h=10,
        sailings=[SAILING],
        cargo_class="perishable",
    )
    weights = result.get("weights_applied", {})
    total = sum(weights.values())
    assert abs(total - 1.0) < 1e-9
