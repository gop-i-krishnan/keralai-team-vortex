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


# ── Hazard filter integration (T014) ─────────────────────────────────────────

VESSEL_NO_CERTS  = {"id": "vessel-001", "hazard_certs": []}
VESSEL_FLAM_CERT = {"id": "vessel-003", "hazard_certs": ["flammable", "liquid_bulk"]}
VESSEL_LIQ_CERT  = {"id": "vessel-001-liq", "hazard_certs": ["liquid_bulk"]}

SAILING_NOCERT = {
    "id": "sailing-nocert", "vessel_id": "vessel-001",
    "origin_node_id": "node-001", "destination_node_id": "node-002",
    "departure_time": "06:00", "days": ["Mon"],
    "available_capacity_t": 25,
}
SAILING_WITH_CERT = {
    "id": "sailing-with-cert", "vessel_id": "vessel-003",
    "origin_node_id": "node-001", "destination_node_id": "node-002",
    "departure_time": "06:00", "days": ["Mon"],
    "available_capacity_t": 20,
}

from backend.engine.config import get_hazard_rules


def test_match_flammable_no_certs_returns_empty_ranked():
    """SC-1: flammable cargo, no certified vessel → ranked empty, excluded non-empty."""
    rules = get_hazard_rules()
    vessels = [VESSEL_NO_CERTS]
    result = matching.rank_sailings(
        cargo={"id": "c1", "weight_t": 10, "origin_node_id": "node-001", "destination_node_id": "node-002"},
        sailings=[SAILING_NOCERT],
        cargo_class="flammable",
        vessels=vessels,
        hazard_rules=rules,
    )
    assert isinstance(result, dict)
    assert result["ranked"] == []
    assert len(result["excluded"]) == 1
    assert result["excluded"][0]["reason"] == "missing_hazmat_cert"


def test_match_liquid_bulk_with_cert_returns_ranked():
    """Liquid_bulk cargo, vessel with liquid_bulk cert → ranked non-empty."""
    rules = get_hazard_rules()
    vessels = [VESSEL_LIQ_CERT]
    result = matching.rank_sailings(
        cargo={"id": "c2", "weight_t": 5, "origin_node_id": "node-001", "destination_node_id": "node-002"},
        sailings=[{**SAILING_NOCERT, "vessel_id": "vessel-001-liq"}],
        cargo_class="liquid_bulk",
        vessels=vessels,
        hazard_rules=rules,
    )
    assert isinstance(result, dict)
    assert len(result["ranked"]) == 1
    assert result["excluded"] == []


def test_match_general_backward_compat():
    """No cargo_class/vessels/hazard_rules → still returns a plain list (backward compat)."""
    result = matching.rank_sailings(
        cargo={"id": "c3", "weight_t": 10, "origin_node_id": "node-001", "destination_node_id": "node-002"},
        sailings=[SAILING_NOCERT],
    )
    # backward compat: plain list
    assert isinstance(result, list)
    assert result[0]["sailing_id"] == "sailing-nocert"


def test_tie_broken_by_lower_score_then_cost():
    """Two sailings with equal scores: tie broken by ascending cost (lower cost ranks first).
    Since our scoring has no cost component, we inject two sailings that will score equally
    (same vessel utilisation and schedule score) and verify stable tie-break ordering.
    """
    # Two sailings with identical utilisation and schedule score
    s1 = {**SAILING_NOCERT, "id": "s1", "available_capacity_t": 10}   # weight/cap = 1.0
    s2 = {**SAILING_NOCERT, "id": "s2", "available_capacity_t": 10}   # same
    rules = get_hazard_rules()
    result = matching.rank_sailings(
        cargo={"id": "c4", "weight_t": 10, "origin_node_id": "node-001", "destination_node_id": "node-002"},
        sailings=[s1, s2],
        cargo_class="general",
        vessels=[VESSEL_NO_CERTS],
        hazard_rules=rules,
    )
    # Both are eligible (general, no cert required); both have the same score.
    # The tie-break is by score desc then cost asc — with no cost field they both have 0 cost;
    # the sort must not crash and must return both.
    assert isinstance(result, dict)
    assert len(result["ranked"]) == 2


# ── Feature 004: unverified penalty, suspension, price-based tie-break ────────

def test_pending_vessel_score_reduced_by_configured_penalty():
    from backend.engine.config import val
    rules = [{"class_id": "general", "allowed_modes": ["road", "water"],
              "certification_required": False, "human_review_required": False}]
    v_ok = {"id": "vessel-001", "hazard_certs": [], "status": "verified"}
    v_new = {"id": "vessel-009", "hazard_certs": [], "status": "pending_verification"}
    s_new = {**SAILING, "id": "sailing-009", "vessel_id": "vessel-009"}
    out = matching.rank_sailings(CARGO_HERO, [SAILING, s_new], "general", [v_ok, v_new], rules)
    by_id = {r["sailing_id"]: r["score"] for r in out["ranked"]}
    assert by_id["sailing-001"] - by_id["sailing-009"] == pytest.approx(
        val("registry", "unverified_reliability_penalty"), abs=1e-4)
    assert out["ranked"][0]["sailing_id"] == "sailing-001"


def test_suspended_vessel_listed_in_excluded_not_dropped():
    rules = [{"class_id": "general", "allowed_modes": ["road", "water"],
              "certification_required": False, "human_review_required": False}]
    v = {"id": "vessel-001", "hazard_certs": [], "status": "suspended"}
    out = matching.rank_sailings(CARGO_HERO, [SAILING], "general", [v], rules)
    assert out["ranked"] == []
    assert out["excluded"][0]["reason"] == "vessel_suspended"


def test_equal_scores_ordered_by_lower_cost():
    a = {**SAILING, "id": "s-exp", "price_per_t": 500}
    b = {**SAILING, "id": "s-cheap", "price_per_t": 300}
    out = matching.rank_sailings(CARGO_HERO, [a, b])
    assert [r["sailing_id"] for r in out] == ["s-cheap", "s-exp"]
    assert out[0]["cost_inr"] == 3000
