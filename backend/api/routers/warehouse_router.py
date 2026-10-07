"""
backend/api/routers/warehouse_router.py
Warehouse CRUD and staging endpoints.
FR-4, FR-7, FR-8, FR-11.
Constitution P12: staging is a two-step proposal → confirm flow.
Constitution P13: all warehouse records carry source_status: "simulated".
"""
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from backend import data_store as ds
from backend.api.routers.tracking import _ist_now
from backend.engine.config import val, get_hazard_rules
from backend.engine.warehouse import find_eligible_warehouses, compute_staging_plan

router = APIRouter()

_VALID_CLASSES = {
    "general", "perishable", "liquid_bulk",
    "flammable", "explosive", "toxic_corrosive", "oversized",
}


# ── Request/Response models ───────────────────────────────────────────────────

class WarehouseRegisterRequest(BaseModel):
    name: str
    location_node_id: str
    total_capacity_t: float
    storage_cost_per_t_per_day: float
    handling_in_cost_per_t: float
    handling_out_cost_per_t: float
    allowed_cargo_classes: list[str]


class StagingProposalRequest(BaseModel):
    cargo_id: str
    next_sailing_wait_h: float
    deadline_h: float
    booking_id: Optional[str] = None   # optional: attach the staging to this booking on confirm


class StagingConfirmRequest(BaseModel):
    proposal_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wh_public(wh: dict) -> dict:
    """Return warehouse dict without internal fields."""
    cap_used = wh.get("capacity_used_t", 0.0)
    total = wh.get("total_capacity_t", 0.0)
    available = round(total - cap_used, 4)
    utilisation_pct = round((cap_used / total * 100) if total > 0 else 0.0, 2)
    return {
        "id": wh["id"],
        "name": wh["name"],
        "location_node_id": wh["location_node_id"],
        "total_capacity_t": total,
        "capacity_used_t": cap_used,
        "available_capacity_t": available,
        "utilisation_pct": utilisation_pct,
        "storage_cost_per_t_per_day": wh["storage_cost_per_t_per_day"],
        "handling_in_cost_per_t": wh["handling_in_cost_per_t"],
        "handling_out_cost_per_t": wh["handling_out_cost_per_t"],
        "allowed_cargo_classes": wh["allowed_cargo_classes"],
        "source_status": wh.get("source_status", "simulated"),
    }


def _validate_warehouse_request(req: WarehouseRegisterRequest) -> list[dict]:
    """Return a list of validation errors; empty list means valid."""
    errors = []

    if req.total_capacity_t <= 0:
        errors.append({
            "field": "total_capacity_t",
            "code": "invalid_value",
            "message": "total_capacity_t must be > 0",
        })

    for field_name in ("storage_cost_per_t_per_day", "handling_in_cost_per_t", "handling_out_cost_per_t"):
        v = getattr(req, field_name)
        if v < 0:
            errors.append({
                "field": field_name,
                "code": "invalid_value",
                "message": f"{field_name} must be >= 0",
            })

    # location_node_id must exist
    nodes = ds.get_nodes()
    if not any(n["id"] == req.location_node_id for n in nodes):
        errors.append({
            "field": "location_node_id",
            "code": "not_found",
            "message": f"Node '{req.location_node_id}' not found",
        })

    # allowed_cargo_classes: must be non-empty and all valid
    if not req.allowed_cargo_classes:
        errors.append({
            "field": "allowed_cargo_classes",
            "code": "required",
            "message": "At least one cargo class must be selected",
        })
    else:
        for cls in req.allowed_cargo_classes:
            if cls not in _VALID_CLASSES:
                errors.append({
                    "field": "allowed_cargo_classes",
                    "code": "invalid_class",
                    "message": f"Unknown cargo class: {cls}",
                })

    return errors


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/warehouse/list")
def list_warehouses():
    """List all registered warehouses. All carry source_status: simulated (P13)."""
    return {"warehouses": [_wh_public(wh) for wh in ds.get_warehouses()]}


@router.post("/warehouse/register", status_code=201)
def register_warehouse(req: WarehouseRegisterRequest):
    """Register a new warehouse node (FR-4)."""
    errors = _validate_warehouse_request(req)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    wh_id = f"wh-{str(uuid.uuid4())[:8]}"
    warehouse = {
        "id": wh_id,
        "name": req.name,
        "location_node_id": req.location_node_id,
        "total_capacity_t": req.total_capacity_t,
        "capacity_used_t": 0.0,
        "storage_cost_per_t_per_day": req.storage_cost_per_t_per_day,
        "handling_in_cost_per_t": req.handling_in_cost_per_t,
        "handling_out_cost_per_t": req.handling_out_cost_per_t,
        "allowed_cargo_classes": req.allowed_cargo_classes,
        "source_status": "simulated",
    }
    ds.add_warehouse(warehouse)
    return _wh_public(ds.get_warehouse_by_id(wh_id))


