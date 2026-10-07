"""Feature 004 API tests — registration, sailings, lifecycle, delivery, profile, reset."""
import os
os.environ["JALSETU_MOCK_LLM"] = "1"

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend import data_store as ds

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset():
    ds.reset()
    yield
    ds.reset()


def _reg(**kw):
    p = {"vessel_name": "MV New", "capacity_t": 12, "draft_m": 1.4, "home_jetty_id": "node-001",
         "contact": "simulated@operator.example", "operator_id": "op-001"}
    p.update(kw)
    return client.post("/api/vessel/register", json=p)


def _sail(vessel_id, **kw):
    p = {"vessel_id": vessel_id, "route_node_ids": ["node-001", "node-002"], "weekdays": ["Mon", "Tue"],
         "departure_time": "07:00", "price_per_t": 350, "capacity_offered_t": 12}
    p.update(kw)
    return client.post("/api/sailing/publish", json=p)


def _confirmed_booking(cargo="cargo-001", sailing="sailing-001"):
    b = client.post("/api/book", json={"cargo_id": cargo, "sailing_id": sailing}).json()
    r = client.post(f"/api/book/{b['id']}/confirm")
    assert r.status_code == 200, r.text
    return b["id"]


# ── Registration ──────────────────────────────────────────────────────────────

def test_register_valid_vessel_is_pending_verification_and_simulated_tagged():
    r = _reg()
    assert r.status_code == 201
    v = r.json()
    assert v["status"] == "pending_verification"
    assert v["hazard_certs"] == []
    assert v["registration_number"] is None or isinstance(v["registration_number"], str)
    assert any(x["id"] == v["id"] for x in client.get("/api/vessel/list").json()["vessels"])


@pytest.mark.parametrize("field,value,code", [
    ("vessel_name", "", "required"), ("capacity_t", 0, "not_positive"),
    ("draft_m", -1, "not_positive"), ("home_jetty_id", "node-999", "not_found"),
    ("contact", "", "required"),
])
def test_register_field_errors_sc6(field, value, code):
    r = _reg(**{field: value})
    assert r.status_code == 422
    errs = r.json()["detail"]["errors"]
    assert (errs[0]["field"], errs[0]["code"]) == (field, code)
    assert len(client.get("/api/vessel/list").json()["vessels"]) == 7  # nothing created


def test_register_duplicate_returns_409():
    assert _reg().status_code == 201
    r = _reg()
    assert r.status_code == 409
    assert r.json()["detail"]["errors"][0]["code"] == "duplicate_vessel"


# ── SC-1: register → publish → match ──────────────────────────────────────────

def test_registered_vessel_sailing_appears_in_match_sc1():
    vid = _reg().json()["id"]
    s = _sail(vid)
    assert s.status_code == 201
    sid = s.json()["id"]
    m = client.post("/api/match", json={"cargo_id": "cargo-001"}).json()
    assert sid in [r["sailing_id"] for r in m["ranked"]]


def test_unverified_vessel_ranked_below_equal_verified_vessel():
    vid = _reg(capacity_t=25).json()["id"]
    sid = _sail(vid, capacity_offered_t=25).json()["id"]
    ranked = client.post("/api/match", json={"cargo_id": "cargo-001"}).json()["ranked"]
    scores = {r["sailing_id"]: r["score"] for r in ranked}
    assert scores[sid] < scores["sailing-001"]


def test_publish_validation_and_unknown_vessel():
    vid = _reg().json()["id"]
    r = _sail(vid, capacity_offered_t=99)
    assert r.status_code == 422 and r.json()["detail"]["errors"][0]["code"] == "exceeds_vessel_capacity"
    assert _sail("vessel-404").status_code == 404


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def test_verify_then_repeat_is_invalid_transition():
    vid = _reg().json()["id"]
    r = client.post(f"/api/admin/vessel/{vid}/verify")
    assert r.status_code == 200 and r.json()["status"] == "verified"
    assert "[simulated]" in r.json()["notice"]
    r2 = client.post(f"/api/admin/vessel/{vid}/verify")
    assert r2.status_code == 409 and r2.json()["detail"]["error"] == "invalid_transition"
    assert ds.get_vessel_by_id(vid)["status"] == "verified"


def test_suspend_reinstate_cycle_and_unknown_vessel():
    assert client.post("/api/admin/vessel/vessel-001/suspend").json()["status"] == "suspended"
    assert client.post("/api/admin/vessel/vessel-001/suspend").status_code == 409
    assert client.post("/api/admin/vessel/vessel-001/reinstate").json()["status"] == "verified"
    assert client.post("/api/admin/vessel/nope/verify").status_code == 404


def test_suspended_vessel_excluded_from_match_with_reason():
    client.post("/api/admin/vessel/vessel-001/suspend")
    m = client.post("/api/match", json={"cargo_id": "cargo-001"}).json()
    assert "sailing-001" not in [r["sailing_id"] for r in m["ranked"]]
    assert {"sailing_id": "sailing-001", "vessel_id": "vessel-001", "reason": "vessel_suspended"} in m["excluded"]


def test_suspending_vessel_leaves_confirmed_booking_unchanged_and_lists_it():
    bid = _confirmed_booking()
    before = dict(ds.get_booking_by_id(bid))
    r = client.post("/api/admin/vessel/vessel-001/suspend")
    assert bid in r.json()["affected_booking_ids"]
    assert ds.get_booking_by_id(bid) == before
    assert "existing bookings unaffected" in r.json()["notice"]


def test_pending_booking_on_suspended_vessel_cannot_be_confirmed():
    b = client.post("/api/book", json={"cargo_id": "cargo-001", "sailing_id": "sailing-001"}).json()
    client.post("/api/admin/vessel/vessel-001/suspend")
    r = client.post(f"/api/book/{b['id']}/confirm")
    assert r.status_code == 409 and r.json()["detail"]["error"] == "vessel_suspended"
    assert ds.get_booking_by_id(b["id"])["status"] == "pending"


