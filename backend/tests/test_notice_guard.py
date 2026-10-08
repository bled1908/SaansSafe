import dataclasses

import pytest
from notice_support import facts_for

from saanssafe.notice_facts import HourFact, ParentNotice
from saanssafe.notice_guard import MAX_BODY, allowed_numbers, validate_notice
from saanssafe.notice_template import render_template

EN = facts_for("Poor", "en")  # AQI 249, Thu 8 Oct, 11:30 IST, move strenuous activities indoors
HI = facts_for("Poor", "hi")

AI_EN = ParentNotice(
    "en",
    "Air update for parents, Thu 8 Oct",
    "Dear parents, our forecast/model estimate shows AQI 249 (Poor) near the school at "
    "11:30 IST. PE, sports and assembly will be held indoors today, and outdoor recess "
    "will be short.",
    ("Assembly: indoors", "PE and sports: indoors", "Recess: short, with an indoor option"),
    "— The Principal",
)
AI_HI = ParentNotice(
    "hi",
    "अभिभावकों के लिए सूचना",
    "प्रिय अभिभावकगण, आज ११:३० बजे का पूर्वानुमान/मॉडल अनुमान AQI २४९ है, जो “ख़राब” श्रेणी है। "
    "आज प्रार्थना सभा, पीई और खेलकूद भवन के अंदर होंगे।",
    ("प्रार्थना सभा: भवन के अंदर",),
    "— प्रधानाचार्य",
)


def body(notice, old, new):
    assert old in notice.body
    return dataclasses.replace(notice, body=notice.body.replace(old, new))


def test_paraphrased_ai_notices_pass_without_the_english_headline():
    assert "Move assembly, PE and sports indoors" not in AI_EN.body
    assert validate_notice(AI_EN, EN) == ()
    assert validate_notice(AI_HI, HI) == ()  # Devanagari digits are normalised


def test_allowed_numbers_come_from_the_facts():
    assert {249.0, 11.0, 30.0, 8.0, 10.0, 1.0} <= allowed_numbers(EN)
    assert 75.0 not in allowed_numbers(EN)


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ("AQI 249", "AQI 251", "aqi_display_missing"),
        ("AQI 249 (Poor)", "AQI 249 (Poor), about 75 µg/m³", "unsupported_number"),
        ("11:30", "10:30", "time_changed"),
        ("(Poor)", "(Moderate)", "category_changed"),
        ("(Poor)", "(fine)", "category_missing"),
        ("held indoors", "held in the hall", "action_missing"),
        ("today, and", "today; matches continue as normal, and", "action_conflict"),
        ("forecast/model estimate", "estimate", "forecast_basis_missing"),
        ("near the school", "at the CPCB AQI station", "banned_term"),
        ("will be short.", "will be short. Carry an inhaler.", "banned_term"),
        ("will be short.", "will be short. It is 100% safe.", "banned_term"),
        ("will be short.", "will be short. School will be closed.", "banned_term"),
        ("will be short.", "will be short. Check https://example.com", "forbidden_characters"),
    ],
)
def test_english_violations_are_caught(old, new, problem):
    notice = body(AI_EN, old, new)
    if problem == "action_missing":
        notice = dataclasses.replace(notice, key_points=("Assembly: in the hall",))
    assert problem in validate_notice(notice, EN)


def test_changed_date_and_weekday_are_caught():
    assert "date_changed" in validate_notice(dataclasses.replace(AI_EN, title="Update, 12 Oct"), EN)
    assert "weekday_changed" in validate_notice(dataclasses.replace(AI_EN, title="Update, Mon"), EN)


def test_401_plus_must_keep_its_plus():
    facts = facts_for("Severe", "en")
    notice = render_template(facts)
    assert validate_notice(notice, facts) == ()
    broken = body(notice, "AQI 401+", "AQI 401")
    assert "beyond_scale_changed" in validate_notice(broken, facts)


def test_conflicting_action_is_allowed_when_the_forecast_contains_it():
    later = HourFact(
        EN.valid_for, "40", "Good", "normal_outdoor_activities", "Outdoor activities can go ahead as normal"
    )
    notice = body(AI_EN, "today, and", "today (later, activities can go ahead as normal), and")
    assert "action_conflict" in validate_notice(notice, EN)
    assert "action_conflict" not in validate_notice(notice, dataclasses.replace(EN, next_change=later))


def test_good_greeting_is_not_a_category():
    notice = dataclasses.replace(AI_EN, body="Good morning! " + AI_EN.body)
    assert validate_notice(notice, EN) == ()


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ("AQI २४९", "AQI २५१", "aqi_display_missing"),
        ("११:३०", "१०:३०", "time_changed"),
        ("“ख़राब”", "“मध्यम”", "category_changed"),
        ("भवन के अंदर होंगे", "होंगे", "action_missing"),
        ("होंगे।", "होंगे। डॉक्टर से मिलें।", "banned_term"),
        ("पूर्वानुमान/मॉडल अनुमान", "अनुमान", "forecast_basis_missing"),
    ],
)
def test_hindi_violations_are_caught(old, new, problem):
    notice = body(AI_HI, old, new)
    if problem == "action_missing":
        notice = dataclasses.replace(notice, key_points=("प्रार्थना सभा: हॉल में",))
    assert problem in validate_notice(notice, HI)


