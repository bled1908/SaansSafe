"""SaansSafe school safety decisions: deterministic and explainable.

IMPORTANT: this is SaansSafe's own PRODUCT POLICY, not a CPCB rule.
CPCB's National AQI report (CUPS/82/2014-15) defines the AQI categories and their
health statements (Table 3.12), plus broad action guidelines for regulators and the
public (section 3.4). It defines no school-specific thresholds or actions.
This module maps each CPCB AQI category of a forecast/model AQI to a conservative
school action.

It takes an already-computed AqiResult and never calculates AQI. No LLM is involved:
the action is decided here, and any later text generation may only explain it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from saanssafe.aqi import AqiResult, Category, Pollutant

POLICY_VERSION = "saanssafe-school-v1"
POLICY_NAME = "SaansSafe school safety policy"
POLICY_BASIS = (
    f"{POLICY_NAME} (a product policy, not a CPCB rule), applied to the "
    "CPCB category of a forecast/model AQI. Not medical advice."
)


class SchoolAction(str, Enum):
    NORMAL = "normal_outdoor_activities"
    PROTECT_SENSITIVE = "outdoor_ok_protect_sensitive_students"
    REDUCE_EXERTION = "reduce_outdoor_exertion"
    MOVE_STRENUOUS_INDOORS = "move_strenuous_activities_indoors"
    SUSPEND_OUTDOOR = "suspend_outdoor_activities"


class Severity(str, Enum):
    """Ordered from least to most severe (see `rank`)."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return list(Severity).index(self)


class Activity(str, Enum):
    ASSEMBLY = "morning_assembly"
    PE_AND_SPORTS = "pe_and_sports"
    RECESS = "recess_and_breaks"


class Guidance(str, Enum):
    """Ordered from most to least permissive (see `rank`)."""

    ALLOWED = "allowed"
    LIMITED = "limited"  # shorter and lighter; sensitive students indoors
    INDOORS = "move_indoors"

    @property
    def rank(self) -> int:
        return list(Guidance).index(self)


POLLUTANT_NAMES: Mapping[Pollutant, str] = MappingProxyType(
    {
        Pollutant.PM25: "PM2.5 (fine particulate matter)",
        Pollutant.PM10: "PM10 (coarse particulate matter)",
        Pollutant.NO2: "NO2 (nitrogen dioxide)",
        Pollutant.SO2: "SO2 (sulphur dioxide)",
        Pollutant.O3: "O3 (ground-level ozone)",
        Pollutant.CO: "CO (carbon monoxide)",
        Pollutant.NH3: "NH3 (ammonia)",
    }
)


@dataclass(frozen=True)
class _Rule:
    action: SchoolAction
    severity: Severity
    headline: str
    activities: Mapping[Activity, Guidance]
    recommendations: tuple[str, ...]


def _activities(assembly: Guidance, pe: Guidance, recess: Guidance) -> Mapping[Activity, Guidance]:
    return MappingProxyType(
        {Activity.ASSEMBLY: assembly, Activity.PE_AND_SPORTS: pe, Activity.RECESS: recess}
    )


_A, _L, _I = Guidance.ALLOWED, Guidance.LIMITED, Guidance.INDOORS

