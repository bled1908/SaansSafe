"""Grounding facts and the notice data model for the Parent Notice.

`build_notice_facts` copies values that the existing GET /aqi and GET /forecast bodies
(`api.report_body`, `api.forecast_body`) already contain. Nothing is calculated here: no
AQI, no category, no school action. The only transformation is presenting UTC hours as
IST date/time strings, so parents see local times.

Both the deterministic template and any AI writer receive exactly these facts, and the
guard checks AI output against them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30), "IST")
LANGUAGES = ("en", "hi")


class NoticeFactsError(ValueError):
    """The /aqi or /forecast body is missing a value the notice needs."""


@dataclass(frozen=True)
class Moment:
    """One UTC hour from the API, also shown as an IST date and HH:MM."""

    utc: str  # as in the API, e.g. "2026-10-08T11:00:00Z"
    ist_date: date
    ist_time: str  # "16:30"


@dataclass(frozen=True)
class HourFact:
    """A /forecast hour (next change or worst hour): its time, AQI and policy action."""

    at: Moment
    aqi_display: str
    category: str
    action: str
    headline: str


@dataclass(frozen=True)
class WindowFact:
    """/forecast summary.best_school_period, with its worst hour's AQI and action."""

    label: str  # API label, e.g. "Tomorrow morning"
    part: str  # "morning" | "afternoon" | "night"
    start: Moment
    end: Moment
    worst: HourFact | None


@dataclass(frozen=True)
class NoticeFacts:
    language: str  # "en" | "hi"
    school_name: str | None
    valid_for: Moment
    aqi_display: str  # exactly as /aqi reports it ("401+" beyond the scale)
    beyond_scale: bool
    category: str  # CPCB category label
    health_statement: str  # CPCB Table 3.12 statement, verbatim from /aqi
    health_statement_source: str
    dominant_pollutant_code: str
    dominant_pollutant_name: str
    action: str
    severity: str
    headline: str
    activities: tuple[tuple[str, str], ...]  # (activity, guidance) in API order
    recommendations: tuple[str, ...]
    policy_name: str
    policy_version: str
    best_window: WindowFact | None
    next_change: HourFact | None
    worst: HourFact | None
    forecast_complete: bool
    forecast_hours: int
    forecast_requested_hours: int
    freshness_status: str  # "fresh" | "stale"
    age_minutes: int
    freshness_warning: str | None
    data_type: str
    disclaimer: str

    @property
    def stale(self) -> bool:
        return self.freshness_status == "stale"

    def grounding(self) -> dict[str, Any]:
        """JSON-ready copy of the facts, shown to users as "Facts used"."""
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class ParentNotice:
    """The part of a notice that a writer (template or AI) produces."""

    language: str
    title: str
    body: str
    key_points: tuple[str, ...]
    sign_off: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "key_points": list(self.key_points),
            "sign_off": self.sign_off,
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


# --- Extraction from the API bodies ---------------------------------------------------------

def _get(body: Mapping[str, Any], *path: str) -> Any:
    value: Any = body
    for name in path:
        if not isinstance(value, Mapping) or name not in value:
            raise NoticeFactsError(f"missing {'.'.join(path)}")
        value = value[name]
    return value


def _text(body: Mapping[str, Any], *path: str) -> str:
    value = _get(body, *path)
    if not isinstance(value, str) or not value:
        raise NoticeFactsError(f"{'.'.join(path)} must be a non-empty string")
    return value


def moment(utc_iso: str) -> Moment:
    try:
        parsed = datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (TypeError, ValueError):
        raise NoticeFactsError(f"invalid UTC time {utc_iso!r}") from None
    local = parsed.astimezone(IST)
    return Moment(utc_iso, local.date(), local.strftime("%H:%M"))


def _hour_fact(hour: Mapping[str, Any] | None) -> HourFact | None:
    """None when the hour is absent or the backend had too little data for it."""
    if not hour or not hour.get("aqi") or not hour.get("decision"):
        return None
    return HourFact(
        at=moment(_text(hour, "valid_for_hour")),
        aqi_display=_text(hour, "aqi", "display"),
        category=_text(hour, "aqi", "category"),
        action=_text(hour, "decision", "action"),
        headline=_text(hour, "decision", "headline"),
    )


def _window_fact(period: Mapping[str, Any] | None) -> WindowFact | None:
    if not period:
        return None
    return WindowFact(
        label=_text(period, "label"),
        part=_text(period, "part"),
        start=moment(_text(period, "start")),
        end=moment(_text(period, "end")),
        worst=_hour_fact(period.get("worst")),
    )


def _collapse_spaces(raw: str | None) -> str | None:
    """Collapse whitespace; an empty name means "no name". Validation lives in the API."""
    if raw is None:
        return None
    name = " ".join(raw.split())
    return name or None


def build_notice_facts(
    aqi_body: Mapping[str, Any],
    forecast_body: Mapping[str, Any],
    language: str,
    school_name: str | None = None,
) -> NoticeFacts:
    """Collect the notice's grounding facts from existing /aqi and /forecast bodies."""
    if language not in LANGUAGES:
        raise ValueError(f"language must be one of {LANGUAGES}, got {language!r}")
    decision = _get(aqi_body, "decision")
    summary = _get(forecast_body, "summary")
    activities = _get(decision, "activities")
    recommendations = _get(decision, "recommendations")
    if not isinstance(activities, Mapping) or not isinstance(recommendations, list):
        raise NoticeFactsError("decision.activities/recommendations have the wrong shape")
    return NoticeFacts(
        language=language,
        school_name=_collapse_spaces(school_name),
        valid_for=moment(_text(aqi_body, "valid_for_hour")),
        aqi_display=_text(aqi_body, "aqi", "display"),
        beyond_scale=bool(_get(aqi_body, "aqi", "beyond_scale")),
        category=_text(aqi_body, "aqi", "category"),
        health_statement=_text(decision, "cpcb_health_statement", "text"),
        health_statement_source=_text(decision, "cpcb_health_statement", "source"),
        dominant_pollutant_code=_text(decision, "dominant_pollutant", "code"),
        dominant_pollutant_name=_text(decision, "dominant_pollutant", "name"),
        action=_text(decision, "action"),
        severity=_text(decision, "severity"),
        headline=_text(decision, "headline"),
        activities=tuple((str(k), str(v)) for k, v in activities.items()),
        recommendations=tuple(str(r) for r in recommendations),
        policy_name=_text(decision, "policy", "name"),
        policy_version=_text(decision, "policy", "version"),
        best_window=_window_fact(summary.get("best_school_period")),
        next_change=_hour_fact(summary.get("next_change")),
        worst=_hour_fact(summary.get("worst")),
        forecast_complete=bool(_get(forecast_body, "coverage", "complete")),
        forecast_hours=int(_get(forecast_body, "coverage", "hours")),
        forecast_requested_hours=int(_get(forecast_body, "coverage", "requested_hours")),
        freshness_status=_text(aqi_body, "freshness", "status"),
        age_minutes=int(_get(aqi_body, "freshness", "age_minutes")),
        freshness_warning=_get(aqi_body, "freshness", "warning"),
        data_type=_text(aqi_body, "data_type"),
        disclaimer=_text(aqi_body, "disclaimer"),
    )