def test_script_must_match_the_language():
    english_for_hindi = dataclasses.replace(AI_EN, language="hi")
    assert "wrong_script" in validate_notice(english_for_hindi, HI)
    devanagari_in_english = body(AI_EN, "Dear parents,", "प्रिय अभिभावकगण,")
    assert "wrong_script" in validate_notice(devanagari_in_english, EN)


def test_school_name_script_is_ignored():
    facts = facts_for("Poor", "en", "सरस्वती विद्यालय")
    assert validate_notice(render_template(facts), facts) == ()


def test_weaker_action_wording_is_caught():
    # "An indoor option" alone is the reduce action, not "move indoors".
    weaker = dataclasses.replace(
        body(AI_EN, "PE, sports and assembly will be held indoors today", "Strenuous PE will be reduced today"),
        key_points=("PE: shorter, with an indoor option",),
    )
    assert "action_missing" in validate_notice(weaker, EN)
    hindi = dataclasses.replace(
        body(AI_HI, "भवन के अंदर होंगे", "कम होंगे, अंदर का विकल्प रहेगा"), key_points=("पीई: कम",)
    )
    assert "action_missing" in validate_notice(hindi, HI)


def test_stricter_action_wording_is_caught():
    moderate = facts_for("Moderate", "en")
    notice = render_template(moderate)
    assert "action_conflict" in validate_notice(body(notice, "today, with", "today; we will move PE indoors, with"), moderate)
    assert "action_conflict" in validate_notice(body(AI_EN, "today, and", "today; all outdoor activity is suspended, and"), EN)


def test_hindi_category_relabelled_is_caught():
    relabelled = body(AI_HI, "“ख़राब”", "बहुत ख़राब")
    assert {"category_missing", "category_changed"} <= set(validate_notice(relabelled, HI))


def test_relative_days_must_exist_in_the_facts():
    assert "relative_day_changed" in validate_notice(body(AI_EN, "today, and", "today and tomorrow, and"), EN)
    assert "relative_day_changed" in validate_notice(body(AI_HI, "आज प्रार्थना", "कल प्रार्थना"), HI)
    tomorrow = dataclasses.replace(EN.valid_for, ist_date=EN.valid_for.ist_date.replace(day=9))
    later = HourFact(tomorrow, "249", "Poor", EN.action, EN.headline)
    facts = dataclasses.replace(EN, worst=later)
    assert "relative_day_changed" not in validate_notice(body(AI_EN, "today, and", "today and tomorrow, and"), facts)
    assert validate_notice(AI_HI, HI) == ()  # "विकल्प" etc. never read as "कल"


@pytest.mark.parametrize("name", ["Good Shepherd School", "Station Road School", "Holiday Public School 2"])
def test_school_name_is_data_not_wording(name):
    facts = facts_for("Poor", "en", name)
    assert validate_notice(render_template(facts), facts) == ()


def test_everyday_hindi_for_recess_is_allowed_but_closures_and_staying_home_are_not():
    recess = dataclasses.replace(AI_HI, key_points=AI_HI.key_points + ("आधी छुट्टी: छोटी रहेगी",))
    assert validate_notice(recess, HI) == ()
    assert "banned_term" in validate_notice(body(AI_HI, "होंगे।", "होंगे। विद्यालय में छुट्टी रहेगी।"), HI)
    assert "banned_term" in validate_notice(body(AI_HI, "होंगे।", "होंगे। बच्चों को घर पर ही रखें।"), HI)
    assert "banned_term" in validate_notice(body(AI_EN, "will be short.", "will be short. Keep your child at home."), EN)


def test_invisible_and_bidi_characters_are_rejected():
    for char in ("‮", "⁦", "​", "﻿"):
        assert "forbidden_characters" in validate_notice(dataclasses.replace(AI_EN, title=AI_EN.title + char), EN)


def test_schema_limits():
    assert "language_mismatch" in validate_notice(AI_HI, EN)
    assert "too_long" in validate_notice(dataclasses.replace(AI_EN, body="x" * (MAX_BODY + 1)), EN)
    assert "key_points_count" in validate_notice(dataclasses.replace(AI_EN, key_points=()), EN)
    assert "empty_field" in validate_notice(dataclasses.replace(AI_EN, title="  "), EN)
    assert "forbidden_characters" in validate_notice(dataclasses.replace(AI_EN, sign_off="<b>x</b>"), EN)
