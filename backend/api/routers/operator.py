"""
backend/api/routers/operator.py
POST /operator/message — operator sends free-text; system parses + suggests options.
"""
from fastapi import APIRouter, HTTPException
from backend.api.models import OperatorMessageRequest
from backend.api.routers.parse import parse_shipment
from backend.api.models import ParseRequest
from backend import data_store as ds
from backend.engine import options as opt_eng

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
