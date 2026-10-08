"""Tests for the CPCB AQI engine.

Expected values are hand-computed from CPCB CUPS/82/2014-15 Table 3.11 and the
section 3.5 formula, Ip = (IHI - ILO')/(BHI - BLO) * (Cp - BLO) + ILO',
where ILO' = ILO - 1 when ILO > 50.
"""

import math

import pytest

from saanssafe.aqi import (
    AVERAGING_HOURS,
    BEYOND_SCALE_NOTE,
    BREAKPOINTS,
    SEVERE_THRESHOLD,
    Category,
    InsufficientDataError,
    Pollutant,
    aqi_from_hourly,
    averaged_concentrations,
    category_for,
    compute_aqi,
    is_beyond_scale,
    rolling_average,
    round_half_up,
    sub_index,
)

P = Pollutant


# --- Sub-index at CPCB published breakpoints (ILO - 1 rule) -------------------

@pytest.mark.parametrize(
    ("pollutant", "concentration", "expected"),
    [
        # PM2.5 (24 h): each band above Good starts at ILO - 1
        (P.PM25, 0, 0), (P.PM25, 30, 50), (P.PM25, 31, 50), (P.PM25, 60, 100),
        (P.PM25, 61, 100), (P.PM25, 90, 200), (P.PM25, 91, 200), (P.PM25, 120, 300),
        (P.PM25, 121, 300),
        # PM10 (24 h)
        (P.PM10, 50, 50), (P.PM10, 51, 50), (P.PM10, 100, 100), (P.PM10, 101, 100),
        (P.PM10, 250, 200), (P.PM10, 350, 300), (P.PM10, 351, 300),
        # NO2 (24 h)
        (P.NO2, 40, 50), (P.NO2, 80, 100), (P.NO2, 180, 200), (P.NO2, 280, 300),
        # SO2 (24 h)
        (P.SO2, 40, 50), (P.SO2, 80, 100), (P.SO2, 380, 200), (P.SO2, 800, 300),
        # O3 (8 h)
        (P.O3, 50, 50), (P.O3, 100, 100), (P.O3, 168, 200), (P.O3, 208, 300),
        # CO (8 h, mg/m3)
        (P.CO, 1.0, 50), (P.CO, 1.1, 50), (P.CO, 2.0, 100), (P.CO, 10, 200),
        (P.CO, 17, 300),
        # NH3 (24 h)
        (P.NH3, 200, 50), (P.NH3, 400, 100), (P.NH3, 800, 200), (P.NH3, 1200, 300),
    ],
)
def test_sub_index_at_published_breakpoints(pollutant, concentration, expected):
    assert sub_index(pollutant, concentration) == pytest.approx(expected)


def test_cpcb_ilo_minus_one_pm25_31_gives_50():
    # CPCB section 3.5: "subtract one from ILO, if ILO is greater than 50".
    assert sub_index(P.PM25, 31) == pytest.approx(50)
    assert BREAKPOINTS[P.PM25][1].interpolation_i_lo == 50
    assert BREAKPOINTS[P.PM25][0].interpolation_i_lo == 0  # Good band unchanged (ILO = 0)


def test_ilo_minus_one_applies_only_above_50():
    assert [b.interpolation_i_lo for b in BREAKPOINTS[P.PM10]] == [0, 50, 100, 200, 300]


# --- Interpolation inside bands (hand-computed midpoints) ------------------------

@pytest.mark.parametrize(
    ("pollutant", "concentration", "expected"),
    [
        (P.PM25, 15, 25.0),      # 50 * 15/30
        (P.PM25, 45.5, 75.0),    # midpoint of 31-60 -> midpoint of 50-100
        (P.PM10, 175.5, 150.0),  # midpoint of 101-250 -> midpoint of 100-200
        (P.NO2, 230.5, 250.0),   # midpoint of 181-280 -> midpoint of 200-300
        (P.SO2, 20, 25.0),
        (P.O3, 134.5, 150.0),    # midpoint of 101-168
        (P.CO, 6.05, 150.0),     # midpoint of 2.1-10
        (P.PM25, 185.5, 350.0),  # midpoint of Very Poor 121-250 -> 300-400
    ],
)
def test_sub_index_interpolates_linearly(pollutant, concentration, expected):
    assert sub_index(pollutant, concentration) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("pollutant", "gap_value", "expected"),
    [(P.PM25, 30.5, 50), (P.PM10, 100.4, 100), (P.CO, 1.05, 50), (P.NO2, 180.9, 200),
     (P.NH3, 1200.5, 300)],
)
def test_values_in_gaps_take_interpolation_start_of_next_band(pollutant, gap_value, expected):
    assert sub_index(pollutant, gap_value) == pytest.approx(expected)


