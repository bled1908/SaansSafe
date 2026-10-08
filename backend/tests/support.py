"""Shared fakes and factories for backend tests. No network, no AWS."""

from datetime import UTC, datetime, timedelta

from saanssafe.readings import HourlyReading, ReadingSeries

T0 = datetime(2026, 10, 7, tzinfo=UTC)
H = timedelta(hours=1)
NOW = T0 + 30 * H + timedelta(minutes=25)  # 2026-10-08 06:25 UTC

# Default concentrations -> PM10 sub-index 150 dominates (AQI 150, Moderate)
DEFAULT_VALUES = {"pm2_5": 45.5, "pm10": 175.5, "no2": 20.0, "so2": 10.0, "o3": 40.0, "co": 1.5}


def make_series(hours=96, start=T0, lat=28.6, lon=77.2, source="open-meteo", **values):
    vals = {**DEFAULT_VALUES, **values}
    readings = tuple(HourlyReading(start + H * i, **vals) for i in range(hours))
    return ReadingSeries(lat, lon, source, readings)


class FakeProvider:
    name = "open-meteo"

    def __init__(self, series=None, error=None):
        self.series = make_series() if series is None else series
        self.error = error
        self.calls = []

    def fetch_hourly(self, latitude, longitude):
        self.calls.append((latitude, longitude))
        if self.error:
            raise self.error
        return self.series


class FakeCache:
    def __init__(self, entries=None, get_error=None, put_error=None):
        self.entries = dict(entries or {})
        self.get_error = get_error
        self.put_error = put_error
        self.puts = []

    def get(self, key):
        if self.get_error:
            raise self.get_error
        return self.entries.get(key)

    def put(self, key, cached):
        self.puts.append((key, cached))
        if self.put_error:
            raise self.put_error
        self.entries[key] = cached


class FakeDynamoClient:
    def __init__(self, item=None, error=None):
        self.item = item
        self.error = error
        self.calls = []

    def get_item(self, **kwargs):
        self.calls.append(("get_item", kwargs))
        if self.error:
            raise self.error
        return {"Item": self.item} if self.item else {}

    def put_item(self, **kwargs):
        self.calls.append(("put_item", kwargs))
        if self.error:
            raise self.error
        self.item = kwargs["Item"]
        return {}
