"""
backend/engine/reliability.py
Pure reliability scoring for road and hybrid (water) modes.
Constitution P2: deterministic, no I/O.
Constitution P3: all constants from config.
"""
from backend.engine.config import val


def score_reliability(mode: str, monsoon: bool = False, night: bool = False) -> float:
    """
    Return a reliability score in [0, 1] for the given mode.
    mode: "road" | "hybrid"
    monsoon: True during June–September
    night: True when sailing departs after 20:00
    """
    if mode == "road":
        score = val("reliability", "road_base_score")
        # Road reliability unaffected by monsoon or night in this model
    else:  # hybrid / water
        score = val("reliability", "water_base_score")
        if monsoon:
            score -= val("reliability", "monsoon_penalty")
        if night:
            score -= val("reliability", "night_sailing_penalty")

    return max(0.0, min(1.0, float(score)))
