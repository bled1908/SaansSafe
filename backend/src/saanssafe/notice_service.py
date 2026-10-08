"""Parent Notice orchestration: existing AQI + outlook -> facts -> (AI writer) -> guard.

The deterministic template is authoritative and always available. An AI writer is only
used when enabled; its output is served only if notice_guard accepts it. Any writer
exception, timeout or guard failure serves the template with a `fallback_reason`.

Data comes from the unchanged AqiService.current_aqi / AqiService.forecast, rendered
through the same api.report_body / api.forecast_body as GET /aqi and GET /forecast, so
the notice uses exactly the values those endpoints serve.

Notice cache: final response bodies, in the existing DynamoDB table, under keys that
cannot collide with the series cache ("notice#..." vs "<source>#..."):
    pk              S  notice#<lat 2dp>#<lon 2dp>#<valid hour UTC>#<language>#<mode>#<facts hash>
                       (the facts hash covers the school name and every served value)
    created_at      N  epoch seconds
    expires_at      N  epoch seconds; DynamoDB TTL (cleanup only)
    schema_version  N  NOTICE_SCHEMA_VERSION
    payload         S  JSON response body
Notices built from stale data, or after a transient AI failure, are not cached.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from saanssafe.api import forecast_body, report_body
from saanssafe.cache import CacheError
from saanssafe.notice_facts import NoticeFacts, ParentNotice, build_notice_facts
from saanssafe.notice_guard import validate_notice
from saanssafe.notice_template import compose_share_text, render_footer, render_template
from saanssafe.notice_writer import NoticeWriter
from saanssafe.service import AqiService

logger = logging.getLogger(__name__)

NOTICE_SCHEMA_VERSION = 1
DEFAULT_NOTICE_CACHE_FOR = timedelta(hours=1)
DEFAULT_AI_TIMEOUT_S = 8.0
TRANSIENT_FALLBACKS = frozenset({"ai_timeout", "ai_unavailable"})


@dataclass(frozen=True)
class CachedNotice:
    body: dict[str, Any]
    created_at: datetime  # UTC


class NoticeCache(Protocol):
    def get(self, key: str) -> CachedNotice | None: ...

    def put(self, key: str, cached: CachedNotice) -> None: ...


class DynamoNoticeCache:
    """NoticeCache in the existing DynamoDB table (string `pk`), via a low-level client."""

    def __init__(self, client: Any, table_name: str, retention: timedelta = DEFAULT_NOTICE_CACHE_FOR):
        if not table_name:
            raise ValueError("table_name is required")
        self._client = client
        self._table = table_name
        self._retention = retention

    def get(self, key: str) -> CachedNotice | None:
        try:
            response = self._client.get_item(TableName=self._table, Key={"pk": {"S": key}})
        except Exception as err:  # botocore raises many types; all mean "cache unavailable"
            raise CacheError(f"DynamoDB get_item failed: {type(err).__name__}") from err
        item = response.get("Item")
        if not item:
            return None
        try:
            if int(item["schema_version"]["N"]) != NOTICE_SCHEMA_VERSION:
                return None
            created = datetime.fromtimestamp(int(item["created_at"]["N"]), UTC)
            body = json.loads(item["payload"]["S"])
            if not isinstance(body, dict):
                raise ValueError("payload is not an object")
        except (KeyError, TypeError, ValueError) as err:
            raise CacheError(f"Corrupt notice cache item: {err}") from err
        return CachedNotice(body, created)

    def put(self, key: str, cached: CachedNotice) -> None:
        created = int(cached.created_at.timestamp())
        item = {
            "pk": {"S": key},
            "created_at": {"N": str(created)},
            "expires_at": {"N": str(created + int(self._retention.total_seconds()))},
            "schema_version": {"N": str(NOTICE_SCHEMA_VERSION)},
            "payload": {"S": json.dumps(cached.body, ensure_ascii=False, separators=(",", ":"))},
        }
        try:
            self._client.put_item(TableName=self._table, Item=item)
        except Exception as err:
            raise CacheError(f"DynamoDB put_item failed: {type(err).__name__}") from err


def facts_fingerprint(facts: NoticeFacts) -> str:
    """Hash of every fact except the data's age, so a cached notice is reused only while
    /aqi and /forecast still serve the same values (a refetch within the hour changes it)."""
    grounding = facts.grounding()
    grounding.pop("age_minutes")
    grounding.pop("freshness_warning")
    canonical = json.dumps(grounding, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def notice_cache_key(aqi: dict[str, Any], facts: NoticeFacts, mode: str) -> str:
    """notice#<lat>#<lon>#<valid hour>#<language>#<mode>#<facts hash>; never the raw name."""
    query = aqi["location"]["query"]
    return (
        f"notice#{query['lat']:.2f}#{query['lon']:.2f}#{aqi['valid_for_hour']}"
        f"#{facts.language}#{mode}#{facts_fingerprint(facts)}"
    )


@dataclass(frozen=True)
class _Written:
    notice: ParentNotice
    generated_by: str
    model: str | None
    fallback_reason: str | None


def _utc_now() -> datetime:
    return datetime.now(UTC)


