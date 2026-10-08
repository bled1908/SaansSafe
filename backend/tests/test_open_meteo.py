"""Open-Meteo client tests. All HTTP is faked; no test touches the network."""

import json
import socket
from datetime import UTC, datetime, timedelta
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from saanssafe.aqi import Pollutant, aqi_from_hourly
from saanssafe.providers.base import (
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from saanssafe.providers.open_meteo import (
    DEFAULT_BASE_URL,
    VARIABLES,
    OpenMeteoClient,
    parse_response,
)

START = int(datetime(2026, 10, 7, tzinfo=UTC).timestamp())
UNIT = "μg/m³"


def payload(hours: int = 48, **overrides) -> dict:
    hourly = {"time": [START + 3600 * i for i in range(hours)]}
    hourly |= {
        "pm2_5": [45.5] * hours,
        "pm10": [175.5] * hours,
        "nitrogen_dioxide": [20.0] * hours,
        "sulphur_dioxide": [10.0] * hours,
        "ozone": [40.0] * hours,
        "carbon_monoxide": [1500.0] * hours,  # ug/m3 -> 1.5 mg/m3
        "ammonia": [None] * hours,            # not available for India
    }
    hourly |= overrides
    return {
        "latitude": 28.625,
        "longitude": 77.25,
        "generationtime_ms": 0.5,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "hourly_units": {"time": "unixtime", **{v: UNIT for v in VARIABLES}},
        "hourly": hourly,
    }


class FakeTransport:
    def __init__(self, status: int = 200, body: bytes | None = None, exc: Exception | None = None):
        self.status = status
        self.body = json.dumps(payload()).encode() if body is None else body
        self.exc = exc
        self.calls: list[tuple[str, float]] = []

    def __call__(self, url: str, timeout_s: float) -> tuple[int, bytes]:
        self.calls.append((url, timeout_s))
        if self.exc:
            raise self.exc
        return self.status, self.body


def client(transport: FakeTransport, **kwargs) -> OpenMeteoClient:
    return OpenMeteoClient(transport=transport, **kwargs)


# --- Request building ---------------------------------------------------------------------------

def test_request_url_and_timeout():
    transport = FakeTransport()
    client(transport, timeout_s=7).fetch_hourly(28.6139, 77.209)
    url, timeout = transport.calls[0]
    assert timeout == 7.0
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == DEFAULT_BASE_URL
    query = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert query["latitude"] == "28.6139" and query["longitude"] == "77.2090"
    assert query["hourly"].split(",") == list(VARIABLES)
    assert query["timeformat"] == "unixtime" and query["timezone"] == "GMT"
    # 4 forecast days (GMT) always reach >= 72 h past the current UTC hour; see FORECAST_DAYS.
    assert query["past_days"] == "1" and query["forecast_days"] == "4"


@pytest.mark.parametrize(
    ("lat", "lon"), [(91, 0), (-91, 0), (0, 181), (0, -181), (float("nan"), 0), (True, 0), ("28", 77)]
)
def test_invalid_coordinates_rejected_before_any_request(lat, lon):
    transport = FakeTransport()
    with pytest.raises(ValueError):
        client(transport).fetch_hourly(lat, lon)
    assert transport.calls == []


@pytest.mark.parametrize(
    "kwargs", [{"timeout_s": 0}, {"timeout_s": -1}, {"timeout_s": 120}, {"base_url": "http://x"}]
)
def test_client_rejects_unsafe_configuration(kwargs):
    with pytest.raises(ValueError):
        OpenMeteoClient(transport=FakeTransport(), **kwargs)


# --- Successful parsing -----------------------------------------------------------------------

def test_successful_response_is_normalized():
    series = client(FakeTransport()).fetch_hourly(28.6, 77.2)
    assert series.source == "open-meteo"
    assert (series.latitude, series.longitude) == (28.625, 77.25)
    assert len(series.readings) == 48
    assert series.first_time == datetime(2026, 10, 7, tzinfo=UTC)
    assert series.last_time == datetime(2026, 10, 8, 23, tzinfo=UTC)
    first = series.readings[0]
    assert (first.pm2_5, first.pm10, first.no2, first.so2, first.o3) == (45.5, 175.5, 20, 10, 40)


def test_carbon_monoxide_converted_from_ug_to_mg():
    series = parse_response(payload())
    assert series.readings[0].co == pytest.approx(1.5)


def test_parsed_series_produces_cpcb_aqi():
    series = parse_response(payload())
    result = aqi_from_hourly(series.hourly_until(datetime(2026, 10, 8, 10, tzinfo=UTC)))
    assert result.aqi == 150  # PM10 175.5 is the midpoint of 101-250 -> 150
    assert result.dominant is Pollutant.PM10
    assert Pollutant.NH3 not in result.sub_indices  # all-null ammonia is excluded, not invented


# --- Missing pollutant data ----------------------------------------------------------------------

def test_null_values_become_none():
    series = parse_response(payload(pm2_5=[None, 12.0] * 24))
    assert series.readings[0].pm2_5 is None
    assert series.readings[1].pm2_5 == 12.0


def test_absent_variable_becomes_all_missing():
    data = payload()
    del data["hourly"]["sulphur_dioxide"]
    series = parse_response(data)
    assert all(r.so2 is None for r in series.readings)


def test_all_null_ammonia_is_none():
    assert all(r.nh3 is None for r in parse_response(payload()).readings)


# --- Malformed responses ----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "body",
    [b"not json", b"\xff\xfe", b"[1, 2, 3]", b"null", json.dumps({"latitude": 1}).encode()],
)
def test_malformed_body_raises_response_error(body):
    with pytest.raises(ProviderResponseError):
        client(FakeTransport(body=body)).fetch_hourly(28.6, 77.2)


