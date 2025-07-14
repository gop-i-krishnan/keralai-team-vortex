"""
backend/api/routers/match.py
POST /match — rank sailings for a cargo.
"""
from fastapi import APIRouter, HTTPException
from backend.api.models import MatchRequest, MatchResponse
from backend.engine import matching as eng
from backend import data_store as ds

router = APIRouter()


@router.post("/match", response_model=MatchResponse)
def match_cargo(req: MatchRequest):
    all_cargo = ds.get_cargo()
    cargo = next((c for c in all_cargo if c["id"] == req.cargo_id), None)
    if not cargo:
        raise HTTPException(status_code=404, detail=f"Cargo {req.cargo_id!r} not found")

    sailings = ds.get_sailings()
    if req.sailing_ids:
        sailings = [s for s in sailings if s["id"] in req.sailing_ids]

    ranked = eng.rank_sailings(cargo=cargo, sailings=sailings)
    return MatchResponse(cargo_id=req.cargo_id, ranked=ranked)
