"""Feature 005 — pure re-plan engine (SC-1, SC-2, SC-4, SC-5, SC-7)."""
import copy
import json
import pathlib
import pytest

from backend.engine import replan
from backend.engine.config import val
from backend.engine.geo import haversine_km

SEED = json.loads((pathlib.Path(__file__).parents[3] / "data" / "seed.json").read_text(encoding="utf-8"))
NODES = SEED["nodes"]
N = {n["id"]: n for n in NODES}
VESSELS = SEED["vessels"]
SAILINGS = SEED["sailings"]
WAREHOUSES = [dict(w) for w in SEED["warehouses"]]

BOOKING = {
    "id": "bk1", "cargo_id": "cargo-001", "weight_t": 10, "cargo_class": "general",
    "origin_node_id": "node-001", "destination_node_id": "node-002",
    "route_node_ids": ["node-001", "node-004", "node-002"],
    "sailing_id": "sailing-001", "vessel_id": "vessel-001",
    "ready_time": "06:00", "deadline_h": 10.0,
    "planned_cost_inr": 8200.0, "planned_time_h": 5.0, "milestone_index": 2, "status": "disrupted",
}


def dis(type_="vessel_breakdown", node="node-004", dur=4.0, at="06:00"):
    return {"id": "dis-1", "booking_id": "bk1", "type": type_, "location_node_id": node,
            "detected_at": at, "expected_duration_h": dur, "severity": "moderate",
            "source_status": "simulated"}


# A second vessel sailing Vaikom -> Alappuzha so an alternative_vessel can exist.
EXTRA = {"id": "sailing-x", "vessel_id": "vessel-007", "origin_node_id": "node-004",
         "destination_node_id": "node-002", "route_node_ids": ["node-004", "node-002"],
         "departure_time": "09:00", "available_capacity_t": 10, "price_per_t": 300}


def run(booking=BOOKING, disruption=None, sailings=None, warehouses=None, vessels=VESSELS):
    return replan.replan(booking, disruption or dis(), sailings if sailings is not None else SAILINGS,
                         NODES, vessels, warehouses if warehouses is not None else WAREHOUSES)


def types(p):
    return [a["type"] for a in p["alternatives"]]


# ── Severity ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dur,slack,expected", [
    (1.99, 10, "minor"), (2, 10, "moderate"), (6, 10, "moderate"), (6.01, 10, "severe"),
    (None, 10, "severe"), (3, 2, "severe"),
])
def test_severity_boundaries(dur, slack, expected):
    assert replan.classify_severity(dur, slack) == expected


# ── Alternatives ─────────────────────────────────────────────────────────────

def test_sc1_at_least_two_types_with_different_tradeoffs():
    p = run()
    assert len(p["alternatives"]) >= 2
    assert len({a["type"] for a in p["alternatives"]}) >= 2
    assert len({(a["extra_cost_inr"], a["new_total_time_h"]) for a in p["alternatives"]}) >= 2
    assert p["no_alternatives_found"] is False


def test_all_alternatives_carry_required_fields_and_simulated_tag():
    for a in run()["alternatives"]:
        for k in ("id", "type", "extra_cost_inr", "new_eta", "total_time_delta_h", "deadline_met",
                  "reliability_score", "reason", "score", "source_status"):
            assert k in a
        assert a["reason"]


def test_sc2_tight_deadline_only_truck_meets_and_ranks_first():
    b = {**BOOKING, "deadline_h": 2.0}
    p = run(b, dis(dur=4.0))
    met = [a["type"] for a in p["alternatives"] if a["deadline_met"]]
    assert met == ["truck_from_jetty"]
    assert p["alternatives"][0]["type"] == "truck_from_jetty"


