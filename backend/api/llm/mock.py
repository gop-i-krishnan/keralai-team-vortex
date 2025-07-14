"""
backend/api/llm/mock.py
MockAdapter — returns deterministic fixture results.
Activated by JALSETU_MOCK_LLM=1 (Constitution P8: offline demo must work).
"""
from __future__ import annotations
import re
from backend.api.llm.adapter import LLMAdapter

# Fixtures keyed by a pattern in the text
_FIXTURES: list[tuple[str, dict]] = [
    ("kochi.*alappuzha|thevara.*alleppey", {
        "weight_t": 10.0,
        "origin_raw": "Kochi Thevara Jetty",
        "destination_raw": "Alappuzha Boat Jetty",
        "deadline_raw": "10 hours",
        "confidence": 0.95,
    }),
    ("alappuzha.*kollam|alleppey.*quilon", {
        "weight_t": 5.0,
        "origin_raw": "Alappuzha Boat Jetty",
        "destination_raw": "Kollam Jetty",
        "deadline_raw": "8 hours",
        "confidence": 0.90,
    }),
]

_DEFAULT_FIXTURE = {
    "weight_t": None,
    "origin_raw": None,
    "destination_raw": None,
    "deadline_raw": None,
    "confidence": 0.50,
}


class MockAdapter(LLMAdapter):
    def parse_shipment_text(self, text: str) -> dict:
        lower = text.lower()
        for pattern, fixture in _FIXTURES:
            if re.search(pattern, lower):
                return dict(fixture)
        return dict(_DEFAULT_FIXTURE)
