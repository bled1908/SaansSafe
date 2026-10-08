"""Hard-invariant checks for a ParentNotice written by AI (the template must pass them too).

`validate_notice(notice, facts)` returns every problem it finds; an empty tuple means the
notice may be served. Any problem means the deterministic template is served instead.

Checks (only on the writer's fields; the fixed footer is never AI-written):
  schema    language matches, non-empty fields, length limits, no URLs/markup/control chars
  script    "en": no Devanagari; "hi": mostly Devanagari letters
  aqi       today's AQI display appears exactly ("401+" never loses its "+")
  numbers   every number appears somewhere in the facts (Devanagari digits normalised)
  times     every HH:MM, day+month and weekday matches a time/date in the facts
  category  today's CPCB category appears; no category label absent from the facts
  action    today's school action is expressed through the approved phrase mapping, and
            no conflicting action is expressed unless the forecast facts contain it
  terms     no banned medical, safety-guarantee, station-reading or "CPCB AQI" wording
  basis     says the values are a forecast/model estimate
The English decision headline does not have to be reproduced verbatim.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from saanssafe.notice_facts import HourFact, Moment, NoticeFacts, ParentNotice
from saanssafe.notice_template import (
    CATEGORY_HI,
    MONTHS_EN,
    MONTHS_HI,
    POLLUTANT_HI,
    WEEKDAYS_EN,
    WEEKDAYS_HI,
)

MAX_TITLE = 120
MAX_BODY = 1500
MAX_KEY_POINTS = 6
MAX_KEY_POINT = 240
MAX_SIGN_OFF = 120
MIN_DEVANAGARI_SHARE = 0.6

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_NUKTA = "़"
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Control characters (newline allowed), zero-width space/BOM, and bidi overrides/isolates.
_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f​﻿‪-‮⁦-⁩]")
_MARKUP = re.compile(r"https?://|www\.|<[a-z/!]", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_TIME = re.compile(r"(?<!\d)(\d{1,2})[:.](\d{2})(?!\d)")
_MONTH_ABBR = [m[:3] for m in MONTHS_EN]
_HI_MOVE = r"भवन के अंदर|अंदर (?:ही )?(?:होंगे|होगी|होगा|आयोजित|कराए|कराई|कराया)|भीतर"
_HI_WORD_EDGE = r"[ऀ-ॿ]"

# Approved action mapping: how each SaansSafe action must be expressed (REQUIRED), and the
# unmistakable phrasing (STRONG) of actions that contradict it (CONFLICTS). Patterns run on
# lower-cased, nukta-free text.
REQUIRED = {
    "en": {
        "normal_outdoor_activities": r"\bas (?:normal|usual)\b",
        "outdoor_ok_protect_sensitive_students": r"\bsensitive\b",
        "reduce_outdoor_exertion": r"\breduc\w*|\blighter\b|\bshort(?:er)?\b",
        # "indoors", not "indoor": "an indoor option" alone is the weaker reduce action.
        "move_strenuous_activities_indoors": r"\bindoors\b",
        "suspend_outdoor_activities": r"\bsuspend\w*|\bcancel\w*",
    },
    "hi": {
        "normal_outdoor_activities": r"सामान्य",
        "outdoor_ok_protect_sensitive_students": r"संवेदनशील",
        "reduce_outdoor_exertion": r"कम |छोटी|हल्की",
        # Not bare "अंदर": "अंदर का विकल्प" (an indoor option) is the weaker reduce action.
        "move_strenuous_activities_indoors": _HI_MOVE,
        "suspend_outdoor_activities": r"स्थगित|रद्द",
    },
}
STRONG = {
    "en": {
        "normal_outdoor_activities": r"\bas (?:normal|usual)\b",
        "move_strenuous_activities_indoors": r"\bmov\w*\b[^.\n]*\bindoors\b",
        "suspend_outdoor_activities": r"\bsuspend\w*|\bcancel\w*",
    },
    "hi": {
        "normal_outdoor_activities": r"सामान्य रूप से",
        "move_strenuous_activities_indoors": _HI_MOVE,
        "suspend_outdoor_activities": r"स्थगित|रद्द",
    },
}
# Stating a stricter or looser action than today's changes its meaning, unless the
# forecast facts themselves contain that action (e.g. the next change).
CONFLICTS = {
    "normal_outdoor_activities": ("move_strenuous_activities_indoors", "suspend_outdoor_activities"),
    "outdoor_ok_protect_sensitive_students": (
        "move_strenuous_activities_indoors", "suspend_outdoor_activities",
    ),
    "reduce_outdoor_exertion": ("move_strenuous_activities_indoors", "suspend_outdoor_activities"),
    "move_strenuous_activities_indoors": ("normal_outdoor_activities", "suspend_outdoor_activities"),
    "suspend_outdoor_activities": ("normal_outdoor_activities",),
}

BANNED = {
    "en": (
        r"cpcb\s*aqi", r"\bstations?\b", r"\bmeasured\b", r"\breal[- ]time reading",
        r"medication", r"medicine", r"inhaler", r"prescri", r"\bdoses?\b", r"diagnos",
        r"asthma", r"treatment", r"symptom", r"\bdoctors?\b", r"hospital", r"\bcure",
        r"\bmasks?\b", r"\bn95\b", r"guarantee", r"100\s*%\s*safe",
        r"(?:completely|totally|perfectly) safe", r"risk[- ]free", r"\bno risk\b",
        r"\bharmless\b", r"\bschools? (?:is |are |will be |will remain )?(?:closed|shut)\b",
        r"\bholiday\b", r"\b(?:stay|kept|keep \w+(?: \w+)?) (?:at )?home\b",
    ),
    "hi": (
        r"स्टेशन", r"दवा", r"इनहेलर", r"डॉक्टर", r"डाक्टर", r"अस्पताल", r"इलाज", r"उपचार",
        r"लक्षण", r"अस्थमा", r"दमा", r"मास्क", r"गारंटी", r"पूरी तरह सुरक्षित", r"कोई ख़तरा नहीं",
        r"कोई खतरा नहीं", r"(?:स्कूल|विद्यालय)\S* (?:\S+ )?(?:बंद|छुट्टी|अवकाश)", r"घर पर (?:ही )?रख",
    ),
}
BASIS = {"en": r"\bforecast", "hi": r"पूर्वानुमान"}
CATEGORIES = ("Very Poor", "Satisfactory", "Moderate", "Severe", "Poor", "Good")
_GOOD_GREETING = re.compile(r"\bGood (?:morning|afternoon|evening|day|night)\b")


def _normalise(text: str) -> str:
    return text.translate(_DEVANAGARI_DIGITS).replace(_NUKTA, "")


def _hours(facts: NoticeFacts) -> list[HourFact]:
    window = facts.best_window.worst if facts.best_window else None
    return [h for h in (facts.next_change, facts.worst, window) if h is not None]


def _moments(facts: NoticeFacts) -> Iterator[Moment]:
    yield facts.valid_for
    for hour in _hours(facts):
        yield hour.at
    if facts.best_window:
        yield facts.best_window.start
        yield facts.best_window.end


def _numbers(texts: Iterable[str]) -> set[float]:
    return {float(n) for text in texts for n in _NUMBER.findall(_normalise(text))}


def allowed_numbers(facts: NoticeFacts) -> set[float]:
    """Every number a notice may mention: those that appear in the facts."""
    texts = [
        facts.aqi_display, facts.policy_version, facts.dominant_pollutant_name,
        POLLUTANT_HI.get(facts.dominant_pollutant_code, ""), facts.school_name or "",
        str(facts.age_minutes), str(facts.forecast_hours), str(facts.forecast_requested_hours),
        *(h.aqi_display for h in _hours(facts)),
    ]
    for m in _moments(facts):
        texts += [m.ist_time, str(m.ist_date.day)]
    return _numbers(texts)


# --- Individual checks ----------------------------------------------------------------------

def _schema(notice: ParentNotice, facts: NoticeFacts) -> list[str]:
    problems = []
    if notice.language != facts.language:
        problems.append("language_mismatch")
    if not 1 <= len(notice.key_points) <= MAX_KEY_POINTS:
        problems.append("key_points_count")
    fields = [(notice.title, MAX_TITLE), (notice.body, MAX_BODY), (notice.sign_off, MAX_SIGN_OFF)]
    fields += [(point, MAX_KEY_POINT) for point in notice.key_points]
    for value, limit in fields:
        if not isinstance(value, str) or not value.strip():
            problems.append("empty_field")
        elif len(value) > limit:
            problems.append("too_long")
        elif _CONTROL.search(value) or _MARKUP.search(value):
            problems.append("forbidden_characters")
    return problems


def _script(text: str, facts: NoticeFacts) -> list[str]:
    devanagari = len(_DEVANAGARI.findall(text))
    if facts.language == "en":
        return ["wrong_script"] if devanagari else []
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    share = devanagari / (devanagari + latin) if devanagari + latin else 0.0
    return [] if share >= MIN_DEVANAGARI_SHARE else ["wrong_script"]


def _aqi(text: str, facts: NoticeFacts) -> list[str]:
    problems = []
    if not re.search(rf"(?<![\d.]){re.escape(facts.aqi_display)}(?!\d)", text):
        problems.append("aqi_display_missing")
    displays = [facts.aqi_display, *(h.aqi_display for h in _hours(facts))]
    for value in {d.rstrip("+") for d in displays if d.endswith("+")}:
        if re.search(rf"(?<![\d.]){value}(?![\d+])", text):
            problems.append("beyond_scale_changed")
    return problems


def _numbers_check(text: str, facts: NoticeFacts) -> list[str]:
    return [] if _numbers([text]) <= allowed_numbers(facts) else ["unsupported_number"]


def _dates_found(text: str) -> set[tuple[int, int]]:
    months = "|".join(_MONTH_ABBR)
    found = {
        (int(d), _MONTH_ABBR.index(m) + 1)
        for d, m in re.findall(rf"\b(\d{{1,2}})\s+({months})[a-z]*\b", text)
    }
    found |= {
        (int(d), _MONTH_ABBR.index(m) + 1)
        for m, d in re.findall(rf"\b({months})[a-z]*\.?\s+(\d{{1,2}})\b", text)
    }
    hi_months = [_normalise(m) for m in MONTHS_HI]
    found |= {
        (int(d), hi_months.index(m) + 1)
        for d, m in re.findall(rf"(\d{{1,2}})\s*({'|'.join(hi_months)})", text)
    }
    return found


def _times(text: str, facts: NoticeFacts) -> list[str]:
    moments = list(_moments(facts))
    problems = []
    times = {m.ist_time for m in moments}
    if any(f"{int(h):02d}:{mm}" not in times for h, mm in _TIME.findall(text)):
        problems.append("time_changed")
    if not _dates_found(text) <= {(m.ist_date.day, m.ist_date.month) for m in moments}:
        problems.append("date_changed")
    named = {i for i, w in enumerate(WEEKDAYS_EN) if re.search(rf"\b{w[:3]}(?:{w[3:]})?\b", text)}
    named |= {i for i, w in enumerate(WEEKDAYS_HI) if _normalise(w) in text}
    if not named <= {m.ist_date.weekday() for m in moments}:
        problems.append("weekday_changed")
    if not _relative_days(text) <= {(m.ist_date - facts.valid_for.ist_date).days for m in moments}:
        problems.append("relative_day_changed")
    return problems


def _relative_days(text: str) -> set[int]:
    """Day offsets named by "tomorrow"-style words (today/tonight always match the facts)."""
    offsets = set()
    if re.search(r"\bday after tomorrow\b", text, re.IGNORECASE) or "परसों" in text:
        offsets.add(2)
    without = re.sub(r"\bday after tomorrow\b", " ", text, flags=re.IGNORECASE)
    if re.search(r"\btomorrow\b", without, re.IGNORECASE) or re.search(
        rf"(?<!{_HI_WORD_EDGE})कल(?!{_HI_WORD_EDGE})", text
    ):
        offsets.add(1)
    return offsets


# Hindi category words that are not also everyday words ("अच्छा", "मध्यम" and "गंभीर" are,
# so those count only when quoted, as the template quotes every category).
_DISTINCT_HI = frozenset({"Very Poor", "Poor", "Satisfactory"})


def _categories(text: str, facts: NoticeFacts) -> list[str]:
    allowed = {facts.category, *(h.category for h in _hours(facts))}
    found, scrubbed = set(), _GOOD_GREETING.sub(" ", text)
    for label in CATEGORIES:  # longest first, so "Very Poor" is not also read as "Poor"
        if re.search(rf"\b{label}\b", scrubbed):
            found.add(label)
            scrubbed = re.sub(rf"\b{label}\b", " ", scrubbed)
    present = facts.category in found
    if facts.language == "hi":
        hindi = {label: _normalise(name) for label, name in CATEGORY_HI.items()}
        found_hi = set()
        for label in sorted(hindi, key=lambda k: -len(hindi[k])):  # "बहुत खराब" before "खराब"
            if hindi[label] in scrubbed:
                found_hi.add(label)
                scrubbed = scrubbed.replace(hindi[label], " ")
        quoted = {k for k, v in hindi.items() if f"“{v}”" in text}
        present = present or facts.category in found_hi
        found |= (found_hi & _DISTINCT_HI) | quoted
    problems = [] if present else ["category_missing"]
    if found - allowed:
        problems.append("category_changed")
    return problems


def _action(text: str, facts: NoticeFacts) -> list[str]:
    lang, lowered = facts.language, text.lower()
    required = REQUIRED[lang].get(facts.action)
    if required is None:
        return ["unknown_action"]
    problems = [] if re.search(required, lowered) else ["action_missing"]
    in_facts = {facts.action, *(h.action for h in _hours(facts))}
    for other in CONFLICTS[facts.action]:
        if other not in in_facts and re.search(STRONG[lang][other], lowered):
            problems.append("action_conflict")
    return problems


def _terms(text: str, facts: NoticeFacts) -> list[str]:
    lowered = text.lower()
    patterns = BANNED["en"] + (BANNED["hi"] if facts.language == "hi" else ())
    problems = ["banned_term"] if any(re.search(_normalise(p), lowered) for p in patterns) else []
    if not re.search(_normalise(BASIS[facts.language]), lowered):
        problems.append("forecast_basis_missing")
    return problems


def validate_notice(notice: ParentNotice, facts: NoticeFacts) -> tuple[str, ...]:
    """All guard problems for this notice (empty when it may be served)."""
    problems = _schema(notice, facts)
    if problems:
        return tuple(dict.fromkeys(problems))
    text = _normalise("\n".join([notice.title, notice.body, *notice.key_points, notice.sign_off]))
    if facts.school_name:  # a name is data, not wording: "Good Shepherd" is not a category
        text = text.replace(_normalise(facts.school_name), " ")
    for check in (_script, _aqi, _numbers_check, _times, _categories, _action, _terms):
        problems += check(text, facts)
    return tuple(dict.fromkeys(problems))
