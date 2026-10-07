"""
backend/api/routers/tracking.py
Feature 005: booking view, simulated milestone advance, demo disruption trigger.
Constitution P13: everything here is simulated and says so.
Constitution P12: triggering a disruption proposes nothing and switches nothing.
"""
import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException

from backend import data_store as ds
from backend.api.models import DisruptRequest
from backend.engine import replan as replan_eng, tracking
from backend.engine.config import val

router = APIRouter()

DISRUPTION_TYPES = ("vessel_breakdown", "low_depth", "jetty_closed", "road_blocked", "weather_delay")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _ist_now() -> str:
    tz = timezone(timedelta(minutes=val("meta", "ist_offset_min")))
    return datetime.now(tz).strftime("%H:%M")


def _event(booking: dict, event_type: str, detail: str, timestamp: str | None = None) -> None:
    booking["event_log"].append({
        "id": f"{booking['id']}-ev-{len(booking['event_log']) + 1}",
        "event_type": event_type,
        "timestamp": timestamp or _ist_now(),
        "detail": detail,
        "source_status": "simulated",
    })


def _node_name(node_id: str) -> str:
    return next((n["name"] for n in ds.get_nodes() if n["id"] == node_id), node_id)


def _schedule(booking: dict) -> list[dict]:
    sailing = next((s for s in ds.get_sailings() if s["id"] == booking["sailing_id"]), None)
    nodes = {n["id"]: n for n in ds.get_nodes()}
    route = booking["route_node_ids"]
    sail_h = tracking.sail_time_h(nodes[route[0]], nodes[route[-1]])
    dep = sailing["departure_time"] if sailing else booking["ready_time"]
    return tracking.milestone_schedule(booking["ready_time"], dep, sail_h)


def _deadline_at_risk(booking: dict, dur) -> bool:
    return dur is None or (booking["planned_time_h"] + dur) > (booking["deadline_h"] - val("scoring", "deadline_buffer_h"))


def booking_view(booking: dict) -> dict:
    idx = booking.get("milestone_index", 0)
    actual = booking.get("milestone_actual", {})
    milestones = []
    for i, m in enumerate(_schedule(booking)):
        milestones.append({
            **m,
            "actual_time": actual.get(m["name"]),
            "status": "completed" if i < idx else ("current" if i == idx else "pending"),
        })
    view = {k: v for k, v in booking.items() if k != "milestone_actual"}
    view["milestones"] = milestones
    view["current_milestone"] = tracking.MILESTONES[idx]
    view["current_node_id"] = tracking.current_node(booking["route_node_ids"], idx)
    view["current_node_name"] = _node_name(view["current_node_id"])
    view["deadline_hhmm"] = tracking.format_hhmm(
        tracking.to_minutes(booking["ready_time"]) + booking["deadline_h"] * 60)
    view["open_disruption"] = ds.get_open_disruption(booking["id"])
    if view["open_disruption"]:
        view["deadline_at_risk"] = _deadline_at_risk(booking, view["open_disruption"]["expected_duration_h"])
    view["compliance_review_required"] = booking.get("status") == "pending_review"
    view["source_status"] = "simulated"
    return view


def _get(booking_id: str) -> dict:
    b = ds.get_booking_by_id(booking_id)
    if not b:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id!r} not found")
    return b


@router.get("/bookings")
def list_bookings():
    return {"bookings": [booking_view(b) for b in ds.get_bookings()], "source_status": "simulated"}


@router.get("/booking/{booking_id}")
def get_booking(booking_id: str):
    return booking_view(_get(booking_id))


