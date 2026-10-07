"""
backend/engine/history.py
Pure delivery-history helpers and Bayesian reliability (Feature 004).
Constitution P2: deterministic, no I/O, no clock, no ids minted here.
Constitution P3: prior and wrap constants from data/config.yaml.
Constitution P14: rate is always reported with its trip count; only recorded
delivery events are inputs (no ratings).
"""
from __future__ import annotations
import re

from backend.engine.config import val

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
VALID_STATUSES = ("on_time", "late", "incident")


def _to_min(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def delay_minutes(planned_eta: str, actual_arrival: str) -> int:
    """actual − planned in minutes; negative = early. Wraps across midnight."""
    d = _to_min(actual_arrival) - _to_min(planned_eta)
    wrap_min = val("history", "midnight_wrap_h") * 60
    day = 24 * 60
    if d < -wrap_min:
        d += day
    elif d > wrap_min:
        d -= day
    return int(d)


def _rate(on_time: int, total: int) -> float:
    k = val("history", "prior_trip_count")
    p = val("history", "prior_on_time_rate")
    return round((on_time + k * p) / (total + k), 4)


def compute_reliability(records: list[dict]) -> dict:
    """Bayesian on-time rate: (on_time + k*prior) / (total + k)."""
    total = len(records)
    on_time = sum(1 for r in records if r.get("status") == "on_time")
    incidents = sum(1 for r in records if r.get("status") == "incident")

    trend = []
    running = 0
    for i, r in enumerate(records, start=1):
        if r.get("status") == "on_time":
            running += 1
        trend.append({"trip_number": i, "running_on_time_rate": _rate(running, i)})

    recorded_only = total > 0 and all(r.get("source_status") == "recorded" for r in records)
    tag = "recorded" if recorded_only else "simulated"
    delays = [r.get("delay_min", 0) for r in records]
    return {
        "total_trips": total,
        "on_time_trips": on_time,
        "on_time_rate": _rate(on_time, total),
        "avg_delay_min": round(sum(delays) / total, 1) if total else None,
        "incident_count": incidents,
        "trip_count_label": f"{total} trips [{tag}]",
        "reliability_trend": trend,
        "source_status": tag,
    }


def build_delivery_record(
    record_id: str, vessel_id: str, booking_id: str,
    planned_eta: str, actual_arrival: str, status: str, cargo_class: str,
) -> tuple[dict | None, list[dict]]:
    """Return (record, errors). Status comes from the caller, never inferred."""
    errors: list[dict] = []
    if not isinstance(actual_arrival, str) or not _HHMM.match(actual_arrival):
        errors.append({"field": "actual_arrival", "code": "invalid_time",
                       "message": "actual_arrival must be HH:MM (IST), 00:00–23:59"})
    if status not in VALID_STATUSES:
        errors.append({"field": "status", "code": "invalid_status",
                       "message": "status must be one of: " + ", ".join(VALID_STATUSES)})
    if errors:
        return None, errors
    return {
        "id": record_id,
        "vessel_id": vessel_id,
        "booking_id": booking_id,
        "planned_eta": planned_eta,
        "actual_arrival": actual_arrival,
        "delay_min": delay_minutes(planned_eta, actual_arrival),
        "status": status,
        "cargo_class": cargo_class,
        "source_status": "recorded",
    }, []


def planned_eta_for_sailing(sailing: dict, nodes: list[dict]) -> str:
    """HH:MM IST planned arrival: departure + straight-line x tortuosity / speed (same model as options)."""
    from backend.engine.geo import haversine_km
    by_id = {n["id"]: n for n in nodes}
    o, d = by_id[sailing["origin_node_id"]], by_id[sailing["destination_node_id"]]
    km = haversine_km(o["lat"], o["lon"], d["lat"], d["lon"]) * val("water", "tortuosity_factor")
    sail_min = round(km / val("water", "speed_kmh") * 60)
    t = (_to_min(sailing["departure_time"]) + sail_min) % (24 * 60)
    return f"{t // 60:02d}:{t % 60:02d}"
