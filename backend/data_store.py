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

def reset() -> None:
    """Restore state to seed. POST /demo/reset calls this."""
    global _state, _bookings
    _state = copy.deepcopy(_SEED)
    _bookings = []
