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


def get(section: str, key: str):
    """Return the raw value dict for CFG[section][key]."""
    return CFG[section][key]


def val(section: str, key: str) -> float | int | str:
    """Return just the numeric/string value for CFG[section][key]."""
    return CFG[section][key]["value"]
