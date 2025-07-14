"""
backend/engine/tests/test_reliability.py
Tests for reliability scoring (pure function, TDD).
"""
from backend.engine import reliability as rel


def test_road_base_score():
    score = rel.score_reliability("road", monsoon=False, night=False)
    assert 0 < score <= 1.0


def test_water_base_score():
    score = rel.score_reliability("hybrid", monsoon=False, night=False)
    assert 0 < score <= 1.0


def test_road_higher_than_water_baseline():
    road = rel.score_reliability("road", monsoon=False, night=False)
    water = rel.score_reliability("hybrid", monsoon=False, night=False)
    assert road > water


def test_monsoon_reduces_water():
    normal = rel.score_reliability("hybrid", monsoon=False, night=False)
    monsoon = rel.score_reliability("hybrid", monsoon=True, night=False)
    assert monsoon < normal


def test_night_sailing_reduces_water():
    day = rel.score_reliability("hybrid", monsoon=False, night=False)
    night = rel.score_reliability("hybrid", monsoon=False, night=True)
    assert night < day


def test_monsoon_does_not_affect_road():
    normal = rel.score_reliability("road", monsoon=False, night=False)
    monsoon = rel.score_reliability("road", monsoon=True, night=False)
    assert normal == monsoon


def test_score_clamped_between_0_and_1():
    for mode in ("road", "hybrid"):
        for m in (True, False):
            for n in (True, False):
                s = rel.score_reliability(mode, monsoon=m, night=n)
                assert 0.0 <= s <= 1.0, f"Score {s} out of range for mode={mode} monsoon={m} night={n}"
