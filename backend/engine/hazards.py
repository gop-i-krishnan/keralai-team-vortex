"""
backend/engine/hazards.py
Pure hazard hard-filter engine.
Constitution P2: deterministic, no I/O, no LLM calls.
Constitution P11: excluded sailings always appear in the excluded list with named reasons.
"""
from __future__ import annotations
from backend.engine.config import ConfigError, get_hazard_rule
from backend.engine.registry import effective_status


def apply_hazard_filters(
    cargo_class: str,
    sailings: list[dict],
    vessels: list[dict],
    hazard_rules: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Apply hazard hard-filters to a list of sailings.

    Two filters run in order for each sailing:
    1. Mode filter: if 'water' is not in the rule's allowed_modes, exclude with
       reason 'mode_not_permitted_for_class'.
    2. Certification filter: if certification_required is True and the vessel
       does not have cargo_class in its hazard_certs, exclude with reason
       'missing_hazmat_cert'.

    Raises ConfigError if cargo_class is not found in hazard_rules.

    Returns (eligible_sailings, excluded_list).
    excluded_list items: {sailing_id, vessel_id, reason}.

    P11: excluded sailings MUST NOT be silently dropped.
    P2: pure function — same inputs → same outputs.
    """
    # Look up the rule — raises ConfigError for unknown class (SC-5)
    rule = get_hazard_rule(cargo_class)

    # Build vessel lookup map for O(1) access
    vessel_map: dict[str, dict] = {v["id"]: v for v in vessels}

    eligible: list[dict] = []
    excluded: list[dict] = []

    hazardous = bool(rule.get("certification_required", False) or rule.get("human_review_required", False))

    for sailing in sailings:
        # Vessel-status filters (Feature 004 FR-7, FR-8) run before mode/cert filters
        status = effective_status(vessel_map.get(sailing.get("vessel_id", ""), {}))
        if status == "suspended":
            excluded.append({
                "sailing_id": sailing["id"],
                "vessel_id": sailing.get("vessel_id", ""),
                "reason": "vessel_suspended",
            })
            continue
        if hazardous and status != "verified":
            excluded.append({
                "sailing_id": sailing["id"],
                "vessel_id": sailing.get("vessel_id", ""),
                "reason": "unverified_vessel_for_hazmat",
            })
            continue

        # Mode filter: water mode must be permitted for this class
        if "water" not in rule.get("allowed_modes", []):
            excluded.append({
                "sailing_id": sailing["id"],
                "vessel_id": sailing.get("vessel_id", ""),
                "reason": "mode_not_permitted_for_class",
            })
            continue

        # Certification filter: if required, vessel must carry the cert
        if rule.get("certification_required", False):
            vessel = vessel_map.get(sailing.get("vessel_id", ""), {})
            certs: list[str] = vessel.get("hazard_certs", [])
            if cargo_class not in certs:
                excluded.append({
                    "sailing_id": sailing["id"],
                    "vessel_id": sailing.get("vessel_id", ""),
                    "reason": "missing_hazmat_cert",
                })
                continue

        eligible.append(sailing)

    return eligible, excluded
