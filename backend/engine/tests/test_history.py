"""Feature 004 — delivery history and Bayesian reliability (P14, SC-3, SC-4)."""
import pytest
from backend.engine import history
from backend.engine.config import val


def _rec(status, delay=0, src="simulated"):
    return {"vessel_id": "v", "status": status, "delay_min": delay, "source_status": src}


def test_zero_records_returns_prior():
    r = history.compute_reliability([])
    assert r["total_trips"] == 0
    assert r["on_time_rate"] == pytest.approx(val("history", "prior_on_time_rate"))
    assert r["avg_delay_min"] is None
    assert r["reliability_trend"] == []
    assert r["trip_count_label"] == "0 trips [simulated]"


def test_bayesian_rate_hand_calculated():
    k = val("history", "prior_trip_count")
    p = val("history", "prior_on_time_rate")
    recs = [_rec("on_time")] * 3 + [_rec("late", 30), _rec("incident", 60)]
    expected = round((3 + k * p) / (5 + k), 4)
    r = history.compute_reliability(recs)
    assert r["total_trips"] == 5 and r["on_time_trips"] == 3
    assert r["on_time_rate"] == expected
    assert r["incident_count"] == 1
    assert r["trip_count_label"] == "5 trips [simulated]"


def test_one_more_on_time_trip_changes_rate_by_formula():
    k = val("history", "prior_trip_count")
    p = val("history", "prior_on_time_rate")
    base = [_rec("on_time"), _rec("late", 20)]
    before = history.compute_reliability(base)
    after = history.compute_reliability(base + [_rec("on_time")])
    assert after["on_time_trips"] == before["on_time_trips"] + 1
    assert after["on_time_rate"] == round((2 + k * p) / (3 + k), 4)


def test_trend_has_one_point_per_record_in_order():
    recs = [_rec("on_time"), _rec("late", 10), _rec("on_time")]
    t = history.compute_reliability(recs)["reliability_trend"]
    assert [x["trip_number"] for x in t] == [1, 2, 3]
    assert t[-1]["running_on_time_rate"] == history.compute_reliability(recs)["on_time_rate"]


def test_runtime_records_label_recorded():
    r = history.compute_reliability([_rec("on_time", 0, "recorded")])
    assert r["trip_count_label"] == "1 trips [recorded]"


def test_deterministic():
    recs = [_rec("on_time"), _rec("late", 15)]
    assert history.compute_reliability(recs) == history.compute_reliability(recs)


def test_delay_minutes_early_late_and_wrap():
    assert history.delay_minutes("08:00", "08:30") == 30
    assert history.delay_minutes("08:00", "07:50") == -10
    # arrives just after midnight for a 23:30 plan -> +60, not -1380
    assert history.delay_minutes("23:30", "00:30") == 60


def test_build_delivery_record_status_from_caller_not_delay():
    rec, errs = history.build_delivery_record(
        "del-x", "vessel-001", "bk-1", "08:00", "08:05", "incident", "general")
    assert errs == []
    assert rec["status"] == "incident" and rec["delay_min"] == 5
    assert rec["source_status"] == "recorded"


@pytest.mark.parametrize("arr,status,field", [
    ("25:00", "on_time", "actual_arrival"),
    ("8am", "on_time", "actual_arrival"),
    ("08:00", "great", "status"),
])
def test_build_delivery_record_validation(arr, status, field):
    rec, errs = history.build_delivery_record("d", "v", "b", "08:00", arr, status, "general")
    assert rec is None
    assert errs[0]["field"] == field
