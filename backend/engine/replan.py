"""
backend/engine/replan.py
Pure disruption re-plan engine (Feature 005).
Constitution P2: deterministic, no I/O, no clock, no ids minted, no LLM.
Constitution P3: every threshold, penalty and rate comes from data/config.yaml.
Constitution P12: replan() only reads its inputs and returns a proposal.
Constitution P11: alternatives pass the hazard hard filter.
"""
from __future__ import annotations
import math

from backend.engine.config import (
    val, get_hazard_rule, get_hazard_rules, get_scoring_weights, get_notification_template,
)
from backend.engine.geo import haversine_km
from backend.engine.hazards import apply_hazard_filters
from backend.engine.options import build_plans
from backend.engine.reliability import score_reliability
from backend.engine.registry import effective_status
from backend.engine.tracking import elapsed_h, format_hhmm, to_minutes
from backend.engine.warehouse import find_eligible_warehouses

_NO_LIMIT = float("inf")


def classify_severity(expected_duration_h, slack_h: float) -> str:
    """minor / moderate / severe. Unknown duration or a missed deadline is severe."""
    if expected_duration_h is None or expected_duration_h > slack_h:
        return "severe"
    if expected_duration_h < val("replan", "severity_minor_max_h"):
        return "minor"
    if expected_duration_h <= val("replan", "severity_moderate_max_h"):
        return "moderate"
    return "severe"


def _route(s: dict) -> list[str]:
    return s.get("route_node_ids") or [s["origin_node_id"], s["destination_node_id"]]


def _usable_sailings(booking: dict, disruption: dict, sailings: list[dict], vessels: list[dict]) -> list[dict]:
    """Disruption filters (FR-2) then hazard/vessel-status hard filters (P11)."""
    kind, where = disruption["type"], disruption["location_node_id"]
    out = []
    for s in sailings:
        if kind == "vessel_breakdown" and s["vessel_id"] == booking.get("vessel_id"):
            continue
        if kind == "low_depth" and where in _route(s):
            continue
        if kind == "jetty_closed" and where in (s["origin_node_id"], s["destination_node_id"]):
            continue
        out.append(s)
    eligible, _excluded = apply_hazard_filters(
        booking.get("cargo_class", "general"), out, vessels, get_hazard_rules())
    return eligible


def _rel(mode: str, weather: bool) -> float:
    r = score_reliability(mode)
    if weather and mode == "hybrid":
        r = max(0.0, r - val("replan", "weather_reliability_penalty"))
    return round(r, 4)


def _score(alts: list[dict]) -> None:
    w = get_scoring_weights()

    def norm(vals):
        lo, hi = min(vals), max(vals)
        return [1.0] * len(vals) if hi == lo else [(hi - v) / (hi - lo) for v in vals]

    if len(alts) == 1:
        a = alts[0]
        a["score"] = round(1.0 - w["reliability"] + w["reliability"] * a["reliability_score"], 4)
        return
    nc = norm([a["extra_cost_inr"] for a in alts])
    nt = norm([a["new_total_time_h"] for a in alts])
    ne = norm([a["co2_kg"] for a in alts])
    for i, a in enumerate(alts):
        a["score"] = round(w["cost"] * nc[i] + w["time"] * nt[i] + w["co2"] * ne[i]
                           + w["reliability"] * a["reliability_score"], 4)


