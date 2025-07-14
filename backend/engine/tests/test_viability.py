"""
backend/engine/tests/test_viability.py
TDD tests for corridor viability / break-even engine.
"""
from backend.engine import viability as v


CORRIDORS = [
    {
        "id": "corridor-001",
        "origin_node_id": "node-001",
        "destination_node_id": "node-002",
        "distance_km": 75.0,
    }
]

CARGO = [
    {"id": "cargo-001", "weight_t": 10, "origin_node_id": "node-001", "destination_node_id": "node-002"},
    {"id": "cargo-011", "weight_t": 4,  "origin_node_id": "node-001", "destination_node_id": "node-002"},
    {"id": "cargo-012", "weight_t": 3,  "origin_node_id": "node-001", "destination_node_id": "node-002"},
]


def test_breakeven_distance_positive():
    d_star = v.breakeven_distance()
    assert d_star > 0


def test_breakeven_distance_formula():
    # d* = F_total / road_rate_per_t_km  (per-tonne basis, single tonne)
    from backend.engine.config import val
    f_total = val("water", "loading_cost_per_t") + val("water", "unloading_cost_per_t") + val("water", "water_freight_rate_per_t")
    road_rate = val("road", "rate_per_t_km")
    expected = f_total / road_rate
    assert abs(v.breakeven_distance() - expected) < 0.01


def test_classify_corridors_returns_list():
    result = v.classify_corridors(CORRIDORS)
    assert isinstance(result, list)
    assert len(result) == 1


def test_classify_corridor_has_viability_flag():
    result = v.classify_corridors(CORRIDORS)
    assert "viable" in result[0]
    assert "d_star_km" in result[0]
    assert "distance_km" in result[0]


def test_demand_summary_totals():
    summary = v.demand_summary(CARGO, CORRIDORS)
    assert len(summary) == 1
    assert summary[0]["total_t"] == 17.0  # 10+4+3
