import dataclasses
import re
from datetime import timedelta

import pytest
from notice_support import (
    ACTION_FOR,
    LEVELS,
    SERIES_KEY,
    aqi_service,
    bodies,
    changing_series,
    facts_for,
    full_series,
)
from support import NOW, FakeCache, FakeProvider

from saanssafe.cache import CachedSeries
from saanssafe.decision import SchoolAction
from saanssafe.notice_facts import build_notice_facts
from saanssafe.notice_guard import validate_notice
from saanssafe.notice_template import (
    ACTION_SENTENCES,
    ACTION_SHORT_HI,
    ACTIONS,
    CATEGORY_HI,
    NoticeTemplateError,
    compose_share_text,
    render_footer,
    render_template,
)
from saanssafe.providers.base import ProviderUnavailableError

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def test_every_policy_action_has_wording_in_both_languages():
    assert set(ACTIONS) == {a.value for a in SchoolAction}
    for language in ("en", "hi"):
        assert set(ACTION_SENTENCES[language]) == set(ACTIONS)
    assert set(ACTION_SHORT_HI) == set(ACTIONS)


@pytest.mark.parametrize("language", ["en", "hi"])
@pytest.mark.parametrize("level", list(LEVELS))
def test_template_is_complete_and_passes_its_own_guard(level, language):
    facts = facts_for(level, language)
    assert facts.action == ACTION_FOR[level]
    notice = render_template(facts)
    footer = render_footer(facts)
    assert validate_notice(notice, facts) == ()
    assert notice.language == language
    assert f"AQI {facts.aqi_display}" in notice.body
    assert len(notice.key_points) == 3
    assert footer.health_statement == facts.health_statement  # verbatim CPCB statement
    share = compose_share_text(notice, footer)
    assert facts.health_statement in share and footer.disclaimer in share
    assert "CPCB AQI" not in share


@pytest.mark.parametrize("language", ["en", "hi"])
@pytest.mark.parametrize("before", list(LEVELS))
@pytest.mark.parametrize("after", ["Good", "Moderate", "Poor", "Severe"])
def test_template_passes_the_guard_whenever_air_changes(before, after, language):
    """Next-change and best-window sentences name other actions; the guard must allow them."""
    facts = facts_for(language=language, series=changing_series(before, after))
    assert validate_notice(render_template(facts), facts) == ()


def test_protect_sensitive_wording_follows_the_policy():
    body = render_template(facts_for("Satisfactory", "en")).body
    assert "reduce prolonged or strenuous outdoor exertion" in body and "avoid" not in body


def test_english_wording_names_category_action_and_disclaimers():
    facts = facts_for("Poor", "en")
    notice, footer = render_template(facts), render_footer(facts)
    assert "forecast/model" in notice.body and "“Poor” category" in notice.body
    assert "hold assembly indoors and move PE and sports indoors" in notice.body
    assert notice.key_points == (
        "Morning assembly: indoors",
        "PE and sports: indoors",
        "Recess and breaks: shorter outdoors, with an indoor option",
    )
    assert "Not a reading from a CPCB monitoring station." in footer.disclaimer
    assert "not a CPCB rule" in footer.disclaimer
    assert footer.disclaimer.endswith("This is not medical advice.")
    assert notice.sign_off == "— School administration"


def test_hindi_wording_is_devanagari_with_hindi_category():
    facts = facts_for("Poor", "hi")
    notice, footer = render_template(facts), render_footer(facts)
    assert DEVANAGARI.search(notice.title)
    assert f"“{CATEGORY_HI['Poor']}” (Poor)" in notice.body
    assert "पूर्वानुमान/मॉडल अनुमान" in notice.body
    assert "भवन के अंदर" in notice.body
    assert "यह चिकित्सा सलाह नहीं है।" in footer.disclaimer
    assert "मूल अंग्रेज़ी में" in footer.health_label
    assert notice.sign_off == "— विद्यालय प्रशासन"


@pytest.mark.parametrize("language", ["en", "hi"])
def test_severe_shows_401_plus_and_never_a_bare_401(language):
    facts = facts_for("Severe", language)
    text = compose_share_text(render_template(facts), render_footer(facts))
    assert "AQI 401+" in text
    assert not re.search(r"401(?!\+)", text)
    assert ("top of the published scale" in text) if language == "en" else ("ऊपरी सीमा" in text)


def test_suspend_wording_for_very_poor():
    notice = render_template(facts_for("Very Poor", "en"))
    assert "suspending all outdoor activities" in notice.body
    assert "401" not in notice.body


@pytest.mark.parametrize("language", ["en", "hi"])
def test_stale_data_is_flagged_with_its_age(language):
    cache = FakeCache({SERIES_KEY: CachedSeries(full_series(), NOW - timedelta(minutes=95))})
    svc = aqi_service(provider=FakeProvider(error=ProviderUnavailableError("down")), cache=cache)
    facts = build_notice_facts(*bodies(service=svc), language)
    notice = render_template(facts)
    assert "95" in notice.body
    assert validate_notice(notice, facts) == ()


def test_outlook_sentences_with_next_change_and_best_window():
    facts = facts_for(series=changing_series("Poor", "Good"))
    body = render_template(facts).body
    assert f"Best school window in the forecast: {facts.best_window.label}" in body
    assert f"“{facts.next_change.headline}”" in body  # API headline quoted verbatim
    hindi = render_template(facts_for(language="hi", series=changing_series("Poor", "Good"))).body
    assert ACTION_SHORT_HI[facts.next_change.action] in hindi


@pytest.mark.parametrize("language", ["en", "hi"])
def test_null_best_window_and_partial_forecast_wording(language):
    facts = facts_for(language=language, series=full_series("Poor", hours=34))
    notice = render_template(facts)
    if language == "en":
        assert "no full weekday school period" in notice.body
        assert "covers 4 of 73 hours" in notice.body
        assert "No change to this school action is expected in the available forecast." in notice.body
    else:
        assert "कार्यदिवस" in notice.body and "73 में से 4" in notice.body
    assert validate_notice(notice, facts) == ()


def test_school_name_is_used_in_opening_and_sign_off():
    notice = render_template(facts_for("Moderate", "en", "St. Mary's School"))
    assert "near St. Mary's School" in notice.body
    assert notice.sign_off == "— St. Mary's School"
    hindi = render_template(facts_for("Moderate", "hi", "सरस्वती विद्यालय"))
    assert "सरस्वती विद्यालय के आसपास" in hindi.body


def test_unknown_values_fail_loudly():
    facts = facts_for()
    with pytest.raises(NoticeTemplateError):
        render_template(dataclasses.replace(facts, action="close_school"))
    with pytest.raises(NoticeTemplateError):
        render_template(dataclasses.replace(facts, activities=(("lunch", "allowed"),)))
