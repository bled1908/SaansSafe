"""Deterministic Parent Notice in English or Hindi (Devanagari), from NoticeFacts only.

This is the authoritative notice: it is served whenever AI is disabled, unavailable,
slow, or produces text that fails the guard. Every value comes from the facts; the
wording per school action is fixed here. The footer (verbatim CPCB health statement,
forecast/model disclaimer, policy note, not-medical-advice line) is always attached,
whoever wrote the notice.

The Hindi wording is SaansSafe's own and should be reviewed by a native speaker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from saanssafe.notice_facts import HourFact, NoticeFacts, ParentNotice, WindowFact

ACTIONS = (
    "normal_outdoor_activities",
    "outdoor_ok_protect_sensitive_students",
    "reduce_outdoor_exertion",
    "move_strenuous_activities_indoors",
    "suspend_outdoor_activities",
)

CATEGORY_HI = {
    "Good": "अच्छा",
    "Satisfactory": "संतोषजनक",
    "Moderate": "मध्यम",
    "Poor": "ख़राब",
    "Very Poor": "बहुत ख़राब",
    "Severe": "गंभीर",
}

WEEKDAYS_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEEKDAYS_HI = ("सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार")
MONTHS_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
MONTHS_HI = (
    "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून",
    "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
)
PART_HI = {"morning": "सुबह", "afternoon": "दोपहर", "night": "रात"}

ACTIVITY_LABELS = {
    "en": {
        "morning_assembly": "Morning assembly",
        "pe_and_sports": "PE and sports",
        "recess_and_breaks": "Recess and breaks",
    },
    "hi": {
        "morning_assembly": "सुबह की प्रार्थना सभा",
        "pe_and_sports": "पीई और खेलकूद",
        "recess_and_breaks": "मध्यांतर और ब्रेक",
    },
}
GUIDANCE_LABELS = {
    "en": {
        "allowed": "outdoors",
        "limited": "shorter outdoors, with an indoor option",
        "move_indoors": "indoors",
    },
    "hi": {
        "allowed": "बाहर",
        "limited": "बाहर कम समय के लिए, अंदर का विकल्प भी",
        "move_indoors": "भवन के अंदर",
    },
}

# Today's action, one fixed sentence per SaansSafe policy action.
ACTION_SENTENCES = {
    "en": {
        "normal_outdoor_activities":
            "outdoor assembly, PE, sports and recess will take place as normal today.",
        "outdoor_ok_protect_sensitive_students":
            "outdoor activities can go ahead today. Students who are sensitive to air "
            "pollution will be encouraged to reduce prolonged or strenuous outdoor exertion.",
        "reduce_outdoor_exertion":
            "we will keep outdoor assembly short and reduce strenuous outdoor PE and sports "
            "today, with an indoor option for students who are sensitive to air pollution.",
        "move_strenuous_activities_indoors":
            "we will hold assembly indoors and move PE and sports indoors today. Outdoor "
            "recess will be kept short, with an indoor option.",
        "suspend_outdoor_activities":
            "we are suspending all outdoor activities today, including assembly, PE, sports "
            "and recess. Students will have indoor alternatives.",
    },
    "hi": {
        "normal_outdoor_activities":
            "आज प्रार्थना सभा, पीई, खेलकूद और मध्यांतर सामान्य रूप से बाहर होंगे।",
        "outdoor_ok_protect_sensitive_students":
            "आज बाहरी गतिविधियाँ जारी रहेंगी। वायु प्रदूषण के प्रति संवेदनशील विद्यार्थियों को "
            "लंबे समय तक या अधिक मेहनत वाली बाहरी गतिविधियाँ कम करने के लिए कहा जाएगा।",
        "reduce_outdoor_exertion":
            "आज बाहर की प्रार्थना सभा छोटी रखी जाएगी और बाहर अधिक मेहनत वाली पीई व खेलकूद "
            "गतिविधियाँ कम की जाएँगी। वायु प्रदूषण के प्रति संवेदनशील विद्यार्थियों को अंदर का "
            "विकल्प मिलेगा।",
        "move_strenuous_activities_indoors":
            "आज प्रार्थना सभा, पीई और खेलकूद भवन के अंदर होंगे। बाहर का मध्यांतर छोटा रखा "
            "जाएगा और अंदर का विकल्प भी रहेगा।",
        "suspend_outdoor_activities":
            "आज प्रार्थना सभा, पीई, खेलकूद और मध्यांतर सहित सभी बाहरी गतिविधियाँ स्थगित "
            "रहेंगी। विद्यार्थियों के लिए अंदर की वैकल्पिक व्यवस्था रहेगी।",
    },
}

# Short form of a later hour's action. English quotes the API headline verbatim.
ACTION_SHORT_HI = {
    "normal_outdoor_activities": "बाहरी गतिविधियाँ सामान्य रूप से हो सकती हैं",
    "outdoor_ok_protect_sensitive_students":
        "बाहरी गतिविधियाँ जारी रह सकती हैं, संवेदनशील विद्यार्थियों का ध्यान रखें",
    "reduce_outdoor_exertion": "बाहर की अधिक मेहनत वाली गतिविधियाँ कम करें",
    "move_strenuous_activities_indoors": "प्रार्थना सभा, पीई और खेलकूद भवन के अंदर",
    "suspend_outdoor_activities": "सभी बाहरी गतिविधियाँ स्थगित",
}

POLLUTANT_HI = {
    "pm2_5": "PM2.5 (सूक्ष्म कण)",
    "pm10": "PM10 (मोटे कण)",
    "no2": "NO2 (नाइट्रोजन डाइऑक्साइड)",
    "so2": "SO2 (सल्फ़र डाइऑक्साइड)",
    "o3": "O3 (ज़मीनी स्तर की ओज़ोन)",
    "co": "CO (कार्बन मोनोऑक्साइड)",
    "nh3": "NH3 (अमोनिया)",
}


class NoticeTemplateError(ValueError):
    """The facts contain a value the template has no wording for."""


@dataclass(frozen=True)
class NoticeFooter:
    """Fixed text attached to every notice. Never written by AI."""

    health_label: str
    health_statement: str  # verbatim CPCB Table 3.12 text (English)
    health_source: str
    disclaimer: str  # forecast/model + policy + not medical advice

    def as_dict(self) -> dict[str, str]:
        return {
            "health_label": self.health_label,
            "health_statement": self.health_statement,
            "health_source": self.health_source,
            "disclaimer": self.disclaimer,
        }


# --- Formatting -----------------------------------------------------------------------------

def format_date(day: date, language: str) -> str:
    if language == "hi":
        return f"{WEEKDAYS_HI[day.weekday()]}, {day.day} {MONTHS_HI[day.month - 1]}"
    return f"{WEEKDAYS_EN[day.weekday()][:3]} {day.day} {MONTHS_EN[day.month - 1][:3]}"


def _lookup(table: dict[str, str], key: str, what: str) -> str:
    try:
        return table[key]
    except KeyError:
        raise NoticeTemplateError(f"no wording for {what} {key!r}") from None


def _category(label: str, language: str) -> str:
    if language == "hi":
        return f"“{_lookup(CATEGORY_HI, label, 'category')}” ({label})"
    return f"“{label}”"


def _when(hour: HourFact, language: str) -> str:
    day = format_date(hour.at.ist_date, language)
    return f"{day}, {hour.at.ist_time} बजे" if language == "hi" else f"{day}, {hour.at.ist_time} IST"


def _window_text(window: WindowFact, language: str) -> str:
    day = format_date(window.start.ist_date, language)
    span = f"{window.start.ist_time}–{window.end.ist_time}"
    if language == "hi":
        text = f"{day}, {_lookup(PART_HI, window.part, 'period part')} ({span})"
    else:
        text = f"{window.label} ({day}, {span} IST)"
    if window.worst is None:
        return text
    return f"{text}, AQI {window.worst.aqi_display} {_category(window.worst.category, language)}"


# --- Sentences ------------------------------------------------------------------------------

def _opening(f: NoticeFacts) -> str:
    when = _when(HourFact(f.valid_for, f.aqi_display, f.category, f.action, f.headline), f.language)
    category = _category(f.category, f.language)
    if f.language == "hi":
        place = f"{f.school_name} के आसपास" if f.school_name else "विद्यालय के आसपास"
        pollutant = _lookup(POLLUTANT_HI, f.dominant_pollutant_code, "pollutant")
        text = (
            f"प्रिय अभिभावकगण, {place} {when} के लिए वायु गुणवत्ता का पूर्वानुमान/मॉडल अनुमान "
            f"AQI {f.aqi_display} है, जो {category} श्रेणी में आता है। मुख्य प्रदूषक {pollutant} है।"
        )
        if f.beyond_scale:
            text += (
                f" यह प्रकाशित पैमाने की ऊपरी सीमा पर या उससे अधिक है, इसलिए इसे {f.aqi_display} "
                "के रूप में दिखाया गया है।"
            )
        return text
    place = f"near {f.school_name}" if f.school_name else "near the school"
    text = (
        f"Dear parents, the forecast/model air quality estimate {place} for {when} is "
        f"AQI {f.aqi_display}, in the {category} category. The main pollutant is "
        f"{f.dominant_pollutant_name}."
    )
    if f.beyond_scale:
        text += (
            " This is at or above the top of the published scale, so it is shown as "
            f"{f.aqi_display} rather than an exact number."
        )
    return text


def _action(f: NoticeFacts) -> str:
    sentence = _lookup(ACTION_SENTENCES[f.language], f.action, "school action")
    if f.language == "hi":
        return f"SaansSafe विद्यालय सुरक्षा नीति के अनुसार, {sentence}"
    return f"Under the SaansSafe school safety policy, {sentence}"


def _best_window(f: NoticeFacts) -> str:
    if f.language == "hi":
        if f.best_window is None:
            return (
                "पूर्वानुमान में ऐसी कोई पूरी कार्यदिवस विद्यालय अवधि नहीं है जिसे बेहतर समय के रूप "
                "में सुझाया जा सके।"
            )
        return f"पूर्वानुमान के अनुसार विद्यालय के लिए सबसे अच्छा समय: {_window_text(f.best_window, 'hi')}।"
    if f.best_window is None:
        return "The forecast has no full weekday school period to suggest as a better window."
    return f"Best school window in the forecast: {_window_text(f.best_window, 'en')}."


def _next_change(f: NoticeFacts) -> str:
    change = f.next_change
    if f.language == "hi":
        if change is None:
            scope = "पूर्वानुमान अवधि" if f.forecast_complete else "उपलब्ध पूर्वानुमान"
            return f"{scope} में इस निर्णय में कोई बदलाव अपेक्षित नहीं है।"
        short = _lookup(ACTION_SHORT_HI, change.action, "school action")
        return f"अगला बदलाव {_when(change, 'hi')} से अपेक्षित है: {short}।"
    if change is None:
        scope = "the forecast period" if f.forecast_complete else "the available forecast"
        return f"No change to this school action is expected in {scope}."
    return f"The next expected change is from {_when(change, 'en')}: “{change.headline}”."


def _caveats(f: NoticeFacts) -> list[str]:
    notes = []
    if not f.forecast_complete:
        notes.append(
            f"उपलब्ध पूर्वानुमान {f.forecast_requested_hours} में से {f.forecast_hours} घंटों का है।"
            if f.language == "hi"
            else f"The forecast currently covers {f.forecast_hours} of "
            f"{f.forecast_requested_hours} hours."
        )
    if f.stale:
        notes.append(
            "ध्यान दें: ताज़ा डेटा नहीं मिल सका, इसलिए यह सूचना "
            f"{f.age_minutes} मिनट पहले प्राप्त पूर्वानुमान डेटा पर आधारित है।"
            if f.language == "hi"
            else "Please note: the live data refresh failed, so this notice uses forecast "
            f"data fetched {f.age_minutes} minutes ago."
        )
    return notes


def _key_points(f: NoticeFacts) -> tuple[str, ...]:
    activities = ACTIVITY_LABELS[f.language]
    guidance = GUIDANCE_LABELS[f.language]
    return tuple(
        f"{_lookup(activities, activity, 'activity')}: {_lookup(guidance, value, 'guidance')}"
        for activity, value in f.activities
    )


# --- Public API -----------------------------------------------------------------------------

def render_template(facts: NoticeFacts) -> ParentNotice:
    """The deterministic notice for these facts, in facts.language."""
    lang = facts.language
    day = format_date(facts.valid_for.ist_date, lang)
    outlook = " ".join([_best_window(facts), _next_change(facts), *_caveats(facts)])
    if lang == "hi":
        title = f"अभिभावकों के लिए वायु गुणवत्ता सूचना · {day}"
        sign_off = f"— {facts.school_name or 'विद्यालय प्रशासन'}"
    else:
        title = f"Air quality update for parents · {day}"
        sign_off = f"— {facts.school_name or 'School administration'}"
    body = "\n\n".join([_opening(facts), _action(facts), outlook])
    return ParentNotice(lang, title, body, _key_points(facts), sign_off)


def render_footer(facts: NoticeFacts) -> NoticeFooter:
    """Fixed footer: verbatim CPCB health statement and the required disclaimers."""
    if facts.language == "hi":
        label = f"CPCB स्वास्थ्य कथन, {_category(facts.category, 'hi')} श्रेणी (मूल अंग्रेज़ी में)"
        disclaimer = (
            "यह किसी मॉडल ग्रिड क्षेत्र का पूर्वानुमान/मॉडल अनुमान है, किसी CPCB निगरानी स्टेशन की "
            f"माप नहीं। विद्यालय के निर्णय SaansSafe विद्यालय सुरक्षा नीति ({facts.policy_version}) "
            "के अनुसार हैं, जो एक उत्पाद नीति है, CPCB का नियम नहीं। यह चिकित्सा सलाह नहीं है।"
        )
    else:
        label = f"CPCB health statement for the “{facts.category}” category"
        disclaimer = (
            f"{facts.disclaimer} School actions follow the {facts.policy_name} "
            f"({facts.policy_version}), a product policy, not a CPCB rule. "
            "This is not medical advice."
        )
    return NoticeFooter(label, facts.health_statement, facts.health_statement_source, disclaimer)


def compose_share_text(notice: ParentNotice, footer: NoticeFooter) -> str:
    """Plain text for copy / WhatsApp: the notice plus the fixed footer."""
    points = "\n".join(f"• {point}" for point in notice.key_points)
    return "\n\n".join(
        [
            notice.title,
            notice.body,
            points,
            f"{footer.health_label}: {footer.health_statement}",
            footer.disclaimer,
            notice.sign_off,
        ]
    )