def test_sc4_return_to_origin_cost_is_hand_calculated_road_cost():
    p = run()
    a = next(x for x in p["alternatives"] if x["type"] == "return_to_origin")
    km = haversine_km(N["node-004"]["lat"], N["node-004"]["lon"], N["node-001"]["lat"], N["node-001"]["lon"])
    km *= val("road", "road_factor")
    expected = round(10 * km * val("road", "rate_per_t_km"), 2)
    assert a["extra_cost_inr"] == pytest.approx(expected, abs=0.02)
    assert a["distance_already_travelled_km"] == pytest.approx(round(km, 2), abs=0.02)
    assert a["deadline_met"] is False


def test_return_to_origin_omitted_when_current_is_origin():
    b = {**BOOKING, "milestone_index": 0}
    assert "return_to_origin" not in types(run(b, dis(node="node-001")))


def test_wait_omitted_without_duration_and_present_with_it():
    assert "wait_and_continue" not in types(run(disruption=dis(dur=None)))
    w = next(a for a in run()["alternatives"] if a["type"] == "wait_and_continue")
    assert w["extra_cost_inr"] == pytest.approx(10 * val("replan", "wait_cost_per_t_h") * 4.0)
    assert w["new_total_time_h"] == pytest.approx(BOOKING["planned_time_h"] + 4.0)


def test_alternative_vessel_uses_other_sailing_and_never_the_broken_vessel():
    p = run(sailings=SAILINGS + [EXTRA])
    a = next(x for x in p["alternatives"] if x["type"] == "alternative_vessel")
    assert a["sailing_id"] == "sailing-x"
    broken = {**EXTRA, "id": "sailing-y", "vessel_id": "vessel-001"}
    p2 = run(sailings=[broken])
    assert "alternative_vessel" not in types(p2)


def test_low_depth_removes_sailings_through_node():
    assert "alternative_vessel" not in types(run(disruption=dis("low_depth"), sailings=SAILINGS + [EXTRA]))


def test_jetty_closed_removes_sailings_touching_node():
    p = run(disruption=dis("jetty_closed", node="node-002"), sailings=SAILINGS + [EXTRA])
    assert "alternative_vessel" not in types(p)


def test_road_blocked_adds_configured_delay_to_truck():
    base = next(a for a in run(disruption=dis("vessel_breakdown"))["alternatives"] if a["type"] == "truck_from_jetty")
    blocked = next(a for a in run(disruption=dis("road_blocked"))["alternatives"] if a["type"] == "truck_from_jetty")
    assert blocked["new_total_time_h"] - base["new_total_time_h"] == pytest.approx(
        val("replan", "road_blocked_delay_h"), abs=0.02)


def test_weather_delay_lowers_water_reliability_only():
    base = {a["type"]: a for a in run(disruption=dis("vessel_breakdown"))["alternatives"]}
    wx = {a["type"]: a for a in run(disruption=dis("weather_delay"))["alternatives"]}
    assert base["wait_and_continue"]["reliability_score"] - wx["wait_and_continue"]["reliability_score"] == \
        pytest.approx(val("replan", "weather_reliability_penalty"), abs=1e-3)
    assert base["truck_from_jetty"]["reliability_score"] == wx["truck_from_jetty"]["reliability_score"]


def test_hold_warehouse_needs_nearby_eligible_warehouse():
    near = [{**WAREHOUSES[0], "id": "wh-near", "location_node_id": "node-004"}]
    p = run(warehouses=near)
    h = next(a for a in p["alternatives"] if a["type"] == "hold_warehouse")
    wh = near[0]
    expected = 10 * (wh["handling_in_cost_per_t"] + wh["handling_out_cost_per_t"]) + 10 * 1 * wh["storage_cost_per_t_per_day"]
    assert h["extra_cost_inr"] == pytest.approx(expected)
    assert "hold_warehouse" not in types(run(warehouses=[]))


