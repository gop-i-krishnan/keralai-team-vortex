"""
backend/api/llm/adapter.py
Abstract base class for LLM adapters.
Constitution P2: LLM may ONLY parse text → structured data.
                 Never price, rank, score, or recommend.
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class LLMAdapter(ABC):
    @abstractmethod
    def parse_shipment_text(self, text: str) -> dict:
        """
        Parse free-text shipment request into structured dict.
        Returns keys: weight_t, origin_raw, destination_raw, deadline_raw, confidence.
        MUST NOT return cost, score, recommendation, or ranking.
        """
        ...
