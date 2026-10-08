"""Indian National Air Quality Index (CPCB): pure, deterministic functions.

Nothing in this module touches the network, AWS, or an LLM. Every AQI number
SaansSafe shows comes from here.

Authority: CPCB, "National Air Quality Index", CUPS/82/2014-15,
https://cpcb.nic.in/upload/national-air-quality-index/FINAL-REPORT_AQI_.pdf
(Table 3.11 breakpoints; section 3.5 formula; section 3.7 data sufficiency). Verification
notes, with page numbers: HACKATHON_MASTER_PLAN.md section 12.

How the index works:
1. Average each pollutant over its CPCB window: 24 h, or 8 h for O3 and CO.
   CPCB: "a minimum of 16 hours' data is considered necessary for calculating
   subindex", so every pollutant needs >= 16 valid hours in the latest 24.
   SaansSafe product decision (CPCB doesn't specify): O3/CO use the latest
   8-hour window, not the maximum 8-hour average of the day.
2. Map each average to a sub-index:
   Ip = (IHI - ILO) / (BHI - BLO) * (Cp - BLO) + ILO,
   where "ILO" has one subtracted when ILO > 50 (CPCB section 3.5).
3. CPCB publishes Severe (401-500) as open-ended ("250+") with no upper concentration.
   We don't invent one: at or above the threshold the sub-index is 401 and the
   result is flagged as beyond the published scale (shown as "401+").
4. AQI is the highest sub-index. CPCB requires >= 3 pollutants, including PM2.5 or PM10.

Units: CO in mg/m3; every other pollutant in ug/m3.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

AQI_SCALE_MAX = 500
SEVERE_SUB_INDEX = 401
MIN_POLLUTANTS = 3
COMPLETENESS_WINDOW_HOURS = 24
MIN_VALID_HOURS = 16  # CPCB section 3.7, applied to every pollutant
BEYOND_SCALE_NOTE = (
    "At or above CPCB's published Severe threshold. CPCB publishes no upper "
    "concentration for Severe, so no exact AQI above 401 is given."
)


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
    """One published breakpoint row: concentration [c_lo, c_hi] maps to index [i_lo, i_hi]."""

    c_lo: float
    c_hi: float
    i_lo: int
    i_hi: int

    @property
    def interpolation_i_lo(self) -> int:
        """CPCB section 3.5: 'subtract one from ILO, if ILO is greater than 50'."""
        return self.i_lo - 1 if self.i_lo > 50 else self.i_lo


_INDEX_RANGES = tuple((c.low, c.high) for c in Category if c is not Category.SEVERE)

# CPCB Table 3.11: (low, high) concentration per category from Good to Very Poor,
# then the open-ended Severe threshold ("X+").
_PUBLISHED: Mapping[Pollutant, tuple[tuple[tuple[float, float], ...], float]] = {
    Pollutant.PM10: (((0, 50), (51, 100), (101, 250), (251, 350), (351, 430)), 430),
    Pollutant.PM25: (((0, 30), (31, 60), (61, 90), (91, 120), (121, 250)), 250),
    Pollutant.NO2: (((0, 40), (41, 80), (81, 180), (181, 280), (281, 400)), 400),
    Pollutant.O3: (((0, 50), (51, 100), (101, 168), (169, 208), (209, 748)), 748),
    Pollutant.CO: (((0, 1.0), (1.1, 2.0), (2.1, 10), (10.1, 17), (17.1, 34)), 34),
    Pollutant.SO2: (((0, 40), (41, 80), (81, 380), (381, 800), (801, 1600)), 1600),
    Pollutant.NH3: (((0, 200), (201, 400), (401, 800), (801, 1200), (1201, 1800)), 1800),
}

BREAKPOINTS: Mapping[Pollutant, tuple[Band, ...]] = MappingProxyType(
    {
        p: tuple(
            Band(c_lo, c_hi, i_lo, i_hi)
            for (c_lo, c_hi), (i_lo, i_hi) in zip(rows, _INDEX_RANGES, strict=True)
        )
        for p, (rows, _) in _PUBLISHED.items()
    }
)

SEVERE_THRESHOLD: Mapping[Pollutant, float] = MappingProxyType(
    {p: float(threshold) for p, (_, threshold) in _PUBLISHED.items()}
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
    beyond_scale: bool  # dominant pollutant is at or above its open-ended Severe threshold

    @property
    def display(self) -> str:
        """Public representation: '401+' when beyond the published scale."""
        return f"{self.aqi}+" if self.beyond_scale else str(self.aqi)


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


def is_beyond_scale(pollutant: Pollutant | str, concentration: float) -> bool:
    """True when the concentration is at or above CPCB's open-ended Severe threshold."""
    pollutant = _to_pollutant(pollutant)
    c = _validate_concentration(concentration, pollutant.value)
    return c >= SEVERE_THRESHOLD[pollutant]


