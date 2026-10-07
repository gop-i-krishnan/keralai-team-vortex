"""
backend/api/models.py
Pydantic request/response models for all three features.
Constitution P7: human_confirmed defaults False.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ── Feature 001: Shipment Decision Engine ────────────────────────────────────

class OptionsRequest(BaseModel):
    weight_t: float = Field(..., gt=0, description="Shipment weight in tonnes")
    origin_node_id: str
    destination_node_id: str
    ready_time: str = Field("06:00", description="Ready time HH:MM IST")
    deadline_h: float = Field(..., gt=0, description="Deadline in hours from ready_time")
    subsidy: bool = Field(False, description="Apply water subsidy scenario (OFF by default)")


class PlanDetail(BaseModel):
    mode: str
    cost_inr: float
    time_h: float
    co2_kg: float
    distance_km: Optional[float] = None
    source_status: str
    note: str
    subsidy_applied: Optional[bool] = None
    wait_h: Optional[float] = None
    sail_time_h: Optional[float] = None
    sailing_id: Optional[str] = None


class OptionsResponse(BaseModel):
    plans: dict[str, PlanDetail]
    recommended: str
    scores: dict[str, float]
    why: str


# ── Feature 002: Capacity Matching / Backhaul / Pooling ─────────────────────

class MatchRequest(BaseModel):
    cargo_id: str
    sailing_ids: Optional[list[str]] = None  # None = use all available sailings
    cargo_class: Optional[str] = Field(None, description="Override; defaults to the cargo record class, then 'general'")


class MatchedSailing(BaseModel):
    sailing_id: str
    vessel_id: str
    departure_time: str
    available_capacity_t: float
    score: float


class ExcludedSailing(BaseModel):
    sailing_id: str
    vessel_id: str
    reason: str  # "mode_not_permitted_for_class" | "missing_hazmat_cert"


class MatchResponse(BaseModel):
    cargo_id: str
    ranked: list[MatchedSailing]
    excluded: list[ExcludedSailing] = Field(default_factory=list)


class BookingRequest(BaseModel):
    cargo_id: str
    sailing_id: str
    deadline_h: Optional[float] = Field(None, gt=0, description="Hours from ready_time; defaults to demo config")
    ready_time: str = Field("06:00", pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$", description="HH:MM IST")
    human_confirmed: bool = Field(False, description="Must be True to confirm booking")


class BookingResponse(BaseModel):
    id: str
    cargo_id: str
    sailing_id: str
    human_confirmed: bool
    status: str  # "preview" | "confirmed"


class BackhaulResponse(BaseModel):
    booking_id: str
    opportunities: list[dict]


class PoolingResponse(BaseModel):
    booking_id: str
    opportunities: list[dict]


# ── Feature 003: Intake / Operator / Viability ───────────────────────────────

class ParseRequest(BaseModel):
    text: str = Field(..., description="Free-text shipment request from shipper/operator")


class ParsedShipment(BaseModel):
    weight_t: Optional[float] = None
    origin_raw: Optional[str] = None
    destination_raw: Optional[str] = None
    origin_node_id: Optional[str] = None
    destination_node_id: Optional[str] = None
    deadline_raw: Optional[str] = None
    deadline_h: Optional[float] = None
    confidence: float = 0.0
    needs_review: bool = True
    method: str = "regex"  # "regex" | "llm"


class OperatorMessageRequest(BaseModel):
    operator_id: str
    message: str


class ViabilityResponse(BaseModel):
    d_star_km: float
    corridors: list[dict]
    demand_summary: list[dict]


# ── Feature 004: Vessel registration and delivery history ────────────────────
# Fields are Optional so the engine (registry.py) reports per-field {field, code, message}.

class VesselRegisterRequest(BaseModel):
    vessel_name: Optional[str] = None
    registration_number: Optional[str] = Field(None, description="Placeholder - not validated")
    vessel_type: Optional[str] = None
    capacity_t: Optional[float | str] = None
    draft_m: Optional[float | str] = None
    home_jetty_id: Optional[str] = None
    hazard_certs: list[str] = Field(default_factory=list)
    contact: Optional[str] = None
    operator_id: Optional[str] = None


class SailingPublishRequest(BaseModel):
    vessel_id: str
    route_node_ids: list[str] = Field(default_factory=list)
    weekdays: list[str] = Field(default_factory=list)
    departure_time: Optional[str] = None
    price_per_t: Optional[float | str] = None
    capacity_offered_t: Optional[float | str] = None


class DeliverRequest(BaseModel):
    actual_arrival: Optional[str] = None
    status: Optional[str] = None


class VesselMessageRequest(BaseModel):
    message: str


# ── Feature 005: disruption, re-plan, cargo ──────────────────────────────────

class DisruptRequest(BaseModel):
    type: Optional[str] = None
    scenario_id: Optional[str] = None
    location_node_id: Optional[str] = None
    expected_duration_h: Optional[float | str] = None
    now_hhmm: Optional[str] = Field(None, description="Demo/test override, HH:MM IST")


class ReplanConfirmRequest(BaseModel):
    alternative_id: str


class ReplanReviewRequest(BaseModel):
    reviewer_note: str


class CargoCreateRequest(BaseModel):
    description: Optional[str] = None
    weight_t: Optional[float | str] = None
    cargo_class: Optional[str] = "general"
    origin_node_id: Optional[str] = None
    destination_node_id: Optional[str] = None