@router.post("/demo/booking/{booking_id}/advance")
def advance(booking_id: str):
    """Demo control — simulated. Steps the booking to the next milestone."""
    b = _get(booking_id)
    if b["status"] == "disrupted":
        raise HTTPException(status_code=409, detail={"error": "booking_disrupted"})
    if b["status"] not in ("confirmed", "replanned"):
        raise HTTPException(status_code=409, detail={"error": "booking_not_active"})
    try:
        b["milestone_index"] = tracking.advance_milestone(b["milestone_index"])
    except tracking.FinalMilestone:
        raise HTTPException(status_code=409, detail={"error": "final_milestone",
                                                     "message": "Booking already at final milestone."})
    name = tracking.MILESTONES[b["milestone_index"]]
    now = _ist_now()
    b["milestone_actual"][name] = now
    _event(b, "milestone_advanced", f"Milestone advanced to {name} (demo control).", now)
    return {"booking_id": b["id"], "current_milestone": name, "source_status": "simulated"}


@router.get("/demo/disruption-scenarios")
def scenarios():
    return {"scenarios": ds.get_scenarios(), "source_status": "simulated"}


def _err(field: str, code: str, message: str):
    return HTTPException(status_code=422, detail={"errors": [{"field": field, "code": code, "message": message}]})


@router.post("/demo/booking/{booking_id}/disrupt", status_code=201)
def disrupt(booking_id: str, req: DisruptRequest):
    """Demo control — simulated disruption. Records it and previews the notification. No re-plan happens."""
    b = _get(booking_id)
    kind, where, dur = req.type, req.location_node_id, req.expected_duration_h

    if req.scenario_id:
        sc = next((s for s in ds.get_scenarios() if s["id"] == req.scenario_id), None)
        if not sc:
            raise _err("scenario_id", "not_found", f"Unknown scenario: {req.scenario_id}")
        kind = kind or sc["type"]
        where = where or sc["location_node_id"]
        dur = dur if dur is not None else sc.get("expected_duration_h")

    if kind not in DISRUPTION_TYPES:
        raise _err("type", "invalid_type", "type must be one of: " + ", ".join(DISRUPTION_TYPES))
    if dur is not None:
        try:
            dur = float(dur)
        except (TypeError, ValueError):
            raise _err("expected_duration_h", "invalid_duration", "Expected duration must be a number of hours")
        if dur < 0:
            raise _err("expected_duration_h", "invalid_duration", "Expected duration cannot be negative")
    if where is not None and where not in {n["id"] for n in ds.get_nodes()}:
        raise _err("location_node_id", "not_found", f"Unknown node: {where}")
    if req.now_hhmm is not None and not _HHMM.match(req.now_hhmm):
        raise _err("now_hhmm", "invalid_time", "now_hhmm must be HH:MM")

    if ds.get_open_disruption(booking_id):
        raise HTTPException(status_code=409, detail={"error": "disruption_already_open"})
    if b["status"] not in ("confirmed", "replanned"):
        raise HTTPException(status_code=409, detail={"error": "booking_not_disruptable"})

    idx = b["milestone_index"]
    where = where or tracking.current_node(b["route_node_ids"], idx)
    sched = _schedule(b)
    detected = req.now_hhmm or sched[idx]["planned_time"]   # demo clock: planned time of the current milestone
    slack = b["deadline_h"] - b["planned_time_h"]
    disruption = {
        "id": f"dis-{len(ds.get_disruptions()) + 1:03d}",
        "booking_id": booking_id, "type": kind, "location_node_id": where,
        "detected_at": detected, "expected_duration_h": dur,
        "severity": replan_eng.classify_severity(dur, slack),
        "status": "open", "source_status": "simulated",
    }
    ds.add_disruption(disruption)
    b["status"] = "disrupted"
    _event(b, "disruption_recorded", f"{kind.replace('_', ' ').capitalize()} at {_node_name(where)} "
                                      f"(severity {disruption['severity']}) — simulated.", detected)
    notification = replan_eng.render_notification(
        kind, b["cargo_id"], _node_name(where), tracking.format_hhmm(
            tracking.to_minutes(b["ready_time"]) + b["deadline_h"] * 60))
    return {"disruption": disruption, "notification": notification, "deadline_at_risk": _deadline_at_risk(b, dur),
            "booking": booking_view(b), "source_status": "simulated"}
