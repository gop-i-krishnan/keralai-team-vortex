"""
backend/api/routers/options.py
POST /options — shipment decision endpoint.
"""
from fastapi import APIRouter, HTTPException
from backend.api.models import OptionsRequest, OptionsResponse
from backend.engine import options as eng
from backend import data_store as ds

router = APIRouter()


@router.post("/options", response_model=OptionsResponse)
def get_options(req: OptionsRequest):
    nodes = {n["id"]: n for n in ds.get_nodes()}

    origin = nodes.get(req.origin_node_id)
    destination = nodes.get(req.destination_node_id)
    if not origin:
        raise HTTPException(status_code=404, detail=f"Origin node {req.origin_node_id!r} not found")
    if not destination:
        raise HTTPException(status_code=404, detail=f"Destination node {req.destination_node_id!r} not found")

    sailings = ds.get_sailings()

    result = eng.build_plans(
        weight_t=req.weight_t,
        origin=origin,
        destination=destination,
        ready_time=req.ready_time,
        deadline_h=req.deadline_h,
        sailings=sailings,
        subsidy=req.subsidy,
    )
    return result
