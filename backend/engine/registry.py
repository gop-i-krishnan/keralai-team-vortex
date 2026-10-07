"""
backend/engine/registry.py
Pure vessel/sailing validation and lifecycle (Feature 004).
Constitution P2: no I/O. Errors are structured {field, code, message}.
"""
from __future__ import annotations
import re

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# FR-1: the only permitted lifecycle transitions.
_TRANSITIONS = {
    ("draft", "submit"): "pending_verification",
    ("pending_verification", "verify"): "verified",
    ("verified", "suspend"): "suspended",
    ("suspended", "reinstate"): "verified",
}


class InvalidTransition(ValueError):
    """Raised for a lifecycle transition not allowed by FR-1."""


def effective_status(vessel: dict) -> str:
    """Legacy vessels without a status are treated as verified."""
    return vessel.get("status") or "verified"


def transition_status(current: str, action: str) -> str:
    try:
        return _TRANSITIONS[(current, action)]
    except KeyError:
        raise InvalidTransition(f"Cannot '{action}' a vessel in state '{current}'") from None


def _err(field: str, code: str, message: str) -> dict:
    return {"field": field, "code": code, "message": message}


def _positive(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def validate_registration(
    payload: dict, node_ids: set, operator_ids: set, class_ids: set, existing_vessels: list[dict],
) -> list[dict]:
    errs: list[dict] = []
    name = payload.get("vessel_name")
    if not isinstance(name, str) or not name.strip():
        errs.append(_err("vessel_name", "required", "Vessel name is required"))
    for f, label in (("capacity_t", "Capacity (t)"), ("draft_m", "Draft (m)")):
        v = payload.get(f)
        if v is None:
            errs.append(_err(f, "required", f"{label} is required"))
        elif not _positive(v):
            errs.append(_err(f, "not_positive", f"{label} must be a number greater than 0"))
    jetty = payload.get("home_jetty_id")
    if not jetty:
        errs.append(_err("home_jetty_id", "required", "Home jetty is required"))
    elif jetty not in node_ids:
        errs.append(_err("home_jetty_id", "not_found", f"Unknown jetty: {jetty}"))
    contact = payload.get("contact")
    if not isinstance(contact, str) or not contact.strip():
        errs.append(_err("contact", "required", "Contact is required (fictional in demo)"))
    op = payload.get("operator_id")
    if not op:
        errs.append(_err("operator_id", "required", "Operator is required"))
    elif op not in operator_ids:
        errs.append(_err("operator_id", "not_found", f"Unknown operator: {op}"))
    for c in payload.get("hazard_certs") or []:
        if c not in class_ids:
            errs.append(_err("hazard_certs", "invalid_class", f"Unknown cargo class: {c}"))
    if not errs and any(
        v.get("name") == name.strip() and v.get("home_jetty_id") == jetty for v in existing_vessels
    ):
        errs.append(_err("vessel_name", "duplicate_vessel",
                         "A vessel with this name and home jetty is already registered"))
    return errs


def validate_sailing(payload: dict, vessel: dict, node_ids: set) -> list[dict]:
    if effective_status(vessel) == "suspended":
        return [_err("vessel_id", "vessel_suspended",
                     "This vessel is suspended — existing bookings unaffected; no new sailings can be published.")]
    errs: list[dict] = []
    route = payload.get("route_node_ids") or []
    if len(route) < 2:
        errs.append(_err("route_node_ids", "too_few_stops", "Route needs at least two jetties"))
    else:
        bad = [n for n in route if n not in node_ids]
        if bad:
            errs.append(_err("route_node_ids", "not_found", f"Unknown jetty: {bad[0]}"))
    days = payload.get("weekdays") or []
    if not days:
        errs.append(_err("weekdays", "required", "Choose at least one weekday"))
    elif any(d not in WEEKDAYS for d in days):
        errs.append(_err("weekdays", "invalid_day", "Weekdays must be Mon..Sun"))
    t = payload.get("departure_time")
    if not isinstance(t, str) or not _HHMM.match(t):
        errs.append(_err("departure_time", "invalid_time", "Departure must be HH:MM (IST)"))
    if not _positive(payload.get("price_per_t")):
        errs.append(_err("price_per_t", "not_positive", "Price per tonne must be greater than 0"))
    cap = payload.get("capacity_offered_t")
    if not _positive(cap):
        errs.append(_err("capacity_offered_t", "not_positive", "Capacity offered must be greater than 0"))
    elif cap > vessel.get("capacity_t", 0):
        errs.append(_err("capacity_offered_t", "exceeds_vessel_capacity",
                         "Capacity offered cannot exceed the vessel's capacity"))
    return errs