def test_sub_index_is_monotonic_non_decreasing_for_every_pollutant():
    for pollutant in Pollutant:
        top = SEVERE_THRESHOLD[pollutant] * 1.2
        steps = [top * i / 2000 for i in range(2001)]
        values = [sub_index(pollutant, c) for c in steps]
        assert all(b >= a for a, b in zip(values, values[1:])), pollutant


# --- NH3 Very Poor boundary (CPCB: 1201-1800) ----------------------------------------

def test_nh3_very_poor_band_starts_at_1201():
    very_poor = BREAKPOINTS[P.NH3][-1]
    assert (very_poor.c_lo, very_poor.c_hi) == (1201, 1800)
    assert sub_index(P.NH3, 1201) == pytest.approx(300)
    assert sub_index(P.NH3, 1500.5) == pytest.approx(350)  # midpoint of 1201-1800


# --- Severe: open-ended, no invented interpolation -------------------------------------

@pytest.mark.parametrize(
    ("pollutant", "threshold"),
    [(P.PM10, 430), (P.PM25, 250), (P.NO2, 400), (P.O3, 748), (P.CO, 34),
     (P.SO2, 1600), (P.NH3, 1800)],
)
def test_severe_thresholds_match_cpcb_table(pollutant, threshold):
    assert SEVERE_THRESHOLD[pollutant] == threshold


@pytest.mark.parametrize("pollutant", list(Pollutant))
def test_at_or_above_severe_threshold_returns_401_not_interpolated(pollutant):
    threshold = SEVERE_THRESHOLD[pollutant]
    for c in (threshold, threshold * 1.01, threshold * 2, 1_000_000):
        assert sub_index(pollutant, c) == 401
        assert is_beyond_scale(pollutant, c)


def test_just_below_severe_threshold_stays_very_poor():
    assert 399 < sub_index(P.PM25, 249.9) < 400
    assert not is_beyond_scale(P.PM25, 249.9)


def test_severe_overall_is_401_plus_and_flagged():
    result = compute_aqi({P.PM25: 999, P.PM10: 300, P.NO2: 20})
    assert result.aqi == 401
    assert result.beyond_scale is True
    assert result.display == "401+"
    assert result.category is Category.SEVERE
    assert result.dominant is P.PM25
    assert "no upper" in BEYOND_SCALE_NOTE


def test_very_different_severe_levels_are_not_given_fake_precision():
    a = compute_aqi({P.PM25: 260, P.PM10: 10, P.NO2: 10})
    b = compute_aqi({P.PM25: 900, P.PM10: 10, P.NO2: 10})
    assert a.aqi == b.aqi == 401
    assert a.display == b.display == "401+"


def test_non_severe_result_displays_plain_number():
    result = compute_aqi({P.PM25: 45.5, P.PM10: 20, P.NO2: 20})
    assert result.beyond_scale is False
    assert result.display == "75"


# --- Category mapping --------------------------------------------------------------------

@pytest.mark.parametrize(
    ("aqi", "category"),
    [
        (0, Category.GOOD), (50, Category.GOOD),
        (51, Category.SATISFACTORY), (100, Category.SATISFACTORY),
        (101, Category.MODERATE), (200, Category.MODERATE),
        (201, Category.POOR), (300, Category.POOR),
        (301, Category.VERY_POOR), (400, Category.VERY_POOR),
        (401, Category.SEVERE), (500, Category.SEVERE),
    ],
)
def test_category_boundaries(aqi, category):
    assert category_for(aqi) is category


@pytest.mark.parametrize("bad", [-1, 501, 50.5, True, None, "100"])
def test_category_rejects_invalid_aqi(bad):
    with pytest.raises(ValueError):
        category_for(bad)