POLICY: Mapping[Category, _Rule] = MappingProxyType(
    {
        Category.GOOD: _Rule(
            SchoolAction.NORMAL,
            Severity.MINIMAL,
            "Outdoor activities can go ahead as normal",
            _activities(_A, _A, _A),
            (
                "Outdoor assembly, PE, sports and recess can go ahead as normal.",
                "Check the forecast again later; air quality can change during the day.",
            ),
        ),
        Category.SATISFACTORY: _Rule(
            SchoolAction.PROTECT_SENSITIVE,
            Severity.LOW,
            "Outdoor activities OK; take care of sensitive students",
            _activities(_A, _A, _A),
            (
                "Outdoor activities can go ahead.",
                "Students who are sensitive to air pollution should reduce prolonged or "
                "strenuous outdoor exertion.",
                "Allow students to rest if they feel unwell.",
            ),
        ),
        Category.MODERATE: _Rule(
            SchoolAction.REDUCE_EXERTION,
            Severity.MODERATE,
            "Reduce strenuous outdoor activity",
            _activities(_A, _L, _A),
            (
                "Keep outdoor assembly short.",
                "Reduce prolonged outdoor exertion: replace strenuous outdoor PE and sports "
                "practice with lighter activity or shorter sessions.",
                "Offer students who are sensitive to air pollution an indoor alternative.",
                "Allow students to rest if they feel unwell.",
            ),
        ),
        Category.POOR: _Rule(
            SchoolAction.MOVE_STRENUOUS_INDOORS,
            Severity.HIGH,
            "Move assembly, PE and sports indoors",
            _activities(_I, _I, _L),
            (
                "Hold assembly indoors.",
                "Move strenuous activities, including PE and sports, indoors and postpone "
                "outdoor matches.",
                "Keep outdoor recess short and offer an indoor option; students who are "
                "sensitive to air pollution should stay indoors.",
                "Allow students to rest if they feel unwell.",
                "Inform parents about today's precautions.",
            ),
        ),
        Category.VERY_POOR: _Rule(
            SchoolAction.SUSPEND_OUTDOOR,
            Severity.VERY_HIGH,
            "Suspend outdoor activities",
            _activities(_I, _I, _I),
            (
                "Suspend outdoor assembly, PE, sports and recess; use indoor alternatives.",
                "Keep indoor physical activity light.",
                "Allow students to rest if they feel unwell.",
                "Inform parents about today's precautions.",
            ),
        ),
        Category.SEVERE: _Rule(
            SchoolAction.SUSPEND_OUTDOOR,
            Severity.CRITICAL,
            "Suspend all outdoor activities",
            _activities(_I, _I, _I),
            (
                "Suspend all outdoor activities, including recess.",
                "Keep indoor physical activity light.",
                "Allow students to rest if they feel unwell.",
                "Inform parents today.",
                "Follow any instructions issued by local or education authorities.",
            ),
        ),
    }
)

if set(POLICY) != set(Category):  # pragma: no cover - guards future edits
    raise RuntimeError("POLICY must cover every AQI category")


@dataclass(frozen=True)
class SafetyDecision:
    action: SchoolAction
    severity: Severity
    headline: str
    short_reason: str
    recommendations: tuple[str, ...]
    activities: Mapping[Activity, Guidance]
    aqi_value: int
    aqi_display: str  # "401+" when beyond the published scale
    beyond_scale: bool
    category: Category
    health_impact: str  # CPCB category health statement (as stored in aqi.Category)
    dominant_pollutant: Pollutant
    dominant_pollutant_name: str
    dominant_sub_index: float
    policy_version: str = POLICY_VERSION
    policy_basis: str = POLICY_BASIS


def _short_reason(result: AqiResult) -> str:
    scale = " (beyond the published CPCB scale)" if result.beyond_scale else ""
    sub = result.sub_indices[result.dominant]
    sub_text = "401+" if result.beyond_scale else f"{sub:.0f}"
    return (
        f"Forecast/model AQI {result.display} is {result.category.label}{scale}. "
        f"Main pollutant: {POLLUTANT_NAMES[result.dominant]}, sub-index {sub_text}. "
        f"Action per the {POLICY_NAME} (not a CPCB rule)."
    )


def decide_school_safety(result: AqiResult) -> SafetyDecision:
    """Map an already-computed forecast/model AQI to SaansSafe's school action."""
    if not isinstance(result, AqiResult):
        raise TypeError(f"expected AqiResult, got {type(result).__name__}")
    rule = POLICY[result.category]
    return SafetyDecision(
        action=rule.action,
        severity=rule.severity,
        headline=rule.headline,
        short_reason=_short_reason(result),
        recommendations=rule.recommendations,
        activities=rule.activities,
        aqi_value=result.aqi,
        aqi_display=result.display,
        beyond_scale=result.beyond_scale,
        category=result.category,
        health_impact=result.category.health_impact,
        dominant_pollutant=result.dominant,
        dominant_pollutant_name=POLLUTANT_NAMES[result.dominant],
        dominant_sub_index=result.sub_indices[result.dominant],
    )
