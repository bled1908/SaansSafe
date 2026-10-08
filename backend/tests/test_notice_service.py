import dataclasses
import json
from datetime import UTC, datetime, timedelta

import pytest
from notice_support import LAT, LON, SERIES_KEY, aqi_service, bodies, changing_series, full_series
from support import NOW, FakeCache, FakeDynamoClient, FakeProvider

from saanssafe.cache import CacheError, CachedSeries
from saanssafe.notice_facts import build_notice_facts
from saanssafe.notice_service import (
    NOTICE_SCHEMA_VERSION,
    CachedNotice,
    DynamoNoticeCache,
    NoticeService,
    facts_fingerprint,
    notice_cache_key,
)
from saanssafe.notice_template import render_template
from saanssafe.notice_writer import FakeNoticeWriter, NoticeWriterError
from saanssafe.providers.base import ProviderRequestError, ProviderUnavailableError


class FakeNoticeCache:
    def __init__(self, get_error=None, put_error=None):
        self.entries = {}
        self.get_error = get_error
        self.put_error = put_error
        self.puts = []

    def get(self, key):
        if self.get_error:
            raise self.get_error
        return self.entries.get(key)

    def put(self, key, cached):
        self.puts.append(key)
        if self.put_error:
            raise self.put_error
        self.entries[key] = cached


def ai_rewrite(facts):
    """A valid "AI" notice: the template with a different title and sign-off."""
    notice = render_template(facts)
    if facts.language == "hi":
        return dataclasses.replace(notice, title="अभिभावकों को संदेश", sign_off="— प्रधानाचार्य")
    return dataclasses.replace(notice, title="Message to parents", sign_off="— Principal")


def make(writer=None, series=None, aqi=None, cache=None, clock=lambda: NOW, **kwargs):
    return NoticeService(
        aqi or aqi_service(series or full_series("Poor")),
        cache if cache is not None else FakeNoticeCache(),
        writer,
        clock=clock,
        **kwargs,
    )


def test_ai_success_is_served_with_model_metadata():
    writer = FakeNoticeWriter(ai_rewrite)
    body = make(writer).create(LAT, LON, "en")
    assert (body["generated_by"], body["model"], body["fallback_reason"]) == ("fake", "fake-model-v1", None)
    assert body["notice"]["title"] == "Message to parents"
    assert body["share_text"].startswith("Message to parents")
    assert len(writer.calls) == 1 and writer.calls[0].language == "en"


def test_hindi_ai_success():
    body = make(FakeNoticeWriter(ai_rewrite)).create(LAT, LON, "hi", "सरस्वती विद्यालय")
    assert body["generated_by"] == "fake" and body["language"] == "hi"
    assert body["school_name"] == "सरस्वती विद्यालय"


@pytest.mark.parametrize(
    ("writer", "reason"),
    [
        (None, "ai_unavailable"),
        (FakeNoticeWriter(error=NoticeWriterError("throttled")), "ai_unavailable"),
        (FakeNoticeWriter(error=RuntimeError("boom")), "ai_unavailable"),
        (FakeNoticeWriter(error=TimeoutError("read timeout")), "ai_timeout"),
    ],
)
def test_writer_failures_fall_back_to_the_template(writer, reason):
    body = make(writer).create(LAT, LON, "en")
    assert (body["generated_by"], body["model"], body["fallback_reason"]) == ("template", None, reason)
    assert body["notice"]["title"].startswith("Air quality update for parents")


def test_slow_writer_times_out_and_falls_back():
    writer = FakeNoticeWriter(ai_rewrite, delay_s=0.5)
    body = make(writer, ai_timeout_s=0.05).create(LAT, LON, "en")
    assert (body["generated_by"], body["fallback_reason"]) == ("template", "ai_timeout")


def test_guard_failure_falls_back_to_the_template():
    def wrong_number(facts):
        notice = render_template(facts)
        return dataclasses.replace(notice, body=notice.body.replace(f"AQI {facts.aqi_display}", "AQI 180"))

    body = make(FakeNoticeWriter(wrong_number)).create(LAT, LON, "en")
    assert (body["generated_by"], body["fallback_reason"]) == ("template", "validation_failed")
    assert "AQI 249" in body["notice"]["body"]


