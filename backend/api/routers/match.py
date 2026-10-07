"""
backend/api/routers/match.py
POST /match — rank sailings for a cargo, with hazard hard-filter (FR-2).
"""
from fastapi import APIRouter, HTTPException
from backend.api.models import MatchRequest, MatchResponse
from backend.engine import matching as eng
from backend.engine.config import get_hazard_rules
from backend import data_store as ds

router = APIRouter()


@router.post("/match", response_model=MatchResponse)
def match_cargo(req: MatchRequest):
    all_cargo = ds.get_cargo()
    cargo = next((c for c in all_cargo if c["id"] == req.cargo_id), None)
    if not cargo:
        raise HTTPException(status_code=404, detail=f"Cargo {req.cargo_id!r} not found")

    # Resolve cargo_class: request param > cargo record field > default "general" (spec assumption 8)
    cargo_class = req.cargo_class or cargo.get("cargo_class") or "general"

    sailings = ds.get_sailings()
    if req.sailing_ids:
        sailings = [s for s in sailings if s["id"] in req.sailing_ids]

    vessels = ds.get_vessels()
    hazard_rules = get_hazard_rules()

    result = eng.rank_sailings(
        cargo=cargo,
        sailings=sailings,
        cargo_class=cargo_class,
        vessels=vessels,
        hazard_rules=hazard_rules,
    )

    # result is now a dict {"ranked": [...], "excluded": [...]}
    return MatchResponse(
        cargo_id=req.cargo_id,
        ranked=result["ranked"],
        excluded=result["excluded"],
    )
