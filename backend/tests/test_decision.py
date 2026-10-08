"""School safety decision policy tests. AQI inputs come from the real CPCB engine."""

import pytest

from saanssafe.aqi import Category, Pollutant, compute_aqi
from saanssafe.decision import (
    POLICY,
    POLICY_BASIS,
    POLICY_VERSION,
    POLLUTANT_NAMES,
    Activity,
    Guidance,
    SchoolAction,
    Severity,
    decide_school_safety,
)


def aqi_for_pm25(pm25: float, **others: float):
    """AQI dominated by PM2.5 (other pollutants low)."""
    return compute_aqi({"pm2_5": pm25, "no2": 10.0, "so2": 10.0, **others})


# --- Category -> action mapping -----------------------------------------------------------

@pytest.mark.parametrize(
    ("pm25", "aqi", "category", "action", "severity"),
    [
        (15, 25, Category.GOOD, SchoolAction.NORMAL, Severity.MINIMAL),
        (45.5, 75, Category.SATISFACTORY, SchoolAction.PROTECT_SENSITIVE, Severity.LOW),
        (75, 148, Category.MODERATE, SchoolAction.REDUCE_EXERTION, Severity.MODERATE),
        (105, 248, Category.POOR, SchoolAction.MOVE_STRENUOUS_INDOORS, Severity.HIGH),
        (185.5, 350, Category.VERY_POOR, SchoolAction.SUSPEND_OUTDOOR, Severity.VERY_HIGH),
        (300, 401, Category.SEVERE, SchoolAction.SUSPEND_OUTDOOR, Severity.CRITICAL),
    ],
)
def test_each_category_maps_to_policy_action(pm25, aqi, category, action, severity):
    decision = decide_school_safety(aqi_for_pm25(pm25))
    assert (decision.aqi_value, decision.category) == (aqi, category)
    assert (decision.action, decision.severity) == (action, severity)


@pytest.mark.parametrize(
    ("low_pm25", "high_pm25", "low_cat", "high_cat"),
    [
        (30, 32, Category.GOOD, Category.SATISFACTORY),        # AQI 50 -> 52
        (60, 62, Category.SATISFACTORY, Category.MODERATE),    # AQI 100 -> 103
        (90, 92, Category.MODERATE, Category.POOR),            # AQI 200 -> 203
        (120, 122, Category.POOR, Category.VERY_POOR),         # AQI 300 -> 301
        (249.9, 250, Category.VERY_POOR, Category.SEVERE),     # AQI 400 -> 401+
    ],
)
def test_category_boundaries_switch_action(low_pm25, high_pm25, low_cat, high_cat):
    low = decide_school_safety(aqi_for_pm25(low_pm25))
    high = decide_school_safety(aqi_for_pm25(high_pm25))
    assert (low.category, high.category) == (low_cat, high_cat)
    assert high.severity.rank == low.severity.rank + 1


def test_policy_covers_every_category():
    assert set(POLICY) == set(Category)


def test_policy_is_monotonic_never_less_protective_as_aqi_rises():
    rules = [POLICY[c] for c in Category]  # Category is ordered Good -> Severe
    for prev, curr in zip(rules, rules[1:]):
        assert curr.severity.rank > prev.severity.rank
        for activity in Activity:
            assert curr.activities[activity].rank >= prev.activities[activity].rank


def test_every_rule_covers_every_activity_and_has_recommendations():
    for rule in POLICY.values():
        assert set(rule.activities) == set(Activity)
        assert rule.recommendations and all(r.strip() for r in rule.recommendations)
        assert rule.headline


# --- Activity guidance at key levels ------------------------------------------------------------

def test_good_allows_everything():
    d = decide_school_safety(aqi_for_pm25(15))
    assert all(g is Guidance.ALLOWED for g in d.activities.values())


def test_moderate_limits_pe_only():
    d = decide_school_safety(aqi_for_pm25(75))
    assert d.activities[Activity.PE_AND_SPORTS] is Guidance.LIMITED
    assert d.activities[Activity.ASSEMBLY] is Guidance.ALLOWED


def test_poor_moves_assembly_and_pe_indoors():
    d = decide_school_safety(aqi_for_pm25(105))
    assert d.activities[Activity.ASSEMBLY] is Guidance.INDOORS
    assert d.activities[Activity.PE_AND_SPORTS] is Guidance.INDOORS
    assert d.activities[Activity.RECESS] is Guidance.LIMITED


@pytest.mark.parametrize("pm25", [185.5, 300, 5000])
def test_very_poor_and_severe_move_everything_indoors(pm25):
    d = decide_school_safety(aqi_for_pm25(pm25))
    assert all(g is Guidance.INDOORS for g in d.activities.values())


