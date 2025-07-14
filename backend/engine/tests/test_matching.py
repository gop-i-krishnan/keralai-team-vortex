"""
backend/engine/tests/test_matching.py
TDD tests for capacity matching, backhaul, and pooling.
"""
import pytest
from backend.engine import matching, backhaul, pooling


SAILING = {
    "id": "sailing-001",
    "vessel_id": "vessel-001",
    "origin_node_id": "node-001",
    "destination_node_id": "node-002",
    "departure_time": "06:00",
    "days": ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],
    "available_capacity_t": 25,
}

CARGO_HERO = {"id": "cargo-001", "weight_t": 10, "origin_node_id": "node-001", "destination_node_id": "node-002"}
CARGO_POOL1 = {"id": "cargo-011", "weight_t": 4,  "origin_node_id": "node-001", "destination_node_id": "node-002"}
CARGO_POOL2 = {"id": "cargo-012", "weight_t": 3,  "origin_node_id": "node-001", "destination_node_id": "node-002"}
CARGO_BACK  = {"id": "cargo-013", "weight_t": 7,  "origin_node_id": "node-002", "destination_node_id": "node-001"}


# ── Matching ──────────────────────────────────────────────────────────────────

def test_match_returns_ranked_list():
    result = matching.rank_sailings(
        cargo=CARGO_HERO,
        sailings=[SAILING],
    )
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["sailing_id"] == "sailing-001"


def test_no_capacity_excluded():
    small_sailing = {**SAILING, "id": "s-tiny", "available_capacity_t": 5}
    result = matching.rank_sailings(cargo=CARGO_HERO, sailings=[small_sailing])
    assert result == []


def test_match_score_between_0_and_1():
    result = matching.rank_sailings(cargo=CARGO_HERO, sailings=[SAILING])
    assert 0 <= result[0]["score"] <= 1.0


# ── Backhaul ──────────────────────────────────────────────────────────────────

def test_backhaul_finds_reverse_cargo():
    result = backhaul.find_backhaul(
        sailing=SAILING,
        all_cargo=[CARGO_HERO, CARGO_BACK],
        booked_weight_t=10,
    )
    assert len(result) > 0
    assert all(c["cargo_id"] == "cargo-013" for c in result)


def test_backhaul_ignores_same_direction():
    result = backhaul.find_backhaul(
        sailing=SAILING,
        all_cargo=[CARGO_HERO],
        booked_weight_t=10,
    )
    assert result == []


def test_backhaul_respects_capacity():
    huge_cargo = {**CARGO_BACK, "weight_t": 100}
    result = backhaul.find_backhaul(
        sailing=SAILING,
        all_cargo=[huge_cargo],
        booked_weight_t=10,
    )
    # 100t > remaining capacity of vessel → no backhaul
    assert result == []


# ── Pooling ───────────────────────────────────────────────────────────────────

def test_pooling_finds_compatible_cargo():
    result = pooling.find_pooling(
        sailing=SAILING,
        booked_weight_t=10,
        all_cargo=[CARGO_POOL1, CARGO_POOL2, CARGO_BACK],
    )
    # cargo-013 is reverse direction, should be excluded
    pool_ids = [r["cargo_id"] for r in result]
    assert "cargo-013" not in pool_ids
    assert len(result) >= 1


def test_pooling_does_not_exceed_capacity():
    result = pooling.find_pooling(
        sailing=SAILING,
        booked_weight_t=10,
        all_cargo=[CARGO_POOL1, CARGO_POOL2],
    )
    total = sum(r["weight_t"] for r in result)
    remaining = SAILING["available_capacity_t"] - 10
    assert total <= remaining