def replan(booking: dict, disruption: dict, sailings: list[dict], nodes: list[dict],
           vessels: list[dict], warehouses: list[dict]) -> dict:
    """
    Compute ranked alternatives from the cargo's current node. Pure and read-only.
    Time of the disruption (HH:MM IST) is taken from disruption["detected_at"].
    """
    from backend.engine.tracking import current_node

    N = {n["id"]: n for n in nodes}
    route = booking.get("route_node_ids") or [booking["origin_node_id"], booking["destination_node_id"]]
    cur_id = current_node(route, booking.get("milestone_index", 0))
    cur, org, dst = N[cur_id], N[booking["origin_node_id"]], N[booking["destination_node_id"]]
    W = booking["weight_t"]
    kind = disruption["type"]
    dur = disruption.get("expected_duration_h")
    now = disruption["detected_at"]
    ready = booking["ready_time"]
    elapsed = elapsed_h(ready, now)
    planned_t = booking["planned_time_h"]
    cls = booking.get("cargo_class", "general")
    weather = kind == "weather_delay"
    cargo = {"weight_t": W, "cargo_class": cls}

    buffer_h = val("perishable", "schedule_buffer_h") if cls == "perishable" else val("scoring", "deadline_buffer_h")
    limit_h = booking["deadline_h"] - buffer_h

    alts: list[dict] = []

    def add(type_, extra, total, co2, rel, reason, completes=True, **more):
        alts.append({
            "id": f"alt-{type_}", "type": type_,
            "extra_cost_inr": round(extra, 2),
            "new_total_time_h": round(total, 2),
            "new_eta": format_hhmm(to_minutes(ready) + total * 60),
            "total_time_delta_h": round(total - planned_t, 2),
            "deadline_met": bool(completes and total <= limit_h),
            "reliability_score": rel, "co2_kg": round(co2, 2),
            "reason": reason, "score": 0.0, "source_status": "simulated", **more,
        })

    # 1. wait_and_continue ------------------------------------------------------
    if dur is not None:
        extra = W * val("replan", "wait_cost_per_t_h") * dur
        add("wait_and_continue", extra, planned_t + dur, 0.0, _rel("hybrid", weather),
            f"Wait {dur:g} h for the original plan to resume; waiting cost Rs {extra:,.0f} [assumed].")

    if cur_id != booking["destination_node_id"] and cur.get("type") == "jetty":
        # 2. truck_from_jetty ---------------------------------------------------
        road = build_plans(W, cur, dst, now, _NO_LIMIT, [], cargo_class=cls)["plans"]["road"]
        delay = val("replan", "road_blocked_delay_h") if (kind == "road_blocked" and
                                                           disruption["location_node_id"] == cur_id) else 0.0
        add("truck_from_jetty", road["cost_inr"], elapsed + road["time_h"] + delay, road["co2_kg"],
            _rel("road", weather),
            f"Truck {road['distance_km']:.0f} km from {cur['name']} to {dst['name']}; "
            f"new spend Rs {road['cost_inr']:,.0f} (earlier payments treated as sunk) [assumed]."
            + (f" Includes {delay:g} h road-blocked delay." if delay else ""))

        # 3. alternative_vessel -------------------------------------------------
        virtual = []
        for s in _usable_sailings(booking, disruption, sailings, vessels):
            r = _route(s)
            if cur_id in r and booking["destination_node_id"] in r and r.index(cur_id) < r.index(booking["destination_node_id"]):
                virtual.append({**s, "origin_node_id": cur_id, "destination_node_id": booking["destination_node_id"]})
        hy = build_plans(W, cur, dst, now, _NO_LIMIT, virtual, cargo_class=cls)["plans"].get("hybrid") if virtual else None
        if hy:
            add("alternative_vessel", hy["cost_inr"], elapsed + hy["time_h"], hy["co2_kg"], _rel("hybrid", weather),
                f"Next sailing {hy['sailing_id']} from {cur['name']}: wait {hy['wait_h']:.1f} h + sail "
                f"{hy['sail_time_h']:.1f} h; port-to-port cost Rs {hy['cost_inr']:,.0f} [assumed].",
                sailing_id=hy["sailing_id"],
                vessel_id=next(s["vessel_id"] for s in virtual if s["id"] == hy["sailing_id"]))

    # 4. return_to_origin -------------------------------------------------------
    if cur_id != booking["origin_node_id"]:
        back = build_plans(W, cur, org, now, _NO_LIMIT, [], cargo_class=cls)["plans"]["road"]
        km_done = haversine_km(org["lat"], org["lon"], cur["lat"], cur["lon"]) * val("road", "road_factor")
        add("return_to_origin", back["cost_inr"], elapsed + back["time_h"], back["co2_kg"], _rel("road", weather),
            f"Truck back to {org['name']} ({back['distance_km']:.0f} km). Delivery is not completed; "
            f"the shipment would need re-booking.", completes=False,
            distance_already_travelled_km=round(km_done, 2),
            already_travelled_cost_inr=round(W * km_done * val("road", "rate_per_t_km"), 2))

    # 5. hold_warehouse ---------------------------------------------------------
    if dur is not None:
        eligible, _ = find_eligible_warehouses(cargo, cur, warehouses, nodes)
        best = None
        for wh in eligible:
            days = max(1, math.ceil(dur / 24))
            cost = W * (wh["handling_in_cost_per_t"] + wh["handling_out_cost_per_t"]) \
                + W * days * wh["storage_cost_per_t_per_day"]
            if best is None or cost < best[0]:
                best = (cost, wh, days)
        if best:
            cost, wh, days = best
            add("hold_warehouse", cost, planned_t + dur, 0.0, _rel("hybrid", weather),
                f"Hold at {wh['name']} for {days} day(s): handling in/out plus storage Rs {cost:,.0f} "
                f"[simulated warehouse; storage CO2 not modelled].", warehouse_id=wh["id"])

    # Rank: deadline-met first, then score, then lower extra cost (spec tie rule)
    if alts:
        _score(alts)
    alts.sort(key=lambda a: (not a["deadline_met"], -a["score"], a["extra_cost_inr"]))
    alts = alts[: int(val("replan", "max_alternatives"))]

    fallback = None
    if alts and not any(a["deadline_met"] for a in alts):
        completing = [a for a in alts if a["type"] != "return_to_origin"]
        if completing:
            fallback = min(completing, key=lambda a: a["new_total_time_h"])["id"]

    return {
        "proposal_id": f"{booking['id']}:{disruption['id']}",
        "booking_id": booking["id"], "disruption_id": disruption["id"],
        "current_node_id": cur_id, "alternatives": alts,
        "fastest_fallback_id": fallback, "no_alternatives_found": not alts,
        "source_status": "simulated",
    }


def render_notification(disruption_type: str, cargo_id: str, location_name: str, deadline: str) -> dict:
    """Render a template. Nothing is ever sent (delivered is always False)."""
    t = get_notification_template(disruption_type)
    return {
        "disruption_type": disruption_type,
        "subject_en": t["subject_en"],
        "body_rendered": t["body_en"].format(cargo_id=cargo_id, location=location_name, deadline=deadline),
        "delivered": False,
        "note": "message preview — not sent [simulated]",
        "source_status": "simulated",
    }
