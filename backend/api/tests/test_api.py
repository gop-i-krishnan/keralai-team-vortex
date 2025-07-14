"""
backend/api/tests/test_api.py
Integration tests against the FastAPI app.
All tests use in-memory seed data; reset between each test.
"""
import os
os.environ["JALSETU_MOCK_LLM"] = "1"  # ensure offline mode

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


# ── Root ──────────────────────────────────────────────────────────────────────

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Demo reset ────────────────────────────────────────────────────────────────

def test_demo_reset():
    r = client.post("/api/demo/reset")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_demo_status():
    r = client.get("/api/demo/status")
    assert r.status_code == 200
    data = r.json()
    assert data["nodes"] >= 2
    assert data["sailings"] >= 1


# ── Options ───────────────────────────────────────────────────────────────────

def test_options_10h_recommends_hybrid():
    r = client.post("/api/options", json={
        "weight_t": 10,
        "origin_node_id": "node-001",
        "destination_node_id": "node-002",
        "ready_time": "04:00",
        "deadline_h": 10,
        "subsidy": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["recommended"] == "hybrid"
    assert "why" in data


def test_options_3h_recommends_road():
    r = client.post("/api/options", json={
        "weight_t": 10,
        "origin_node_id": "node-001",
        "destination_node_id": "node-002",
        "ready_time": "04:00",
        "deadline_h": 3,
        "subsidy": False,
    })
    assert r.status_code == 200
    assert r.json()["recommended"] == "road"


def test_options_unknown_node_404():
    r = client.post("/api/options", json={
        "weight_t": 5,
        "origin_node_id": "node-999",
        "destination_node_id": "node-002",
        "ready_time": "04:00",
        "deadline_h": 10,
        "subsidy": False,
    })
    assert r.status_code == 404


# ── Config assumptions ────────────────────────────────────────────────────────

def test_config_assumptions_has_source_status():
    r = client.get("/api/config/assumptions")
    assert r.status_code == 200
    items = r.json()["assumptions"]
    assert len(items) > 0
    for item in items:
        assert "source_status" in item
        assert item["source_status"] in ("sourced", "assumed")


# ── Match ─────────────────────────────────────────────────────────────────────

def test_match_cargo_001():
    r = client.post("/api/match", json={"cargo_id": "cargo-001"})
    assert r.status_code == 200
    data = r.json()
    assert data["cargo_id"] == "cargo-001"
    assert len(data["ranked"]) >= 1


def test_match_nonexistent_cargo():
    r = client.post("/api/match", json={"cargo_id": "cargo-999"})
    assert r.status_code == 404


# ── Booking ───────────────────────────────────────────────────────────────────

def test_booking_preview():
    r = client.post("/api/book", json={
        "cargo_id": "cargo-001",
        "sailing_id": "sailing-001",
        "human_confirmed": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "preview"
    assert data["human_confirmed"] is False


def test_booking_confirm():
    # Create preview first
    r = client.post("/api/book", json={
        "cargo_id": "cargo-001",
        "sailing_id": "sailing-001",
        "human_confirmed": False,
    })
    booking_id = r.json()["id"]

    # Explicit confirm step
    r2 = client.post(f"/api/book/{booking_id}/confirm")
    assert r2.status_code == 200
    assert r2.json()["human_confirmed"] is True
    assert r2.json()["status"] == "confirmed"


def test_backhaul_opportunities():
    # Create a booking first
    r = client.post("/api/book", json={
        "cargo_id": "cargo-001",
        "sailing_id": "sailing-001",
        "human_confirmed": False,
    })
    booking_id = r.json()["id"]

    r2 = client.get(f"/api/backhaul/{booking_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert "backhaul_opportunities" in data
    assert "pooling_opportunities" in data


# ── Parse ─────────────────────────────────────────────────────────────────────

def test_parse_kochi_alappuzha():
    r = client.post("/api/parse", json={"text": "Send 10 tonnes from Kochi to Alappuzha"})
    assert r.status_code == 200
    data = r.json()
    assert data["weight_t"] == 10.0 or data["origin_node_id"] is not None


def test_parse_returns_needs_review_flag():
    r = client.post("/api/parse", json={"text": "ship something somewhere"})
    assert r.status_code == 200
    assert "needs_review" in r.json()


# ── Viability ─────────────────────────────────────────────────────────────────

def test_viability_response():
    r = client.get("/api/viability")
    assert r.status_code == 200
    data = r.json()
    assert "d_star_km" in data
    assert data["d_star_km"] > 0
    assert len(data["corridors"]) >= 1
    assert "viable" in data["corridors"][0]


# ── Operator message ──────────────────────────────────────────────────────────

def test_operator_message():
    r = client.post("/api/operator/message", json={
        "operator_id": "op-001",
        "message": "I have 10 tonnes from Kochi to Alappuzha in 10 hours",
    })
    assert r.status_code == 200
    data = r.json()
    assert "parsed" in data
    assert "message" in data


def test_demo_reset_full_cycle():
    """Full demo: reset → options → book → confirm → backhaul → reset."""
    client.post("/api/demo/reset")

    # Options
    r = client.post("/api/options", json={
        "weight_t": 10,
        "origin_node_id": "node-001",
        "destination_node_id": "node-002",
        "ready_time": "04:00",
        "deadline_h": 10,
        "subsidy": False,
    })
    assert r.json()["recommended"] == "hybrid"

    # Book
    r2 = client.post("/api/book", json={
        "cargo_id": "cargo-001",
        "sailing_id": "sailing-001",
        "human_confirmed": False,
    })
    bid = r2.json()["id"]

    # Confirm
    r3 = client.post(f"/api/book/{bid}/confirm")
    assert r3.json()["human_confirmed"] is True

    # Backhaul
    r4 = client.get(f"/api/backhaul/{bid}")
    assert r4.status_code == 200

    # Reset
    client.post("/api/demo/reset")
    r5 = client.get("/api/demo/status")
    assert r5.json()["bookings"] == 0
