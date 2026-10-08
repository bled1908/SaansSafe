"""Deterministic 72-hour outlook: coverage, IST grouping, summaries, reuse of engine + policy."""

from datetime import UTC, datetime, timedelta

import pytest
from support import NOW, T0, H, make_series

from saanssafe.aqi import Category, InsufficientDataError, Pollutant, aqi_from_hourly
from saanssafe.decision import SchoolAction, Severity, decide_school_safety
from saanssafe.outlook import IST, OUTLOOK_HOURS, build_outlook, period_label
from saanssafe.readings import HourlyReading, ReadingSeries

START = T0 + 30 * H  # NOW floored: 2026-10-08 06:00 UTC = 11:30 IST (Thu)
CLEAN = {"pm2_5": 15.0, "pm10": 10.0, "no2": 20.0, "so2": 10.0, "o3": 40.0, "co": 0.5}  # AQI 40, Good


def varying_series(hours: int, pm25_at) -> ReadingSeries:
    readings = tuple(
        HourlyReading(T0 + H * i, **{**CLEAN, "pm2_5": pm25_at(i)}) for i in range(hours)
    )
    return ReadingSeries(28.6, 77.2, "open-meteo", readings)


def polluting_later(i: int) -> float:
    return 15.0 if i < 60 else 400.0  # clean, then heavy PM2.5 from T0+60h


# --- Coverage -----------------------------------------------------------------------------

def test_covers_current_hour_plus_72_hours():
    outlook = build_outlook(make_series(hours=130), NOW)
    assert len(outlook.hours) == OUTLOOK_HOURS + 1 == 73
    assert outlook.hours[0].valid_for_hour == START
    assert outlook.hours[-1].valid_for_hour == START + 72 * H
    assert outlook.complete is True


def test_truncates_honestly_when_data_ends_early():
    outlook = build_outlook(make_series(hours=61), NOW)  # last hour T0+60h
    assert len(outlook.hours) == 31
    assert outlook.hours[-1].valid_for_hour == T0 + 60 * H
    assert outlook.complete is False


def test_current_hour_not_covered_is_insufficient():
    with pytest.raises(InsufficientDataError):
        build_outlook(make_series(hours=20), NOW)


def test_current_hour_without_enough_pollutants_is_insufficient():
    sparse = make_series(hours=130, pm10=None, no2=None, so2=None, o3=None, co=None)
    with pytest.raises(InsufficientDataError):
        build_outlook(sparse, NOW)


def test_invalid_horizon_rejected():
    with pytest.raises(ValueError):
        build_outlook(make_series(hours=130), NOW, hours=0)


# --- Reuse of the CPCB engine and the SaansSafe policy -----------------------------------------

def test_each_hour_reuses_engine_and_policy_exactly():
    series = varying_series(130, polluting_later)
    outlook = build_outlook(series, NOW)
    for i in (0, 10, 35, 50, 72):
        hour = outlook.hours[i]
        expected = aqi_from_hourly(series.hourly_until(hour.valid_for_hour))
        assert hour.result == expected
        assert hour.decision == decide_school_safety(expected)


def test_dominant_pollutant_follows_engine():
    outlook = build_outlook(varying_series(130, polluting_later), NOW)
    assert outlook.hours[0].result.dominant is Pollutant.O3  # clean air: ozone 40 leads
    assert outlook.hours[-1].result.dominant is Pollutant.PM25  # heavy PM2.5 later


def test_severe_hours_stay_401_plus():
    outlook = build_outlook(make_series(hours=130, pm2_5=400.0), NOW)
    worst = outlook.worst
    assert worst.result.display == "401+" and worst.result.beyond_scale
    assert worst.result.category is Category.SEVERE
    assert worst.decision.severity is Severity.CRITICAL
    assert all(h.decision.action is SchoolAction.SUSPEND_OUTDOOR for h in outlook.hours)


# --- IST grouping ---------------------------------------------------------------------------------

def test_periods_follow_ist_school_clock():
    outlook = build_outlook(make_series(hours=130), NOW)
    labels = [p.label for p in outlook.periods]
    assert labels == [
        "This morning", "This afternoon", "Tonight",
        "Tomorrow morning", "Tomorrow afternoon", "Tomorrow night",
        "Saturday morning", "Saturday afternoon", "Saturday night",
        "Sunday morning",
    ]
    first, afternoon, tonight = outlook.periods[:3]
    assert (len(first.hours), first.partial) == (1, True)  # 11:30 IST only
    assert (len(afternoon.hours), afternoon.partial, afternoon.school_hours) == (6, False, True)
    assert (len(tonight.hours), tonight.partial, tonight.school_hours) == (12, False, False)
    assert afternoon.start.astimezone(IST).hour == 12 and afternoon.end.astimezone(IST).hour == 18


def test_periods_are_contiguous_and_cover_every_hour_once():
    outlook = build_outlook(make_series(hours=130), NOW)
    assert sum(len(p.hours) for p in outlook.periods) == len(outlook.hours)
    for prev, curr in zip(outlook.periods, outlook.periods[1:]):
        assert prev.end == curr.start


def test_early_morning_belongs_to_overnight():
    now = T0 + 20 * H + timedelta(minutes=5)  # 20:05 UTC = 01:35 IST Thu
    outlook = build_outlook(make_series(hours=130), now)
    assert outlook.periods[0].label == "Overnight"
    assert outlook.periods[0].part == "night"
    assert outlook.periods[1].label == "This morning"


