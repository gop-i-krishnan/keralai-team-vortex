"""
backend/data_store.py
In-memory state for the running demo.
Loaded once from data/seed.json; reset restores to that initial state.
Constitution P10: no database — in-memory only.
"""
from __future__ import annotations
import copy
import json
import pathlib

_SEED_PATH = pathlib.Path(__file__).parent.parent / "data" / "seed.json"


def _load_seed() -> dict:
    with open(_SEED_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


_SEED: dict = _load_seed()

# Live mutable state
_state: dict = copy.deepcopy(_SEED)

# Bookings added at runtime
_bookings: list[dict] = []

# Compliance reviews keyed by booking_id (FR-3, P11)
_compliance_reviews: dict[str, dict] = {}

# Staging proposals keyed by proposal_id (FR-7, P12)
_staging_proposals: dict[str, dict] = {}

# Disruptions, re-plan proposals and re-plan compliance reviews (Feature 005)
_disruptions: list[dict] = []
_replan_proposals: dict[str, dict] = {}     # keyed by booking_id
_replan_reviews: dict[str, dict] = {}       # keyed by proposal_id

# Warehouses list — seeded from seed.json; runtime additions marked _is_seed=False
def _init_warehouses() -> list[dict]:
    warehouses = []
    for wh in _SEED.get("warehouses", []):
        warehouses.append({**copy.deepcopy(wh), "_is_seed": True})
    return warehouses

_warehouses: list[dict] = _init_warehouses()


def get_nodes() -> list[dict]:
    return _state["nodes"]

def get_vessels() -> list[dict]:
    return _state["vessels"]

def get_sailings() -> list[dict]:
    return _state["sailings"]

def get_corridors() -> list[dict]:
    return _state["corridors"]

def get_cargo() -> list[dict]:
    return _state["cargo"]

def get_operators() -> list[dict]:
    return _state["operators"]

def get_bookings() -> list[dict]:
    return list(_bookings)

def add_booking(booking: dict) -> None:
    _bookings.append(booking)

def get_booking_by_id(booking_id: str) -> dict | None:
    for b in _bookings:
        if b.get("id") == booking_id:
            return b
    return None

def confirm_booking(booking_id: str) -> dict | None:
    for b in _bookings:
        if b.get("id") == booking_id:
            b["human_confirmed"] = True
            return b
    return None

# ── Compliance reviews ────────────────────────────────────────────────────────

def add_compliance_review(booking_id: str, review: dict) -> None:
    _compliance_reviews[booking_id] = review

def get_compliance_review(booking_id: str) -> dict | None:
    return _compliance_reviews.get(booking_id)

def get_compliance_reviews() -> list[dict]:
    return list(_compliance_reviews.values())

# ── Staging proposals ─────────────────────────────────────────────────────────

def add_staging_proposal(proposal_id: str, proposal: dict) -> None:
    _staging_proposals[proposal_id] = proposal

def get_staging_proposal(proposal_id: str) -> dict | None:
    return _staging_proposals.get(proposal_id)

def remove_staging_proposal(proposal_id: str) -> None:
    _staging_proposals.pop(proposal_id, None)

# ── Warehouses ────────────────────────────────────────────────────────────────

def get_warehouses() -> list[dict]:
    return _warehouses

def add_warehouse(warehouse: dict) -> None:
    _warehouses.append({**warehouse, "_is_seed": False})

def get_warehouse_by_id(warehouse_id: str) -> dict | None:
    for wh in _warehouses:
        if wh.get("id") == warehouse_id:
            return wh
    return None

def update_warehouse_capacity(warehouse_id: str, delta_t: float) -> dict | None:
    """Increase capacity_used_t by delta_t. Returns updated warehouse or None."""
    for wh in _warehouses:
        if wh.get("id") == warehouse_id:
            wh["capacity_used_t"] = round(wh.get("capacity_used_t", 0.0) + delta_t, 4)
            return wh
    return None

# ── Vessels, sailings, delivery history (Feature 004) ─────────────────────────

def get_delivery_history() -> list[dict]:
    return _state.setdefault("delivery_history", [])

def add_delivery(record: dict) -> None:
    get_delivery_history().append(record)

def get_vessel_by_id(vessel_id: str) -> dict | None:
    return next((v for v in _state["vessels"] if v.get("id") == vessel_id), None)

def add_vessel(vessel: dict) -> None:
    _state["vessels"].append(vessel)

def add_sailing(sailing: dict) -> None:
    _state["sailings"].append(sailing)


# ── Disruptions / re-plan (Feature 005) ───────────────────────────────────────

def get_scenarios() -> list[dict]:
    return _state.get("disruption_scenarios", [])

def add_disruption(d: dict) -> None:
    _disruptions.append(d)

def get_disruptions() -> list[dict]:
    return list(_disruptions)

def get_open_disruption(booking_id: str) -> dict | None:
    for d in reversed(_disruptions):
        if d["booking_id"] == booking_id and d.get("status") == "open":
            return d
    return None

def get_latest_disruption(booking_id: str) -> dict | None:
    for d in reversed(_disruptions):
        if d["booking_id"] == booking_id:
            return d
    return None

def set_proposal(booking_id: str, proposal: dict) -> None:
    _replan_proposals[booking_id] = proposal

def get_proposal(booking_id: str) -> dict | None:
    return _replan_proposals.get(booking_id)

def get_proposal_by_id(proposal_id: str) -> dict | None:
    return next((p for p in _replan_proposals.values() if p["proposal_id"] == proposal_id), None)

def add_replan_review(proposal_id: str, review: dict) -> None:
    _replan_reviews[proposal_id] = review

def get_replan_review(proposal_id: str) -> dict | None:
    return _replan_reviews.get(proposal_id)

def add_cargo(cargo: dict) -> None:
    _state["cargo"].append(cargo)

# ── Reset ─────────────────────────────────────────────────────────────────────

def reset() -> None:
    """Restore state to seed. POST /demo/reset calls this.
    - Reloads nodes/vessels/sailings/corridors/cargo from seed.
    - Resets capacity_used_t to 0 for all seed warehouses.
    - Removes all runtime-registered warehouses.
    - Clears all compliance reviews and staging proposals.
    Constitution P8: must complete in < 1 second.
    """
    global _state, _bookings, _compliance_reviews, _staging_proposals, _warehouses
    global _disruptions, _replan_proposals, _replan_reviews
    _state = copy.deepcopy(_SEED)
    _bookings = []
    _compliance_reviews = {}
    _staging_proposals = {}
    _disruptions = []
    _replan_proposals = {}
    _replan_reviews = {}
    # Restore seed warehouses (reset capacity_used_t to 0), drop runtime ones
    _warehouses = _init_warehouses()