# --- 401+ / beyond scale --------------------------------------------------------------------------

@pytest.mark.parametrize("pm25", [250, 400, 5000])
def test_beyond_scale_is_critical_and_displayed_as_401_plus(pm25):
    d = decide_school_safety(aqi_for_pm25(pm25))
    assert d.beyond_scale is True
    assert d.aqi_display == "401+"
    assert d.severity is Severity.CRITICAL
    assert "401+" in d.short_reason and "beyond the published CPCB scale" in d.short_reason
    assert "sub-index 401+" in d.short_reason
    assert "Follow any instructions issued by local or education authorities." in d.recommendations


def test_severe_driven_by_non_pm_pollutant_still_critical():
    d = decide_school_safety(compute_aqi({"pm10": 50, "no2": 20, "o3": 800}))
    assert d.dominant_pollutant is Pollutant.O3
    assert d.severity is Severity.CRITICAL and d.aqi_display == "401+"


# --- Explanation and context ---------------------------------------------------------------------------

def test_decision_carries_aqi_and_dominant_pollutant_context():
    result = compute_aqi({"pm2_5": 45.5, "pm10": 175.5, "no2": 20})
    d = decide_school_safety(result)
    assert (d.aqi_value, d.aqi_display, d.category) == (150, "150", Category.MODERATE)
    assert d.dominant_pollutant is Pollutant.PM10
    assert d.dominant_pollutant_name == "PM10 (coarse particulate matter)"
    assert d.dominant_sub_index == pytest.approx(150)
    assert d.health_impact == Category.MODERATE.health_impact
    assert d.short_reason == (
        "Forecast/model AQI 150 is Moderate. "
        "Main pollutant: PM10 (coarse particulate matter), sub-index 150. "
        "Action per the SaansSafe school safety policy (not a CPCB rule)."
    )


def test_policy_is_labelled_as_saanssafe_policy_not_cpcb_rule():
    d = decide_school_safety(aqi_for_pm25(15))
    assert d.policy_version == POLICY_VERSION == "saanssafe-school-v1"
    assert d.policy_basis == POLICY_BASIS
    assert "not a CPCB rule" in POLICY_BASIS
    assert "forecast/model" in POLICY_BASIS


@pytest.mark.parametrize("pm25", [15, 45.5, 75, 105, 185.5, 300])
def test_every_user_facing_explanation_names_saanssafe_policy(pm25):
    d = decide_school_safety(aqi_for_pm25(pm25))
    assert "SaansSafe school safety policy" in d.short_reason
    assert "not a CPCB rule" in d.short_reason
    assert d.policy_basis.startswith("SaansSafe school safety policy")
    assert "Not medical advice" in d.policy_basis


FORBIDDEN_MEDICAL_TERMS = (
    "medication", "medicine", "inhaler", "prescri", "dose", "diagnos", "asthma",
    "treatment", "symptom",
)


def test_recommendations_are_general_and_non_diagnostic():
    for rule in POLICY.values():
        for text in (rule.headline, *rule.recommendations):
            lowered = text.lower()
            assert not any(term in lowered for term in FORBIDDEN_MEDICAL_TERMS), text


def test_elevated_categories_tell_staff_to_let_unwell_students_rest():
    for category in (Category.SATISFACTORY, Category.MODERATE, Category.POOR,
                     Category.VERY_POOR, Category.SEVERE):
        assert "Allow students to rest if they feel unwell." in POLICY[category].recommendations


def test_recommendations_never_claim_cpcb_mandates():
    for rule in POLICY.values():
        for text in (rule.headline, *rule.recommendations):
            assert "CPCB" not in text


def test_every_pollutant_has_a_display_name():
    assert set(POLLUTANT_NAMES) == set(Pollutant)


# --- Purity / determinism / validation ----------------------------------------------------------------

def test_decision_is_deterministic():
    result = aqi_for_pm25(105)
    assert decide_school_safety(result) == decide_school_safety(result)


def test_decision_is_immutable():
    d = decide_school_safety(aqi_for_pm25(105))
    with pytest.raises(AttributeError):
        d.action = SchoolAction.NORMAL  # type: ignore[misc]
    with pytest.raises(TypeError):
        d.activities[Activity.RECESS] = Guidance.ALLOWED  # type: ignore[index]


@pytest.mark.parametrize("bad", [None, 150, {"aqi": 150}, "Moderate"])
def test_rejects_non_aqi_result(bad):
    with pytest.raises(TypeError):
        decide_school_safety(bad)


def test_severity_and_guidance_ranks_are_ordered():
    assert [s.rank for s in Severity] == list(range(len(Severity)))
    assert Guidance.ALLOWED.rank < Guidance.LIMITED.rank < Guidance.INDOORS.rank
