"""Indian National Air Quality Index (CPCB, 2014): pure, deterministic functions.

Nothing in this module touches the network, AWS, or an LLM. Every AQI number
SaansSafe shows comes from here.

How the index works:
1. Average each pollutant over its CPCB window (24 h, or 8 h for O3 and CO).
2. Map each average to a sub-index with CPCB's breakpoint table, interpolating
   linearly inside a band.
3. The AQI is the highest sub-index. That pollutant is the "dominant" one.
   CPCB requires at least 3 pollutants, one of which is PM2.5 or PM10.

Units: CO in mg/m3; every other pollutant in ug/m3.

UNVERIFIED ASSUMPTIONS (V1-V3, see HACKATHON_MASTER_PLAN.md section 12). These must be
checked against authoritative CPCB documents before the data-provider layer is built:
  V1 completeness thresholds (MIN_VALID_HOURS)
  V2 latest vs. maximum 8 h average for O3/CO (rolling_average)
  V3 upper bound of the open-ended Severe band (_build_bands)
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

AQI_MAX = 500
MIN_POLLUTANTS = 3
# CPCB data-completeness practice: about 2/3 of the hours in the window must be valid.
MIN_VALID_HOURS = MappingProxyType({24: 16, 8: 6})


class Pollutant(str, Enum):
    PM25 = "pm2_5"
    PM10 = "pm10"
    NO2 = "no2"
    SO2 = "so2"
    O3 = "o3"
    CO = "co"
    NH3 = "nh3"


PARTICULATES = frozenset({Pollutant.PM25, Pollutant.PM10})

AVERAGING_HOURS: Mapping[Pollutant, int] = MappingProxyType(
    {
        Pollutant.PM25: 24,
        Pollutant.PM10: 24,
        Pollutant.NO2: 24,
        Pollutant.SO2: 24,
        Pollutant.NH3: 24,
        Pollutant.O3: 8,
        Pollutant.CO: 8,
    }
)


class Category(Enum):
    """CPCB AQI categories with their index range and health impact statement."""

    GOOD = ("Good", 0, 50, "Minimal impact")
    SATISFACTORY = ("Satisfactory", 51, 100, "Minor breathing discomfort to sensitive people")
    MODERATE = (
        "Moderate",
        101,
        200,
        "Breathing discomfort to people with lung disease such as asthma, and to "
        "people with heart disease, children and older adults",
    )
    POOR = ("Poor", 201, 300, "Breathing discomfort to most people on prolonged exposure")
    VERY_POOR = ("Very Poor", 301, 400, "Respiratory illness on prolonged exposure")
    SEVERE = (
        "Severe",
        401,
        500,
        "Affects healthy people and seriously impacts those with existing diseases",
    )

    def __init__(self, label: str, low: int, high: int, health_impact: str) -> None:
        self.label = label
        self.low = low
        self.high = high
        self.health_impact = health_impact


@dataclass(frozen=True)
class Band:
    """One breakpoint row: concentration range [c_lo, c_hi] maps to index [i_lo, i_hi]."""

    c_lo: float
    c_hi: float
    i_lo: int
    i_hi: int


_INDEX_RANGES = tuple((c.low, c.high) for c in Category)

# CPCB published concentration breakpoints, one (low, high) pair per category from
# Good to Very Poor, followed by the open-ended Severe lower bound ("X+").
_PUBLISHED: Mapping[Pollutant, tuple[tuple[tuple[float, float], ...], float]] = {
    Pollutant.PM10: (((0, 50), (51, 100), (101, 250), (251, 350), (351, 430)), 430),
    Pollutant.PM25: (((0, 30), (31, 60), (61, 90), (91, 120), (121, 250)), 250),
    Pollutant.NO2: (((0, 40), (41, 80), (81, 180), (181, 280), (281, 400)), 400),
    Pollutant.O3: (((0, 50), (51, 100), (101, 168), (169, 208), (209, 748)), 748),
    Pollutant.CO: (((0, 1.0), (1.1, 2.0), (2.1, 10), (10.1, 17), (17.1, 34)), 34),
    Pollutant.SO2: (((0, 40), (41, 80), (81, 380), (381, 800), (801, 1600)), 1600),
    Pollutant.NH3: (((0, 200), (201, 400), (401, 800), (801, 1200), (1200, 1800)), 1800),
}


def _build_bands(
    published: tuple[tuple[float, float], ...], severe_lo: float
) -> tuple[Band, ...]:
    bands = [
        Band(c_lo, c_hi, i_lo, i_hi)
        for (c_lo, c_hi), (i_lo, i_hi) in zip(published, _INDEX_RANGES, strict=False)
    ]
    # CPCB leaves Severe open-ended. Give it the same concentration width as the
    # Very Poor band, so the index reaches 500 at a finite concentration.
    very_poor = published[-1]
    severe_hi = severe_lo + (very_poor[1] - very_poor[0])
    bands.append(Band(severe_lo, severe_hi, *_INDEX_RANGES[-1]))
    return tuple(bands)


BREAKPOINTS: Mapping[Pollutant, tuple[Band, ...]] = MappingProxyType(
    {p: _build_bands(rows, severe_lo) for p, (rows, severe_lo) in _PUBLISHED.items()}
)


class InsufficientDataError(ValueError):
    """Raised when there isn't enough valid data to compute an AQI under CPCB rules."""


