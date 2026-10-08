import math

import pytest

from saanssafe.aqi import (
    AVERAGING_HOURS,
    BREAKPOINTS,
    Category,
    InsufficientDataError,
    Pollutant,
    aqi_from_hourly,
    averaged_concentrations,
    category_for,
    compute_aqi,
    rolling_average,
    round_half_up,
    sub_index,
)

P = Pollutant


# --- Sub-index: exact values at CPCB published breakpoints ------------------

@pytest.mark.parametrize(
    ("pollutant", "concentration", "expected"),
    [
        # PM2.5 (24 h)
        (P.PM25, 0, 0), (P.PM25, 30, 50), (P.PM25, 31, 51), (P.PM25, 60, 100),
        (P.PM25, 61, 101), (P.PM25, 90, 200), (P.PM25, 91, 201), (P.PM25, 120, 300),
        (P.PM25, 121, 301), (P.PM25, 250, 400),
        # PM10 (24 h)
        (P.PM10, 50, 50), (P.PM10, 51, 51), (P.PM10, 100, 100), (P.PM10, 101, 101),
        (P.PM10, 250, 200), (P.PM10, 350, 300), (P.PM10, 430, 400),
        # NO2 (24 h)
        (P.NO2, 40, 50), (P.NO2, 80, 100), (P.NO2, 180, 200), (P.NO2, 280, 300),
        (P.NO2, 400, 400),
        # SO2 (24 h)
        (P.SO2, 40, 50), (P.SO2, 80, 100), (P.SO2, 380, 200), (P.SO2, 800, 300),
        (P.SO2, 1600, 400),
        # O3 (8 h)
        (P.O3, 50, 50), (P.O3, 100, 100), (P.O3, 168, 200), (P.O3, 208, 300),
        (P.O3, 748, 400),
        # CO (8 h, mg/m3)
        (P.CO, 1.0, 50), (P.CO, 1.1, 51), (P.CO, 2.0, 100), (P.CO, 10, 200),
        (P.CO, 17, 300), (P.CO, 34, 400),
        # NH3 (24 h)
        (P.NH3, 200, 50), (P.NH3, 400, 100), (P.NH3, 800, 200), (P.NH3, 1200, 300),
        (P.NH3, 1800, 400),
    ],
)
def test_sub_index_at_published_breakpoints(pollutant, concentration, expected):
    assert sub_index(pollutant, concentration) == pytest.approx(expected)


# --- Sub-index: interpolation inside bands (hand-computed midpoints) --------

@pytest.mark.parametrize(
    ("pollutant", "concentration", "expected"),
    [
        (P.PM25, 15, 25.0),       # 15/30*50
        (P.PM25, 45.5, 75.5),     # midpoint of 31-60 -> midpoint of 51-100
        (P.PM10, 175.5, 150.5),   # midpoint of 101-250
        (P.NO2, 230.5, 250.5),    # midpoint of 181-280
        (P.SO2, 20, 25.0),
        (P.O3, 134.5, 150.5),     # midpoint of 101-168
        (P.CO, 6.05, 150.5),      # midpoint of 2.1-10
    ],
)
def test_sub_index_interpolates_linearly(pollutant, concentration, expected):
    assert sub_index(pollutant, concentration) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("pollutant", "gap_value", "expected"),
    [(P.PM25, 30.5, 51), (P.PM10, 100.4, 101), (P.CO, 1.05, 51), (P.NO2, 180.9, 201)],
)
def test_values_in_gaps_between_bands_take_lower_index_of_next_band(
    pollutant, gap_value, expected
):
    assert sub_index(pollutant, gap_value) == pytest.approx(expected)


def test_sub_index_is_monotonic_non_decreasing_for_every_pollutant():
    for pollutant, bands in BREAKPOINTS.items():
        top = bands[-1].c_hi * 1.2
        steps = [top * i / 2000 for i in range(2001)]
        values = [sub_index(pollutant, c) for c in steps]
        assert all(b >= a for a, b in zip(values, values[1:])), pollutant


# --- Severe (open-ended) band and cap ----------------------------------------

def test_severe_band_extends_with_very_poor_width():
    # PM2.5 Very Poor is 121-250 (width 129), so Severe spans 250-379.
    assert BREAKPOINTS[P.PM25][-1].c_hi == pytest.approx(379)
    assert BREAKPOINTS[P.PM10][-1].c_hi == pytest.approx(509)
    assert sub_index(P.PM25, 314.5) == pytest.approx(450.5)
    assert sub_index(P.PM25, 379) == pytest.approx(500)


@pytest.mark.parametrize("pollutant", list(Pollutant))
def test_sub_index_caps_at_500_far_above_scale(pollutant):
    assert sub_index(pollutant, 1_000_000) == 500


def test_just_above_very_poor_enters_severe():
    assert 400 < sub_index(P.PM25, 250.01) < 401.1


# --- Category mapping ---------------------------------------------------------

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


def test_categories_have_labels_and_health_impact():
    assert Category.VERY_POOR.label == "Very Poor"
    assert all(c.health_impact for c in Category)


# --- Overall AQI ----------------------------------------------------------------