@pytest.mark.parametrize(
    ("day_offset", "part", "label"),
    [(0, "morning", "This morning"), (1, "afternoon", "Tomorrow afternoon"), (-1, "night", "Overnight"),
     (0, "night", "Tonight"), (1, "night", "Tomorrow night"), (2, "morning", "Saturday morning")],
)
def test_period_labels(day_offset, part, label):
    today = datetime(2026, 10, 8, tzinfo=IST).date()  # Thursday
    assert period_label(today + timedelta(days=day_offset), part, today) == label


# --- Deterministic summaries ---------------------------------------------------------------------------

def test_summary_finds_change_restriction_worst_and_best_period():
    outlook = build_outlook(varying_series(130, polluting_later), NOW)
    now_action = outlook.hours[0].decision.action
    assert now_action is SchoolAction.NORMAL and outlook.hours[0].restricted is False

    change = outlook.next_change
    i_change = outlook.hours.index(change)
    assert change.decision.action is not now_action
    assert all(h.decision.action is now_action for h in outlook.hours[1:i_change])

    restricted = outlook.first_restricted
    i_restricted = outlook.hours.index(restricted)
    assert restricted.restricted is True
    assert not any(h.restricted for h in outlook.hours[:i_restricted])

    ranks = [(h.decision.severity.rank, h.result.aqi) for h in outlook.hours]
    assert (outlook.worst.decision.severity.rank, outlook.worst.result.aqi) == max(ranks)
    assert outlook.worst.decision.severity is Severity.CRITICAL

    best = outlook.best_school_period
    candidates = [p for p in outlook.periods if p.school_hours and p.school_day and not p.partial]
    assert best in candidates
    best_rank = (best.worst.decision.severity.rank, best.worst.result.aqi)
    assert best_rank == min((p.worst.decision.severity.rank, p.worst.result.aqi) for p in candidates)


# --- Best school window: Monday–Friday only (v1) -----------------------------------------------

SATURDAY_IST = datetime(2026, 10, 10, tzinfo=IST).date()


def weekend_is_cleaner(i: int) -> float:
    """Heavy PM2.5 through Friday; clean air from Saturday 00:30 IST (T0+67h) onwards."""
    return 400.0 if i < 67 else 15.0


def test_weekend_period_never_becomes_best_school_period():
    outlook = build_outlook(varying_series(140, weekend_is_cleaner), NOW)
    best = outlook.best_school_period
    assert best is not None
    assert best.school_day and best.day.weekday() < 5
    assert all(not p.school_day for p in outlook.periods if p.day >= SATURDAY_IST)


def test_weekday_wins_even_when_weekend_air_is_better():
    outlook = build_outlook(varying_series(140, weekend_is_cleaner), NOW)
    best = outlook.best_school_period
    weekend = [p for p in outlook.periods if p.school_hours and not p.partial and not p.school_day]
    assert weekend, "fixture must include full weekend school-hours periods"
    milder_weekend = min(weekend, key=lambda p: (p.worst.decision.severity.rank, p.worst.result.aqi))
    assert (milder_weekend.worst.decision.severity.rank, milder_weekend.worst.result.aqi) < (
        best.worst.decision.severity.rank,
        best.worst.result.aqi,
    )  # the weekend really is cleaner...
    assert best.school_day  # ...yet a weekday period is chosen


def test_no_weekday_school_period_returns_none():
    saturday_night = T0 + 67 * H + timedelta(minutes=5)  # Sat 00:35 IST
    # A 48 h horizon spans Sat 00:30 -> Mon 00:30 IST: weekend-only school periods.
    outlook = build_outlook(make_series(hours=150), saturday_night, hours=48)
    assert not any(p.school_hours and p.school_day and not p.partial for p in outlook.periods)
    assert outlook.best_school_period is None
    assert outlook.worst is not None and outlook.first_restricted is not None  # other summaries unaffected


def test_weekday_rule_leaves_other_summaries_unchanged():
    outlook = build_outlook(varying_series(140, weekend_is_cleaner), NOW)
    ranks = [(h.decision.severity.rank, h.result.aqi) for h in outlook.hours]
    assert (outlook.worst.decision.severity.rank, outlook.worst.result.aqi) == max(ranks)  # full 72 h
    assert outlook.first_restricted is outlook.hours[0]


def test_best_school_period_is_deterministic():
    series = varying_series(140, weekend_is_cleaner)
    assert build_outlook(series, NOW).best_school_period == build_outlook(series, NOW).best_school_period


def test_school_day_follows_ist_date():
    outlook = build_outlook(make_series(hours=130), NOW)
    flags = {p.label: p.school_day for p in outlook.periods}
    assert flags["This afternoon"] and flags["Tomorrow morning"]  # Thu, Fri
    assert not flags["Saturday morning"] and not flags["Sunday morning"]


def test_steady_air_has_no_change():
    outlook = build_outlook(make_series(hours=130), NOW)
    assert outlook.next_change is None
    assert outlook.first_restricted is outlook.hours[0]  # Moderate restricts PE from now


def test_outlook_is_deterministic():
    series = varying_series(130, polluting_later)
    assert build_outlook(series, NOW) == build_outlook(series, NOW)


def test_timestamps_are_utc_hours():
    outlook = build_outlook(make_series(hours=130), NOW)
    assert all(h.valid_for_hour.tzinfo is UTC and h.valid_for_hour.minute == 0 for h in outlook.hours)
    assert outlook.hours[0].valid_for_hour == datetime(2026, 10, 8, 6, tzinfo=UTC)
