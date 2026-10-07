"""
backend/engine/parser.py
Pure text-parsing helpers.
Constitution P2: LLM may only call these helpers; it never calls engine functions.
Constitution P7: low-confidence results are flagged for human review.
Constitution P9: scrub_pii called before any text goes to LLM.
"""
from __future__ import annotations
import re
from typing import Optional

from rapidfuzz import fuzz

from backend.engine.config import val


# ── PII scrubbing ─────────────────────────────────────────────────────────────

_PHONE_RE = re.compile(r'\b\d{10}\b|\+\d[\d\s\-]{8,14}\d')
_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}')


def scrub_pii(text: str) -> str:
    """Remove phone numbers and email addresses before sending to LLM."""
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    return text


# ── Regex-based structured extract ───────────────────────────────────────────

_WEIGHT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:tonnes?|tons?|t\b)', re.IGNORECASE)
_FROM_RE   = re.compile(r'(?:from|frm)\s+([A-Za-z][A-Za-z\s]+?)(?:\s+to\b|$)', re.IGNORECASE)
_TO_RE     = re.compile(r'(?:\bto\b)\s+([A-Za-z][A-Za-z\s]+?)(?:\s+by\b|\s+before\b|$)', re.IGNORECASE)


def regex_parse(text: str) -> dict:
    """
    Extract structured fields from free text using regex only.
    Returns partial dict; missing fields are None.
    Used as LLM fallback (Constitution P8).
    """
    result: dict = {}

    m = _WEIGHT_RE.search(text)
    result["weight_t"] = float(m.group(1)) if m else None

    m = _FROM_RE.search(text)
    result["origin_raw"] = m.group(1).strip() if m else None

    m = _TO_RE.search(text)
    result["destination_raw"] = m.group(1).strip() if m else None

    result["deadline_raw"] = None  # deadline resolved separately
    return result


# ── Node fuzzy matching (2-stage: substring → rapidfuzz) ─────────────────────

def fuzzy_match_node(raw: str, nodes: list[dict]) -> Optional[dict]:
    """
    Stage 1: case-insensitive substring match against name + alternate_names.
    Stage 2: rapidfuzz WRatio >= config threshold.
    Returns matched node dict or None.
    """
    raw_lower = raw.strip().lower()

    # Stage 1: substring
    for node in nodes:
        names = [node["name"]] + node.get("alternate_names", [])
        for n in names:
            if raw_lower in n.lower() or n.lower() in raw_lower:
                return node

    # Stage 2: fuzzy
    cutoff = val("matching", "fuzzy_match_cutoff")
    best_score = 0
    best_node = None
    for node in nodes:
        names = [node["name"]] + node.get("alternate_names", [])
        for n in names:
            score = fuzz.WRatio(raw_lower, n.lower())
            if score > best_score:
                best_score = score
                best_node = node

    if best_score >= cutoff:
        return best_node
    return None


# ── Deadline resolution ───────────────────────────────────────────────────────

# Matches: "10h", "10 hr", "10 hours", "10 hour", "in 10 hours", "urgent 3 hours",
#          "within 2 hours", "by 5 hours" — any leading words before the number are ignored.
_DEADLINE_H_RE = re.compile(r'\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b', re.IGNORECASE)
_DEADLINE_AMPM_RE = re.compile(r'(?:by\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)', re.IGNORECASE)


def resolve_deadline(text: str) -> Optional[float]:
    """
    Return deadline in hours-from-now if parseable, else None.
    Handles "X hours", "X hrs", "Xh", "in X hours", "by X hours", "urgent X hours".
    Also handles "by H am/pm" as an approximate hour-of-day value.
    """
    m = _DEADLINE_H_RE.search(text)
    if m:
        return float(m.group(1))

    m = _DEADLINE_AMPM_RE.search(text)
    if m:
        hour = int(m.group(1))
        meridiem = m.group(3).lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        return float(hour)  # approximate: treat as deadline hour of day

    return None


# ── Operator vessel message (Feature 004) ─────────────────────────────────────

_VESSEL_TYPE_RE = re.compile(r'\b(barge|country boat|boat|launch|vessel|ferry)\b', re.IGNORECASE)
_ROUTE_RE = re.compile(r'\b(?:going(?:\s+to)?|towards?|to)\s+([A-Za-z][A-Za-z ]*?)\s*(?:,|$|\.)', re.IGNORECASE)


def parse_vessel_message(text: str) -> dict:
    """
    Extract vessel fields from an operator message using regex only.
    PII is scrubbed first (P15). Never raises; missing fields are None.
    Confidence is the sum of weights for fields found (structural, not a model score).
    """
    text = scrub_pii(text or "")
    out: dict = {"capacity_t": None, "vessel_type": None, "home_raw": None, "route_hint_raw": None}

    m = _WEIGHT_RE.search(text)
    if m:
        out["capacity_t"] = float(m.group(1)) if "." in m.group(1) else int(m.group(1))
    m = _VESSEL_TYPE_RE.search(text)
    if m:
        out["vessel_type"] = m.group(1).lower()
    m = _ROUTE_RE.search(text)
    if m:
        out["route_hint_raw"] = m.group(1).strip()

    segments = [s.strip() for s in text.split(",")]
    anchor = next((i for i, s in enumerate(segments) if _WEIGHT_RE.search(s)), None)
    if anchor is not None and anchor + 1 < len(segments):
        cand = segments[anchor + 1]
        if (re.fullmatch(r"[A-Za-z][A-Za-z ]*", cand)
                and not re.match(r"(?i)(free|going|call|to|available)\b", cand)):
            out["home_raw"] = cand

    conf = 0.0
    if out["capacity_t"] is not None:
        conf += val("vessel_parse", "weight_capacity")
    if out["vessel_type"]:
        conf += val("vessel_parse", "weight_type")
    if out["home_raw"]:
        conf += val("vessel_parse", "weight_home")
    if out["route_hint_raw"]:
        conf += val("vessel_parse", "weight_route")
    out["confidence"] = round(conf, 2)
    return out