def test_hazardous_cargo_excludes_uncertified_and_unverified_vessels():
    b = {**BOOKING, "cargo_class": "flammable"}
    x = {**EXTRA, "vessel_id": "vessel-007"}   # vessel-007 has no flammable cert
    assert "alternative_vessel" not in types(run(b, sailings=SAILINGS + [x]))
    cert = [{**v} for v in VESSELS]
    for v in cert:
        if v["id"] == "vessel-007":
            v["hazard_certs"] = ["flammable"]
            v["status"] = "pending_verification"
    assert "alternative_vessel" not in types(run(b, sailings=SAILINGS + [x], vessels=cert))
    for v in cert:
        if v["id"] == "vessel-007":
            v["status"] = "verified"
    assert "alternative_vessel" in types(run(b, sailings=SAILINGS + [x], vessels=cert))


def test_suspended_vessel_not_offered():
    sus = [{**v, "status": "suspended"} if v["id"] == "vessel-007" else v for v in VESSELS]
    assert "alternative_vessel" not in types(run(sailings=SAILINGS + [EXTRA], vessels=sus))


# ── Fallbacks / empty ────────────────────────────────────────────────────────

def test_sc5_no_feasible_alternative_is_empty_not_exception():
    b = {**BOOKING, "origin_node_id": "node-004", "destination_node_id": "node-004",
         "route_node_ids": ["node-004", "node-004"], "milestone_index": 0}
    p = run(b, dis(dur=None, node="node-004"), sailings=[], warehouses=[])
    assert p["alternatives"] == [] and p["no_alternatives_found"] is True
    assert p["fastest_fallback_id"] is None


def test_fr4_no_deadline_met_sets_fastest_fallback():
    b = {**BOOKING, "deadline_h": 0.6}
    p = run(b, sailings=SAILINGS + [EXTRA], warehouses=[{**WAREHOUSES[0], "location_node_id": "node-004"}])
    assert all(a["deadline_met"] is False for a in p["alternatives"])
    completing = [a for a in p["alternatives"] if a["type"] != "return_to_origin"]
    fastest = min(completing, key=lambda a: a["new_total_time_h"])
    assert p["fastest_fallback_id"] == fastest["id"]


def test_max_alternatives_respected_and_ids_unique():
    p = run(sailings=SAILINGS + [EXTRA], warehouses=[{**WAREHOUSES[0], "location_node_id": "node-004"}])
    assert len(p["alternatives"]) <= val("replan", "max_alternatives")
    ids = [a["id"] for a in p["alternatives"]]
    assert len(ids) == len(set(ids))


def test_deadline_met_alternatives_rank_before_missed_ones():
    p = run()
    flags = [a["deadline_met"] for a in p["alternatives"]]
    assert flags == sorted(flags, reverse=True)


# ── Purity ───────────────────────────────────────────────────────────────────

def test_inputs_not_mutated_and_output_deterministic():
    b, d = copy.deepcopy(BOOKING), copy.deepcopy(dis())
    s, w = copy.deepcopy(SAILINGS + [EXTRA]), copy.deepcopy(WAREHOUSES)
    p1 = replan.replan(b, d, s, NODES, VESSELS, w)
    p2 = replan.replan(b, d, s, NODES, VESSELS, w)
    assert p1 == p2
    assert b == BOOKING and d == dis() and s == SAILINGS + [EXTRA] and w == WAREHOUSES


def test_proposal_identity_is_deterministic_and_simulated():
    p = run()
    assert p["proposal_id"] == "bk1:dis-1"
    assert p["source_status"] == "simulated"


# ── Notifications (SC-7) ─────────────────────────────────────────────────────

@pytest.mark.parametrize("t", ["vessel_breakdown", "low_depth", "jetty_closed", "road_blocked", "weather_delay"])
def test_notification_renders_for_every_type(t):
    n = replan.render_notification(t, "cargo-001", "Vaikom Jetty", "16:00")
    assert n["delivered"] is False
    assert n["body_rendered"] and "{" not in n["body_rendered"]
    assert "cargo-001" in n["body_rendered"] and "Vaikom Jetty" in n["body_rendered"]
    assert "not sent" in n["note"] and "[simulated]" in n["note"]
    assert n["source_status"] == "simulated"
