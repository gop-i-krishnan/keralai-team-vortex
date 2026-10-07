"""Feature 005 API tests — milestones, disruption, re-plan gate, notify, summary, reset."""
import copy
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


def book(cargo="cargo-001", sailing="sailing-001", confirm=True, **extra):
    b = client.post("/api/book", json={"cargo_id": cargo, "sailing_id": sailing, **extra}).json()
    if confirm:
        r = client.post(f"/api/book/{b['id']}/confirm")
        assert r.status_code == 200, r.text
    return b["id"]


def to_transit(bid):
    for _ in range(2):
        assert client.post(f"/api/demo/booking/{bid}/advance").status_code == 200


def disrupt(bid, **kw):
    body = {"type": "vessel_breakdown", "expected_duration_h": 4, **kw}
    return client.post(f"/api/demo/booking/{bid}/disrupt", json=body)


def err(r):
    d = r.json()["detail"]
    return d.get("error") if isinstance(d, dict) and "error" in d else d


# ── Booking snapshot ──────────────────────────────────────────────────────────

def test_booking_stores_plan_snapshot_and_event_log():
    bid = book()
    b = client.get(f"/api/booking/{bid}").json()
    for k in ("weight_t", "deadline_h", "ready_time", "planned_cost_inr", "planned_time_h"):
        assert b[k] is not None
    assert b["event_log"] == []
    assert [m["name"] for m in b["milestones"]][0] == "Booked"
    assert b["milestones"][0]["status"] == "current"
    assert all(m["source_status"] == "simulated" for m in b["milestones"])


def test_get_unknown_booking_404():
    assert client.get("/api/booking/nope").status_code == 404


# ── Milestones (SC-6) ─────────────────────────────────────────────────────────

def test_advance_through_all_then_structured_error_sc6():
    bid = book()
    seen = []
    for _ in range(4):
        r = client.post(f"/api/demo/booking/{bid}/advance")
        assert r.status_code == 200 and r.json()["source_status"] == "simulated"
        seen.append(r.json()["current_milestone"])
    assert seen == ["Loading", "In Transit", "Arrived", "Delivered"]
    r = client.post(f"/api/demo/booking/{bid}/advance")
    assert r.status_code == 409 and err(r) == "final_milestone"
    log = client.get(f"/api/booking/{bid}").json()["event_log"]
    assert [e["event_type"] for e in log] == ["milestone_advanced"] * 4


def test_advance_requires_active_booking():
    bid = book(confirm=False)
    assert err(client.post(f"/api/demo/booking/{bid}/advance")) == "booking_not_active"
    assert client.post("/api/demo/booking/nope/advance").status_code == 404


def test_advance_blocked_while_disrupted():
    bid = book(); to_transit(bid); disrupt(bid)
    assert err(client.post(f"/api/demo/booking/{bid}/advance")) == "booking_disrupted"


# ── Disruption trigger ────────────────────────────────────────────────────────

def test_disrupt_sets_status_returns_notification_and_severity():
    bid = book(); to_transit(bid)
    r = disrupt(bid)
    assert r.status_code == 201
    d = r.json()
    assert d["disruption"]["source_status"] == "simulated"
    assert d["disruption"]["severity"] in ("minor", "moderate", "severe")
    assert d["disruption"]["location_node_id"] == "node-004"       # In Transit -> Vaikom
    assert d["notification"]["delivered"] is False
    assert d["booking"]["status"] == "disrupted"
    log = [e["event_type"] for e in d["booking"]["event_log"]]
    assert log[-1] == "disruption_recorded"


def test_disrupt_validation_and_state_errors():
    bid = book(); to_transit(bid)
    assert client.post(f"/api/demo/booking/{bid}/disrupt", json={"type": "meteor"}).status_code == 422
    r = disrupt(bid, expected_duration_h=-1)
    assert r.status_code == 422 and r.json()["detail"]["errors"][0]["code"] == "invalid_duration"
    r = disrupt(bid, location_node_id="node-999")
    assert r.status_code == 422 and r.json()["detail"]["errors"][0]["code"] == "not_found"
    assert disrupt(bid).status_code == 201
    assert err(disrupt(bid)) == "disruption_already_open"
    pending = book("cargo-011", confirm=False)
    assert err(disrupt(pending)) == "booking_not_disruptable"
    assert disrupt("nope").status_code == 404


