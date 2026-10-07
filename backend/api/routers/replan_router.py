"""
backend/api/routers/replan_router.py
Feature 005: re-plan proposal (read-only), explicit confirm, notify preview, analytics.
Constitution P12: POST /replan/{id} changes nothing; only /confirm applies an alternative.
Constitution P11: hazardous classes need a recorded re-plan compliance review first.
Constitution P13: everything is simulated; notifications are previews and are never sent.
"""
from fastapi import APIRouter, HTTPException

from backend import data_store as ds
from backend.api.models import ReplanConfirmRequest, ReplanReviewRequest
from backend.api.routers.tracking import _event, _get, _node_name, _ist_now, booking_view
from backend.engine import replan as replan_eng, tracking
from backend.engine.config import get_hazard_rule, ConfigError

router = APIRouter()

NO_DEADLINE_BANNER = "No option meets your deadline — fastest shown."


def _needs_review(cargo_class: str) -> bool:
    try:
        return bool(get_hazard_rule(cargo_class).get("human_review_required", False))
    except ConfigError:
        return False


def _conflict(code: str, status: int = 409):
    return HTTPException(status_code=status, detail={"error": code})


@router.post("/replan/{booking_id}")
def propose(booking_id: str):
    """Compute ranked alternatives. Read-only: the booking is not modified (P12)."""
    b = _get(booking_id)
    dis = ds.get_open_disruption(booking_id)
    if b["status"] != "disrupted" or not dis:
        raise _conflict("booking_not_disrupted")
    proposal = replan_eng.replan(b, dis, ds.get_sailings(), ds.get_nodes(), ds.get_vessels(), ds.get_warehouses())
    proposal["compliance_review_required"] = _needs_review(b.get("cargo_class", "general"))
    proposal["banner"] = NO_DEADLINE_BANNER if proposal["fastest_fallback_id"] else None
    proposal["booking_unchanged"] = True
    ds.set_proposal(booking_id, proposal)
    return proposal


@router.post("/replan/{booking_id}/confirm")
def confirm(booking_id: str, req: ReplanConfirmRequest):
    """Explicit human confirmation. Applies exactly one alternative (P12)."""
    b = _get(booking_id)
    proposal = ds.get_proposal(booking_id)
    if proposal is None:
        raise _conflict("no_proposal")
    dis = ds.get_open_disruption(booking_id)
    if dis is not None and dis["id"] != proposal["disruption_id"]:
        raise _conflict("proposal_stale")
    if proposal.get("confirmed"):
        raise _conflict("replan_already_confirmed")
    if b["status"] != "disrupted" or dis is None:
        raise _conflict("proposal_stale")
    alt = next((a for a in proposal["alternatives"] if a["id"] == req.alternative_id), None)
    if alt is None:
        raise HTTPException(status_code=422, detail={"error": "unknown_alternative"})
    if proposal["compliance_review_required"] and ds.get_replan_review(proposal["proposal_id"]) is None:
        raise HTTPException(status_code=400, detail={"error": "compliance_review_required"})

    # Apply the chosen alternative to the booking plan fields only. Sailing capacity is not touched.
    b["planned_cost_inr"] = round((b["planned_cost_inr"] or 0) + alt["extra_cost_inr"], 2)
    b["planned_time_h"] = alt["new_total_time_h"]
    b["mode"] = {"truck_from_jetty": "road", "return_to_origin": "road"}.get(alt["type"], "hybrid")
    if alt["type"] == "alternative_vessel":
        b["sailing_id"], b["vessel_id"] = alt["sailing_id"], alt["vessel_id"]
    b["resolution"] = alt
    b["status"] = "replanned"
    dis["status"] = "resolved"
    proposal["confirmed"] = True

    ts = _ist_now()
    _event(b, "replan_proposed", f"{len(proposal['alternatives'])} alternatives proposed for {dis['type']}.", ts)
    _event(b, "replan_confirmed", f"Owner accepted '{alt['type']}' (extra Rs {alt['extra_cost_inr']:,.0f}, "
                                  f"new ETA {alt['new_eta']}) — simulated.", ts)
    _event(b, "notification_preview", "Operator notified of the chosen plan — message preview, not sent [simulated].", ts)
    return booking_view(b)


@router.post("/booking/{booking_id}/notify")
def notify(booking_id: str):
    """Render the notification template for the latest disruption. Never sends anything."""
    b = _get(booking_id)
    dis = ds.get_latest_disruption(booking_id)
    if dis is None:
        raise _conflict("no_disruption")
    n = replan_eng.render_notification(
        dis["type"], b["cargo_id"], _node_name(dis["location_node_id"]),
        tracking.format_hhmm(tracking.to_minutes(b["ready_time"]) + b["deadline_h"] * 60))
    return {**n, "preview": n["body_rendered"], "booking_id": booking_id}


@router.post("/compliance/replan-review/{proposal_id}/approve")
def approve_replan_review(proposal_id: str, req: ReplanReviewRequest):
    """Simulated compliance review of a re-plan for hazardous cargo (P11). Demo action only."""
    p = ds.get_proposal_by_id(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id!r} not found")
    if not p["compliance_review_required"]:
        raise HTTPException(status_code=400, detail={"error": "review_not_required_for_class"})
    if ds.get_replan_review(proposal_id):
        raise _conflict("compliance_already_reviewed")
    review = {"proposal_id": proposal_id, "booking_id": p["booking_id"], "reviewer_note": req.reviewer_note,
              "approved_at": _ist_now(), "source_status": "simulated",
              "label": "Compliance review — simulated; production requires a qualified person."}
    ds.add_replan_review(proposal_id, review)
    return review


@router.get("/disruptions/summary")
def summary():
    corridors = ds.get_corridors()
    counts: dict[tuple, int] = {}
    for d in ds.get_disruptions():
        b = ds.get_booking_by_id(d["booking_id"])
        route = set((b or {}).get("route_node_ids", [])) | {d["location_node_id"]}
        corridor = next((c["id"] for c in corridors
                         if c["origin_node_id"] in route and c["destination_node_id"] in route), "unknown")
        counts[(d["type"], corridor)] = counts.get((d["type"], corridor), 0) + 1
    rows = [{"disruption_type": t, "corridor_id": c, "count": n, "source_status": "simulated"}
            for (t, c), n in sorted(counts.items())]
    return {"rows": rows, "source_status": "simulated",
            "note": "Simulated counts for this session; they reset on demo reset."}