# Verbatim from CPCB National AQI report CUPS/82/2014-15, Table 3.12
# "Health Statements for AQI Categories" (PDF p.38 / printed p.36).
CPCB_TABLE_3_12 = {
    Category.GOOD: "Minimal Impact",
    Category.SATISFACTORY: "May cause minor breathing discomfort to sensitive people",
    Category.MODERATE: (
        "May cause breathing discomfort to the people with lung disease such as asthma and "
        "discomfort to people with heart disease, children and older adults"
    ),
    Category.POOR: (
        "May cause breathing discomfort to people on prolonged exposure and discomfort to "
        "people with heart disease with short exposure"
    ),
    Category.VERY_POOR: (
        "May cause respiratory illness to the people on prolonged exposure. Effect may be "
        "more pronounced in people with lung and heart diseases"
    ),
    Category.SEVERE: (
        "May cause respiratory effects even on healthy people and serious health impacts on "
        "people with lung/heart diseases. The health impacts may be experienced even during "
        "light physical activity"
    ),
}


@pytest.mark.parametrize("category", list(Category))
def test_health_impact_matches_cpcb_table_3_12_verbatim(category):
    assert category.health_impact == CPCB_TABLE_3_12[category]


def test_health_impact_has_no_doubled_whitespace():
    assert all("  " not in c.health_impact for c in Category)


def test_categories_have_labels_and_health_impact():
    assert Category.VERY_POOR.label == "Very Poor"
    assert all(c.health_impact for c in Category)


# --- Overall AQI ---------------------------------------------------------------------------

def test_overall_aqi_is_max_sub_index_and_reports_dominant():
    result = compute_aqi({P.PM25: 45.5, P.PM10: 175.5, P.NO2: 20})
    assert result.sub_indices[P.PM25] == pytest.approx(75)
    assert result.sub_indices[P.PM10] == pytest.approx(150)
    assert result.sub_indices[P.NO2] == pytest.approx(25)
    assert result.aqi == 150
    assert result.dominant is P.PM10
    assert result.category is Category.MODERATE


def test_overall_aqi_accepts_string_keys():
    result = compute_aqi({"pm2_5": 100, "pm10": 50, "o3": 40})
    assert result.dominant is P.PM25
    assert result.aqi == 231  # 200 + 100*(100-91)/29 ≈ 231.03, rounds to 231
    assert result.category is Category.POOR


def test_overall_aqi_rounds_half_up():
    # NH3 10 -> 50 * 10/200 = 2.5 exactly; half-up gives 3 (banker's rounding would give 2).
    assert compute_aqi({P.PM25: 0, P.PM10: 0, P.NH3: 10}).aqi == 3


def test_category_at_pm25_31_follows_cpcb_formula():
    # A consequence of the ILO - 1 rule: PM2.5 = 31 gives AQI 50 (Good); 32 gives 52.
    at_31 = compute_aqi({P.PM25: 31, P.NO2: 10, P.SO2: 10})
    assert (at_31.aqi, at_31.category) == (50, Category.GOOD)
    at_32 = compute_aqi({P.PM25: 32, P.NO2: 10, P.SO2: 10})
    assert (at_32.aqi, at_32.category) == (52, Category.SATISFACTORY)  # 50 + 50/29 ≈ 51.72


def test_tie_breaks_deterministically_by_pollutant_order():
    result = compute_aqi({P.NO2: 40, P.PM10: 50, P.PM25: 30})  # all exactly 50
    assert result.aqi == 50
    assert result.dominant is P.PM25


def test_result_mappings_are_read_only():
    result = compute_aqi({P.PM25: 10, P.PM10: 10, P.NO2: 10})
    with pytest.raises(TypeError):
        result.sub_indices[P.PM25] = 0  # type: ignore[index]


# --- Insufficient data ---------------------------------------------------------------------

def test_fewer_than_three_pollutants_is_insufficient():
    with pytest.raises(InsufficientDataError, match="at least 3"):
        compute_aqi({P.PM25: 50, P.PM10: 80})


def test_no_particulate_is_insufficient():
    with pytest.raises(InsufficientDataError, match="PM2.5 or PM10"):
        compute_aqi({P.NO2: 50, P.SO2: 20, P.O3: 30, P.CO: 1.0})


def test_pm10_alone_satisfies_particulate_rule():
    assert compute_aqi({P.PM10: 80, P.NO2: 20, P.O3: 30}).dominant is P.PM10


def test_insufficient_data_error_is_a_value_error():
    assert issubclass(InsufficientDataError, ValueError)


# --- Invalid inputs ----------------------------------------------------------------------

@pytest.mark.parametrize("bad", [-0.1, math.nan, math.inf, -math.inf, True, None, "12"])
def test_sub_index_rejects_invalid_concentrations(bad):
    with pytest.raises(ValueError):
        sub_index(P.PM25, bad)


