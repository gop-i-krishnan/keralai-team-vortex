"""
backend/api/routers/booking.py
POST /book        — create a booking (preview or confirmed).
POST /book/{id}/confirm — human confirmation step.
Constitution P7: human_confirmed must be explicitly set.
"""
import uuid
from fastapi import APIRouter, HTTPException
from backend.api.models import BookingRequest, BookingResponse
from backend import data_store as ds
from backend.engine import backhaul as bh_eng, pooling as pool_eng

router = APIRouter()


@router.post("/book", response_model=BookingResponse)
def create_booking(req: BookingRequest):
    # Validate cargo exists
    cargo = next((c for c in ds.get_cargo() if c["id"] == req.cargo_id), None)
    if not cargo:
        raise HTTPException(status_code=404, detail=f"Cargo {req.cargo_id!r} not found")

    # Validate sailing exists
    sailing = next((s for s in ds.get_sailings() if s["id"] == req.sailing_id), None)
    if not sailing:
        raise HTTPException(status_code=404, detail=f"Sailing {req.sailing_id!r} not found")

    # Capacity check
    if sailing["available_capacity_t"] < cargo["weight_t"]:
        raise HTTPException(status_code=400, detail="Insufficient vessel capacity")

    booking = {
        "id": str(uuid.uuid4()),
        "cargo_id": req.cargo_id,
        "sailing_id": req.sailing_id,
        "human_confirmed": req.human_confirmed,  # Constitution P7: never force True
        "status": "confirmed" if req.human_confirmed else "preview",
    }
    ds.add_booking(booking)

    return BookingResponse(**booking)


@router.post("/book/{booking_id}/confirm", response_model=BookingResponse)
def confirm_booking(booking_id: str):
    """Explicit human confirmation step — Constitution P7."""
    booking = ds.confirm_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id!r} not found")
    booking["status"] = "confirmed"
    return BookingResponse(**booking)


@router.get("/backhaul/{booking_id}")
def get_backhaul(booking_id: str):
    booking = ds.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id!r} not found")

    sailing = next((s for s in ds.get_sailings() if s["id"] == booking["sailing_id"]), None)
    if not sailing:
        raise HTTPException(status_code=404, detail="Sailing not found for this booking")

    cargo = ds.get_cargo()
    cargo_item = next((c for c in cargo if c["id"] == booking["cargo_id"]), None)
    booked_weight = cargo_item["weight_t"] if cargo_item else 0

    opps = bh_eng.find_backhaul(sailing=sailing, all_cargo=cargo, booked_weight_t=booked_weight)
    pool = pool_eng.find_pooling(sailing=sailing, booked_weight_t=booked_weight, all_cargo=cargo)

    return {
        "booking_id": booking_id,
        "backhaul_opportunities": opps,
        "pooling_opportunities": pool,
    }
