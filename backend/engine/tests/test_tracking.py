"""Feature 005 — milestone tracking helpers (pure)."""
import pytest
from backend.engine import tracking
from backend.engine.config import val


def test_milestone_order():
    assert tracking.MILESTONES == ("Booked", "Loading", "In Transit", "Arrived", "Delivered")


def test_advance_walks_sequence_then_raises_final():
    i = 0
    seen = []
    while True:
        try:
            i = tracking.advance_milestone(i)
            seen.append(tracking.MILESTONES[i])
        except tracking.FinalMilestone:
            break
    assert seen == ["Loading", "In Transit", "Arrived", "Delivered"]


@pytest.mark.parametrize("idx,expected", [(0, "n1"), (1, "n1"), (2, "n2"), (3, "n3"), (4, "n3")])
def test_current_node_three_stop_route(idx, expected):
    assert tracking.current_node(["n1", "n2", "n3"], idx) == expected


@pytest.mark.parametrize("idx", [0, 1, 2])
def test_current_node_two_stop_route_in_transit_is_origin(idx):
    assert tracking.current_node(["n1", "n2"], idx) == "n1"


def test_current_node_arrived_two_stop_is_destination():
    assert tracking.current_node(["n1", "n2"], 3) == "n2"


def test_format_hhmm_wraps_and_pads():
    assert tracking.format_hhmm(5 * 60 + 7) == "05:07"
    assert tracking.format_hhmm(25 * 60) == "01:00"
    assert tracking.format_hhmm(-30) == "23:30"


def test_elapsed_h_across_midnight():
    assert tracking.elapsed_h("22:00", "02:00") == pytest.approx(4.0)
    assert tracking.elapsed_h("06:00", "06:00") == 0


def test_schedule_derives_from_departure_and_sail_time():
    sched = tracking.milestone_schedule("05:00", "06:00", 6.0)
    names = [m["name"] for m in sched]
    assert names == list(tracking.MILESTONES)
    t = {m["name"]: m["planned_time"] for m in sched}
    assert t["Booked"] == "05:00"
    assert t["In Transit"] == "06:00"
    assert t["Loading"] == tracking.format_hhmm(6 * 60 - int(val("tracking", "loading_lead_h") * 60))
    assert t["Arrived"] == "12:00"
    assert t["Delivered"] == tracking.format_hhmm(12 * 60 + int(val("tracking", "unloading_h") * 60))
    assert all(m["source_status"] == "simulated" for m in sched)
