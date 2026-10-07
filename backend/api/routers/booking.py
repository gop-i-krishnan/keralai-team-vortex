"""
backend/api/routers/booking.py
POST /book        — create a booking (pending or pending_review for hazmat).
POST /book/{id}/confirm — human confirmation step.
Constitution P7: human_confirmed must be explicitly set.
Constitution P11: hazmat classes require compliance review before confirm.
"""
import uuid
from fastapi import APIRouter, HTTPException
from backend.api.models import BookingRequest, BookingResponse, DeliverRequest
from backend import data_store as ds
from backend.engine import backhaul as bh_eng, pooling as pool_eng
from backend.engine.config import get_hazard_rule, ConfigError
from backend.engine import history, registry
from backend.engine import options as opt_eng
from backend.engine.config import val

router = APIRouter()


@router.post("/book", status_code=201)
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

    # Determine initial status based on cargo class (FR-3, P11)
    cargo_class = cargo.get("cargo_class", "general")
    compliance_review_required = False
    initial_status = "pending"
    try:
        rule = get_hazard_rule(cargo_class)
        if rule.get("human_review_required", False):
            initial_status = "pending_review"
            compliance_review_required = True
    except ConfigError:
        # Unknown class — treat as general (no review required); log for audit
        pass

    # Plan snapshot for later disruption deltas (Feature 005). Hybrid plan with no deadline cut-off.
    nodes = {n["id"]: n for n in ds.get_nodes()}
    deadline_h = req.deadline_h if req.deadline_h is not None else val("demo", "deadline_hybrid_h")
    snap = opt_eng.build_plans(
        cargo["weight_t"], nodes[cargo["origin_node_id"]], nodes[cargo["destination_node_id"]],
        req.ready_time, float("inf"), [sailing], cargo_class=cargo_class,
    )["plans"].get("hybrid", {})

    booking = {
        "id": str(uuid.uuid4()),
        "cargo_id": req.cargo_id,
        "sailing_id": req.sailing_id,
        "human_confirmed": False,  # Constitution P7: never pre-confirm
        "status": initial_status,
        "cargo_class": cargo_class,
        "vessel_id": sailing["vessel_id"],
        "weight_t": cargo["weight_t"],
        "origin_node_id": cargo["origin_node_id"],
        "destination_node_id": cargo["destination_node_id"],
        "route_node_ids": sailing.get("route_node_ids") or [cargo["origin_node_id"], cargo["destination_node_id"]],
        "ready_time": req.ready_time,
        "deadline_h": deadline_h,
        "planned_cost_inr": snap.get("cost_inr"),
        "planned_time_h": snap.get("time_h"),
        "mode": "hybrid",
        "milestone_index": 0,
        "milestone_actual": {},
        "event_log": [],
    }
    ds.add_booking(booking)

    return {
        **booking,
        "compliance_review_required": compliance_review_required,
    }


@router.post("/book/{booking_id}/confirm")
def confirm_booking(booking_id: str):
    """Explicit human confirmation step — Constitution P7."""
    booking = ds.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id!r} not found")

    # Guard: compliance review must be done first (FR-3, P11)
    if booking.get("status") == "pending_review":
        raise HTTPException(status_code=400, detail={"error": "compliance_review_required"})

    # Guard: suspended vessel cannot take new confirmations (Feature 004 FR-1)
    vessel = ds.get_vessel_by_id(booking.get("vessel_id", ""))
    if vessel and registry.effective_status(vessel) == "suspended":
        raise HTTPException(status_code=409, detail={"error": "vessel_suspended"})

    booking = ds.confirm_booking(booking_id)
    booking["status"] = "confirmed"
    return {
        "id": booking["id"],
        "cargo_id": booking["cargo_id"],
        "sailing_id": booking["sailing_id"],
        "human_confirmed": booking["human_confirmed"],
        "status": booking["status"],
    }


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


@router.post("/booking/{booking_id}/deliver")
def deliver_booking(booking_id: str, req: DeliverRequest):
    """Mark a booking delivered: append a delivery record, recompute reliability (Feature 004)."""
    booking = ds.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id!r} not found")
    if booking.get("status") not in ("confirmed", "replanned"):
        raise HTTPException(status_code=409, detail={"error": "booking_not_deliverable"})
    if any(r["booking_id"] == booking_id for r in ds.get_delivery_history()):
        raise HTTPException(status_code=409, detail={"error": "already_delivered"})

    sailing = next(s for s in ds.get_sailings() if s["id"] == booking["sailing_id"])
    record, errors = history.build_delivery_record(
        f"del-{len(ds.get_delivery_history()) + 1:03d}",
        sailing["vessel_id"], booking_id,
        history.planned_eta_for_sailing(sailing, ds.get_nodes()),
        req.actual_arrival, req.status, booking.get("cargo_class", "general"),
    )
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    ds.add_delivery(record)
    booking["delivered"] = True
    own = [r for r in ds.get_delivery_history() if r["vessel_id"] == record["vessel_id"]]
    return {"delivery_record": record, "updated_reliability": history.compute_reliability(own)}
