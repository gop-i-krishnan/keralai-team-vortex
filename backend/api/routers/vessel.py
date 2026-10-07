"""
backend/api/routers/vessel.py
Feature 004: vessel registration, sailing publication, lifecycle, message parse.
Constitution P2: validation/lifecycle logic lives in engine/registry.py; ids minted here.
Constitution P7: parse-message changes no state; registration is the explicit confirm step.
Constitution P13: admin verification is a simulated demo action.
"""
from fastapi import APIRouter, HTTPException
from backend.api.models import VesselRegisterRequest, SailingPublishRequest, VesselMessageRequest
from backend import data_store as ds
from backend.engine import registry
from backend.engine.config import get_hazard_rules, val
from backend.engine.parser import parse_vessel_message, fuzzy_match_node

router = APIRouter()

VERIFY_NOTICE = "Verification is simulated — production would check the national vessel registry [simulated]."
SUSPEND_NOTICE = "This vessel is suspended — existing bookings unaffected; no new bookings can be made."


def vessel_public(v: dict) -> dict:
    return {**v, "status": registry.effective_status(v)}


@router.get("/vessel/list")
def list_vessels():
    return {"vessels": [vessel_public(v) for v in ds.get_vessels()], "source_status": "simulated"}


@router.post("/vessel/register", status_code=201)
def register_vessel(req: VesselRegisterRequest):
    payload = req.model_dump()
    errors = registry.validate_registration(
        payload,
        {n["id"] for n in ds.get_nodes()},
        {o["id"] for o in ds.get_operators()},
        {r["class_id"] for r in get_hazard_rules()},
        ds.get_vessels(),
    )
    if errors:
        status = 409 if any(e["code"] == "duplicate_vessel" for e in errors) else 422
        raise HTTPException(status_code=status, detail={"errors": errors})

    vessel = {
        "id": f"vessel-{len(ds.get_vessels()) + 1:03d}",
        "name": req.vessel_name.strip(),
        "capacity_t": float(req.capacity_t),
        "draft_m": float(req.draft_m),
        "home_jetty_id": req.home_jetty_id,
        "operator_id": req.operator_id,
        "hazard_certs": list(req.hazard_certs),
        "type": req.vessel_type,
        "registration_number": req.registration_number,
        "contact": req.contact,
        "status": registry.transition_status("draft", "submit"),
        "source_status": "simulated",
        "note": "Runtime-registered vessel; contact must be fictional in the demo [simulated].",
    }
    ds.add_vessel(vessel)
    return vessel


@router.post("/vessel/parse-message")
def parse_message(req: VesselMessageRequest):
    """Extract vessel fields from free text. Changes no state (P7)."""
    parsed = parse_vessel_message(req.message)   # scrub_pii runs inside (P15)
    nodes = ds.get_nodes()
    home = fuzzy_match_node(parsed["home_raw"], nodes) if parsed["home_raw"] else None
    route = fuzzy_match_node(parsed["route_hint_raw"], nodes) if parsed["route_hint_raw"] else None
    threshold = val("llm", "confidence_threshold")
    needs_review = parsed["confidence"] < threshold or home is None or parsed["capacity_t"] is None
    return {
        **parsed,
        "home_jetty_id": home["id"] if home else None,
        "route_hint_node_id": route["id"] if route else None,
        "needs_review": needs_review,
        "method": "regex",
    }


@router.post("/sailing/publish", status_code=201)
def publish_sailing(req: SailingPublishRequest):
    vessel = ds.get_vessel_by_id(req.vessel_id)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel {req.vessel_id!r} not found")
    errors = registry.validate_sailing(req.model_dump(), vessel, {n["id"] for n in ds.get_nodes()})
    if errors:
        status = 409 if errors[0]["code"] == "vessel_suspended" else 422
        raise HTTPException(status_code=status, detail={"errors": errors})
    sailing = {
        "id": f"sailing-{len(ds.get_sailings()) + 1:03d}",
        "vessel_id": req.vessel_id,
        "origin_node_id": req.route_node_ids[0],
        "destination_node_id": req.route_node_ids[-1],
        "route_node_ids": list(req.route_node_ids),
        "departure_time": req.departure_time,
        "days": list(req.weekdays),
        "price_per_t": float(req.price_per_t),
        "available_capacity_t": float(req.capacity_offered_t),
        "source_status": "recorded",
        "note": "Operator-published sailing; price is operator-quoted. Intermediate stops are display-only.",
    }
    ds.add_sailing(sailing)
    return sailing


def _transition(vessel_id: str, action: str):
    vessel = ds.get_vessel_by_id(vessel_id)
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel {vessel_id!r} not found")
    try:
        new = registry.transition_status(registry.effective_status(vessel), action)
    except registry.InvalidTransition as e:
        raise HTTPException(status_code=409, detail={"error": "invalid_transition", "message": str(e)})
    vessel["status"] = new
    return vessel


@router.post("/admin/vessel/{vessel_id}/verify")
def verify_vessel(vessel_id: str):
    v = _transition(vessel_id, "verify")
    return {"id": v["id"], "status": v["status"], "notice": VERIFY_NOTICE, "source_status": "simulated"}


@router.post("/admin/vessel/{vessel_id}/reinstate")
def reinstate_vessel(vessel_id: str):
    v = _transition(vessel_id, "reinstate")
    return {"id": v["id"], "status": v["status"], "notice": VERIFY_NOTICE, "source_status": "simulated"}


@router.post("/admin/vessel/{vessel_id}/suspend")
def suspend_vessel(vessel_id: str):
    v = _transition(vessel_id, "suspend")
    sailing_ids = {s["id"] for s in ds.get_sailings() if s["vessel_id"] == vessel_id}
    affected = [b["id"] for b in ds.get_bookings() if b.get("sailing_id") in sailing_ids]
    return {"id": v["id"], "status": v["status"], "notice": SUSPEND_NOTICE,
            "affected_booking_ids": affected, "source_status": "simulated"}


@router.get("/sailing/list")
def list_sailings():
    return {"sailings": ds.get_sailings(), "source_status": "simulated"}
