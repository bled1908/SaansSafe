"""Business logic for "current forecast/model AQI at a point": cache first, provider second.

No HTTP or AWS code here. The AQI itself always comes from saanssafe.aqi.

Freshness policy:
  - cached data fetched <= fresh_for ago     -> served as-is            (fresh, hit)
  - older, or no longer covers what's needed  -> refetch from provider (fresh, miss/refreshed)
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
from saanssafe.outlook import OUTLOOK_HOURS, Outlook, build_outlook
from saanssafe.providers.base import (
    AirQualityProvider,
    ProviderUnavailableError,
    validate_coordinates,
)
from saanssafe.readings import HOUR

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
class ForecastReport:
    outlook: Outlook
    requested_lat: float
    requested_lon: float
    query_lat: float
    query_lon: float
    grid_lat: float
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


@dataclass(frozen=True)
class _Obtained:
    cached: CachedSeries
    freshness: Freshness
    outcome: CacheOutcome
    warning: str | None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _hour(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _succeeds(build: Callable[[CachedSeries], object]) -> Callable[[CachedSeries], bool]:
    def check(cached: CachedSeries) -> bool:
        try:
            build(cached)
        except InsufficientDataError:
            return False
        return True

    return check


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
        query = self._query(latitude, longitude)
        now = self._clock()
        hour = _hour(now)

        def compute(cached: CachedSeries) -> AqiResult:
            return aqi_from_hourly(cached.series.hourly_until(hour))

        usable = _succeeds(compute)
        obtained = self._obtain(query, now, fresh_ok=usable, stale_ok=usable)
        result = compute(obtained.cached)  # fresh data that is still insufficient raises here
        return AqiReport(result, hour, *self._meta(query, obtained, now))

    def forecast(self, latitude: float, longitude: float, hours: int = OUTLOOK_HOURS) -> ForecastReport:
        """Deterministic outlook from the current hour through `hours` later."""
        query = self._query(latitude, longitude)
        now = self._clock()
        horizon = _hour(now) + HOUR * hours

        def compute(cached: CachedSeries) -> Outlook:
            return build_outlook(cached.series, now, hours)

        usable = _succeeds(compute)

        def covers_horizon(cached: CachedSeries) -> bool:
            last = cached.series.last_time
            return last is not None and last >= horizon and usable(cached)

        # Fresh cache must cover the full horizon; a stale fallback may be partial (flagged).
        obtained = self._obtain(query, now, fresh_ok=covers_horizon, stale_ok=usable)
        return ForecastReport(compute(obtained.cached), *self._meta(query, obtained, now))

    # --- helpers ---------------------------------------------------------------------------

    def _query(self, latitude: float, longitude: float) -> _Query:
        lat, lon = validate_coordinates(latitude, longitude)
        q_lat, q_lon = round_coordinate(lat), round_coordinate(lon)
        return _Query(lat, lon, q_lat, q_lon, cache_key(self._provider.name, q_lat, q_lon))

    def _obtain(
        self,
        query: _Query,
        now: datetime,
        *,
        fresh_ok: Callable[[CachedSeries], bool],
        stale_ok: Callable[[CachedSeries], bool],
    ) -> _Obtained:
        cached, cache_readable = self._read_cache(query.key)
        if cached is not None and now - cached.fetched_at <= self._fresh_for and fresh_ok(cached):
            return _Obtained(cached, Freshness.FRESH, CacheOutcome.HIT, None)

        try:
            series = self._provider.fetch_hourly(query.q_lat, query.q_lon)
        except ProviderUnavailableError as err:  # only transient failures may use stale data
            if cached is not None and now - cached.fetched_at <= self._max_stale and stale_ok(cached):
                minutes = int((now - cached.fetched_at).total_seconds() // 60)
                logger.warning("provider failed (%s); serving cached data %d min old", err, minutes)
                warning = (
                    f"Live data refresh failed ({type(err).__name__}). Showing forecast data "
                    f"fetched {minutes} minutes ago."
                )
                return _Obtained(cached, Freshness.STALE, CacheOutcome.STALE_FALLBACK, warning)
            raise

        fresh = CachedSeries(series, now)
        self._write_cache(query.key, fresh)
        if not cache_readable:
            outcome = CacheOutcome.BYPASSED
        else:
            outcome = CacheOutcome.MISS if cached is None else CacheOutcome.REFRESHED
        return _Obtained(fresh, Freshness.FRESH, outcome, None)

    @staticmethod
    def _meta(query: _Query, obtained: _Obtained, now: datetime) -> tuple:
        series = obtained.cached.series
        return (
            query.lat,
            query.lon,
            query.q_lat,
            query.q_lon,
            series.latitude,
            series.longitude,
            series.source,
            obtained.cached.fetched_at,
            max(now - obtained.cached.fetched_at, timedelta(0)),
            obtained.freshness,
            obtained.outcome,
            obtained.warning,
        )

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
