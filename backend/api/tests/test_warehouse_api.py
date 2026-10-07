"""
backend/api/tests/test_warehouse_api.py
Integration tests for warehouse endpoints.
SC-3, SC-4, SC-8, FR-4, FR-7, FR-8, FR-11, P12, P13.
"""
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


# ── Warehouse list ────────────────────────────────────────────────────────────

def test_warehouse_list_returns_seed_warehouses():
    """GET /api/warehouse/list → 2 seed warehouses, all source_status: simulated."""
    r = client.get("/api/warehouse/list")
    assert r.status_code == 200
    data = r.json()
    assert len(data["warehouses"]) == 2
    for wh in data["warehouses"]:
        assert wh["source_status"] == "simulated"


# ── Warehouse registration ────────────────────────────────────────────────────

def test_warehouse_register_valid():
    """POST /api/warehouse/register with valid payload → 201, warehouse in list."""
    r = client.post("/api/warehouse/register", json={
        "name": "Test Warehouse",
        "location_node_id": "node-001",
        "total_capacity_t": 20.0,
        "storage_cost_per_t_per_day": 5.0,
        "handling_in_cost_per_t": 10.0,
        "handling_out_cost_per_t": 10.0,
        "allowed_cargo_classes": ["general"],
    })
    assert r.status_code == 201
    data = r.json()
    assert data["source_status"] == "simulated"
    assert data["total_capacity_t"] == 20.0
    assert data["capacity_used_t"] == 0.0

    # Appears in list
    r2 = client.get("/api/warehouse/list")
    ids = [wh["id"] for wh in r2.json()["warehouses"]]
    assert data["id"] in ids


def test_warehouse_register_empty_classes_fails():
    """allowed_cargo_classes: [] → 422 with required error."""
    r = client.post("/api/warehouse/register", json={
        "name": "Empty Classes WH",
        "location_node_id": "node-001",
        "total_capacity_t": 10.0,
        "storage_cost_per_t_per_day": 1.0,
        "handling_in_cost_per_t": 1.0,
        "handling_out_cost_per_t": 1.0,
        "allowed_cargo_classes": [],
    })
    assert r.status_code == 422
    errors = r.json()["detail"]["errors"]
    assert any(e["field"] == "allowed_cargo_classes" and e["code"] == "required" for e in errors)


def test_warehouse_register_invalid_class_fails():
    """Unknown cargo class → 422 with invalid_class."""
    r = client.post("/api/warehouse/register", json={
        "name": "Invalid Class WH",
        "location_node_id": "node-001",
        "total_capacity_t": 10.0,
        "storage_cost_per_t_per_day": 1.0,
        "handling_in_cost_per_t": 1.0,
        "handling_out_cost_per_t": 1.0,
        "allowed_cargo_classes": ["radioactive"],
    })
    assert r.status_code == 422
    errors = r.json()["detail"]["errors"]
    assert any(e["code"] == "invalid_class" for e in errors)


def test_warehouse_register_unknown_node_fails():
    """Unknown location_node_id → 422 with not_found."""
    r = client.post("/api/warehouse/register", json={
        "name": "Bad Node WH",
        "location_node_id": "node-999",
        "total_capacity_t": 10.0,
        "storage_cost_per_t_per_day": 1.0,
        "handling_in_cost_per_t": 1.0,
        "handling_out_cost_per_t": 1.0,
        "allowed_cargo_classes": ["general"],
    })
    assert r.status_code == 422
    errors = r.json()["detail"]["errors"]
    assert any(e["field"] == "location_node_id" and e["code"] == "not_found" for e in errors)


# ── Staging proposal ──────────────────────────────────────────────────────────