def sub_index(pollutant: Pollutant | str, concentration: float) -> float:
    """CPCB sub-index for one pollutant's averaged concentration.

    Returns 401 for any concentration at or above the Severe threshold (see
    is_beyond_scale). Values in the gaps between published bands (e.g. PM2.5 30.5,
    between 0-30 and 31-60) take the interpolation start of the band above.
    """
    pollutant = _to_pollutant(pollutant)
    c = _validate_concentration(concentration, pollutant.value)
    if c >= SEVERE_THRESHOLD[pollutant]:
        return float(SEVERE_SUB_INDEX)
    for band in BREAKPOINTS[pollutant]:
        if c <= band.c_hi:
            i_lo = band.interpolation_i_lo
            if c < band.c_lo:
                return float(i_lo)
            return i_lo + (band.i_hi - i_lo) * (c - band.c_lo) / (band.c_hi - band.c_lo)
    # Unreachable: every table's last c_hi equals its Severe threshold.
    raise AssertionError(f"No breakpoint band for {pollutant.value}={c}")


def category_for(aqi: int) -> Category:
    """Category for a reported (integer) AQI value in 0..500."""
    if isinstance(aqi, bool) or not isinstance(aqi, int):
        raise ValueError(f"AQI must be an integer, got {aqi!r}")
    for category in Category:
        if category.low <= aqi <= category.high:
            return category
    raise ValueError(f"AQI must be within 0..{AQI_SCALE_MAX}, got {aqi}")


def rolling_average(hourly: Sequence[float | None], averaging_hours: int) -> float | None:
    """Average over the latest `averaging_hours` (24 or 8) of an hourly series.

    `hourly` is oldest first, latest last. `None` marks a missing hour.
    Returns None (never a filled-in value) when:
      - fewer than 16 of the latest 24 hours are valid (CPCB section 3.7), or
      - the latest averaging window holds no valid hour.
    """
    if averaging_hours not in (8, 24):
        raise ValueError(f"Unsupported averaging window: {averaging_hours} h")
    recent = list(hourly)[-COMPLETENESS_WINDOW_HOURS:]
    checked = [
        None if v is None else _validate_concentration(v, f"hour {i}")
        for i, v in enumerate(recent)
    ]
    if sum(v is not None for v in checked) < MIN_VALID_HOURS:
        return None
    window = [v for v in checked[-averaging_hours:] if v is not None]
    if not window:
        return None
    return sum(window) / len(window)


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
    aqi = round_half_up(indices[dominant])
    return AqiResult(
        aqi=aqi,
        category=category_for(aqi),
        dominant=dominant,
        sub_indices=MappingProxyType(indices),
        concentrations=MappingProxyType(clean),
        beyond_scale=is_beyond_scale(dominant, clean[dominant]),
    )


def aqi_from_hourly(
    hourly_by_pollutant: Mapping[Pollutant | str, Sequence[float | None]],
) -> AqiResult:
    """AQI from hourly series: average each over its window, then compute."""
    return compute_aqi(averaged_concentrations(hourly_by_pollutant))
