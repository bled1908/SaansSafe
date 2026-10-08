import json
from datetime import timedelta

import pytest
from support import NOW, FakeCache, FakeProvider, make_series

from saanssafe import api
from saanssafe.aqi import BEYOND_SCALE_NOTE, InsufficientDataError
from saanssafe.cache import CachedSeries
from saanssafe.providers.base import (
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from saanssafe.service import AqiService

KEY = "open-meteo#28.61#77.21"


def event(path="/aqi", method="GET", params=None):
    return {
        "rawPath": path,
        "requestContext": {"http": {"method": method}},
        "queryStringParameters": params,
    }


def real_service(provider=None, cache=None):
    return AqiService(provider or FakeProvider(), cache or FakeCache(), clock=lambda: NOW)


class StubService:
    def __init__(self, error):
        self.error = error

    def current_aqi(self, lat, lon):
        raise self.error


def call(evt, service):
    response = api.handle(evt, service)
    return response["statusCode"], json.loads(response["body"]), response["headers"]


# --- Routing ---------------------------------------------------------------------------------

def test_health():
    status, body, headers = call(event("/health"), None)
    assert (status, body) == (200, {"status": "ok"})
    assert headers["Content-Type"].startswith("application/json")


def test_unknown_path_404_and_wrong_method_405():
    assert call(event("/nope"), None)[0] == 404
    status, body, headers = call(event("/aqi", "POST"), real_service())
    assert (status, body["error"]["code"], headers["Allow"]) == (405, "method_not_allowed", "GET")


# --- Success contract ---------------------------------------------------------------------------

def test_aqi_success_contract():
    status, body, headers = call(event(params={"lat": "28.6139", "lon": "77.209"}), real_service())
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert body["data_type"] == "forecast_model"
    assert "CPCB monitoring station" in body["disclaimer"]
    assert "CPCB AQI" not in json.dumps(body)  # never labelled as an official CPCB AQI
    assert body["valid_for_hour"] == "2026-10-08T06:00:00Z"
    assert body["location"] == {
        "requested": {"lat": 28.6139, "lon": 77.209},
        "query": {"lat": 28.61, "lon": 77.21},
        "model_grid": {"lat": 28.6, "lon": 77.2},
    }
    assert body["aqi"] == {
        "value": 150,
        "display": "150",
        "beyond_scale": False,
        "category": "Moderate",
        "health_impact": body["aqi"]["health_impact"],
        "dominant_pollutant": "pm10",
    }
    assert body["pollutants"]["co"] == {
        "sub_index": 72.2,  # 50 + 50*(1.5-1.1)/(2.0-1.1)
        "beyond_scale": False, "concentration": 1.5,
        "unit": "mg/m³", "averaging_hours": 8,
    }
    assert body["pollutants"]["pm10"]["unit"] == "µg/m³"
    assert "nh3" not in body["pollutants"]
    assert body["freshness"] == {
        "status": "fresh", "cache": "miss", "fetched_at": "2026-10-08T06:25:00Z",
        "age_minutes": 0, "warning": None,
    }
    assert body["source"]["provider"] == "open-meteo"
    assert "Copernicus" in body["source"]["attribution"]
    assert body["notes"] == []


def test_stale_fallback_is_explicit_in_response():
    cache = FakeCache({KEY: CachedSeries(make_series(), NOW - timedelta(minutes=95))})
    service = real_service(FakeProvider(error=ProviderUnavailableError("down")), cache)
    status, body, _ = call(event(params={"lat": "28.6139", "lon": "77.209"}), service)
    assert status == 200
    assert body["freshness"]["status"] == "stale"
    assert body["freshness"]["cache"] == "stale_fallback"
    assert body["freshness"]["age_minutes"] == 95
    assert "95 minutes ago" in body["freshness"]["warning"]


def test_4xx_with_stale_cache_returns_upstream_rejected_not_stale_fallback():
    cache = FakeCache({KEY: CachedSeries(make_series(), NOW - timedelta(minutes=95))})
    service = real_service(FakeProvider(error=ProviderRequestError("HTTP 400")), cache)
    status, body, _ = call(event(params={"lat": "28.6139", "lon": "77.209"}), service)
    assert (status, body["error"]["code"]) == (502, "upstream_rejected")


def test_beyond_scale_response():
    service = real_service(FakeProvider(series=make_series(pm2_5=300.0)))
    _, body, _ = call(event(params={"lat": "28.6", "lon": "77.2"}), service)
    assert body["aqi"]["display"] == "401+"
    assert body["aqi"]["value"] == 401 and body["aqi"]["beyond_scale"] is True
    assert body["pollutants"]["pm2_5"]["beyond_scale"] is True
    assert body["notes"] == [BEYOND_SCALE_NOTE]


# --- Input validation ----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "params",
    [None, {}, {"lat": "28.6"}, {"lon": "77.2"}, {"lat": "abc", "lon": "77.2"},
     {"lat": "91", "lon": "77.2"}, {"lat": "28.6", "lon": "-181"}, {"lat": "nan", "lon": "77"},
     {"lat": "1e999", "lon": "77"}, {"lat": " ", "lon": "77"}, {"lat": "1" * 40, "lon": "77"}],
)
def test_invalid_coordinates_400(params):
    provider = FakeProvider()
    status, body, _ = call(event(params=params), real_service(provider))
    assert status == 400
    assert body["error"]["code"] == "invalid_coordinates"
    assert provider.calls == []


