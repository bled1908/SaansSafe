from datetime import timedelta

import pytest
from support import NOW, T0, FakeCache, FakeProvider, H, make_series

from saanssafe.aqi import Category, InsufficientDataError, Pollutant
from saanssafe.cache import CacheError, CachedSeries
from saanssafe.providers.base import (
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from saanssafe.service import AqiService, CacheOutcome, Freshness

KEY = "open-meteo#28.61#77.21"
LAT, LON = 28.6139, 77.209


def service(provider=None, cache=None, **kwargs):
    return AqiService(provider or FakeProvider(), cache or FakeCache(), clock=lambda: NOW, **kwargs)


def cached(age: timedelta, series=None) -> CachedSeries:
    return CachedSeries(series or make_series(), NOW - age)


# --- Cache miss / hit / refresh -------------------------------------------------------------

def test_cache_miss_fetches_rounded_point_computes_aqi_and_writes_cache():
    provider, cache = FakeProvider(), FakeCache()
    report = service(provider, cache).current_aqi(LAT, LON)
    assert provider.calls == [(28.61, 77.21)]
    assert [k for k, _ in cache.puts] == [KEY]
    assert cache.puts[0][1].fetched_at == NOW
    assert (report.cache, report.freshness, report.age) == (CacheOutcome.MISS, Freshness.FRESH, timedelta(0))
    assert report.result.aqi == 150 and report.result.dominant is Pollutant.PM10
    assert report.valid_for_hour == T0 + 30 * H
    assert (report.requested_lat, report.query_lat, report.grid_lat) == (LAT, 28.61, 28.6)


def test_fresh_cache_hit_skips_provider():
    provider = FakeProvider()
    cache = FakeCache({KEY: cached(timedelta(minutes=20))})
    report = service(provider, cache).current_aqi(LAT, LON)
    assert provider.calls == []
    assert cache.puts == []
    assert (report.cache, report.freshness) == (CacheOutcome.HIT, Freshness.FRESH)
    assert report.age == timedelta(minutes=20)


def test_entry_exactly_at_fresh_limit_is_still_a_hit():
    provider = FakeProvider()
    service(provider, FakeCache({KEY: cached(timedelta(minutes=60))})).current_aqi(LAT, LON)
    assert provider.calls == []


def test_stale_cache_triggers_refresh():
    provider = FakeProvider(series=make_series(pm10=50.0))
    cache = FakeCache({KEY: cached(timedelta(minutes=61))})
    report = service(provider, cache).current_aqi(LAT, LON)
    assert len(provider.calls) == 1
    assert (report.cache, report.freshness, report.age) == (
        CacheOutcome.REFRESHED, Freshness.FRESH, timedelta(0))
    assert cache.entries[KEY].fetched_at == NOW
    assert report.result.dominant is Pollutant.PM25  # refreshed data, not the old values


def test_fresh_entry_not_covering_current_hour_triggers_refresh():
    old = make_series(hours=21)  # ends T0+20h; only 14 of the latest 24 hours covered
    provider = FakeProvider()
    report = service(provider, FakeCache({KEY: cached(timedelta(minutes=5), old)})).current_aqi(LAT, LON)
    assert len(provider.calls) == 1
    assert report.cache is CacheOutcome.REFRESHED


# --- Provider failures and stale fallback -------------------------------------------------------

@pytest.mark.parametrize(
    "error",
    [ProviderUnavailableError("HTTP 429"), ProviderUnavailableError("HTTP 503"),
     ProviderUnavailableError("timed out"), ProviderUnavailableError("DNS failure")],
)
def test_transient_failure_serves_recent_stale_cache_explicitly_marked(error):
    cache = FakeCache({KEY: cached(timedelta(minutes=120))})
    report = service(FakeProvider(error=error), cache).current_aqi(LAT, LON)
    assert report.freshness is Freshness.STALE
    assert report.cache is CacheOutcome.STALE_FALLBACK
    assert report.age == timedelta(minutes=120)
    assert "120 minutes ago" in report.warning
    assert cache.puts == []


@pytest.mark.parametrize("error", [ProviderRequestError("HTTP 400"), ProviderResponseError("bad")])
def test_non_transient_failure_never_uses_stale_cache(error):
    cache = FakeCache({KEY: cached(timedelta(minutes=120))})  # within 6 h, but must not be used
    with pytest.raises(type(error)):
        service(FakeProvider(error=error), cache).current_aqi(LAT, LON)
    assert cache.puts == []


def test_4xx_does_not_affect_fresh_cache_hit():
    provider = FakeProvider(error=ProviderRequestError("HTTP 400"))
    report = service(provider, FakeCache({KEY: cached(timedelta(minutes=30))})).current_aqi(LAT, LON)
    assert provider.calls == []
    assert report.cache is CacheOutcome.HIT


def test_provider_failure_with_too_old_cache_raises():
    cache = FakeCache({KEY: cached(timedelta(hours=6, minutes=1))})
    with pytest.raises(ProviderUnavailableError):
        service(FakeProvider(error=ProviderUnavailableError("down")), cache).current_aqi(LAT, LON)


def test_provider_failure_without_cache_raises_original_error():
    with pytest.raises(ProviderRequestError):
        service(FakeProvider(error=ProviderRequestError("400"))).current_aqi(LAT, LON)


def test_stale_fallback_not_used_when_it_cannot_cover_current_hour():
    old = make_series(hours=21)
    cache = FakeCache({KEY: cached(timedelta(hours=2), old)})
    with pytest.raises(ProviderUnavailableError):
        service(FakeProvider(error=ProviderUnavailableError("down")), cache).current_aqi(LAT, LON)


# --- Cache failures never block a response ------------------------------------------------------

def test_cache_read_failure_falls_back_to_provider():
    provider = FakeProvider()
    cache = FakeCache(get_error=CacheError("throttled"))
    report = service(provider, cache).current_aqi(LAT, LON)
    assert len(provider.calls) == 1
    assert report.cache is CacheOutcome.BYPASSED
    assert len(cache.puts) == 1  # still attempts to repopulate


def test_cache_write_failure_still_returns_result():
    cache = FakeCache(put_error=CacheError("throttled"))
    report = service(FakeProvider(), cache).current_aqi(LAT, LON)
    assert report.result.aqi == 150


# --- Data and input problems --------------------------------------------------------------------

def test_insufficient_provider_data_raises():
    sparse = make_series(pm10=None, no2=None, so2=None, o3=None, co=None)  # only PM2.5
    with pytest.raises(InsufficientDataError):
        service(FakeProvider(series=sparse)).current_aqi(LAT, LON)


@pytest.mark.parametrize(("lat", "lon"), [(91, 0), (0, -181), (float("nan"), 0)])
def test_invalid_coordinates_rejected_before_cache_or_provider(lat, lon):
    provider, cache = FakeProvider(), FakeCache()
    with pytest.raises(ValueError):
        service(provider, cache).current_aqi(lat, lon)
    assert provider.calls == [] and cache.puts == []


def test_severe_result_is_beyond_scale():
    report = service(FakeProvider(series=make_series(pm2_5=300.0))).current_aqi(LAT, LON)
    assert report.result.display == "401+"
    assert report.result.category is Category.SEVERE


@pytest.mark.parametrize(
    "kwargs", [{"fresh_for": timedelta(0)}, {"fresh_for": timedelta(hours=2), "max_stale": timedelta(hours=1)}]
)
def test_invalid_policy_rejected(kwargs):
    with pytest.raises(ValueError):
        service(**kwargs)