@dataclass(frozen=True)
class AqiResult:
    aqi: int
    category: Category
    dominant: Pollutant
    sub_indices: Mapping[Pollutant, float]
    concentrations: Mapping[Pollutant, float]


def _validate_concentration(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: concentration must be a number, got {value!r}")
    if not math.isfinite(value):
        raise ValueError(f"{name}: concentration must be finite, got {value!r}")
    if value < 0:
        raise ValueError(f"{name}: concentration must be >= 0, got {value!r}")
    return float(value)


def _to_pollutant(key: Pollutant | str) -> Pollutant:
    try:
        return Pollutant(key)
    except ValueError:
        raise ValueError(f"Unknown pollutant: {key!r}") from None


def round_half_up(value: float) -> int:
    """Round to the nearest integer, .5 rounding up (avoids Python's banker's rounding)."""
    return math.floor(value + 0.5)


def sub_index(pollutant: Pollutant | str, concentration: float) -> float:
    """CPCB sub-index for one pollutant's averaged concentration, capped at 500.

    Values in the small gaps between published bands (e.g. PM2.5 30.5, between
    0-30 and 31-60) take the lower index of the band above. At the published
    breakpoints this matches CPCB's formula exactly.
    """
    pollutant = _to_pollutant(pollutant)
    c = _validate_concentration(concentration, pollutant.value)
    for band in BREAKPOINTS[pollutant]:
        if c <= band.c_hi:
            if c < band.c_lo:
                return float(band.i_lo)
            span = band.c_hi - band.c_lo
            return band.i_lo + (band.i_hi - band.i_lo) * (c - band.c_lo) / span
    return float(AQI_MAX)


def category_for(aqi: int) -> Category:
    """Category for a reported (integer) AQI value in 0..500."""
    if isinstance(aqi, bool) or not isinstance(aqi, int):
        raise ValueError(f"AQI must be an integer, got {aqi!r}")
    for category in Category:
        if category.low <= aqi <= category.high:
            return category
    raise ValueError(f"AQI must be within 0..{AQI_MAX}, got {aqi}")


def rolling_average(hourly: Sequence[float | None], window_hours: int) -> float | None:
    """Mean of the most recent `window_hours` values (oldest first, latest last).

    `None` marks a missing hour. Returns None when fewer valid hours remain than
    CPCB completeness requires. Missing hours are never filled in.
    """
    if window_hours not in MIN_VALID_HOURS:
        raise ValueError(f"Unsupported averaging window: {window_hours} h")
    window = list(hourly)[-window_hours:]
    valid = [
        _validate_concentration(v, f"hour {i}") for i, v in enumerate(window) if v is not None
    ]
    if len(valid) < MIN_VALID_HOURS[window_hours]:
        return None
    return sum(valid) / len(valid)


def averaged_concentrations(
    hourly_by_pollutant: Mapping[Pollutant | str, Sequence[float | None]],
) -> dict[Pollutant, float]:
    """Average each pollutant over its CPCB window and drop any with too little data."""
    averages: dict[Pollutant, float] = {}
    for key, series in hourly_by_pollutant.items():
        pollutant = _to_pollutant(key)
        avg = rolling_average(series, AVERAGING_HOURS[pollutant])
        if avg is not None:
            averages[pollutant] = avg
    return averages


def compute_aqi(concentrations: Mapping[Pollutant | str, float]) -> AqiResult:
    """Overall AQI from already-averaged concentrations (see AVERAGING_HOURS)."""
    clean = {
        _to_pollutant(k): _validate_concentration(v, str(k)) for k, v in concentrations.items()
    }
    if len(clean) < MIN_POLLUTANTS:
        raise InsufficientDataError(
            f"Need at least {MIN_POLLUTANTS} pollutants, got {len(clean)}: "
            f"{sorted(p.value for p in clean)}"
        )
    if not PARTICULATES & clean.keys():
        raise InsufficientDataError("Need PM2.5 or PM10 among the pollutants")

    indices = {p: sub_index(p, c) for p, c in clean.items()}
    # Highest sub-index wins. Ties go to the earlier pollutant in Pollutant order.
    order = list(Pollutant)
    dominant = max(indices, key=lambda p: (indices[p], -order.index(p)))
    aqi = min(round_half_up(indices[dominant]), AQI_MAX)
    return AqiResult(
        aqi=aqi,
        category=category_for(aqi),
        dominant=dominant,
        sub_indices=MappingProxyType(indices),
        concentrations=MappingProxyType(clean),
    )


def aqi_from_hourly(
    hourly_by_pollutant: Mapping[Pollutant | str, Sequence[float | None]],
) -> AqiResult:
    """AQI from hourly series: average each over its window, then compute."""
    return compute_aqi(averaged_concentrations(hourly_by_pollutant))