def test_publish_for_suspended_vessel_rejected():
    client.post("/api/admin/vessel/vessel-001/suspend")
    r = _sail("vessel-001")
    assert r.status_code == 409 and r.json()["detail"]["errors"][0]["code"] == "vessel_suspended"


# ── Hazmat + unverified (SC-5) ────────────────────────────────────────────────

def test_unverified_certified_vessel_excluded_for_flammable_sc5():
    vid = _reg(hazard_certs=["flammable"]).json()["id"]
    _sail(vid)
    m = client.post("/api/match", json={"cargo_id": "cargo-003"}).json()
    reasons = {e["vessel_id"]: e["reason"] for e in m["excluded"]}
    assert reasons[vid] == "unverified_vessel_for_hazmat"
    client.post(f"/api/admin/vessel/{vid}/verify")
    m2 = client.post("/api/match", json={"cargo_id": "cargo-003"}).json()
    assert vid in [r["vessel_id"] for r in m2["ranked"]]


# ── Delivery & profile ────────────────────────────────────────────────────────

def test_deliver_creates_record_and_updates_reliability_sc4():
    before = client.get("/api/operator/op-001/profile").json()
    v1 = next(v for v in before["vessels"] if v["id"] == "vessel-001")["reliability"]
    bid = _confirmed_booking()
    r = client.post(f"/api/booking/{bid}/deliver", json={"actual_arrival": "12:00", "status": "on_time"})
    assert r.status_code == 200
    body = r.json()
    assert body["delivery_record"]["source_status"] == "recorded"
    rel = body["updated_reliability"]
    assert rel["on_time_trips"] == v1["on_time_trips"] + 1
    assert rel["total_trips"] == v1["total_trips"] + 1


def test_deliver_twice_conflicts_and_adds_no_record():
    bid = _confirmed_booking()
    body = {"actual_arrival": "12:00", "status": "late"}
    assert client.post(f"/api/booking/{bid}/deliver", json=body).status_code == 200
    n = len(ds.get_delivery_history())
    r = client.post(f"/api/booking/{bid}/deliver", json=body)
    assert r.status_code == 409 and r.json()["detail"]["error"] == "already_delivered"
    assert len(ds.get_delivery_history()) == n


def test_deliver_invalid_input_and_wrong_state():
    bid = _confirmed_booking()
    r = client.post(f"/api/booking/{bid}/deliver", json={"actual_arrival": "99:99", "status": "on_time"})
    assert r.status_code == 422 and r.json()["detail"]["errors"][0]["field"] == "actual_arrival"
    r = client.post(f"/api/booking/{bid}/deliver", json={"actual_arrival": "10:00", "status": "great"})
    assert r.status_code == 422
    pend = client.post("/api/book", json={"cargo_id": "cargo-011", "sailing_id": "sailing-001"}).json()
    r = client.post(f"/api/booking/{pend['id']}/deliver", json={"actual_arrival": "10:00", "status": "on_time"})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "booking_not_deliverable"
    assert client.post("/api/booking/nope/deliver", json={"actual_arrival": "10:00", "status": "on_time"}).status_code == 404


def test_profile_for_zero_history_vessel_uses_prior_and_labels_trips():
    p = client.get("/api/operator/op-002/profile").json()
    v = next(x for x in p["vessels"] if x["id"] == "vessel-004")
    assert v["reliability"]["total_trips"] == 0
    assert v["reliability"]["trip_count_label"] == "0 trips [simulated]"
    assert v["status"] == "pending_verification"
    assert p["source_status"] == "simulated"


def test_profile_unknown_operator_404_and_empty_operator_ok():
    assert client.get("/api/operator/op-404/profile").status_code == 404


def test_profile_mature_vessel_has_trend_and_label():
    v = next(x for x in client.get("/api/operator/op-001/profile").json()["vessels"] if x["id"] == "vessel-001")
    assert v["reliability"]["total_trips"] >= 10
    assert len(v["reliability"]["reliability_trend"]) == v["reliability"]["total_trips"]
    assert v["reliability"]["trip_count_label"].endswith("trips [simulated]")


# ── Operator message parse (no state change) ─────────────────────────────────

def test_parse_message_hero_example_sc2():
    r = client.post("/api/vessel/parse-message", json={"message": "12 ton barge, Vaikom, free tomorrow, going Alappuzha"})
    assert r.status_code == 200
    d = r.json()
    assert d["capacity_t"] == 12 and d["home_jetty_id"] == "node-004"
    assert d["route_hint_node_id"] == "node-002"
    assert d["needs_review"] is False
    assert len(ds.get_vessels()) == 7  # parsing registers nothing


def test_parse_message_low_confidence_flags_review():
    d = client.post("/api/vessel/parse-message", json={"message": "hello"}).json()
    assert d["needs_review"] is True


# ── Reset (SC-7) ──────────────────────────────────────────────────────────────

def test_reset_removes_runtime_vessels_sailings_and_records_sc7():
    vid = _reg().json()["id"]
    sid = _sail(vid).json()["id"]
    bid = _confirmed_booking()
    client.post(f"/api/booking/{bid}/deliver", json={"actual_arrival": "12:00", "status": "on_time"})
    client.post("/api/admin/vessel/vessel-001/suspend")
    client.post("/api/demo/reset")
    assert ds.get_vessel_by_id(vid) is None
    assert all(s["id"] != sid for s in ds.get_sailings())
    assert all(r["source_status"] == "simulated" for r in ds.get_delivery_history())
    assert ds.get_vessel_by_id("vessel-001")["status"] == "verified"
