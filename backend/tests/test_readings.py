from datetime import UTC, datetime, timedelta, timezone

import pytest

from saanssafe.aqi import InsufficientDataError, Pollutant, aqi_from_hourly
from saanssafe.readings import HourlyReading, ReadingSeries

T0 = datetime(2026, 10, 7, 0, tzinfo=UTC)
H = timedelta(hours=1)
IST = timezone(timedelta(hours=5, minutes=30))


def series(hours: int, start: datetime = T0, **values: float | None) -> ReadingSeries:
    return ReadingSeries(
        28.6, 77.2, "test", tuple(HourlyReading(start + H * i, **values) for i in range(hours))
    )


# --- HourlyReading validation -------------------------------------------------------------

def test_reading_normalizes_to_utc():
    reading = HourlyReading(datetime(2026, 10, 8, 5, 30, tzinfo=IST), pm2_5=10)
    assert reading.time == datetime(2026, 10, 8, 0, tzinfo=UTC)
    assert reading.time.tzinfo is UTC


def test_reading_missing_values_default_to_none():
    reading = HourlyReading(T0, pm2_5=12.5)
    assert reading.value(Pollutant.PM25) == 12.5
    assert all(reading.value(p) is None for p in Pollutant if p is not Pollutant.PM25)


@pytest.mark.parametrize(
    "bad_time", [datetime(2026, 10, 7, 0), T0.replace(minute=30), "2026-10-07T00:00Z"]
)
def test_reading_rejects_naive_or_off_hour_time(bad_time):
    with pytest.raises(ValueError):
        HourlyReading(bad_time)


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), True, "5"])
def test_reading_rejects_invalid_concentration(bad):
    with pytest.raises(ValueError):
        HourlyReading(T0, pm10=bad)


def test_reading_is_immutable():
    with pytest.raises(AttributeError):
        HourlyReading(T0).pm2_5 = 1.0  # type: ignore[misc]


# --- ReadingSeries validation ------------------------------------------------------------------

def test_series_requires_consecutive_hours():
    with pytest.raises(ValueError, match="consecutive"):
        ReadingSeries(1, 1, "t", (HourlyReading(T0), HourlyReading(T0 + 2 * H)))
    with pytest.raises(ValueError, match="consecutive"):
        ReadingSeries(1, 1, "t", (HourlyReading(T0 + H), HourlyReading(T0)))


def test_series_first_and_last_time():
    s = series(48)
    assert (s.first_time, s.last_time) == (T0, T0 + 47 * H)
    empty = ReadingSeries(1, 1, "t", ())
    assert (empty.first_time, empty.last_time) == (None, None)


# --- hourly_until: the AQI engine input contract ---------------------------------------------

def test_hourly_until_returns_24_hours_ending_at_until_hour_oldest_first():
    s = ReadingSeries(
        1, 1, "t", tuple(HourlyReading(T0 + H * i, pm2_5=float(i)) for i in range(72))
    )
    window = s.hourly_until(T0 + 40 * H + timedelta(minutes=59))  # floors to hour 40
    assert set(window) == set(Pollutant)
    assert window[Pollutant.PM25] == [float(i) for i in range(17, 41)]
    assert all(len(v) == 24 for v in window.values())


def test_hourly_until_pads_hours_beyond_data_with_none():
    s = series(30, pm2_5=50.0)  # covers T0 .. T0+29h
    window = s.hourly_until(T0 + 35 * H)  # data is 6 hours stale
    assert window[Pollutant.PM25] == [50.0] * 18 + [None] * 6


def test_hourly_until_before_data_is_all_missing():
    window = series(24, pm2_5=50.0).hourly_until(T0 - H)
    assert window[Pollutant.PM25] == [None] * 24


def test_hourly_until_accepts_other_timezones_and_rejects_naive():
    s = series(48, pm2_5=1.0)
    assert s.hourly_until((T0 + 30 * H).astimezone(IST)) == s.hourly_until(T0 + 30 * H)
    with pytest.raises(ValueError):
        s.hourly_until(datetime(2026, 10, 8, 6))


def test_series_feeds_aqi_engine_end_to_end():
    s = series(48, pm2_5=45.5, pm10=175.5, no2=20.0, o3=40.0, co=1.0, so2=10.0)
    result = aqi_from_hourly(s.hourly_until(T0 + 47 * H))
    assert result.aqi == 150
    assert result.dominant is Pollutant.PM10


def test_stale_series_becomes_insufficient_instead_of_reusing_old_data():
    s = series(24, pm2_5=45.5, pm10=175.5, no2=20.0)
    # 9 hours after the last reading only 15 of the latest 24 hours are covered (< 16).
    with pytest.raises(InsufficientDataError):
        aqi_from_hourly(s.hourly_until(T0 + 32 * H))