def _broken(mutate) -> dict:
    data = payload()
    mutate(data)
    return data


@pytest.mark.parametrize(
    "data",
    [
        _broken(lambda d: d.pop("hourly")),
        _broken(lambda d: d.pop("hourly_units")),
        _broken(lambda d: d.update(latitude="28.6")),
        _broken(lambda d: d["hourly"].update(time=[])),
        _broken(lambda d: d["hourly"].update(time="2026-10-07T00:00")),
        _broken(lambda d: d["hourly"].update(time=["2026-10-07T00:00"] * 48)),
        _broken(lambda d: d["hourly"].update(pm2_5=[1.0] * 47)),           # length mismatch
        _broken(lambda d: d["hourly"].update(pm10=[-5.0] * 48)),           # negative
        _broken(lambda d: d["hourly"].update(ozone=["40"] * 48)),          # string
        _broken(lambda d: d["hourly"].update(ozone=[True] * 48)),          # bool
        _broken(lambda d: d["hourly_units"].update(carbon_monoxide="mg/m³")),  # unit change
        _broken(lambda d: d["hourly"]["time"].__setitem__(5, START)),      # non-consecutive
        {"error": True, "reason": "Cannot initialize"},
    ],
)
def test_malformed_payload_raises_response_error(data):
    with pytest.raises(ProviderResponseError):
        parse_response(data)


def test_oversized_response_rejected():
    with pytest.raises(ProviderResponseError, match="too large"):
        client(FakeTransport(body=b" " * 2_000_001)).fetch_hourly(28.6, 77.2)


# --- HTTP / network failures ----------------------------------------------------------------------------

def test_http_400_raises_request_error_with_reason():
    body = json.dumps({"error": True, "reason": "Latitude must be in range"}).encode()
    with pytest.raises(ProviderRequestError, match="Latitude must be in range"):
        client(FakeTransport(status=400, body=body)).fetch_hourly(28.6, 77.2)


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_retryable_http_status_raises_unavailable(status):
    with pytest.raises(ProviderUnavailableError, match=str(status)):
        client(FakeTransport(status=status, body=b"<html>oops</html>")).fetch_hourly(28.6, 77.2)


@pytest.mark.parametrize(
    "exc", [TimeoutError("timed out"), socket.timeout("timed out"), URLError("dns failure"),
            ConnectionResetError("reset")],
)
def test_network_failures_raise_unavailable(exc):
    with pytest.raises(ProviderUnavailableError):
        client(FakeTransport(exc=exc)).fetch_hourly(28.6, 77.2)


def test_provider_errors_do_not_leak_as_success():
    # A 200 with an empty forecast must not produce an empty "valid" series.
    with pytest.raises(ProviderResponseError):
        client(FakeTransport(body=json.dumps(payload(hours=0)).encode())).fetch_hourly(1, 1)


def test_unixtime_parsing_is_utc():
    series = parse_response(payload(hours=2))
    assert series.readings[1].time == datetime(2026, 10, 7, tzinfo=UTC) + timedelta(hours=1)