def test_overall_aqi_is_max_sub_index_and_reports_dominant():
    result = compute_aqi({P.PM25: 45.5, P.PM10: 175.5, P.NO2: 20})
    assert result.sub_indices[P.PM25] == pytest.approx(75.5)
    assert result.sub_indices[P.PM10] == pytest.approx(150.5)
    assert result.sub_indices[P.NO2] == pytest.approx(25)
    assert result.aqi == 151  # 150.5 rounds half up
    assert result.dominant is P.PM10
    assert result.category is Category.MODERATE


def test_overall_aqi_accepts_string_keys():
    result = compute_aqi({"pm2_5": 100, "pm10": 50, "o3": 40})
    assert result.dominant is P.PM25
    assert result.aqi == 232  # 201 + 99*(100-91)/29 ≈ 231.72, rounds half up to 232


def test_rounding_feeds_category_at_boundary():
    # PM2.5 30.3 -> gap -> 51; PM2.5 at exactly 30 -> 50 (Good).
    good = compute_aqi({P.PM25: 30, P.NO2: 10, P.SO2: 10})
    assert (good.aqi, good.category) == (50, Category.GOOD)
    sat = compute_aqi({P.PM25: 30.3, P.NO2: 10, P.SO2: 10})
    assert (sat.aqi, sat.category) == (51, Category.SATISFACTORY)


def test_tie_breaks_deterministically_by_pollutant_order():
    result = compute_aqi({P.NO2: 40, P.PM10: 50, P.PM25: 30})  # all exactly 50
    assert result.aqi == 50
    assert result.dominant is P.PM25


def test_result_mappings_are_read_only():
    result = compute_aqi({P.PM25: 10, P.PM10: 10, P.NO2: 10})
    with pytest.raises(TypeError):
        result.sub_indices[P.PM25] = 0  # type: ignore[index]


def test_severe_overall_caps_at_500():
    result = compute_aqi({P.PM25: 999, P.PM10: 999, P.NO2: 999})
    assert result.aqi == 500
    assert result.category is Category.SEVERE


# --- Insufficient data ------------------------------------------------------------

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


# --- Invalid inputs -------------------------------------------------------------------

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


# --- Averaging windows ---------------------------------------------------------------------

def test_averaging_windows_match_cpcb():
    for p in (P.PM25, P.PM10, P.NO2, P.SO2, P.NH3):
        assert AVERAGING_HOURS[p] == 24
    assert AVERAGING_HOURS[P.O3] == 8
    assert AVERAGING_HOURS[P.CO] == 8


def test_rolling_average_uses_only_the_latest_window():
    series = [1000.0] * 10 + [10.0] * 24  # old spike falls outside the 24 h window
    assert rolling_average(series, 24) == pytest.approx(10.0)
    assert rolling_average([5.0] * 16 + [50.0] * 8, 8) == pytest.approx(50.0)


def test_rolling_average_ignores_missing_hours_without_filling():
    series = [None] * 8 + [20.0] * 16
    assert rolling_average(series, 24) == pytest.approx(20.0)


def test_rolling_average_returns_none_below_completeness():
    assert rolling_average([None] * 9 + [20.0] * 15, 24) is None  # 15 < 16
    assert rolling_average([None, None, None] + [1.0] * 5, 8) is None  # 5 < 6
    assert rolling_average([1.0] * 6, 8) == pytest.approx(1.0)  # short series, 6 valid
    assert rolling_average([], 24) is None


def test_rolling_average_rejects_invalid_values_and_windows():
    with pytest.raises(ValueError):
        rolling_average([1.0] * 23 + [-1.0], 24)
    with pytest.raises(ValueError):
        rolling_average([1.0] * 23 + [math.nan], 24)
    with pytest.raises(ValueError, match="Unsupported"):
        rolling_average([1.0] * 12, 12)


def test_averaged_concentrations_drops_incomplete_pollutants():
    averages = averaged_concentrations(
        {
            P.PM25: [40.0] * 24,
            P.NO2: [None] * 20 + [30.0] * 4,  # only 4 valid hours -> dropped
            P.CO: [0.5] * 16 + [2.0] * 8,     # 8 h window -> 2.0
        }
    )
    assert averages == {P.PM25: pytest.approx(40.0), P.CO: pytest.approx(2.0)}


def test_aqi_from_hourly_end_to_end():
    result = aqi_from_hourly(
        {
            "pm2_5": [100.0] * 24,
            "pm10": [150.0] * 24,
            "no2": [40.0] * 24,
            "o3": [500.0] * 16 + [30.0] * 8,  # stale ozone spike outside 8 h window
        }
    )
    assert result.dominant is P.PM25
    assert result.sub_indices[P.O3] == pytest.approx(30.0)
    assert result.category is Category.POOR


def test_aqi_from_hourly_insufficient_when_incomplete_series_dropped():
    with pytest.raises(InsufficientDataError):
        aqi_from_hourly({"pm2_5": [50.0] * 24, "no2": [None] * 24, "so2": [10.0] * 3})


def test_round_half_up():
    assert [round_half_up(x) for x in (0.4, 0.5, 1.5, 2.5, 150.49)] == [0, 1, 2, 3, 150]
