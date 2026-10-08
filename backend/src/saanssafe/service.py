"""Business logic for "current forecast/model AQI at a point": cache first, provider second.

No HTTP or AWS code here. The AQI itself always comes from saanssafe.aqi.

Freshness policy:
  - cached data fetched <= fresh_for ago     -> served as-is            (fresh, hit)
  - older, or no longer covers the current hour -> refetch from provider (fresh, miss/refreshed)
  - refetch fails TRANSIENTLY (ProviderUnavailableError: 429, 5xx, timeout, network)
    and cached data <= max_stale             -> served, marked stale with its age
    (4xx / malformed responses never fall back to stale data; they propagate)
  - otherwise                                  -> the provider error propagates
A cache failure never blocks a response: reads fall through to the provider ("bypassed"),
and write failures are logged.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

from saanssafe.aqi import AqiResult, InsufficientDataError, aqi_from_hourly
from saanssafe.cache import CacheError, CachedSeries, ReadingCache, cache_key, round_coordinate
from saanssafe.providers.base import (
    AirQualityProvider,
    ProviderUnavailableError,
    validate_coordinates,
)

logger = logging.getLogger(__name__)

DEFAULT_FRESH_FOR = timedelta(minutes=60)
DEFAULT_MAX_STALE = timedelta(hours=6)


class Freshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"


class CacheOutcome(str, Enum):
    HIT = "hit"
    MISS = "miss"
    REFRESHED = "refreshed"
    STALE_FALLBACK = "stale_fallback"
    BYPASSED = "bypassed"  # cache unreadable; served straight from the provider


@dataclass(frozen=True)
class AqiReport:
    result: AqiResult
    valid_for_hour: datetime  # UTC hour the AQI describes
    requested_lat: float
    requested_lon: float
    query_lat: float  # rounded point actually fetched and cached
    query_lon: float
    grid_lat: float  # model grid point reported by the provider
    grid_lon: float
    source: str
    fetched_at: datetime
    age: timedelta
    freshness: Freshness
    cache: CacheOutcome
    warning: str | None = None


@dataclass(frozen=True)
class _Query:
    lat: float
    lon: float
    q_lat: float
    q_lon: float
    key: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AqiService:
    def __init__(
        self,
        provider: AirQualityProvider,
        cache: ReadingCache,
        *,
        fresh_for: timedelta = DEFAULT_FRESH_FOR,
        max_stale: timedelta = DEFAULT_MAX_STALE,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if fresh_for <= timedelta(0):
            raise ValueError("fresh_for must be positive")
        if max_stale < fresh_for:
            raise ValueError("max_stale must be >= fresh_for")
        self._provider = provider
        self._cache = cache
        self._fresh_for = fresh_for
        self._max_stale = max_stale
        self._clock = clock

    def current_aqi(self, latitude: float, longitude: float) -> AqiReport:
        lat, lon = validate_coordinates(latitude, longitude)
        q_lat, q_lon = round_coordinate(lat), round_coordinate(lon)
        query = _Query(lat, lon, q_lat, q_lon, cache_key(self._provider.name, q_lat, q_lon))
        now = self._clock()

        cached, cache_readable = self._read_cache(query.key)
        if cached is not None and now - cached.fetched_at <= self._fresh_for:
            report = self._report_or_none(query, cached, now, Freshness.FRESH, CacheOutcome.HIT)
            if report is not None:
                return report

        try:
            series = self._provider.fetch_hourly(q_lat, q_lon)
        except ProviderUnavailableError as err:  # only transient failures may use stale data
            fallback = self._stale_fallback(query, cached, now, err)
            if fallback is not None:
                return fallback
            raise

        fresh = CachedSeries(series, now)
        self._write_cache(query.key, fresh)
        if not cache_readable:
            outcome = CacheOutcome.BYPASSED
        else:
            outcome = CacheOutcome.MISS if cached is None else CacheOutcome.REFRESHED
        return self._report(query, fresh, now, Freshness.FRESH, outcome)

    # --- helpers ---------------------------------------------------------------------------

    def _read_cache(self, key: str) -> tuple[CachedSeries | None, bool]:
        try:
            return self._cache.get(key), True
        except CacheError as err:
            logger.warning("cache read failed for %s: %s", key, err)
            return None, False

    def _write_cache(self, key: str, cached: CachedSeries) -> None:
        try:
            self._cache.put(key, cached)
        except CacheError as err:
            logger.warning("cache write failed for %s: %s", key, err)

    def _stale_fallback(
        self,
        query: _Query,
        cached: CachedSeries | None,
        now: datetime,
        err: ProviderUnavailableError,
    ) -> AqiReport | None:
        if cached is None or now - cached.fetched_at > self._max_stale:
            return None
        minutes = int((now - cached.fetched_at).total_seconds() // 60)
        logger.warning("provider failed (%s); serving cached data %d min old", err, minutes)
        warning = (
            f"Live data refresh failed ({type(err).__name__}). Showing forecast data "
            f"fetched {minutes} minutes ago."
        )
        return self._report_or_none(
            query, cached, now, Freshness.STALE, CacheOutcome.STALE_FALLBACK, warning
        )

    def _report_or_none(self, *args, **kwargs) -> AqiReport | None:
        try:
            return self._report(*args, **kwargs)
        except InsufficientDataError:
            return None  # cached data doesn't cover the current hour well enough

    def _report(
        self,
        query: _Query,
        cached: CachedSeries,
        now: datetime,
        freshness: Freshness,
        outcome: CacheOutcome,
        warning: str | None = None,
    ) -> AqiReport:
        hour = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        result = aqi_from_hourly(cached.series.hourly_until(hour))
        return AqiReport(
            result=result,
            valid_for_hour=hour,
            requested_lat=query.lat,
            requested_lon=query.lon,
            query_lat=query.q_lat,
            query_lon=query.q_lon,
            grid_lat=cached.series.latitude,
            grid_lon=cached.series.longitude,
            source=cached.series.source,
            fetched_at=cached.fetched_at,
            age=max(now - cached.fetched_at, timedelta(0)),
            freshness=freshness,
            cache=outcome,
            warning=warning,
        )
