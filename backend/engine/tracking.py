"""
backend/engine/tracking.py
Pure milestone helpers (Feature 005). Times are HH:MM IST strings.
Constitution P2: no I/O, no clock. P13: every milestone is simulated.
Constitution P10: positions are node ids only (no live GPS).
"""
from __future__ import annotations

from backend.engine.config import val
from backend.engine.geo import haversine_km

MILESTONES = ("Booked", "Loading", "In Transit", "Arrived", "Delivered")

_DAY_MIN = 24 * 60


class FinalMilestone(ValueError):
    """Raised when a booking is already at the last milestone."""


def to_minutes(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def format_hhmm(minutes: float) -> str:
    m = int(round(minutes)) % _DAY_MIN
    return f"{m // 60:02d}:{m % 60:02d}"


def elapsed_h(ready_time: str, now: str) -> float:
    """Hours from ready_time to now, wrapping past midnight."""
    return ((to_minutes(now) - to_minutes(ready_time)) % _DAY_MIN) / 60.0


def advance_milestone(index: int) -> int:
    if index >= len(MILESTONES) - 1:
        raise FinalMilestone("Booking already at final milestone.")
    return index + 1


def current_node(route: list[str], milestone_index: int) -> str:
    """
    Booked/Loading -> first node. In Transit -> the node before the destination
    (the last waterway node; the leg origin on a two-stop route). Arrived/Delivered -> last node.
    Simplification: no partial-leg position (P10).
    """
    if milestone_index <= 1:
        return route[0]
    if milestone_index == 2:
        return route[-2] if len(route) >= 2 else route[0]
    return route[-1]


def sail_time_h(origin: dict, destination: dict) -> float:
    km = haversine_km(origin["lat"], origin["lon"], destination["lat"], destination["lon"])
    return km * val("water", "tortuosity_factor") / val("water", "speed_kmh")


def milestone_schedule(ready_time: str, departure_time: str, sail_h: float) -> list[dict]:
    dep = to_minutes(departure_time)
    arrive = dep + sail_h * 60
    times = {
        "Booked": ready_time,
        "Loading": format_hhmm(dep - val("tracking", "loading_lead_h") * 60),
        "In Transit": format_hhmm(dep),
        "Arrived": format_hhmm(arrive),
        "Delivered": format_hhmm(arrive + val("tracking", "unloading_h") * 60),
    }
    return [{"name": n, "planned_time": times[n], "source_status": "simulated"} for n in MILESTONES]
