"""
backend/api/tests/test_compliance_api.py
Integration tests for the compliance review gate and hazmat booking flow.
SC-2, SC-7, FR-3, P7, P11.
All tests use in-memory seed data; reset between each test.
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


# ── Hazmat booking: pending_review state ─────────────────────────────────────

def test_explosive_booking_created_pending_review():
    """SC-2 step 1: explosive cargo → booking in pending_review."""
    r = client.post("/api/book", json={
        "cargo_id": "cargo-004",
        "sailing_id": "sailing-001",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending_review"
    assert data["compliance_review_required"] is True


def test_confirm_rejected_while_pending_review():
    """SC-2 step 2: confirm on pending_review booking → compliance_review_required error."""
    r = client.post("/api/book", json={
        "cargo_id": "cargo-004",
        "sailing_id": "sailing-001",
    })
    assert r.status_code == 201
    booking_id = r.json()["id"]

    r2 = client.post(f"/api/book/{booking_id}/confirm")
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"] == "compliance_review_required"


def test_approve_compliance_transitions_to_pending():
    """SC-2 step 3: approve review → booking transitions from pending_review to pending."""
    r = client.post("/api/book", json={
        "cargo_id": "cargo-004",
        "sailing_id": "sailing-001",
    })
    booking_id = r.json()["id"]

    r2 = client.post(
        f"/api/compliance/review/{booking_id}/approve",
        json={"reviewer_note": "Demo review approved"},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["booking_id"] == booking_id
    assert data["source_status"] == "simulated"

    # Booking is now in pending state
    booking = ds.get_booking_by_id(booking_id)
    assert booking["status"] == "pending"


def test_compliance_already_reviewed_error():
    """Approve same booking twice → compliance_already_reviewed, no duplicate."""
    r = client.post("/api/book", json={
        "cargo_id": "cargo-004",
        "sailing_id": "sailing-001",
    })
    booking_id = r.json()["id"]

    client.post(
        f"/api/compliance/review/{booking_id}/approve",
        json={"reviewer_note": "First review"},
    )

    r2 = client.post(
        f"/api/compliance/review/{booking_id}/approve",
        json={"reviewer_note": "Duplicate"},
    )
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"] == "compliance_already_reviewed"

    # Confirm no duplicate record
    assert len(ds.get_compliance_reviews()) == 1


def test_review_not_required_for_general():
    """SC-7: compliance review endpoint on a general cargo booking → review_not_required_for_class."""
    r = client.post("/api/book", json={
        "cargo_id": "cargo-001",
        "sailing_id": "sailing-001",
    })
    booking_id = r.json()["id"]

    r2 = client.post(
        f"/api/compliance/review/{booking_id}/approve",
        json={"reviewer_note": "Trying to review general"},
    )
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"] == "review_not_required_for_class"


def test_full_hazmat_flow_sc2():
    """SC-2 full 3-step flow: book explosive → approve → confirm → confirmed."""
    # Step 1: book
    r = client.post("/api/book", json={
        "cargo_id": "cargo-004",
        "sailing_id": "sailing-001",
    })
    assert r.status_code == 201
    assert r.json()["status"] == "pending_review"
    booking_id = r.json()["id"]

    # Step 2: approve compliance
    r2 = client.post(
        f"/api/compliance/review/{booking_id}/approve",
        json={"reviewer_note": "Demo: compliance approved"},
    )
    assert r2.status_code == 200

    # Step 3: confirm booking
    r3 = client.post(f"/api/book/{booking_id}/confirm")
    assert r3.status_code == 200
    assert r3.json()["status"] == "confirmed"
