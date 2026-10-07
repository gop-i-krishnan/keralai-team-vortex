"""
backend/engine/tests/test_parser.py
TDD tests for NLP parse engine helpers (pure, no LLM calls).
"""
from backend.engine import parser as p


def test_scrub_pii_removes_phone():
    text = "Call me at 9876543210 for details"
    result = p.scrub_pii(text)
    assert "9876543210" not in result


def test_scrub_pii_removes_email():
    text = "email: john@example.com for booking"
    result = p.scrub_pii(text)
    assert "john@example.com" not in result


def test_regex_parse_extracts_weight():
    text = "I want to ship 10 tonnes from Kochi to Alappuzha by tomorrow"
    result = p.regex_parse(text)
    assert result.get("weight_t") == 10.0


def test_regex_parse_extracts_origin_destination():
    text = "Send 5 tonnes from Thevara to Alleppey"
    result = p.regex_parse(text)
    assert result.get("origin_raw") is not None
    assert result.get("destination_raw") is not None


def test_fuzzy_match_exact():
    nodes = [{"id": "node-001", "name": "Kochi Thevara Jetty", "alternate_names": ["Thevara"]}]
    match = p.fuzzy_match_node("Thevara", nodes)
    assert match is not None
    assert match["id"] == "node-001"


def test_fuzzy_match_typo():
    nodes = [{"id": "node-002", "name": "Alappuzha Boat Jetty", "alternate_names": ["Alleppey"]}]
    match = p.fuzzy_match_node("Alleppy", nodes)  # typo
    assert match is not None
    assert match["id"] == "node-002"


def test_fuzzy_match_no_match():
    nodes = [{"id": "node-001", "name": "Kochi Thevara Jetty", "alternate_names": []}]
    match = p.fuzzy_match_node("Mumbai Central", nodes)
    assert match is None


def test_resolve_deadline_hours():
    result = p.resolve_deadline("by 5 PM today")
    assert result is None or isinstance(result, float)


# ── Feature 004: operator vessel message (SC-2) ───────────────────────────────

def test_vessel_message_hero_example():
    r = p.parse_vessel_message("12 ton barge, Vaikom, free tomorrow, going Alappuzha")
    assert r["capacity_t"] == 12
    assert r["vessel_type"] == "barge"
    assert r["home_raw"].lower() == "vaikom"
    assert r["route_hint_raw"].lower() == "alappuzha"


def test_vessel_message_scrubs_pii_before_parsing():
    r = p.parse_vessel_message("8 tonne boat, Kollam, call 9876543210 or a@b.com")
    assert "9876543210" not in str(r) and "a@b.com" not in str(r)
    assert r["capacity_t"] == 8


def test_vessel_message_garbage_gives_low_confidence_no_exception():
    r = p.parse_vessel_message("hello there")
    assert r["capacity_t"] is None
    assert r["confidence"] < 0.5