def test_unknown_pollutant_rejected():
    with pytest.raises(ValueError, match="Unknown pollutant"):
        sub_index("pb", 1.0)
    with pytest.raises(ValueError, match="Unknown pollutant"):
        compute_aqi({"pm2_5": 10, "pm10": 10, "benzene": 1})


def test_compute_aqi_rejects_negative_value():
    with pytest.raises(ValueError):
        compute_aqi({P.PM25: -5, P.PM10: 10, P.NO2: 10})


# --- Averaging windows and completeness ----------------------------------------------------

def test_averaging_windows_match_cpcb():
    for p in (P.PM25, P.PM10, P.NO2, P.SO2, P.NH3):
        assert AVERAGING_HOURS[p] == 24
    assert AVERAGING_HOURS[P.O3] == 8
    assert AVERAGING_HOURS[P.CO] == 8


def test_24h_average_uses_only_latest_24_hours():
    series = [1000.0] * 10 + [10.0] * 24  # old spike falls outside the window
    assert rolling_average(series, 24) == pytest.approx(10.0)


def test_24h_completeness_16_of_24():
    assert rolling_average([None] * 8 + [20.0] * 16, 24) == pytest.approx(20.0)
    assert rolling_average([None] * 9 + [20.0] * 15, 24) is None


def test_8h_pollutants_need_16_valid_hours_in_latest_24():
    # 15 valid hours: rejected even though the latest 8 hours are all present.
    assert rolling_average([None] * 9 + [30.0] * 15, 8) is None
    # 16 valid hours: accepted.
    assert rolling_average([None] * 8 + [30.0] * 16, 8) == pytest.approx(30.0)


def test_8h_pollutants_reject_short_series_old_6_of_8_rule_removed():
    assert rolling_average([1.0] * 8, 8) is None  # 8 valid hours < 16
    assert rolling_average([1.0] * 15, 8) is None


def test_8h_average_uses_latest_window_not_daily_maximum():
    # Ozone peaked earlier in the day; SaansSafe reports the latest 8 hours.
    series = [5.0] * 8 + [200.0] * 8 + [50.0] * 8
    assert rolling_average(series, 8) == pytest.approx(50.0)


def test_8h_average_ignores_missing_hours_inside_window():
    series = [1.0] * 16 + [None] * 4 + [10.0] * 4
    assert rolling_average(series, 8) == pytest.approx(10.0)


def test_8h_average_none_when_latest_window_entirely_missing():
    assert rolling_average([1.0] * 16 + [None] * 8, 8) is None


def test_rolling_average_empty_series():
    assert rolling_average([], 24) is None
    assert rolling_average([], 8) is None


def test_rolling_average_rejects_invalid_values_and_windows():
    with pytest.raises(ValueError):
        rolling_average([1.0] * 23 + [-1.0], 24)
    with pytest.raises(ValueError):
        rolling_average([1.0] * 23 + [math.nan], 24)
    with pytest.raises(ValueError, match="Unsupported"):
        rolling_average([1.0] * 24, 12)


def test_averaged_concentrations_drops_incomplete_pollutants():
    averages = averaged_concentrations(
        {
            P.PM25: [40.0] * 24,
            P.NO2: [None] * 20 + [30.0] * 4,  # only 4 valid hours -> dropped
            P.CO: [0.5] * 16 + [2.0] * 8,     # latest 8 h -> 2.0
            P.O3: [None] * 16 + [40.0] * 8,   # only 8 valid of 24 -> dropped
        }
    )
    assert averages == {P.PM25: pytest.approx(40.0), P.CO: pytest.approx(2.0)}


def test_aqi_from_hourly_end_to_end():
    result = aqi_from_hourly(
        {
            "pm2_5": [100.0] * 24,
            "pm10": [150.0] * 24,
            "no2": [40.0] * 24,
            "o3": [500.0] * 16 + [30.0] * 8,  # earlier ozone spike outside latest 8 h
        }
    )
    assert result.dominant is P.PM25
    assert result.sub_indices[P.O3] == pytest.approx(30.0)
    assert result.aqi == 231
    assert result.category is Category.POOR


def test_aqi_from_hourly_insufficient_when_incomplete_series_dropped():
    with pytest.raises(InsufficientDataError):
        aqi_from_hourly({"pm2_5": [50.0] * 24, "no2": [None] * 24, "so2": [10.0] * 3})


def test_round_half_up():
    assert [round_half_up(x) for x in (0.4, 0.5, 1.5, 2.5, 150.49)] == [0, 1, 2, 3, 150]
