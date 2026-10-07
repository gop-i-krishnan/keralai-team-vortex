"""
backend/engine/config.py
Loads data/config.yaml once at import time.
Constitution P3: all constants come from here, never hardcoded.
"""
from __future__ import annotations
import pathlib
import yaml

_CONFIG_PATH = pathlib.Path(__file__).parents[2] / "data" / "config.yaml"

def _load() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)

CFG: dict = _load()


class ConfigError(ValueError):
    """Raised when a required config entry is missing or invalid."""


def get(section: str, key: str):
    """Return the raw value dict for CFG[section][key]."""
    return CFG[section][key]


def val(section: str, key: str) -> float | int | str:
    """Return just the numeric/string value for CFG[section][key]."""
    return CFG[section][key]["value"]


def get_hazard_rules() -> list[dict]:
    """Return the full hazard_rules list from config.
    Returns an empty list if the section is absent (safe fallback).
    Constitution P3: hazard_rules is a list of dicts, not section/key/value shape.
    """
    return CFG.get("hazard_rules", [])


def get_hazard_rule(class_id: str) -> dict:
    """Return the single hazard rule for `class_id`.
    Raises ConfigError if the class is not found in hazard_rules.
    This is the canonical lookup — all engine modules must use this, not raw CFG access.
    """
    for rule in get_hazard_rules():
        if rule.get("class_id") == class_id:
            return rule
    raise ConfigError(
        f"Cargo class '{class_id}' not found in hazard_rules. "
        "Check data/config.yaml and verify with IWAI / PESO / state authority."
    )


def get_scoring_weights() -> dict:
    """Return {cost, time, co2, reliability} from scoring.weights. Raises ConfigError if absent."""
    w = CFG.get("scoring", {}).get("weights")
    needed = ("cost", "time", "co2", "reliability")
    if not w or any(k not in w for k in needed):
        raise ConfigError("scoring.weights must define cost, time, co2 and reliability")
    return {k: float(w[k]["value"]) for k in needed}


def get_notification_template(disruption_type: str) -> dict:
    for t in CFG.get("notifications", []):
        if t.get("type") == disruption_type:
            return t
    raise ConfigError(f"No notification template for disruption type '{disruption_type}'")