class NoticeService:
    def __init__(
        self,
        aqi_service: AqiService,
        cache: NoticeCache,
        writer: NoticeWriter | None = None,
        *,
        ai_enabled: bool = True,
        ai_timeout_s: float = DEFAULT_AI_TIMEOUT_S,
        cache_for: timedelta = DEFAULT_NOTICE_CACHE_FOR,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if ai_timeout_s <= 0:
            raise ValueError("ai_timeout_s must be positive")
        self._aqi = aqi_service
        self._cache = cache
        self._writer = writer
        self._ai_enabled = ai_enabled
        self._ai_timeout_s = ai_timeout_s
        self._cache_for = cache_for
        self._clock = clock

    def create(
        self, latitude: float, longitude: float, language: str, school_name: str | None = None
    ) -> dict[str, Any]:
        """The notice response body. Data/provider errors propagate (mapped by the API)."""
        aqi = report_body(self._aqi.current_aqi(latitude, longitude))
        forecast = forecast_body(self._aqi.forecast(latitude, longitude))
        facts = build_notice_facts(aqi, forecast, language, school_name)
        mode = "ai" if self._ai_enabled and self._writer is not None else "template"
        key = notice_cache_key(aqi, facts, mode)

        cached, cache_state = self._read(key)
        if cached is not None:  # same facts; only the data's age has moved on
            return {**cached.body, "freshness": _freshness(aqi), "cache": "hit"}

        written = self._write(facts)
        body = _response_body(facts, aqi, written, cache_state)
        if not facts.stale and written.fallback_reason not in TRANSIENT_FALLBACKS:
            self._store(key, body)
        return body

    # --- writer ----------------------------------------------------------------------------

    def _write(self, facts: NoticeFacts) -> _Written:
        if not self._ai_enabled:
            return self._fallback(facts, "ai_disabled")
        if self._writer is None:
            return self._fallback(facts, "ai_unavailable")
        started = time.monotonic()
        try:
            notice = self._call_writer(self._writer, facts)
        except (FutureTimeout, TimeoutError):
            return self._fallback(facts, "ai_timeout", started)
        except Exception as err:  # any writer failure is non-fatal by design
            logger.warning("notice writer failed: %s", type(err).__name__)
            return self._fallback(facts, "ai_unavailable", started)
        if not isinstance(notice, ParentNotice):
            return self._fallback(facts, "validation_failed", started)
        problems = validate_notice(notice, facts)
        if problems:
            logger.warning("notice guard rejected AI notice: %s", ",".join(problems))
            return self._fallback(facts, "validation_failed", started)
        self._log(self._writer.name, None, started)
        return _Written(notice, self._writer.name, self._writer.model_id, None)

    def _call_writer(self, writer: NoticeWriter, facts: NoticeFacts) -> ParentNotice:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="notice-writer")
        try:
            return executor.submit(writer.write, facts).result(timeout=self._ai_timeout_s)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)  # never wait for a slow writer

    def _fallback(self, facts: NoticeFacts, reason: str, started: float | None = None) -> _Written:
        self._log("template", reason, started)
        return _Written(render_template(facts), "template", None, reason)

    @staticmethod
    def _log(generated_by: str, reason: str | None, started: float | None) -> None:
        latency = None if started is None else round((time.monotonic() - started) * 1000)
        # Never log the school name or the notice text.
        logger.info(
            "notice generated_by=%s fallback_reason=%s ai_latency_ms=%s", generated_by, reason, latency
        )

    # --- cache -----------------------------------------------------------------------------

    def _read(self, key: str) -> tuple[CachedNotice | None, str]:
        try:
            cached = self._cache.get(key)
        except CacheError as err:
            logger.warning("notice cache read failed: %s", err)
            return None, "bypassed"
        if cached is None or self._clock() - cached.created_at > self._cache_for:
            return None, "miss"
        return cached, "hit"

    def _store(self, key: str, body: dict[str, Any]) -> None:
        try:
            self._cache.put(key, CachedNotice(body, self._clock()))
        except CacheError as err:
            logger.warning("notice cache write failed: %s", err)


def _response_body(
    facts: NoticeFacts, aqi: dict[str, Any], written: _Written, cache_state: str
) -> dict[str, Any]:
    footer = render_footer(facts)
    decision = aqi["decision"]
    return {
        "data_type": facts.data_type,
        "language": facts.language,
        "school_name": facts.school_name,
        "notice": written.notice.as_dict(),
        "footer": footer.as_dict(),
        "share_text": compose_share_text(written.notice, footer),
        "generated_by": written.generated_by,
        "model": written.model,
        "fallback_reason": written.fallback_reason,
        "decision": {
            "action": decision["action"],
            "severity": decision["severity"],
            "headline": decision["headline"],
            "policy_version": decision["policy"]["version"],
        },
        "grounding": facts.grounding(),
        "valid_for_hour": aqi["valid_for_hour"],
        "freshness": _freshness(aqi),
        "disclaimer": footer.disclaimer,
        "cache": cache_state,
    }


def _freshness(aqi: dict[str, Any]) -> dict[str, Any]:
    return {key: aqi["freshness"][key] for key in ("status", "age_minutes", "warning")}