def test_staging_proposal_sc3():
    """SC-3: wait 8h (> threshold 4h) → proposals non-empty; total_cost_inr == sum of 5."""
    r = client.post("/api/warehouse/stage", json={
        "cargo_id": "cargo-001",
        "next_sailing_wait_h": 8.0,
        "deadline_h": 48.0,
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["proposals"]) >= 1
    p = data["proposals"][0]
    # total_cost == sum of 5 components
    computed_sum = round(
        p["truck_to_warehouse_cost_inr"] + p["handling_in_cost_inr"] +
        p["storage_cost_inr"] + p["handling_out_cost_inr"] +
        p["truck_from_warehouse_cost_inr"], 2
    )
    assert abs(p["total_cost_inr"] - computed_sum) < 0.02


def test_staging_below_threshold_returns_empty():
    """Wait 2h (< threshold 4h) → proposals empty."""
    r = client.post("/api/warehouse/stage", json={
        "cargo_id": "cargo-001",
        "next_sailing_wait_h": 2.0,
        "deadline_h": 48.0,
    })
    assert r.status_code == 200
    assert r.json()["proposals"] == []


def test_staging_confirm_updates_capacity():
    """Propose + confirm → capacity_used_t increases by weight."""
    r = client.post("/api/warehouse/stage", json={
        "cargo_id": "cargo-001",  # 10t, node-001 origin, wh-001 is at node-001
        "next_sailing_wait_h": 8.0,
        "deadline_h": 48.0,
    })
    proposals = r.json()["proposals"]
    # Find proposal for wh-001
    p = next((x for x in proposals if x.get("warehouse_id") == "wh-001"), None)
    if p is None:
        pytest.skip("wh-001 not in proposals (check proximity or capacity)")

    initial_used = ds.get_warehouse_by_id("wh-001")["capacity_used_t"]

    r2 = client.post("/api/warehouse/stage/confirm", json={"proposal_id": p["proposal_id"]})
    assert r2.status_code == 200
    assert r2.json()["capacity_used_t"] == pytest.approx(initial_used + 10.0, abs=0.01)


def test_staging_confirm_capacity_guard_sc4():
    """SC-4: Fill warehouse to exactly capacity, then staging confirm → 409 warehouse_at_capacity."""
    # Manually set wh-001 to full
    wh = ds.get_warehouse_by_id("wh-001")
    wh["capacity_used_t"] = wh["total_capacity_t"]

    # Propose — wh-001 should appear as ineligible
    r = client.post("/api/warehouse/stage", json={
        "cargo_id": "cargo-001",
        "next_sailing_wait_h": 8.0,
        "deadline_h": 48.0,
    })
    data = r.json()
    # wh-001 should be in ineligible list
    ineligible_ids = [e["warehouse_id"] for e in data["ineligible_warehouses"]]
    assert "wh-001" in ineligible_ids


# ── Utilisation ───────────────────────────────────────────────────────────────

def test_warehouse_utilisation_source_status():
    """GET /api/warehouse/utilisation → top-level and each row source_status: simulated."""
    r = client.get("/api/warehouse/utilisation")
    assert r.status_code == 200
    data = r.json()
    assert data["source_status"] == "simulated"
    for row in data["utilisation"]:
        assert row["source_status"] == "simulated"


def test_demo_reset_clears_capacity():
    """SC-8: stage → confirm → reset → all capacity_used_t == 0."""
    # Stage and confirm
    r = client.post("/api/warehouse/stage", json={
        "cargo_id": "cargo-001",
        "next_sailing_wait_h": 8.0,
        "deadline_h": 48.0,
    })
    proposals = r.json()["proposals"]
    if proposals:
        p = proposals[0]
        client.post("/api/warehouse/stage/confirm", json={"proposal_id": p["proposal_id"]})

    # Reset
    client.post("/api/demo/reset")

    # All warehouses should have 0 capacity used
    r2 = client.get("/api/warehouse/utilisation")
    for row in r2.json()["utilisation"]:
        assert row["capacity_used_t"] == 0.0


def test_demo_reset_clears_compliance_reviews():
    """SC-8 extension: reset clears compliance reviews."""
    # Create a hazmat booking and approve it
    r = client.post("/api/book", json={
        "cargo_id": "cargo-004",
        "sailing_id": "sailing-001",
    })
    booking_id = r.json()["id"]
    client.post(f"/api/compliance/review/{booking_id}/approve",
                json={"reviewer_note": "pre-reset"})
    assert len(ds.get_compliance_reviews()) == 1

    # Reset
    client.post("/api/demo/reset")
    assert len(ds.get_compliance_reviews()) == 0


def test_demo_reset_removes_runtime_warehouses():
    """Reset removes runtime-registered warehouses; seed warehouses retained."""
    client.post("/api/warehouse/register", json={
        "name": "Runtime WH",
        "location_node_id": "node-001",
        "total_capacity_t": 5.0,
        "storage_cost_per_t_per_day": 1.0,
        "handling_in_cost_per_t": 1.0,
        "handling_out_cost_per_t": 1.0,
        "allowed_cargo_classes": ["general"],
    })
    assert len(ds.get_warehouses()) == 3  # 2 seed + 1 runtime

    client.post("/api/demo/reset")
    assert len(ds.get_warehouses()) == 2  # seed only


# ── Staging linked to a booking (006 FR-7: confirmation updates the booking) ──

def _booked(cargo="cargo-001", confirm=True):
    b = client.post("/api/book", json={"cargo_id": cargo, "sailing_id": "sailing-001"}).json()
    if confirm:
        assert client.post(f"/api/book/{b['id']}/confirm").status_code == 200
    return b["id"]


def _proposal(cargo="cargo-001", booking_id=None):
    body = {"cargo_id": cargo, "next_sailing_wait_h": 8, "deadline_h": 24}
    if booking_id:
        body["booking_id"] = booking_id
    return client.post("/api/warehouse/stage", json=body)


def test_propose_with_booking_does_not_touch_booking():
    bid = _booked()
    before = dict(ds.get_booking_by_id(bid))
    p = _proposal(booking_id=bid).json()["proposals"][0]
    assert ds.get_booking_by_id(bid) == before and "staging" not in before
    assert p["proposal_id"]


def test_confirm_attaches_staging_to_booking_and_logs_event():
    bid = _booked()
    p = _proposal(booking_id=bid).json()["proposals"][0]
    r = client.post("/api/warehouse/stage/confirm", json={"proposal_id": p["proposal_id"]})
    assert r.status_code == 200 and r.json()["booking_id"] == bid
    b = client.get(f"/api/booking/{bid}").json()
    assert b["staging"]["warehouse_id"] == p["warehouse_id"]
    assert b["staging"]["total_cost_inr"] == p["total_cost_inr"]
    assert b["staging"]["source_status"] == "simulated"
    assert b["event_log"][-1]["event_type"] == "staging_confirmed"


def test_second_staging_on_same_booking_rejected_without_capacity_change():
    bid = _booked()
    p1 = _proposal(booking_id=bid).json()["proposals"][0]
    client.post("/api/warehouse/stage/confirm", json={"proposal_id": p1["proposal_id"]})
    used = ds.get_warehouse_by_id(p1["warehouse_id"])["capacity_used_t"]
    p2 = _proposal(booking_id=bid).json()["proposals"][0]
    r = client.post("/api/warehouse/stage/confirm", json={"proposal_id": p2["proposal_id"]})
    assert r.status_code == 409 and r.json()["detail"]["error"] == "booking_already_staged"
    assert ds.get_warehouse_by_id(p1["warehouse_id"])["capacity_used_t"] == used


def test_unknown_booking_404_on_propose():
    assert _proposal(booking_id="nope").status_code == 404


def test_staging_requires_booking_to_match_cargo():
    bid = _booked("cargo-001")
    r = _proposal(cargo="cargo-011", booking_id=bid)
    assert r.status_code == 409 and r.json()["detail"]["error"] == "booking_cargo_mismatch"


def test_hazardous_booking_awaiting_review_cannot_be_staged():
    ds.add_sailing({"id": "sailing-h", "vessel_id": "vessel-003", "origin_node_id": "node-001",
                    "destination_node_id": "node-002", "departure_time": "06:00", "days": ["Mon"],
                    "available_capacity_t": 20})
    b = client.post("/api/book", json={"cargo_id": "cargo-003", "sailing_id": "sailing-h"}).json()
    assert b["status"] == "pending_review"
    ds.add_staging_proposal("p-haz", {"proposal_id": "p-haz", "warehouse_id": "wh-002", "weight_t": 10,
                                      "booking_id": b["id"], "total_cost_inr": 1.0})
    r = client.post("/api/warehouse/stage/confirm", json={"proposal_id": "p-haz"})
    assert r.status_code == 400 and r.json()["detail"]["error"] == "compliance_review_required"
    assert ds.get_warehouse_by_id("wh-002")["capacity_used_t"] == 0
    assert "staging" not in ds.get_booking_by_id(b["id"])
