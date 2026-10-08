import json
from datetime import date, timedelta

import pytest
from notice_support import LAT, LON, SERIES_KEY, aqi_service, bodies, changing_series, full_series
from support import NOW, FakeCache, FakeProvider

from saanssafe import api
from saanssafe.cache import CachedSeries
from saanssafe.notice_facts import NoticeFactsError, build_notice_facts, moment
from saanssafe.providers.base import ProviderUnavailableError


def test_facts_copy_aqi_values_exactly():
    aqi, forecast = bodies(full_series("Poor"))
    facts = build_notice_facts(aqi, forecast, "en")
    decision = aqi["decision"]
    assert facts.aqi_display == aqi["aqi"]["display"]
    assert facts.category == aqi["aqi"]["category"] == "Poor"
    assert facts.health_statement == decision["cpcb_health_statement"]["text"]
    assert facts.health_statement_source == decision["cpcb_health_statement"]["source"]
    assert (facts.action, facts.severity, facts.headline) == (
        decision["action"], decision["severity"], decision["headline"],
    )
    assert dict(facts.activities) == decision["activities"]
    assert list(facts.recommendations) == decision["recommendations"]
    assert facts.policy_version == decision["policy"]["version"]
    assert facts.dominant_pollutant_name == decision["dominant_pollutant"]["name"]
    assert (facts.data_type, facts.disclaimer) == (aqi["data_type"], aqi["disclaimer"])


def test_valid_hour_is_presented_in_ist():
    aqi, forecast = bodies()
    facts = build_notice_facts(aqi, forecast, "en")
    assert facts.valid_for.utc == aqi["valid_for_hour"] == "2026-10-08T06:00:00Z"
    assert (facts.valid_for.ist_date, facts.valid_for.ist_time) == (date(2026, 10, 8), "11:30")


def test_beyond_scale_keeps_401_plus():
    facts = build_notice_facts(*bodies(full_series("Severe")), "en")
    assert (facts.aqi_display, facts.beyond_scale, facts.category) == ("401+", True, "Severe")


def test_forecast_summary_is_copied_from_forecast_body():
    aqi, forecast = bodies(changing_series("Poor", "Good"))
    facts = build_notice_facts(aqi, forecast, "en")
    summary = forecast["summary"]
    assert facts.next_change.at.utc == summary["next_change"]["valid_for_hour"]
    assert facts.next_change.headline == summary["next_change"]["decision"]["headline"]
    assert facts.next_change.action != facts.action
    best = summary["best_school_period"]
    assert (facts.best_window.label, facts.best_window.start.utc) == (best["label"], best["start"])
    assert facts.best_window.worst.aqi_display == best["worst"]["aqi"]["display"]
    assert facts.worst.aqi_display == summary["worst"]["aqi"]["display"]
    assert facts.forecast_complete and facts.forecast_hours == 73


def test_null_best_period_and_partial_forecast():
    facts = build_notice_facts(*bodies(full_series("Poor", hours=34)), "en")
    assert facts.best_window is None and facts.next_change is None
    assert not facts.forecast_complete
    assert (facts.forecast_hours, facts.forecast_requested_hours) == (4, 73)


def test_hours_without_data_become_none():
    aqi, forecast = bodies(changing_series("Poor", "Good"))
    forecast["summary"]["next_change"] = {**forecast["summary"]["next_change"], "aqi": None, "decision": None}
    assert build_notice_facts(aqi, forecast, "en").next_change is None


def test_fresh_and_stale_freshness_are_copied():
    fresh = build_notice_facts(*bodies(), "en")
    assert (fresh.freshness_status, fresh.stale, fresh.freshness_warning) == ("fresh", False, None)

    cache = FakeCache({SERIES_KEY: CachedSeries(full_series(), NOW - timedelta(minutes=95))})
    svc = aqi_service(provider=FakeProvider(error=ProviderUnavailableError("down")), cache=cache)
    stale = build_notice_facts(*bodies(service=svc), "hi")
    assert stale.stale and stale.age_minutes == 95
    assert "95 minutes" in stale.freshness_warning


def test_school_name_whitespace_is_collapsed():
    aqi, forecast = bodies()
    assert build_notice_facts(aqi, forecast, "en", "  St.  Mary's \t School ").school_name == "St. Mary's School"
    assert build_notice_facts(aqi, forecast, "en", "   ").school_name is None


def test_rejects_unknown_language_and_incomplete_bodies():
    aqi, forecast = bodies()
    with pytest.raises(ValueError):
        build_notice_facts(aqi, forecast, "fr")
    with pytest.raises(NoticeFactsError):
        build_notice_facts({k: v for k, v in aqi.items() if k != "decision"}, forecast, "en")
    with pytest.raises(NoticeFactsError):
        moment("2026-10-08 06:00")


def test_grounding_is_json_and_never_says_cpcb_aqi():
    facts = build_notice_facts(*bodies(changing_series()), "hi", "Test School")
    text = json.dumps(facts.grounding(), ensure_ascii=False)
    assert json.loads(text)["valid_for"]["ist_date"] == "2026-10-08"
    assert "CPCB AQI" not in text


def test_facts_use_the_same_values_as_get_aqi():
    svc = aqi_service()
    response = api.handle(
        {"rawPath": "/aqi", "requestContext": {"http": {"method": "GET"}},
         "queryStringParameters": {"lat": str(LAT), "lon": str(LON)}},
        svc,
    )
    served = json.loads(response["body"])
    facts = build_notice_facts(*bodies(service=svc), "en")
    assert facts.aqi_display == served["aqi"]["display"]
    assert facts.action == served["decision"]["action"]