def test_scenarios_listed_and_applicable():
    s = client.get("/api/demo/disruption-scenarios").json()
    assert len(s["scenarios"]) >= 2 and s["source_status"] == "simulated"
    bid = book(); to_transit(bid)
    r = client.post(f"/api/demo/booking/{bid}/disrupt", json={"scenario_id": s["scenarios"][0]["id"]})
    assert r.status_code == 201 and r.json()["disruption"]["type"] == "vessel_breakdown"


def test_unknown_scenario_422():
    bid = book(); to_transit(bid)
    assert client.post(f"/api/demo/booking/{bid}/disrupt", json={"scenario_id": "scn-999"}).status_code == 422


# ── Re-plan gate (SC-3, P12) ──────────────────────────────────────────────────

def test_propose_leaves_booking_unchanged_sc3_and_is_idempotent():
    bid = book(); to_transit(bid); disrupt(bid)
    before = copy.deepcopy(ds.get_booking_by_id(bid))
    r = client.post(f"/api/replan/{bid}", json={"human_confirmed": True})
    assert r.status_code == 200
    p = r.json()
    assert ds.get_booking_by_id(bid) == before
    assert before["status"] == "disrupted"
    assert len(p["alternatives"]) >= 2 and p["source_status"] == "simulated"
    again = client.post(f"/api/replan/{bid}").json()
    assert again["proposal_id"] == p["proposal_id"]
    assert ds.get_booking_by_id(bid) == before


def test_propose_requires_disrupted_booking():
    bid = book()
    assert err(client.post(f"/api/replan/{bid}")) == "booking_not_disrupted"
    assert client.post("/api/replan/nope").status_code == 404


def test_confirm_without_proposal_and_unknown_alternative():
    bid = book(); to_transit(bid); disrupt(bid)
    assert err(client.post(f"/api/replan/{bid}/confirm", json={"alternative_id": "alt-truck_from_jetty"})) == "no_proposal"
    client.post(f"/api/replan/{bid}")
    r = client.post(f"/api/replan/{bid}/confirm", json={"alternative_id": "alt-nonsense"})
    assert r.status_code == 422 and err(r) == "unknown_alternative"
    assert ds.get_booking_by_id(bid)["status"] == "disrupted"


def test_confirm_applies_choice_logs_and_blocks_repeat():
    bid = book(); to_transit(bid); disrupt(bid)
    p = client.post(f"/api/replan/{bid}").json()
    alt = p["alternatives"][0]
    r = client.post(f"/api/replan/{bid}/confirm", json={"alternative_id": alt["id"]})
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "replanned"
    assert b["resolution"]["type"] == alt["type"]
    types = [e["event_type"] for e in b["event_log"]]
    assert types[-3:] == ["replan_proposed", "replan_confirmed", "notification_preview"]
    r2 = client.post(f"/api/replan/{bid}/confirm", json={"alternative_id": alt["id"]})
    assert r2.status_code == 409 and err(r2) == "replan_already_confirmed"
    assert [e["event_type"] for e in ds.get_booking_by_id(bid)["event_log"]].count("replan_confirmed") == 1


def test_confirm_stale_proposal_after_new_disruption():
    bid = book(); to_transit(bid); disrupt(bid)
    p = client.post(f"/api/replan/{bid}").json()
    client.post(f"/api/replan/{bid}/confirm", json={"alternative_id": p["alternatives"][0]["id"]})
    disrupt(bid, type="weather_delay")          # second disruption on a replanned booking
    r = client.post(f"/api/replan/{bid}/confirm", json={"alternative_id": p["alternatives"][0]["id"]})
    assert r.status_code == 409 and err(r) == "proposal_stale"


