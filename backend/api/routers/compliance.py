"""
backend/api/routers/compliance.py
POST /api/compliance/review/{booking_id}/approve — approve compliance review [simulated].
Constitution P11: compliance review gate for hazmat classes.
Constitution P13: source_status: "simulated" on all review records.
Constitution P15: reviewer_note not sent to any LLM or external service.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend import data_store as ds
from backend.engine.config import get_hazard_rule, ConfigError

router = APIRouter()


class ComplianceReviewRequest(BaseModel):
    reviewer_note: str


@router.post("/compliance/review/{booking_id}/approve")
def approve_compliance_review(booking_id: str, req: ComplianceReviewRequest):
    """
    Approve a compliance review for a hazmat booking [simulated].
    Transitions booking from pending_review → pending.

    Demo action — no authentication required.
    UI must label this: "Compliance review — simulated; production requires a qualified person."

    Returns structured error codes (not exceptions) for:
    - compliance_already_reviewed: booking not in pending_review state
    - review_not_required_for_class: cargo class does not require review
    """
    # Fetch booking
    booking = ds.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id!r} not found")

    # Check class eligibility FIRST (SC-7): if the class doesn't require review,
    # return that error regardless of booking state.
    cargo_class = booking.get("cargo_class", "general")
    try:
        rule = get_hazard_rule(cargo_class)
        if not rule.get("human_review_required", False):
            raise HTTPException(status_code=400, detail={"error": "review_not_required_for_class"})
    except ConfigError:
        # Unknown class — no review required by definition
        raise HTTPException(status_code=400, detail={"error": "review_not_required_for_class"})

    # Idempotency guard: class requires review but booking is not in pending_review state
    # (means review was already approved, or booking was already confirmed)
    if booking.get("status") != "pending_review":
        raise HTTPException(status_code=400, detail={"error": "compliance_already_reviewed"})

    # Create compliance review record (P15: reviewer_note stored verbatim, never sent to LLM)
    review = {
        "id": str(uuid.uuid4()),
        "booking_id": booking_id,
        "cargo_class": cargo_class,
        "reviewer_note": req.reviewer_note,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "source_status": "simulated",
    }
    ds.add_compliance_review(booking_id, review)

    # Transition booking status pending_review → pending
    booking["status"] = "pending"

    return review
