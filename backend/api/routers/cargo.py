"""
backend/api/routers/cargo.py
POST /cargo — post a cargo record (needed by the Post-cargo screen); GET /cargo/list.
Constitution P13: runtime cargo is simulated demo data. P15: no personal data fields.
"""
from fastapi import APIRouter, HTTPException

from backend import data_store as ds
from backend.api.models import CargoCreateRequest
from backend.engine.config import get_hazard_rules

router = APIRouter()


def _err(field, code, message):
    return {"field": field, "code": code, "message": message}


@router.get("/cargo/list")
def list_cargo():
    return {"cargo": ds.get_cargo(), "source_status": "simulated"}


@router.post("/cargo", status_code=201)
def create_cargo(req: CargoCreateRequest):
    node_ids = {n["id"] for n in ds.get_nodes()}
    classes = {r["class_id"] for r in get_hazard_rules()}
    errs = []
    if not (req.description or "").strip():
        errs.append(_err("description", "required", "Describe the cargo"))
    try:
        w = float(req.weight_t)
        if w <= 0:
            raise ValueError
    except (TypeError, ValueError):
        errs.append(_err("weight_t", "not_positive", "Weight must be a number greater than 0"))
        w = None
    if (req.cargo_class or "general") not in classes:
        errs.append(_err("cargo_class", "invalid_class", f"Unknown cargo class: {req.cargo_class}"))
    for f in ("origin_node_id", "destination_node_id"):
        v = getattr(req, f)
        if not v:
            errs.append(_err(f, "required", "Required"))
        elif v not in node_ids:
            errs.append(_err(f, "not_found", f"Unknown node: {v}"))
    if (req.origin_node_id and req.origin_node_id == req.destination_node_id):
        errs.append(_err("destination_node_id", "same_as_origin", "Destination must differ from origin"))
    if errs:
        raise HTTPException(status_code=422, detail={"errors": errs})
    cargo = {
        "id": f"cargo-new-{len(ds.get_cargo()) + 1}",
        "description": req.description.strip(), "weight_t": w,
        "cargo_class": req.cargo_class or "general",
        "shipper_id": "shipper-demo",
        "origin_node_id": req.origin_node_id, "destination_node_id": req.destination_node_id,
        "source_status": "simulated", "note": "Runtime-posted cargo [simulated].",
    }
    ds.add_cargo(cargo)
    return cargo


@router.get("/nodes")
def list_nodes():
    return {"nodes": [{"id": n["id"], "name": n["name"], "source_status": n.get("source_status", "assumed")}
                      for n in ds.get_nodes()]}


@router.get("/operators")
def list_operators():
    return {"operators": [{"id": o["id"], "name": o["name"], "source_status": "simulated"}
                          for o in ds.get_operators()]}


@router.get("/hazard-classes")
def hazard_classes():
    """Cargo classes for the selector. Eligibility flags only — no handling or safety text (P11)."""
    return {"classes": [{
        "class_id": r["class_id"],
        "allowed_modes": r["allowed_modes"],
        "certification_required": r["certification_required"],
        "human_review_required": r["human_review_required"],
        "source_status": r["source_status"],
    } for r in get_hazard_rules()],
        "note": "Assumed rules — verify with IWAI / PESO / state authority before production use."}
