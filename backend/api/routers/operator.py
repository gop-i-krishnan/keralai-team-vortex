"""
backend/api/routers/operator.py
POST /operator/message — operator sends free-text; system parses + suggests options.
"""
from fastapi import APIRouter, HTTPException
from backend.api.models import OperatorMessageRequest
from backend.api.routers.parse import parse_shipment
from backend.api.models import ParseRequest
from backend import data_store as ds
from backend.engine import options as opt_eng, history, registry

router = APIRouter()


@router.post("/operator/message")
def operator_message(req: OperatorMessageRequest):
    # Validate operator
    operator = next((o for o in ds.get_operators() if o["id"] == req.operator_id), None)
    if not operator:
        raise HTTPException(status_code=404, detail=f"Operator {req.operator_id!r} not found")

    # Parse the message
    parsed = parse_shipment(ParseRequest(text=req.message))

    response = {
        "operator_id": req.operator_id,
        "parsed": parsed.model_dump(),
        "options": None,
        "message": "",
    }

    if parsed.needs_review:
        response["message"] = (
            "Parsed with low confidence — please review the fields above and correct if needed."
        )
        return response

    # If parsed OK, run options engine
    if parsed.origin_node_id and parsed.destination_node_id and parsed.weight_t and parsed.deadline_h:
        nodes = {n["id"]: n for n in ds.get_nodes()}
        sailings = ds.get_sailings()
        result = opt_eng.build_plans(
            weight_t=parsed.weight_t,
            origin=nodes[parsed.origin_node_id],
            destination=nodes[parsed.destination_node_id],
            ready_time="06:00",
            deadline_h=parsed.deadline_h,
            sailings=sailings,
            subsidy=False,
        )
        response["options"] = result
        response["message"] = f"Recommendation: {result['recommended']}. {result['why']}"
    else:
        response["message"] = "Could not resolve full shipment details. Please use the manual form."

    return response


@router.get("/operator/{operator_id}/profile")
def operator_profile(operator_id: str):
    """Vessels with status and Bayesian reliability. Trip count always accompanies the rate (P14)."""
    if not any(op["id"] == operator_id for op in ds.get_operators()):
        raise HTTPException(status_code=404, detail=f"Operator {operator_id!r} not found")
    records = ds.get_delivery_history()
    vessels = []
    for v in ds.get_vessels():
        if v.get("operator_id") != operator_id:
            continue
        own = [r for r in records if r["vessel_id"] == v["id"]]
        vessels.append({
            "id": v["id"], "name": v["name"], "capacity_t": v["capacity_t"],
            "status": registry.effective_status(v), "hazard_certs": v.get("hazard_certs", []),
            "reliability": history.compute_reliability(own),
            "history": own, "source_status": "simulated",
        })
    return {"operator_id": operator_id, "vessels": vessels, "source_status": "simulated"}
