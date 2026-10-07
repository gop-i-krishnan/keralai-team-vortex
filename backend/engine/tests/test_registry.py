"""Feature 004 — registration validation and vessel lifecycle (FR-1, FR-4, SC-6)."""
import pytest
from backend.engine import registry

NODES = {"node-001", "node-002", "node-004"}
OPS = {"op-001"}
CLASSES = {"general", "flammable", "liquid_bulk"}


def _ok(**kw):
    p = {"vessel_name": "MV Test", "capacity_t": 10, "draft_m": 1.5,
         "home_jetty_id": "node-001", "contact": "simulated@op.example", "operator_id": "op-001"}
    p.update(kw)
    return p


def _errs(p, existing=()):
    return registry.validate_registration(p, NODES, OPS, CLASSES, list(existing))


def test_valid_minimal_registration():
    assert _errs(_ok()) == []


@pytest.mark.parametrize("field,value,code", [
    ("vessel_name", "", "required"),
    ("vessel_name", "   ", "required"),
    ("capacity_t", 0, "not_positive"),
    ("capacity_t", -3, "not_positive"),
    ("draft_m", 0, "not_positive"),
    ("home_jetty_id", "node-999", "not_found"),
    ("contact", "", "required"),
    ("operator_id", "op-404", "not_found"),
])
def test_each_invalid_field_reports_its_own_error(field, value, code):
    errs = _errs(_ok(**{field: value}))
    assert [(e["field"], e["code"]) for e in errs] == [(field, code)]
    assert errs[0]["message"]


def test_missing_field_reports_required():
    p = _ok()
    del p["draft_m"]
    assert [(e["field"], e["code"]) for e in _errs(p)] == [("draft_m", "required")]


def test_non_numeric_capacity():
    assert _errs(_ok(capacity_t="abc"))[0]["code"] == "not_positive"


def test_unknown_hazard_cert():
    errs = _errs(_ok(hazard_certs=["radioactive"]))
    assert errs[0]["field"] == "hazard_certs" and errs[0]["code"] == "invalid_class"


def test_duplicate_vessel():
    existing = [{"name": "MV Test", "home_jetty_id": "node-001"}]
    errs = _errs(_ok(), existing)
    assert errs[0]["code"] == "duplicate_vessel"


def _sail(**kw):
    p = {"vessel_id": "v", "route_node_ids": ["node-001", "node-002"], "weekdays": ["Mon"],
         "departure_time": "06:00", "price_per_t": 400, "capacity_offered_t": 8}
    p.update(kw)
    return p


VESSEL = {"id": "v", "capacity_t": 10, "status": "verified"}


def test_valid_sailing():
    assert registry.validate_sailing(_sail(), VESSEL, NODES) == []


@pytest.mark.parametrize("kw,field,code", [
    ({"route_node_ids": ["node-001"]}, "route_node_ids", "too_few_stops"),
    ({"route_node_ids": ["node-001", "node-999"]}, "route_node_ids", "not_found"),
    ({"weekdays": []}, "weekdays", "required"),
    ({"weekdays": ["Funday"]}, "weekdays", "invalid_day"),
    ({"departure_time": "25:00"}, "departure_time", "invalid_time"),
    ({"price_per_t": 0}, "price_per_t", "not_positive"),
    ({"capacity_offered_t": 0}, "capacity_offered_t", "not_positive"),
    ({"capacity_offered_t": 11}, "capacity_offered_t", "exceeds_vessel_capacity"),
])
def test_sailing_validation(kw, field, code):
    errs = registry.validate_sailing(_sail(**kw), VESSEL, NODES)
    assert (errs[0]["field"], errs[0]["code"]) == (field, code)


def test_sailing_for_suspended_vessel():
    errs = registry.validate_sailing(_sail(), {**VESSEL, "status": "suspended"}, NODES)
    assert errs[0]["code"] == "vessel_suspended"


@pytest.mark.parametrize("cur,act,new", [
    ("draft", "submit", "pending_verification"),
    ("pending_verification", "verify", "verified"),
    ("verified", "suspend", "suspended"),
    ("suspended", "reinstate", "verified"),
])
def test_valid_transitions(cur, act, new):
    assert registry.transition_status(cur, act) == new


@pytest.mark.parametrize("cur,act", [
    ("verified", "verify"), ("suspended", "suspend"), ("pending_verification", "suspend"),
    ("draft", "verify"), ("suspended", "verify"), ("verified", "reinstate"),
])
def test_invalid_transitions_raise_named_error(cur, act):
    with pytest.raises(registry.InvalidTransition):
        registry.transition_status(cur, act)


def test_legacy_vessel_without_status_is_verified():
    assert registry.effective_status({"id": "x"}) == "verified"
    assert registry.effective_status({"status": "suspended"}) == "suspended"