def test_non_notice_output_is_a_validation_failure():
    body = make(FakeNoticeWriter(lambda facts: {"title": "x"})).create(LAT, LON, "en")
    assert body["fallback_reason"] == "validation_failed"


def test_kill_switch_never_calls_the_writer():
    writer = FakeNoticeWriter(ai_rewrite)
    body = make(writer, ai_enabled=False).create(LAT, LON, "hi")
    assert (body["generated_by"], body["fallback_reason"]) == ("template", "ai_disabled")
    assert writer.calls == []


def test_response_body_contract():
    body = make().create(LAT, LON, "en", "Test School")
    assert body["data_type"] == "forecast_model"
    assert body["decision"] == {
        "action": "move_strenuous_activities_indoors",
        "severity": "high",
        "headline": "Move assembly, PE and sports indoors",
        "policy_version": "saanssafe-school-v1",
    }
    assert body["valid_for_hour"] == "2026-10-08T06:00:00Z"
    assert body["freshness"] == {"status": "fresh", "age_minutes": 0, "warning": None}
    assert body["grounding"]["aqi_display"] == "249"
    assert body["footer"]["health_statement"] == body["grounding"]["health_statement"]
    assert body["disclaimer"].endswith("This is not medical advice.")
    assert body["cache"] == "miss"
    assert "CPCB AQI" not in json.dumps(body, ensure_ascii=False)


def test_notice_cache_hit_skips_the_writer():
    writer = FakeNoticeWriter(ai_rewrite)
    cache = FakeNoticeCache()
    service = make(writer, cache=cache)
    first = service.create(LAT, LON, "en")
    second = service.create(LAT, LON, "en")
    assert (first["cache"], second["cache"]) == ("miss", "hit")
    assert second["notice"] == first["notice"]
    assert len(writer.calls) == 1
    assert len(cache.puts) == 1
    assert cache.puts[0].startswith("notice#28.61#77.23#2026-10-08T06:00:00Z#en#ai#")


def test_cache_miss_when_data_changes_within_the_same_hour():
    cache = FakeNoticeCache()
    first = make(cache=cache, ai_enabled=False).create(LAT, LON, "en")
    # A series refetch inside the same valid hour returns different values: never reuse.
    refetched = make(series=full_series("Moderate"), cache=cache, ai_enabled=False).create(LAT, LON, "en")
    assert (first["grounding"]["aqi_display"], refetched["grounding"]["aqi_display"]) == ("249", "150")
    assert refetched["cache"] == "miss" and "AQI 150" in refetched["notice"]["body"]


def test_cache_hit_reports_current_freshness():
    cache = FakeNoticeCache()
    make(cache=cache, ai_enabled=False).create(LAT, LON, "en")
    later = NOW + timedelta(minutes=20)  # same hour, cached series still fresh
    series_cache = FakeCache({SERIES_KEY: CachedSeries(full_series("Poor"), NOW)})
    aqi = aqi_service(cache=series_cache, clock=lambda: later)
    hit = make(aqi=aqi, cache=cache, ai_enabled=False, clock=lambda: later).create(LAT, LON, "en")
    assert hit["cache"] == "hit" and hit["freshness"]["age_minutes"] == 20


def test_cache_entries_expire_after_an_hour():
    cache = FakeNoticeCache()
    service = make(FakeNoticeWriter(ai_rewrite), cache=cache)
    service.create(LAT, LON, "en")
    key = cache.puts[0]
    cache.entries[key] = CachedNotice(cache.entries[key].body, NOW - timedelta(minutes=61))
    assert service.create(LAT, LON, "en")["cache"] == "miss"


def test_cache_keys_separate_language_school_and_mode():
    cache = FakeNoticeCache()
    service = make(cache=cache, ai_enabled=False)
    service.create(LAT, LON, "en")
    service.create(LAT, LON, "hi")
    service.create(LAT, LON, "en", "School A")
    assert service.create(LAT, LON, "en", "School A")["cache"] == "hit"
    service.create(LAT, LON, "en", "school a")  # different spelling -> its own notice
    assert len(cache.puts) == 4
    assert all(key.startswith("notice#") and "chool" not in key for key in cache.puts)


