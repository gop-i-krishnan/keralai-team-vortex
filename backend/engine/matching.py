"""
backend/engine/matching.py
Pure capacity-matching engine.
Constitution P2: deterministic, no I/O.
Constitution P3: all weights from config.yaml.
Constitution P11: excluded sailings returned with named reasons.
"""
from __future__ import annotations
from typing import Optional
from backend.engine.config import val
from backend.engine.registry import effective_status


def rank_sailings(
    cargo: dict,
    sailings: list[dict],
    cargo_class: str = "general",
    vessels: Optional[list[dict]] = None,
    hazard_rules: Optional[list[dict]] = None,
) -> list[dict] | dict:
    """
    Return sailings that can carry `cargo`, ranked by a weighted score.
    Score = w_util * utilisation + w_sched * schedule_score.
    Tie-breaking: equal-score sailings sorted by ascending cost (0 when not present).

    When hazard_rules and vessels are provided (non-None, non-empty), the hazard
    hard-filter is applied first (Constitution P11). Returns a dict:
      {"ranked": [...], "excluded": [...]}

    When hazard_rules is None (legacy callers), returns a plain list for backward
    compatibility.

    Weights from config matching.score_weight_utilisation / score_weight_schedule (P3).
    """
    weight = cargo["weight_t"]
    origin = cargo["origin_node_id"]
    destination = cargo["destination_node_id"]

    w_util  = val("matching", "score_weight_utilisation")
    w_sched = val("matching", "score_weight_schedule")

    # ── Hazard hard-filter (FR-2, P11) ────────────────────────────────────────
    excluded: list[dict] = []
    if hazard_rules is not None and vessels is not None:
        from backend.engine.hazards import apply_hazard_filters
        sailings, excluded = apply_hazard_filters(
            cargo_class, sailings, vessels, hazard_rules
        )

    # ── Capacity and route filter ──────────────────────────────────────────────
    vessel_status = {v["id"]: effective_status(v) for v in (vessels or [])}
    penalty = val("registry", "unverified_reliability_penalty")
    results = []
    for s in sailings:
        if s["origin_node_id"] != origin:
            continue
        if s["destination_node_id"] != destination:
            continue
        cap = s.get("available_capacity_t", 0)
        if cap < weight:
            continue
        utilisation = min(weight / cap, 1.0)
        schedule_score = 0.5  # neutral placeholder
        score = w_util * utilisation + w_sched * schedule_score
        if vessel_status.get(s["vessel_id"]) == "pending_verification":
            score = max(0.0, score - penalty)  # FR-7: unverified penalty
        score = round(score, 4)
        entry = {
            "sailing_id": s["id"],
            "vessel_id": s["vessel_id"],
            "departure_time": s["departure_time"],
            "available_capacity_t": cap,
            "score": score,
        }
        if s.get("price_per_t") is not None:  # operator-quoted price → tie-break cost
            entry["cost_inr"] = round(s["price_per_t"] * weight, 2)
        results.append(entry)

    # Sort by score desc, then cost asc as tie-breaker (spec clarification)
    results.sort(key=lambda x: (-x["score"], x.get("cost_inr", 0)))

    # ── Return format ──────────────────────────────────────────────────────────
    if hazard_rules is None:
        # Backward-compatible: return plain list
        return results
    return {"ranked": results, "excluded": excluded}