# --- Failure mapping ---------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (InsufficientDataError("Need PM2.5 or PM10"), 422, "insufficient_data"),
        (ProviderRequestError("HTTP 400"), 502, "upstream_rejected"),
        (ProviderResponseError("bad json"), 502, "upstream_invalid"),
        (ProviderUnavailableError("timeout"), 503, "upstream_unavailable"),
        (RuntimeError("secret internal detail"), 500, "internal_error"),
    ],
)
def test_error_mapping(error, status, code):
    got_status, body, headers = call(event(params={"lat": "28.6", "lon": "77.2"}), StubService(error))
    assert (got_status, body["error"]["code"]) == (status, code)
    if status == 503:
        assert headers["Retry-After"] == "60"
    assert "secret internal detail" not in body["error"]["message"]


def test_handler_with_missing_config_returns_500(monkeypatch):
    monkeypatch.setattr(api, "_SERVICE", None)
    monkeypatch.delenv("AQI_CACHE_TABLE", raising=False)
    response = api.handler(event(params={"lat": "28.6", "lon": "77.2"}), None)
    assert response["statusCode"] == 500


# --- Settings ----------------------------------------------------------------------------------------

def test_settings_defaults():
    s = api.Settings.from_env({"AQI_CACHE_TABLE": "AqiCache"})
    assert (s.table_name, s.fresh_for, s.max_stale) == ("AqiCache", timedelta(minutes=60), timedelta(hours=6))
    assert s.open_meteo_base_url.startswith("https://") and s.open_meteo_timeout_s == 8


@pytest.mark.parametrize(
    "env",
    [{}, {"AQI_CACHE_TABLE": " "},
     {"AQI_CACHE_TABLE": "t", "CACHE_FRESH_MINUTES": "abc"},
     {"AQI_CACHE_TABLE": "t", "CACHE_FRESH_MINUTES": "0"},
     {"AQI_CACHE_TABLE": "t", "CACHE_FRESH_MINUTES": "600", "CACHE_MAX_STALE_HOURS": "1"},
     {"AQI_CACHE_TABLE": "t", "OPEN_METEO_TIMEOUT_S": "60"}],
)
def test_settings_rejects_bad_config(env):
    with pytest.raises(api.ConfigError):
        api.Settings.from_env(env)