def test_transient_ai_failures_and_stale_data_are_not_cached():
    cache = FakeNoticeCache()
    make(FakeNoticeWriter(error=RuntimeError("down")), cache=cache).create(LAT, LON, "en")
    assert cache.puts == []

    series_cache = FakeCache({SERIES_KEY: CachedSeries(full_series(), NOW - timedelta(minutes=95))})
    stale = aqi_service(provider=FakeProvider(error=ProviderUnavailableError("down")), cache=series_cache)
    body = make(aqi=stale, cache=cache, ai_enabled=False).create(LAT, LON, "en")
    assert body["freshness"]["status"] == "stale" and "95 minutes" in body["notice"]["body"]
    assert cache.puts == []


def test_cache_failures_never_block_a_notice():
    cache = FakeNoticeCache(get_error=CacheError("down"), put_error=CacheError("down"))
    body = make(cache=cache).create(LAT, LON, "en")
    assert body["cache"] == "bypassed" and body["notice"]["body"]


def test_series_cache_is_untouched_by_notices():
    series_cache = FakeCache()
    make(aqi=aqi_service(cache=series_cache), ai_enabled=False).create(LAT, LON, "en")
    assert {key for key, _ in series_cache.puts} == {SERIES_KEY}


def test_data_errors_propagate():
    failing = aqi_service(provider=FakeProvider(error=ProviderRequestError("400")))
    with pytest.raises(ProviderRequestError):
        make(aqi=failing).create(LAT, LON, "en")


def test_changing_air_reaches_the_notice():
    body = make(series=changing_series("Poor", "Good"), ai_enabled=False).create(LAT, LON, "en")
    assert body["grounding"]["next_change"]["action"] == "reduce_outdoor_exertion"
    assert "The next expected change is from" in body["notice"]["body"]


def test_rejects_non_positive_timeout():
    with pytest.raises(ValueError):
        make(ai_timeout_s=0)


# --- DynamoNoticeCache ----------------------------------------------------------------------

def test_dynamo_notice_cache_round_trip():
    client = FakeDynamoClient()
    cache = DynamoNoticeCache(client, "tbl")
    created = datetime(2026, 10, 8, 6, 0, tzinfo=UTC)
    cache.put("notice#k", CachedNotice({"language": "hi", "text": "सूचना"}, created))
    item = client.item
    assert item["pk"] == {"S": "notice#k"}
    assert int(item["expires_at"]["N"]) - int(item["created_at"]["N"]) == 3600
    assert item["schema_version"] == {"N": str(NOTICE_SCHEMA_VERSION)}
    assert cache.get("notice#k") == CachedNotice({"language": "hi", "text": "सूचना"}, created)


def test_dynamo_notice_cache_errors():
    assert DynamoNoticeCache(FakeDynamoClient(), "tbl").get("notice#missing") is None
    with pytest.raises(CacheError):
        DynamoNoticeCache(FakeDynamoClient(error=RuntimeError("x")), "tbl").get("k")
    with pytest.raises(CacheError):
        DynamoNoticeCache(FakeDynamoClient(error=RuntimeError("x")), "tbl").put("k", CachedNotice({}, NOW))
    corrupt = {"pk": {"S": "k"}, "schema_version": {"N": "1"}, "created_at": {"N": "1"}, "payload": {"S": "[]"}}
    with pytest.raises(CacheError):
        DynamoNoticeCache(FakeDynamoClient(corrupt), "tbl").get("k")
    old = {**corrupt, "schema_version": {"N": "0"}}
    assert DynamoNoticeCache(FakeDynamoClient(old), "tbl").get("k") is None
    with pytest.raises(ValueError):
        DynamoNoticeCache(FakeDynamoClient(), "")


def test_notice_key_cannot_collide_with_series_key():
    aqi, forecast = bodies()
    facts = build_notice_facts(aqi, forecast, "en")
    key = notice_cache_key(aqi, facts, "template")
    assert key.startswith("notice#28.61#77.23#2026-10-08T06:00:00Z#en#template#")
    assert key != SERIES_KEY and not key.startswith("open-meteo#")


def test_fingerprint_ignores_only_the_data_age():
    aqi, forecast = bodies()
    facts = build_notice_facts(aqi, forecast, "en")
    older = dataclasses.replace(facts, age_minutes=45)
    assert facts_fingerprint(older) == facts_fingerprint(facts)
    assert facts_fingerprint(dataclasses.replace(facts, aqi_display="250")) != facts_fingerprint(facts)
    assert facts_fingerprint(dataclasses.replace(facts, freshness_status="stale")) != facts_fingerprint(facts)