@router.post("/warehouse/stage")
def propose_staging(req: StagingProposalRequest):
    """Propose a staging plan (read-only). FR-8: only offered when wait >= threshold. P12."""
    # Resolve cargo
    cargo = next((c for c in ds.get_cargo() if c["id"] == req.cargo_id), None)
    if not cargo:
        raise HTTPException(status_code=404, detail=f"Cargo {req.cargo_id!r} not found")

    if req.booking_id:
        bk = ds.get_booking_by_id(req.booking_id)
        if not bk:
            raise HTTPException(status_code=404, detail=f"Booking {req.booking_id!r} not found")
        if bk["cargo_id"] != req.cargo_id:
            raise HTTPException(status_code=409, detail={"error": "booking_cargo_mismatch"})

    staging_threshold_h: float = val("warehouse", "staging_wait_threshold_h")

    # FR-8: do not offer staging below threshold
    if req.next_sailing_wait_h < staging_threshold_h:
        return {
            "proposals": [],
            "ineligible_warehouses": [],
            "staging_threshold_h": staging_threshold_h,
        }

    # Resolve origin and destination nodes
    nodes = ds.get_nodes()
    origin_node = next((n for n in nodes if n["id"] == cargo.get("origin_node_id")), None)
    dest_node = next((n for n in nodes if n["id"] == cargo.get("destination_node_id")), None)
    if not origin_node or not dest_node:
        raise HTTPException(status_code=404, detail="Cargo origin or destination node not found")

    warehouses = ds.get_warehouses()

    # find_eligible_warehouses checks proximity, class, and capacity
    eligible, ineligible = find_eligible_warehouses(cargo, origin_node, warehouses, nodes)

    proposals = []
    for wh in eligible:
        # Resolve warehouse location node for leg computations
        wh_node = next((n for n in nodes if n["id"] == wh.get("location_node_id")), origin_node)

        plan = compute_staging_plan(
            cargo=cargo,
            warehouse=wh,
            next_sailing_wait_h=req.next_sailing_wait_h,
            destination_node=dest_node,
            origin_node=wh_node,          # warehouse location node
            deadline_h=req.deadline_h,
            cargo_origin_node=origin_node, # cargo's actual origin
        )
        # Store proposal in data_store for confirm step (P12)
        ds.add_staging_proposal(plan["proposal_id"], {
            **plan,
            "warehouse_id": wh["id"],
            "weight_t": cargo["weight_t"],
            "booking_id": req.booking_id,
        })
        proposals.append(plan)

    return {
        "proposals": proposals,
        "ineligible_warehouses": ineligible,
        "staging_threshold_h": staging_threshold_h,
    }


@router.post("/warehouse/stage/confirm")
def confirm_staging(req: StagingConfirmRequest):
    """Confirm a staging proposal; applies capacity change. FR-7, P12."""
    proposal = ds.get_staging_proposal(req.proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail={"error": "proposal_not_found"})

    warehouse_id = proposal["warehouse_id"]
    weight_t = proposal["weight_t"]

    # Booking guards run before any state change (P11, P12)
    booking = ds.get_booking_by_id(proposal["booking_id"]) if proposal.get("booking_id") else None
    if booking is not None:
        if booking.get("status") == "pending_review":
            raise HTTPException(status_code=400, detail={"error": "compliance_review_required"})
        if booking.get("staging"):
            raise HTTPException(status_code=409, detail={"error": "booking_already_staged"})

    # Re-check capacity at confirmation time (authoritative guard — FR-7, SC-4)
    wh = ds.get_warehouse_by_id(warehouse_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    if wh["capacity_used_t"] + weight_t > wh["total_capacity_t"]:
        raise HTTPException(status_code=409, detail={"error": "warehouse_at_capacity"})

    # Apply capacity change
    ds.update_warehouse_capacity(warehouse_id, weight_t)
    ds.remove_staging_proposal(req.proposal_id)

    if booking is not None:
        booking["staging"] = {
            "warehouse_id": warehouse_id, "proposal_id": req.proposal_id,
            "total_cost_inr": proposal.get("total_cost_inr"), "total_time_h": proposal.get("total_time_h"),
            "source_status": "simulated",
        }
        booking.setdefault("event_log", []).append({
            "id": f"{booking['id']}-ev-{len(booking.get('event_log', [])) + 1}",
            "event_type": "staging_confirmed",
            "timestamp": _ist_now(),
            "detail": f"Cargo staged at {wh['name']} (Rs {proposal.get('total_cost_inr', 0):,.0f}) — simulated.",
            "source_status": "simulated",
        })

    updated_wh = ds.get_warehouse_by_id(warehouse_id)
    return {
        "booking_id": proposal.get("booking_id"),
        "warehouse_id": warehouse_id,
        "capacity_used_t": updated_wh["capacity_used_t"],
        "available_capacity_t": round(
            updated_wh["total_capacity_t"] - updated_wh["capacity_used_t"], 4
        ),
    }


@router.get("/warehouse/utilisation")
def warehouse_utilisation():
    """Warehouse utilisation summary [simulated]. Resets on demo reset (FR-11, P13)."""
    rows = []
    for wh in ds.get_warehouses():
        cap_used = wh.get("capacity_used_t", 0.0)
        total = wh.get("total_capacity_t", 0.0)
        rows.append({
            "warehouse_id": wh["id"],
            "name": wh["name"],
            "total_capacity_t": total,
            "capacity_used_t": cap_used,
            "available_capacity_t": round(total - cap_used, 4),
            "utilisation_pct": round((cap_used / total * 100) if total > 0 else 0.0, 2),
            "source_status": "simulated",
        })
    return {"utilisation": rows, "source_status": "simulated"}
