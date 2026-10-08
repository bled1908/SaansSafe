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


# --- Decision block (SaansSafe school safety policy) ---------------------------------------------

EXISTING_KEYS = {
    "data_type", "method", "disclaimer", "valid_for_hour", "location", "aqi",
    "pollutants", "freshness", "source", "notes",
}


def aqi_body(series=None, cache=None, provider_error=None):
    provider = FakeProvider(series=series, error=provider_error)
    status, body, _ = call(event(params={"lat": "28.6139", "lon": "77.209"}),
                           real_service(provider, cache))
    assert status == 200
    return body


def test_success_response_keeps_existing_fields_and_adds_decision():
    body = aqi_body()
    assert set(body) == EXISTING_KEYS | {"decision"}
    assert set(body["decision"]) == {
        "action", "severity", "headline", "short_reason", "recommendations", "activities",
        "aqi_context", "cpcb_health_statement", "dominant_pollutant", "policy", "data_freshness",
    }


def test_decision_for_default_moderate_case():
    d = aqi_body()["decision"]
    assert (d["action"], d["severity"]) == ("reduce_outdoor_exertion", "moderate")
    assert d["activities"] == {
        "morning_assembly": "allowed", "pe_and_sports": "limited", "recess_and_breaks": "allowed",
    }
    assert d["recommendations"] and all(isinstance(r, str) for r in d["recommendations"])
    assert d["aqi_context"] == {
        "value": 150, "display": "150", "beyond_scale": False,
        "category": "Moderate", "data_type": "forecast_model",
    }


@pytest.mark.parametrize(
    ("pm25", "category", "action", "severity"),
    [
        (15, "Good", "normal_outdoor_activities", "minimal"),
        (45.5, "Satisfactory", "outdoor_ok_protect_sensitive_students", "low"),
        (75, "Moderate", "reduce_outdoor_exertion", "moderate"),
        (105, "Poor", "move_strenuous_activities_indoors", "high"),
        (185.5, "Very Poor", "suspend_outdoor_activities", "very_high"),
        (300, "Severe", "suspend_outdoor_activities", "critical"),
    ],
)
def test_decision_for_every_category(pm25, category, action, severity):
    body = aqi_body(make_series(pm2_5=pm25, pm10=10.0, co=0.5))
    d = body["decision"]
    assert body["aqi"]["category"] == d["aqi_context"]["category"] == category
    assert (d["action"], d["severity"]) == (action, severity)


def test_decision_beyond_scale_401_plus():
    body = aqi_body(make_series(pm2_5=300.0))
    d = body["decision"]
    assert d["aqi_context"]["display"] == "401+" and d["aqi_context"]["beyond_scale"] is True
    assert d["dominant_pollutant"] == {
        "code": "pm2_5", "name": "PM2.5 (fine particulate matter)",
        "sub_index": 401.0, "beyond_scale": True,
    }
    assert "401+" in d["short_reason"] and "beyond the published CPCB scale" in d["short_reason"]
    assert all(v == "move_indoors" for v in d["activities"].values())
    assert body["aqi"]["display"] == "401+"  # existing field unchanged


def test_decision_dominant_pollutant_context():
    d = aqi_body()["decision"]
    assert d["dominant_pollutant"] == {
        "code": "pm10", "name": "PM10 (coarse particulate matter)",
        "sub_index": 150.0, "beyond_scale": False,
    }


def test_decision_separates_cpcb_statement_saanssafe_policy_and_model_data():
    body = aqi_body()
    d = body["decision"]
    # CPCB: category + verbatim Table 3.12 statement, same as the existing aqi field
    assert d["cpcb_health_statement"]["text"] == body["aqi"]["health_impact"]
    assert d["cpcb_health_statement"]["source"].endswith("Table 3.12")
    # SaansSafe policy: named, versioned, explicitly not CPCB
    assert d["policy"]["name"] == "SaansSafe school safety policy"
    assert d["policy"]["version"] == "saanssafe-school-v1"
    assert "not a CPCB rule" in d["policy"]["basis"]
    assert "SaansSafe school safety policy (not a CPCB rule)" in d["short_reason"]
    # Data: forecast/model
    assert d["aqi_context"]["data_type"] == body["data_type"] == "forecast_model"
    assert "Forecast/model AQI" in d["short_reason"]


def test_decision_inherits_fresh_status():
    body = aqi_body()
    assert body["decision"]["data_freshness"] == {"status": "fresh", "age_minutes": 0, "warning": None}


def test_decision_inherits_stale_warning_and_existing_freshness_intact():
    cache = FakeCache({KEY: CachedSeries(make_series(), NOW - timedelta(minutes=95))})
    body = aqi_body(cache=cache, provider_error=ProviderUnavailableError("down"))
    fresh = body["freshness"]
    assert (fresh["status"], fresh["cache"], fresh["age_minutes"]) == ("stale", "stale_fallback", 95)
    decision_fresh = body["decision"]["data_freshness"]
    assert decision_fresh == {"status": "stale", "age_minutes": 95, "warning": fresh["warning"]}
    assert "95 minutes ago" in decision_fresh["warning"]


@pytest.mark.parametrize(
    "error",
    [InsufficientDataError("x"), ProviderRequestError("x"), ProviderResponseError("x"),
     ProviderUnavailableError("x"), RuntimeError("x")],
)
def test_error_responses_have_no_decision(error):
    _, body, _ = call(event(params={"lat": "28.6", "lon": "77.2"}), StubService(error))
    assert set(body) == {"error"}


def test_decision_is_deterministic_across_requests():
    assert aqi_body()["decision"] == aqi_body()["decision"]
