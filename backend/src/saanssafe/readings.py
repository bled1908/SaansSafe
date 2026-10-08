"""Normalized hourly air-quality readings: the boundary between data providers and the AQI engine.

Providers (Open-Meteo now, CPCB later) convert their responses into a ReadingSeries.
The AQI engine only ever sees `ReadingSeries.hourly_until(...)`, which returns exactly
one value per hour (None = missing), oldest first, in the engine's units:
CO in mg/m3, all other pollutants in ug/m3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from saanssafe.aqi import COMPLETENESS_WINDOW_HOURS, Pollutant

HOUR = timedelta(hours=1)


def _check_utc_hour(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must be a timezone-aware datetime, got {value!r}")
    return value.astimezone(UTC)


def _check_concentration(value: object, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number or None, got {value!r}")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0, got {value!r}")
    return float(value)


@dataclass(frozen=True)
class HourlyReading:
    """One hour of pollutant concentrations. None means the value is missing."""

    time: datetime  # start of the hour, UTC
    pm2_5: float | None = None  # ug/m3
    pm10: float | None = None  # ug/m3
    no2: float | None = None  # ug/m3
    so2: float | None = None  # ug/m3
    o3: float | None = None  # ug/m3
    co: float | None = None  # mg/m3 (engine unit)
    nh3: float | None = None  # ug/m3

    def __post_init__(self) -> None:
        time = _check_utc_hour(self.time, "time")
        if time != time.replace(minute=0, second=0, microsecond=0):
            raise ValueError(f"time must be on the hour, got {time.isoformat()}")
        object.__setattr__(self, "time", time)
        for pollutant in Pollutant:
            checked = _check_concentration(getattr(self, pollutant.value), pollutant.value)
            object.__setattr__(self, pollutant.value, checked)

    def value(self, pollutant: Pollutant) -> float | None:
        return getattr(self, pollutant.value)


@dataclass(frozen=True)
class ReadingSeries:
    """Consecutive hourly readings for one location from one source."""

    latitude: float
    longitude: float
    source: str
    readings: tuple[HourlyReading, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "readings", tuple(self.readings))
        for prev, curr in zip(self.readings, self.readings[1:]):
            if curr.time - prev.time != HOUR:
                raise ValueError(
                    f"readings must be consecutive hours: {prev.time.isoformat()} -> "
                    f"{curr.time.isoformat()}"
                )

    @property
    def first_time(self) -> datetime | None:
        return self.readings[0].time if self.readings else None

    @property
    def last_time(self) -> datetime | None:
        return self.readings[-1].time if self.readings else None

    def hourly_until(self, until: datetime) -> dict[Pollutant, list[float | None]]:
        """AQI-engine input for the hour containing `until`.

        Returns the 24 hours ending at that hour (oldest first) for every pollutant.
        Hours not covered by this series are None, never estimated, so stale or
        partial data shows up as missing and the engine's 16-hour rule decides.
        """
        end = _check_utc_hour(until, "until").replace(minute=0, second=0, microsecond=0)
        by_time = {r.time: r for r in self.readings}
        hours = [end - HOUR * i for i in range(COMPLETENESS_WINDOW_HOURS - 1, -1, -1)]
        window = [by_time.get(h) for h in hours]
        return {
            p: [None if r is None else r.value(p) for r in window] for p in Pollutant
        }
