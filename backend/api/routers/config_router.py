"""
backend/api/routers/config_router.py
GET /config/assumptions — list all config values with source_status tags.
Constitution P3: every number in UI must display its tag.
"""
from fastapi import APIRouter
from backend.engine.config import CFG

router = APIRouter()


@router.get("/config/assumptions")
def get_assumptions():
    """Return all config values with source_status + note for UI badge display."""
    flat = []
    for section, entries in CFG.items():
        if section == "meta":
            continue
        if isinstance(entries, dict):
            for key, val in entries.items():
                if isinstance(val, dict) and "source_status" in val:
                    flat.append({
                        "section": section,
                        "key": key,
                        "value": val.get("value"),
                        "source_status": val["source_status"],
                        "note": val.get("note", ""),
                    })
    return {"assumptions": flat}