def test_hazardous_replan_needs_compliance_review():
    # flammable cargo-003 booked on the flammable-certified vessel-003 sailing
    ds.add_sailing({"id": "sailing-h", "vessel_id": "vessel-003", "origin_node_id": "node-001",
                    "destination_node_id": "node-002", "route_node_ids": ["node-001", "node-004", "node-002"],
                    "departure_time": "06:00", "days": ["Mon"], "available_capacity_t": 20})
    b = client.post("/api/book", json={"cargo_id": "cargo-003", "sailing_id": "sailing-h"}).json()
    assert b["status"] == "pending_review"
    client.post(f"/api/compliance/review/{b['id']}/approve", json={"reviewer_note": "ok"})
    assert client.post(f"/api/book/{b['id']}/confirm").status_code == 200
    to_transit(b["id"]); disrupt(b["id"])
    p = client.post(f"/api/replan/{b['id']}").json()
    assert p["compliance_review_required"] is True
    alt = p["alternatives"][0]["id"]
    r = client.post(f"/api/replan/{b['id']}/confirm", json={"alternative_id": alt})
    assert r.status_code == 400 and err(r) == "compliance_review_required"
    ok = client.post(f"/api/compliance/replan-review/{p['proposal_id']}/approve", json={"reviewer_note": "reviewed"})
    assert ok.status_code == 200 and ok.json()["source_status"] == "simulated"
    again = client.post(f"/api/compliance/replan-review/{p['proposal_id']}/approve", json={"reviewer_note": "x"})
    assert again.status_code == 409 and err(again) == "compliance_already_reviewed"
    assert client.post(f"/api/replan/{b['id']}/confirm", json={"alternative_id": alt}).status_code == 200


def test_replan_review_not_required_for_general():
    bid = book(); to_transit(bid); disrupt(bid)
    p = client.post(f"/api/replan/{bid}").json()
    r = client.post(f"/api/compliance/replan-review/{p['proposal_id']}/approve", json={"reviewer_note": "x"})
    assert r.status_code == 400 and err(r) == "review_not_required_for_class"


# ── Notify (SC-7) ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("t", ["vessel_breakdown", "low_depth", "jetty_closed", "road_blocked", "weather_delay"])
def test_notify_preview_for_each_type_sc7(t):
    ds.reset()
    bid = book(); to_transit(bid)
    assert disrupt(bid, type=t).status_code == 201
    r = client.post(f"/api/booking/{bid}/notify")
    assert r.status_code == 200
    d = r.json()
    assert d["delivered"] is False and d["preview"] and "[simulated]" in d["note"]


def test_notify_without_disruption_conflicts():
    bid = book()
    assert err(client.post(f"/api/booking/{bid}/notify")) == "no_disruption"


# ── Summary ───────────────────────────────────────────────────────────────────

def test_summary_empty_then_counts():
    s = client.get("/api/disruptions/summary").json()
    assert s["rows"] == [] and s["source_status"] == "simulated"
    bid = book(); to_transit(bid); disrupt(bid)
    rows = client.get("/api/disruptions/summary").json()["rows"]
    assert rows == [{"disruption_type": "vessel_breakdown", "corridor_id": "corridor-001",
                     "count": 1, "source_status": "simulated"}]


# ── Cargo creation (needed by the Post-cargo UI) ──────────────────────────────

def test_post_cargo_valid_and_invalid():
    ok = client.post("/api/cargo", json={"description": "Tiles", "weight_t": 6, "cargo_class": "general",
                                         "origin_node_id": "node-001", "destination_node_id": "node-002"})
    assert ok.status_code == 201 and ok.json()["source_status"] == "simulated"
    bad = client.post("/api/cargo", json={"description": "", "weight_t": 0, "cargo_class": "radioactive",
                                          "origin_node_id": "node-001", "destination_node_id": "node-001"})
    codes = {(e["field"], e["code"]) for e in bad.json()["detail"]["errors"]}
    assert bad.status_code == 422
    assert {("description", "required"), ("weight_t", "not_positive"),
            ("cargo_class", "invalid_class"), ("destination_node_id", "same_as_origin")} <= codes


# ── Reset (SC-8) ──────────────────────────────────────────────────────────────

def test_full_cycle_then_reset_restores_seed_sc8():
    bid = book(); to_transit(bid); disrupt(bid)
    p = client.post(f"/api/replan/{bid}").json()
    client.post(f"/api/replan/{bid}/confirm", json={"alternative_id": p["alternatives"][0]["id"]})
    client.post("/api/demo/reset")
    assert ds.get_booking_by_id(bid) is None
    assert client.get("/api/disruptions/summary").json()["rows"] == []
    assert ds.get_cargo()[0]["id"] == "cargo-001"
    bid2 = book()
    assert client.get(f"/api/booking/{bid2}").json()["status"] == "confirmed"
    assert client.get(f"/api/booking/{bid2}").json()["milestones"][0]["status"] == "current"
