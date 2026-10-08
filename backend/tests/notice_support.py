"""Shared helpers for Parent Notice tests. Builds real /aqi and /forecast bodies from fakes."""

from support import DEFAULT_VALUES, NOW, T0, FakeCache, FakeProvider, H, make_series

from saanssafe import api
from saanssafe.notice_facts import build_notice_facts
from saanssafe.readings import HourlyReading, ReadingSeries
from saanssafe.service import AqiService

LAT, LON = 28.6129, 77.2295
SERIES_KEY = "open-meteo#28.61#77.23"

# Concentrations giving each CPCB category (PM10 dominates; see test_aqi breakpoints).
LEVELS = {
    "Good": dict(pm10=40, pm2_5=20, co=0.5),
    "Satisfactory": dict(pm10=80, pm2_5=20, co=0.5),
    "Moderate": {},
    "Poor": dict(pm10=300),
    "Very Poor": dict(pm10=400),
    "Severe": dict(pm10=500),
}
# A school action for every category: Very Poor and Severe share "suspend".
ACTION_FOR = {
    "Good": "normal_outdoor_activities",
    "Satisfactory": "outdoor_ok_protect_sensitive_students",
    "Moderate": "reduce_outdoor_exertion",
    "Poor": "move_strenuous_activities_indoors",
    "Very Poor": "suspend_outdoor_activities",
    "Severe": "suspend_outdoor_activities",
}


def full_series(level="Poor", hours=110):
    """Constant air quality, long enough for a complete 72-hour outlook from NOW."""
    return make_series(hours=hours, **LEVELS[level])


def changing_series(before="Poor", after="Good", switch=T0 + 40 * H, hours=110):
    """Air quality that changes at `switch`, so the outlook has a next change."""
    readings = tuple(
        HourlyReading(
            T0 + H * i,
            **{**DEFAULT_VALUES, **LEVELS[before if T0 + H * i < switch else after]},
        )
        for i in range(hours)
    )
    return ReadingSeries(28.6, 77.2, "open-meteo", readings)


def aqi_service(series=None, provider=None, cache=None, clock=lambda: NOW):
    return AqiService(provider or FakeProvider(series or full_series()), cache or FakeCache(), clock=clock)


def bodies(series=None, service=None):
    svc = service or aqi_service(series)
    return (
        api.report_body(svc.current_aqi(LAT, LON)),
        api.forecast_body(svc.forecast(LAT, LON)),
    )


def facts_for(level="Poor", language="en", school_name=None, series=None):
    aqi, forecast = bodies(series or full_series(level))
    return build_notice_facts(aqi, forecast, language, school_name)
