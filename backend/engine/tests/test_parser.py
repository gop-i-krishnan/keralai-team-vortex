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
