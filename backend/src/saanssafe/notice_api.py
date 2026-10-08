"""AWS Lambda handler for POST /notice (API Gateway HTTP API, payload format 2.0).

Request JSON (at most 1 KB):
  {"lat": 28.61, "lon": 77.21, "language": "en" | "hi", "school_name": "optional"}
Response 200: see notice_service._response_body. AI problems never cause a non-200:
they return the deterministic template with `generated_by: "template"` and a
`fallback_reason`. Coordinate and data errors use exactly the /aqi mapping
(api._serve): 400, 422, 502, 503 (Retry-After), 500. Also: 405 for non-POST,
413 for an oversized body, 400 for invalid JSON, language or school_name.

Configuration (environment variables), in addition to api.Settings:
  NOTICE_AI_ENABLED      optional  "true" (default) / "false": kill switch for AI writing
  NOTICE_AI_TIMEOUT_S    optional  default 8
  NOTICE_CACHE_MINUTES   optional  default 60
No AI writer is wired yet, so notices are template-only (fallback_reason "ai_unavailable",
or "ai_disabled" when the kill switch is off).
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from saanssafe.api import (
    MAX_PARAM_LENGTH,
    ConfigError,
    Settings,
    _env_number,
    _error,
    _serve,
    build_service,
)
from saanssafe.notice_facts import LANGUAGES
from saanssafe.notice_service import DynamoNoticeCache, NoticeService
from saanssafe.notice_writer import NoticeWriter

logger = logging.getLogger("saanssafe")

MAX_BODY_BYTES = 1024
MAX_SCHOOL_NAME = 60
FIELDS = frozenset({"lat", "lon", "language", "school_name"})
# Letters (Latin or Devanagari), digits, spaces and . , ' ’ - ( ) &  (’: phone keyboards)
_SCHOOL_NAME = re.compile(r"[A-Za-z0-9ऀ-ॿ .,'’\-()&]+")
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class RequestError(ValueError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class NoticeSettings:
    base: Settings
    ai_enabled: bool
    ai_timeout_s: float
    cache_for: timedelta

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> NoticeSettings:
        raw = (env.get("NOTICE_AI_ENABLED") or "true").strip().lower()
        if raw not in _TRUE | _FALSE:
            raise ConfigError(f"NOTICE_AI_ENABLED must be true or false, got {raw!r}")
        return cls(
            base=Settings.from_env(env),
            ai_enabled=raw in _TRUE,
            ai_timeout_s=_env_number(env, "NOTICE_AI_TIMEOUT_S", 8, 1, 20),
            cache_for=timedelta(minutes=_env_number(env, "NOTICE_CACHE_MINUTES", 60, 1, 1440)),
        )


def build_writer(settings: NoticeSettings) -> NoticeWriter | None:
    """The AI writer. None until the Strands/Bedrock writer is implemented."""
    return None


def build_notice_service(settings: NoticeSettings) -> NoticeService:
    import boto3  # provided by the Lambda runtime; imported lazily so tests don't need it

    return NoticeService(
        build_service(settings.base),
        DynamoNoticeCache(boto3.client("dynamodb"), settings.base.table_name, settings.cache_for),
        build_writer(settings),
        ai_enabled=settings.ai_enabled,
        ai_timeout_s=settings.ai_timeout_s,
        cache_for=settings.cache_for,
    )


_SERVICE: NoticeService | None = None


def _get_service() -> NoticeService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = build_notice_service(NoticeSettings.from_env(os.environ))
    return _SERVICE


# --- Request parsing ------------------------------------------------------------------------

def _body(event: Mapping[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or ""
    if len(raw) > 2 * MAX_BODY_BYTES:  # too large even as base64; don't decode it
        raise RequestError(413, "payload_too_large", f"Request body exceeds {MAX_BODY_BYTES} bytes")
    if event.get("isBase64Encoded"):
        try:
            data = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            raise RequestError(400, "invalid_request", "Request body is not valid base64") from None
    else:
        data = raw.encode("utf-8")
    if len(data) > MAX_BODY_BYTES:
        raise RequestError(413, "payload_too_large", f"Request body exceeds {MAX_BODY_BYTES} bytes")
    try:
        body = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise RequestError(400, "invalid_request", "Request body must be JSON") from None
    if not isinstance(body, dict):
        raise RequestError(400, "invalid_request", "Request body must be a JSON object")
    unknown = sorted(set(body) - FIELDS)
    if unknown:
        raise RequestError(400, "invalid_request", f"Unknown field(s): {', '.join(unknown)}")
    return body


def _coordinate(body: Mapping[str, Any], name: str) -> str:
    """The coordinate as text for api._parse_coordinates (which also range-checks it)."""
    value = body.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise RequestError(400, "invalid_coordinates", f"Field '{name}' must be a number")
    text = str(value).strip()
    if len(text) > MAX_PARAM_LENGTH:
        raise RequestError(400, "invalid_coordinates", f"Field '{name}' is too long")
    try:
        float(text)
    except ValueError:
        raise RequestError(400, "invalid_coordinates", f"Field '{name}' must be a number") from None
    return text


def _language(body: Mapping[str, Any]) -> str:
    language = body.get("language")
    if language not in LANGUAGES:
        raise RequestError(400, "invalid_language", "Field 'language' must be 'en' or 'hi'")
    return language


def clean_school_name(value: Any) -> str | None:
    """Optional school name: control characters removed, whitespace collapsed, whitelisted."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise RequestError(400, "invalid_school_name", "Field 'school_name' must be a string")
    visible = "".join(
        ch if unicodedata.category(ch) not in ("Cc", "Cf") else (" " if ch.isspace() else "")
        for ch in value
    )
    name = " ".join(visible.split())
    if not name:
        return None
    if len(name) > MAX_SCHOOL_NAME:
        raise RequestError(
            400, "invalid_school_name",
            f"Field 'school_name' must be at most {MAX_SCHOOL_NAME} characters",
        )
    if not _SCHOOL_NAME.fullmatch(name):
        raise RequestError(
            400, "invalid_school_name",
            "Field 'school_name' may contain only letters, digits, spaces and . , ' - ( ) &",
        )
    return name


# --- Routing --------------------------------------------------------------------------------

def handle(event: Mapping[str, Any], service: NoticeService | None = None):
    """Route one API Gateway event. `service` is injected in tests and built lazily in Lambda."""
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        if event.get("rawPath", "") != "/notice":
            return _error(404, "not_found", "Unknown path")
        if method != "POST":
            return _error(405, "method_not_allowed", "Only POST is supported", {"Allow": "POST"})
        try:
            body = _body(event)
            params = {"lat": _coordinate(body, "lat"), "lon": _coordinate(body, "lon")}
            language = _language(body)
            school_name = clean_school_name(body.get("school_name"))
        except RequestError as err:
            return _error(err.status, err.code, str(err))
        svc = service or _get_service()
        return _serve(
            {"queryStringParameters": params},
            lambda lat, lon: svc.create(lat, lon, language, school_name),
            lambda notice: notice,
        )
    except Exception:
        logger.exception("unhandled error")
        return _error(500, "internal_error", "Unexpected server error")


def handler(event: Mapping[str, Any], context: Any):  # Lambda entry point
    return handle(event)
