"""
backend/engine/tests/test_hazards.py
Tests for apply_hazard_filters().
Constitution P5: tests written before / alongside implementation.
Constitution P2: pure function — no mocking required.
"""
from __future__ import annotations
import pytest
from backend.engine.config import ConfigError
from backend.engine.hazards import apply_hazard_filters


# ── Fixtures ──────────────────────────────────────────────────────────────────

VESSEL_NO_CERTS = {"id": "vessel-a", "hazard_certs": []}
VESSEL_FLAMMABLE = {"id": "vessel-b", "hazard_certs": ["flammable"]}
VESSEL_LIQUID = {"id": "vessel-c", "hazard_certs": ["liquid_bulk"]}

SAILING_A = {
    "id": "sail-a", "vessel_id": "vessel-a",
    "origin_node_id": "n1", "destination_node_id": "n2",
}
SAILING_B = {
    "id": "sail-b", "vessel_id": "vessel-b",
    "origin_node_id": "n1", "destination_node_id": "n2",
}
SAILING_C = {
    "id": "sail-c", "vessel_id": "vessel-c",
    "origin_node_id": "n1", "destination_node_id": "n2",
}

RULE_GENERAL = {
    "class_id": "general",
    "allowed_modes": ["road", "water"],
    "certification_required": False,
    "human_review_required": False,
}
RULE_FLAMMABLE = {
    "class_id": "flammable",
    "allowed_modes": ["road", "water"],
    "certification_required": True,
    "human_review_required": True,
}
RULE_EXPLOSIVE = {
    "class_id": "explosive",
    "allowed_modes": [],
    "certification_required": True,
    "human_review_required": True,
}
RULE_LIQUID = {
    "class_id": "liquid_bulk",
    "allowed_modes": ["road", "water"],
    "certification_required": True,
    "human_review_required": False,
}

ALL_RULES = [RULE_GENERAL, RULE_FLAMMABLE, RULE_EXPLOSIVE, RULE_LIQUID]
ALL_VESSELS = [VESSEL_NO_CERTS, VESSEL_FLAMMABLE, VESSEL_LIQUID]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_general_cargo_passes_all_sailings():
    """General cargo with no cert requirement → all sailings eligible."""
    sailings = [SAILING_A, SAILING_B, SAILING_C]
    eligible, excluded = apply_hazard_filters("general", sailings, ALL_VESSELS, ALL_RULES)
    assert len(eligible) == 3
    assert excluded == []


def test_mode_not_permitted_excludes_sailing():
    """Explosive with allowed_modes: [] → every sailing excluded for mode_not_permitted_for_class."""
    sailings = [SAILING_A, SAILING_B]
    eligible, excluded = apply_hazard_filters("explosive", sailings, ALL_VESSELS, ALL_RULES)
    assert eligible == []
    assert len(excluded) == 2
    assert all(e["reason"] == "mode_not_permitted_for_class" for e in excluded)


def test_missing_hazmat_cert_excludes_sailing():
    """Flammable cargo: vessel without flammable cert is excluded with missing_hazmat_cert."""
    sailings = [SAILING_A]  # vessel-a has no certs
    eligible, excluded = apply_hazard_filters("flammable", sailings, ALL_VESSELS, ALL_RULES)
    assert eligible == []
    assert len(excluded) == 1
    assert excluded[0]["reason"] == "missing_hazmat_cert"
    assert excluded[0]["sailing_id"] == "sail-a"


def test_certified_vessel_remains_eligible():
    """Flammable cargo: vessel WITH flammable cert stays in eligible list."""
    sailings = [SAILING_B]  # vessel-b has flammable cert
    eligible, excluded = apply_hazard_filters("flammable", sailings, ALL_VESSELS, ALL_RULES)
    assert len(eligible) == 1
    assert eligible[0]["id"] == "sail-b"
    assert excluded == []


def test_unknown_cargo_class_raises_config_error():
    """Unknown cargo class → ConfigError (SC-5)."""
    with pytest.raises(ConfigError):
        apply_hazard_filters("radioactive", [SAILING_A], ALL_VESSELS, ALL_RULES)


def test_mixed_sailings_split_correctly():
    """With flammable rule: cert-less vessel excluded, certified vessel eligible."""
    sailings = [SAILING_A, SAILING_B]  # A has no cert, B has flammable cert
    eligible, excluded = apply_hazard_filters("flammable", sailings, ALL_VESSELS, ALL_RULES)
    assert len(eligible) == 1
    assert eligible[0]["id"] == "sail-b"
    assert len(excluded) == 1
    assert excluded[0]["sailing_id"] == "sail-a"
    assert excluded[0]["reason"] == "missing_hazmat_cert"


# ── Feature 004: vessel-status filters (FR-7, FR-8) ───────────────────────────

def test_suspended_vessel_excluded_for_general_cargo():
    v = {"id": "vessel-a", "hazard_certs": [], "status": "suspended"}
    eligible, excluded = apply_hazard_filters("general", [SAILING_A], [v], [RULE_GENERAL])
    assert eligible == []
    assert excluded[0]["reason"] == "vessel_suspended"
    assert excluded[0]["sailing_id"] == "sail-a"


def test_pending_vessel_excluded_for_hazmat():
    v = {"id": "vessel-b", "hazard_certs": ["flammable"], "status": "pending_verification"}
    eligible, excluded = apply_hazard_filters("flammable", [SAILING_B], [v], [RULE_FLAMMABLE])
    assert eligible == []
    assert excluded[0]["reason"] == "unverified_vessel_for_hazmat"


def test_pending_vessel_eligible_for_general_cargo():
    v = {"id": "vessel-a", "hazard_certs": [], "status": "pending_verification"}
    eligible, excluded = apply_hazard_filters("general", [SAILING_A], [v], [RULE_GENERAL])
    assert len(eligible) == 1 and excluded == []


def test_vessel_without_status_treated_as_verified():
    eligible, _ = apply_hazard_filters("flammable", [SAILING_B], [VESSEL_FLAMMABLE], [RULE_FLAMMABLE])
    assert len(eligible) == 1
