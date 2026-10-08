"""AWS Lambda handler for API Gateway HTTP API (payload format 2.0).

Routes:
  GET /health                -> {"status": "ok"}
  GET /aqi?lat=<f>&lon=<f>   -> current forecast/model AQI (see report_body)

Configuration (environment variables):
  AQI_CACHE_TABLE        required  DynamoDB table name
  CACHE_FRESH_MINUTES    optional  default 60
  CACHE_MAX_STALE_HOURS  optional  default 6
  OPEN_METEO_BASE_URL    optional  default official endpoint
  OPEN_METEO_TIMEOUT_S   optional  default 8
AWS region and credentials come from the Lambda environment (AWS_REGION).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from saanssafe.aqi import (
    AVERAGING_HOURS,
    BEYOND_SCALE_NOTE,
    InsufficientDataError,
    Pollutant,
    is_beyond_scale,
)
from saanssafe.decision import (
    POLICY_BASIS,
    POLICY_NAME,
    POLICY_VERSION,
    decide_school_safety,
)
from saanssafe.providers.base import (
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
    validate_coordinates,
)
from saanssafe.providers.open_meteo import DEFAULT_BASE_URL
from saanssafe.service import AqiReport, AqiService

logger = logging.getLogger("saanssafe")
logger.setLevel(logging.INFO)

DATA_TYPE = "forecast_model"
METHOD = "Indian National AQI method (CPCB breakpoints) applied to CAMS model forecast data"
DISCLAIMER = (
    "Forecast/model estimate for a model grid cell. "
    "Not a reading from a CPCB monitoring station."
)
ATTRIBUTION = (
    "Air quality data: Open-Meteo.com, based on CAMS "
    "(Copernicus Atmosphere Monitoring Service)"
)
CPCB_HEALTH_SOURCE = "CPCB National AQI report CUPS/82/2014-15, Table 3.12"
MAX_PARAM_LENGTH = 32
RETRY_AFTER_SECONDS = 60


class ConfigError(ValueError):
    """Invalid or missing environment configuration."""


def _env_number(env: Mapping[str, str], name: str, default: float, low: float, high: float) -> float:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if not low <= value <= high:
        raise ConfigError(f"{name} must be within [{low}, {high}], got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    table_name: str
    fresh_for: timedelta
    max_stale: timedelta
    open_meteo_base_url: str
    open_meteo_timeout_s: float

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        table = env.get("AQI_CACHE_TABLE", "").strip()
        if not table:
            raise ConfigError("AQI_CACHE_TABLE is required")
        fresh = timedelta(minutes=_env_number(env, "CACHE_FRESH_MINUTES", 60, 1, 1440))
        stale = timedelta(hours=_env_number(env, "CACHE_MAX_STALE_HOURS", 6, 0, 24))
        if stale < fresh:
            raise ConfigError("CACHE_MAX_STALE_HOURS must cover at least CACHE_FRESH_MINUTES")
        return cls(
            table_name=table,
            fresh_for=fresh,
            max_stale=stale,
            open_meteo_base_url=env.get("OPEN_METEO_BASE_URL") or DEFAULT_BASE_URL,
            open_meteo_timeout_s=_env_number(env, "OPEN_METEO_TIMEOUT_S", 8, 1, 25),
        )


def build_service(settings: Settings) -> AqiService:
    import boto3  # provided by the Lambda runtime; imported lazily so tests don't need it

    from saanssafe.cache import DynamoReadingCache
    from saanssafe.providers.open_meteo import OpenMeteoClient

    return AqiService(
        OpenMeteoClient(settings.open_meteo_base_url, settings.open_meteo_timeout_s),
        DynamoReadingCache(boto3.client("dynamodb"), settings.table_name),
        fresh_for=settings.fresh_for,
        max_stale=settings.max_stale,
    )


_SERVICE: AqiService | None = None


def _get_service() -> AqiService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = build_service(Settings.from_env(os.environ))
    return _SERVICE


# --- HTTP helpers ---------------------------------------------------------------------------

def _response(status: int, body: Mapping[str, Any], extra_headers: Mapping[str, str] | None = None):
    headers = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"}
    headers.update(extra_headers or {})
    return {"statusCode": status, "headers": headers, "body": json.dumps(body, ensure_ascii=False)}


def _error(status: int, code: str, message: str, extra_headers: Mapping[str, str] | None = None):
    return _response(status, {"error": {"code": code, "message": message}}, extra_headers)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_coordinates(params: Mapping[str, str]) -> tuple[float, float]:
    values = []
    for name in ("lat", "lon"):
        raw = params.get(name)
        if raw is None or not raw.strip():
            raise ValueError(f"Query parameter '{name}' is required")
        if len(raw) > MAX_PARAM_LENGTH:
            raise ValueError(f"Query parameter '{name}' is too long")
        try:
            values.append(float(raw.strip()))
        except ValueError:
            raise ValueError(f"Query parameter '{name}' must be a number") from None
    return validate_coordinates(values[0], values[1])  # rejects nan/inf/out of range


def decision_body(report: AqiReport) -> dict[str, Any]:
    """Deterministic school safety decision (SaansSafe policy) for this report's AQI.

    Keeps three things apart: the CPCB category/health statement, SaansSafe's school
    policy, and the forecast/model nature of the data (including its freshness).
    """
    d = decide_school_safety(report.result)
    return {
        "action": d.action.value,
        "severity": d.severity.value,
        "headline": d.headline,
        "short_reason": d.short_reason,
        "recommendations": list(d.recommendations),
        "activities": {activity.value: guidance.value for activity, guidance in d.activities.items()},
        "aqi_context": {
            "value": d.aqi_value,
            "display": d.aqi_display,
            "beyond_scale": d.beyond_scale,
            "category": d.category.label,
            "data_type": DATA_TYPE,
        },
        "cpcb_health_statement": {
            "category": d.category.label,
            "text": d.health_impact,
            "source": CPCB_HEALTH_SOURCE,
        },
        "dominant_pollutant": {
            "code": d.dominant_pollutant.value,
            "name": d.dominant_pollutant_name,
            "sub_index": round(d.dominant_sub_index, 1),
            "beyond_scale": d.beyond_scale,
        },
        "policy": {"name": POLICY_NAME, "version": POLICY_VERSION, "basis": POLICY_BASIS},
        "data_freshness": {
            "status": report.freshness.value,
            "age_minutes": int(report.age.total_seconds() // 60),
            "warning": report.warning,
        },
    }


def report_body(report: AqiReport) -> dict[str, Any]:
    result = report.result
    pollutants = {}
    for p, sub in result.sub_indices.items():
        conc = result.concentrations[p]
        pollutants[p.value] = {
            "sub_index": round(sub, 1),
            "beyond_scale": is_beyond_scale(p, conc),
            "concentration": round(conc, 3 if p is Pollutant.CO else 1),
            "unit": "mg/m³" if p is Pollutant.CO else "µg/m³",
            "averaging_hours": AVERAGING_HOURS[p],
        }
    return {
        "data_type": DATA_TYPE,
        "method": METHOD,
        "disclaimer": DISCLAIMER,
        "valid_for_hour": _iso(report.valid_for_hour),
        "location": {
            "requested": {"lat": report.requested_lat, "lon": report.requested_lon},
            "query": {"lat": report.query_lat, "lon": report.query_lon},
            "model_grid": {"lat": report.grid_lat, "lon": report.grid_lon},
        },
        "aqi": {
            "value": result.aqi,
            "display": result.display,
            "beyond_scale": result.beyond_scale,
            "category": result.category.label,
            "health_impact": result.category.health_impact,
            "dominant_pollutant": result.dominant.value,
        },
        "pollutants": pollutants,
        "freshness": {
            "status": report.freshness.value,
            "cache": report.cache.value,
            "fetched_at": _iso(report.fetched_at),
            "age_minutes": int(report.age.total_seconds() // 60),
            "warning": report.warning,
        },
        "source": {"provider": report.source, "attribution": ATTRIBUTION},
        "notes": [BEYOND_SCALE_NOTE] if result.beyond_scale else [],
        "decision": decision_body(report),
    }


# --- Routing --------------------------------------------------------------------------------

def _aqi(event: Mapping[str, Any], service: AqiService):
    try:
        lat, lon = _parse_coordinates(event.get("queryStringParameters") or {})
    except ValueError as err:
        return _error(400, "invalid_coordinates", str(err))
    try:
        report = service.current_aqi(lat, lon)
    except InsufficientDataError as err:
        return _error(422, "insufficient_data", f"Not enough forecast data for an AQI: {err}")
    except ProviderUnavailableError:
        logger.warning("upstream unavailable for %.2f,%.2f", lat, lon)
        return _error(
            503, "upstream_unavailable",
            "The air-quality data source is temporarily unavailable. Try again shortly.",
            {"Retry-After": str(RETRY_AFTER_SECONDS)},
        )
    except ProviderRequestError:
        logger.exception("upstream rejected request")
        return _error(502, "upstream_rejected", "The air-quality data source rejected the request.")
    except ProviderResponseError:
        logger.exception("upstream returned invalid data")
        return _error(502, "upstream_invalid", "The air-quality data source returned invalid data.")
    return _response(200, report_body(report))


def handle(event: Mapping[str, Any], service: AqiService | None = None):
    """Route one API Gateway event. `service` is injected in tests and built lazily in Lambda."""
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        path = event.get("rawPath", "")
        if path not in ("/health", "/aqi"):
            return _error(404, "not_found", "Unknown path")
        if method != "GET":
            return _error(405, "method_not_allowed", "Only GET is supported", {"Allow": "GET"})
        if path == "/health":
            return _response(200, {"status": "ok"})
        return _aqi(event, service or _get_service())
    except Exception:
        logger.exception("unhandled error")
        return _error(500, "internal_error", "Unexpected server error")


def handler(event: Mapping[str, Any], context: Any):  # Lambda entry point
    return handle(event)
