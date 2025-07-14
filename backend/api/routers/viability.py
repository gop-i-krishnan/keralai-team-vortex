"""
backend/api/routers/viability.py
GET /viability — corridor viability analysis.
"""
from fastapi import APIRouter
from backend.api.models import ViabilityResponse
from backend.engine import viability as v
from backend import data_store as ds

router = APIRouter()


@router.get("/viability", response_model=ViabilityResponse)
def get_viability():
    corridors = ds.get_corridors()
    cargo = ds.get_cargo()

    classified = v.classify_corridors(corridors)
    demand = v.demand_summary(cargo, corridors)

    return ViabilityResponse(
        d_star_km=v.breakeven_distance(),
        corridors=classified,
        demand_summary=demand,
    )
