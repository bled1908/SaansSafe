"""Open-Meteo Air Quality API client (https://open-meteo.com/en/docs/air-quality-api).

Network I/O lives only in `urllib_transport`. Everything else (URL building, error
mapping, `parse_response`) is deterministic and tested with static payloads.

Data: Open-Meteo, based on Copernicus Atmosphere Monitoring Service (CAMS) forecasts.
These are gridded MODEL values (forecast/analysis), not CPCB ground-station observations.
All concentrations arrive in ug/m3. CO is converted to mg/m3 for the CPCB engine.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from saanssafe.aqi import Pollutant
from saanssafe.providers.base import (
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
    validate_coordinates,
)
from saanssafe.readings import HourlyReading, ReadingSeries

DEFAULT_BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
DEFAULT_TIMEOUT_S = 10.0
PAST_DAYS = 1  # guarantees >= 24 h of history before the current hour
# With timezone=GMT the data ends at 23:00 UTC on the last forecast day, so from UTC hour H
# it reaches 24*FORECAST_DAYS - 1 - H hours ahead: 4 days guarantees >= 72 hours for any H.
FORECAST_DAYS = 4
MAX_RESPONSE_BYTES = 2_000_000
UG_PER_MG = 1000.0
_UG_PER_M3_UNITS = frozenset({"μg/m³", "µg/m³"})  # Greek mu and micro sign

# Open-Meteo variable name -> engine pollutant
VARIABLES: Mapping[str, Pollutant] = {
    "pm2_5": Pollutant.PM25,
    "pm10": Pollutant.PM10,
    "nitrogen_dioxide": Pollutant.NO2,
    "sulphur_dioxide": Pollutant.SO2,
    "ozone": Pollutant.O3,
    "carbon_monoxide": Pollutant.CO,
    "ammonia": Pollutant.NH3,  # Open-Meteo: "Only available for Europe" -> null for India
}

# (url, timeout_s) -> (http_status, body)
Transport = Callable[[str, float], tuple[int, bytes]]


def urllib_transport(url: str, timeout_s: float) -> tuple[int, bytes]:
    """The only function that touches the network. Raises OSError/TimeoutError on failure."""
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "SaansSafe/0.1"})
    try:
        with urlopen(request, timeout=timeout_s) as response:  # noqa: S310 (https-only URL)
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as err:
        return err.code, err.read(MAX_RESPONSE_BYTES + 1)


class OpenMeteoClient:
    name = "open-meteo"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: Transport = urllib_transport,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError(f"base_url must use https, got {base_url!r}")
        if not (isinstance(timeout_s, (int, float)) and 0 < timeout_s <= 60):
            raise ValueError(f"timeout_s must be in (0, 60], got {timeout_s!r}")
        self._base_url = base_url
        self._timeout_s = float(timeout_s)
        self._transport = transport

    def build_url(self, latitude: float, longitude: float) -> str:
        lat, lon = validate_coordinates(latitude, longitude)
        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "hourly": ",".join(VARIABLES),
            "past_days": PAST_DAYS,
            "forecast_days": FORECAST_DAYS,
            "timeformat": "unixtime",
            "timezone": "GMT",
        }
        return f"{self._base_url}?{urlencode(params)}"

    def fetch_hourly(self, latitude: float, longitude: float) -> ReadingSeries:
        url = self.build_url(latitude, longitude)  # validates coordinates before any I/O
        try:
            status, body = self._transport(url, self._timeout_s)
        except (TimeoutError, OSError) as err:  # URLError and socket errors are OSErrors
            raise ProviderUnavailableError(f"Open-Meteo unreachable: {err}") from err
        if len(body) > MAX_RESPONSE_BYTES:
            raise ProviderResponseError("Open-Meteo response too large")
        if status != 200:
            reason = _error_reason(body)
            if status == 429 or status >= 500:
                raise ProviderUnavailableError(f"Open-Meteo HTTP {status}: {reason}")
            raise ProviderRequestError(f"Open-Meteo rejected request (HTTP {status}): {reason}")
        return parse_response(_decode_json(body), source=self.name)


def _decode_json(body: bytes) -> object:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ProviderResponseError(f"Open-Meteo returned invalid JSON: {err}") from err


def _error_reason(body: bytes) -> str:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "no details"
    if isinstance(payload, dict) and isinstance(payload.get("reason"), str):
        return payload["reason"][:200]
    return "no details"


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ProviderResponseError(f"{name} must be a finite number, got {value!r}")
    return float(value)


def _require_dict(container: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = container.get(key)
    if not isinstance(value, dict):
        raise ProviderResponseError(f"'{key}' must be an object")
    return value


def _variable_values(
    hourly: Mapping[str, object], units: Mapping[str, object], variable: str, length: int
) -> list[float | None]:
    """Values for one variable in engine units. Absent variable means all hours missing."""
    if variable not in hourly:
        return [None] * length
    raw = hourly[variable]
    if not isinstance(raw, list) or len(raw) != length:
        raise ProviderResponseError(f"hourly.{variable} must be a list of {length} values")
    if units.get(variable) not in _UG_PER_M3_UNITS:
        raise ProviderResponseError(
            f"Unexpected unit for {variable}: {units.get(variable)!r} (expected μg/m³)"
        )
    values: list[float | None] = []
    for i, v in enumerate(raw):
        if v is None:
            values.append(None)
            continue
        number = _number(v, f"hourly.{variable}[{i}]")
        if number < 0:
            raise ProviderResponseError(f"hourly.{variable}[{i}] is negative: {number}")
        values.append(number / UG_PER_MG if variable == "carbon_monoxide" else number)
    return values


def parse_response(payload: object, source: str = OpenMeteoClient.name) -> ReadingSeries:
    """Convert an Open-Meteo JSON payload (timeformat=unixtime) into a ReadingSeries."""
    if not isinstance(payload, dict):
        raise ProviderResponseError("Open-Meteo response must be a JSON object")
    if payload.get("error") is True:
        raise ProviderResponseError(f"Open-Meteo error: {payload.get('reason', 'no details')}")
    latitude = _number(payload.get("latitude"), "latitude")
    longitude = _number(payload.get("longitude"), "longitude")
    hourly = _require_dict(payload, "hourly")
    units = _require_dict(payload, "hourly_units")

    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        raise ProviderResponseError("hourly.time must be a non-empty list")
    if any(isinstance(t, bool) or not isinstance(t, int) for t in times):
        raise ProviderResponseError("hourly.time must contain unix timestamps (integers)")

    columns = {
        pollutant: _variable_values(hourly, units, variable, len(times))
        for variable, pollutant in VARIABLES.items()
    }
    try:
        readings = tuple(
            HourlyReading(
                time=datetime.fromtimestamp(t, UTC),
                **{p.value: columns[p][i] for p in columns},
            )
            for i, t in enumerate(times)
        )
        return ReadingSeries(latitude, longitude, source, readings)
    except (ValueError, OverflowError, OSError) as err:
        raise ProviderResponseError(f"Open-Meteo returned inconsistent data: {err}") from err
