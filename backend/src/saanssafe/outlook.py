"""Deterministic 72-hour school outlook built from a ReadingSeries.

Every hour reuses the CPCB engine (aqi_from_hourly over that hour's own 24 h window)
and the SaansSafe school policy (decide_school_safety). Nothing here calculates AQI
differently, and no LLM is involved. Grouping into school-facing periods is plain
date arithmetic in IST:
    morning   06:00-12:00 IST
    afternoon 12:00-18:00 IST
    night     18:00-06:00 IST (belongs to the date it starts on)
An hour belongs to the period containing its IST start time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

from saanssafe.aqi import AqiResult, InsufficientDataError, aqi_from_hourly
from saanssafe.decision import Guidance, SafetyDecision, decide_school_safety
from saanssafe.readings import HOUR, ReadingSeries

IST = timezone(timedelta(hours=5, minutes=30), "IST")
OUTLOOK_HOURS = 72  # hours after the current hour
PART_HOURS = {"morning": 6, "afternoon": 6, "night": 12}
SCHOOL_WEEKDAYS = frozenset({0, 1, 2, 3, 4})  # date.weekday(): Monday=0 .. Friday=4
BEST_SCHOOL_PERIOD_RULE = (
    "SaansSafe v1 treats Monday–Friday as school days for best-school-window selection."
)


@dataclass(frozen=True)
class HourOutlook:
    valid_for_hour: datetime  # UTC hour start
    result: AqiResult | None = None  # None: not enough data for this hour
    decision: SafetyDecision | None = None

    @property
    def restricted(self) -> bool | None:
        """True when the policy limits or moves any activity indoors."""
        if self.decision is None:
            return None
        return any(g is not Guidance.ALLOWED for g in self.decision.activities.values())


def _rank(hour: HourOutlook) -> tuple[int, int]:
    assert hour.decision is not None and hour.result is not None
    return (hour.decision.severity.rank, hour.result.aqi)


def _worst(hours: tuple[HourOutlook, ...]) -> HourOutlook | None:
    worst: HourOutlook | None = None
    for hour in hours:
        if hour.decision is not None and (worst is None or _rank(hour) > _rank(worst)):
            worst = hour  # strict ">" keeps the earliest hour on ties
    return worst


@dataclass(frozen=True)
class Period:
    label: str
    part: str  # "morning" | "afternoon" | "night"
    day: date  # IST date the period starts on
    hours: tuple[HourOutlook, ...]

    @property
    def start(self) -> datetime:
        return self.hours[0].valid_for_hour

    @property
    def end(self) -> datetime:
        return self.hours[-1].valid_for_hour + HOUR

    @property
    def school_hours(self) -> bool:
        return self.part != "night"

    @property
    def school_day(self) -> bool:
        """Whether the period's IST date is a school day (v1: Monday–Friday)."""
        return self.day.weekday() in SCHOOL_WEEKDAYS

    @property
    def partial(self) -> bool:
        return len(self.hours) < PART_HOURS[self.part]

    @property
    def worst(self) -> HourOutlook | None:
        return _worst(self.hours)


@dataclass(frozen=True)
class Outlook:
    hours: tuple[HourOutlook, ...]  # hours[0] is the current hour
    periods: tuple[Period, ...]
    requested_hours: int

    @property
    def complete(self) -> bool:
        return len(self.hours) == self.requested_hours + 1 and all(h.decision for h in self.hours)

    @property
    def worst(self) -> HourOutlook | None:
        return _worst(self.hours)

    @property
    def next_change(self) -> HourOutlook | None:
        """First later hour whose school action differs from the current hour's."""
        now = self.hours[0].decision
        assert now is not None
        return next((h for h in self.hours[1:] if h.decision and h.decision.action != now.action), None)

    @property
    def first_restricted(self) -> HourOutlook | None:
        return next((h for h in self.hours if h.restricted), None)

    @property
    def best_school_period(self) -> Period | None:
        """The full weekday school-hours period with the mildest worst hour (earliest on ties).

        Weekends never qualify (BEST_SCHOOL_PERIOD_RULE); None if no weekday period does.
        """
        best: Period | None = None
        for period in self.periods:
            worst = period.worst
            if not (period.school_hours and period.school_day) or period.partial or worst is None:
                continue
            if best is None or _rank(worst) < _rank(best.worst):  # type: ignore[arg-type]
                best = period
        return best


def _period_key(hour: datetime) -> tuple[date, str]:
    ist = hour.astimezone(IST)
    if 6 <= ist.hour < 12:
        return ist.date(), "morning"
    if 12 <= ist.hour < 18:
        return ist.date(), "afternoon"
    night_date = ist.date() if ist.hour >= 18 else ist.date() - timedelta(days=1)
    return night_date, "night"


def period_label(day: date, part: str, today: date) -> str:
    delta = (day - today).days
    weekday = day.strftime("%A")
    if part == "night":
        return {-1: "Overnight", 0: "Tonight", 1: "Tomorrow night"}.get(delta, f"{weekday} night")
    if delta == 0:
        return f"This {part}"
    if delta == 1:
        return f"Tomorrow {part}"
    return f"{weekday} {part}"


def hour_outlook(series: ReadingSeries, hour: datetime) -> HourOutlook:
    try:
        result = aqi_from_hourly(series.hourly_until(hour))
    except InsufficientDataError:
        return HourOutlook(hour)
    return HourOutlook(hour, result, decide_school_safety(result))


def build_outlook(series: ReadingSeries, now: datetime, hours: int = OUTLOOK_HOURS) -> Outlook:
    """Outlook from the current hour through `hours` later (or the end of the data)."""
    if hours < 1:
        raise ValueError("hours must be >= 1")
    start = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    last = series.last_time
    if last is None or last < start:
        raise InsufficientDataError("Forecast data does not cover the current hour")
    count = min(hours, int((last - start) / HOUR)) + 1
    items = tuple(hour_outlook(series, start + HOUR * i) for i in range(count))
    if items[0].decision is None:
        raise InsufficientDataError("Not enough forecast data for the current hour")

    today = start.astimezone(IST).date()
    keys: list[tuple[date, str]] = []
    groups: list[list[HourOutlook]] = []
    for item in items:
        key = _period_key(item.valid_for_hour)
        if not keys or keys[-1] != key:
            keys.append(key)
            groups.append([])
        groups[-1].append(item)
    periods = tuple(
        Period(period_label(day, part, today), part, day, tuple(group))
        for (day, part), group in zip(keys, groups, strict=True)
    )
    return Outlook(items, periods, hours)
