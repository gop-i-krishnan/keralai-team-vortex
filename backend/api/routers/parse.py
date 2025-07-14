"""
backend/api/routers/parse.py
POST /parse — parse free-text shipment request.
Constitution P2: LLM only parses; engine does the work.
Constitution P7: needs_review flag surfaced when confidence is low.
Constitution P8: falls back to regex when JALSETU_MOCK_LLM=1 or LLM fails.
"""
import os
from fastapi import APIRouter
from backend.api.models import ParseRequest, ParsedShipment
from backend.engine.parser import scrub_pii, regex_parse, fuzzy_match_node, resolve_deadline
from backend.engine.config import val
from backend import data_store as ds

router = APIRouter()


def _get_adapter():
    if os.environ.get("JALSETU_MOCK_LLM", "1") == "1":
        from backend.api.llm.mock import MockAdapter
        return MockAdapter()
    try:
        from backend.api.llm.watsonx import WatsonxAdapter
        return WatsonxAdapter()
    except Exception:
        from backend.api.llm.mock import MockAdapter
        return MockAdapter()


@router.post("/parse", response_model=ParsedShipment)
def parse_shipment(req: ParseRequest):
    nodes = ds.get_nodes()
    threshold = val("llm", "confidence_threshold")

    adapter = _get_adapter()
    raw = adapter.parse_shipment_text(req.text)
    method = "llm" if os.environ.get("JALSETU_MOCK_LLM", "1") != "1" else "mock"

    # Fallback to regex for any missing fields
    if not raw.get("weight_t") or not raw.get("origin_raw"):
        regex = regex_parse(req.text)
        for k in ("weight_t", "origin_raw", "destination_raw", "deadline_raw"):
            if not raw.get(k) and regex.get(k):
                raw[k] = regex[k]
        method = "regex"

    # Resolve node IDs via fuzzy matching
    origin_node = fuzzy_match_node(raw.get("origin_raw") or "", nodes) if raw.get("origin_raw") else None
    dest_node = fuzzy_match_node(raw.get("destination_raw") or "", nodes) if raw.get("destination_raw") else None

    # Resolve deadline
    deadline_h = None
    if raw.get("deadline_raw"):
        deadline_h = resolve_deadline(raw["deadline_raw"])

    confidence = float(raw.get("confidence", 0.5))
    needs_review = confidence < threshold or not origin_node or not dest_node or not raw.get("weight_t")

    return ParsedShipment(
        weight_t=raw.get("weight_t"),
        origin_raw=raw.get("origin_raw"),
        destination_raw=raw.get("destination_raw"),
        origin_node_id=origin_node["id"] if origin_node else None,
        destination_node_id=dest_node["id"] if dest_node else None,
        deadline_raw=raw.get("deadline_raw"),
        deadline_h=deadline_h,
        confidence=confidence,
        needs_review=needs_review,
        method=method,
    )
