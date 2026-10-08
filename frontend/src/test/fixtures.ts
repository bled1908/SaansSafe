import type {
  AqiResponse,
  CategoryLabel,
  ForecastHour,
  ForecastPeriod,
  ForecastResponse,
  SchoolAction,
  Severity,
} from "../api/types";

/**
 * TEST-ONLY fixture with the exact shape of the deployed /aqi response
 * (values modelled on a live Delhi response). Never used by the app itself.
 */
export function makeAqiResponse(overrides: Partial<AqiResponse> = {}): AqiResponse {
  const base: AqiResponse = {
    data_type: "forecast_model",
    method: "Indian National AQI method (CPCB breakpoints) applied to CAMS model forecast data",
    disclaimer:
      "Forecast/model estimate for a model grid cell. Not a reading from a CPCB monitoring station.",
    valid_for_hour: "2026-10-08T11:00:00Z",
    location: {
      requested: { lat: 28.6139, lon: 77.209 },
      query: { lat: 28.61, lon: 77.21 },
      model_grid: { lat: 28.599998, lon: 77.20001 },
    },
    aqi: {
      value: 242,
      display: "242",
      beyond_scale: false,
      category: "Poor",
      health_impact:
        "May cause breathing discomfort to people on prolonged exposure and discomfort to people with heart disease with short exposure",
      dominant_pollutant: "o3",
    },
    pollutants: {
      o3: { sub_index: 242, beyond_scale: false, concentration: 185.4, unit: "µg/m³", averaging_hours: 8 },
      pm2_5: { sub_index: 193.2, beyond_scale: false, concentration: 88, unit: "µg/m³", averaging_hours: 24 },
    },
    freshness: {
      status: "fresh",
      cache: "hit",
      fetched_at: "2026-10-08T11:20:32Z",
      age_minutes: 33,
      warning: null,
    },
    source: {
      provider: "open-meteo",
      attribution:
        "Air quality data: Open-Meteo.com, based on CAMS (Copernicus Atmosphere Monitoring Service)",
    },
    notes: [],
    decision: {
      action: "move_strenuous_activities_indoors",
      severity: "high",
      headline: "Move assembly, PE and sports indoors",
      short_reason:
        "Forecast/model AQI 242 is Poor. Main pollutant: O3 (ground-level ozone), sub-index 242. Action per the SaansSafe school safety policy (not a CPCB rule).",
      recommendations: [
        "Hold assembly indoors.",
        "Move strenuous activities, including PE and sports, indoors and postpone outdoor matches.",
        "Allow students to rest if they feel unwell.",
      ],
      activities: {
        morning_assembly: "move_indoors",
        pe_and_sports: "move_indoors",
        recess_and_breaks: "limited",
      },
      aqi_context: { value: 242, display: "242", beyond_scale: false, category: "Poor", data_type: "forecast_model" },
      cpcb_health_statement: {
        category: "Poor",
        text: "May cause breathing discomfort to people on prolonged exposure and discomfort to people with heart disease with short exposure",
        source: "CPCB National AQI report CUPS/82/2014-15, Table 3.12",
      },
      dominant_pollutant: { code: "o3", name: "O3 (ground-level ozone)", sub_index: 242, beyond_scale: false },
      policy: {
        name: "SaansSafe school safety policy",
        version: "saanssafe-school-v1",
        basis:
          "SaansSafe school safety policy (a product policy, not a CPCB rule), applied to the CPCB category of a forecast/model AQI. Not medical advice.",
      },
      data_freshness: { status: "fresh", age_minutes: 33, warning: null },
    },
  };
  return { ...base, ...overrides };
}

export function makeSevereResponse(): AqiResponse {
  const base = makeAqiResponse();
  return {
    ...base,
    aqi: { ...base.aqi, value: 401, display: "401+", beyond_scale: true, category: "Severe", dominant_pollutant: "pm2_5" },
    pollutants: {
      pm2_5: { sub_index: 401, beyond_scale: true, concentration: 300, unit: "µg/m³", averaging_hours: 24 },
      o3: { sub_index: 120, beyond_scale: false, concentration: 120, unit: "µg/m³", averaging_hours: 8 },
    },
    notes: [
      "At or above CPCB's published Severe threshold. CPCB publishes no upper concentration for Severe, so no exact AQI above 401 is given.",
    ],
    decision: {
      ...base.decision,
      action: "suspend_outdoor_activities",
      severity: "critical",
      headline: "Suspend all outdoor activities",
      activities: { morning_assembly: "move_indoors", pe_and_sports: "move_indoors", recess_and_breaks: "move_indoors" },
      aqi_context: { value: 401, display: "401+", beyond_scale: true, category: "Severe", data_type: "forecast_model" },
      dominant_pollutant: { code: "pm2_5", name: "PM2.5 (fine particulate matter)", sub_index: 401, beyond_scale: true },
    },
  };
}

export function makeStaleResponse(): AqiResponse {
  const base = makeAqiResponse();
  const warning = "Live data refresh failed (ProviderUnavailableError). Showing forecast data fetched 95 minutes ago.";
  return {
    ...base,
    freshness: { ...base.freshness, status: "stale", cache: "stale_fallback", age_minutes: 95, warning },
    decision: { ...base.decision, data_freshness: { status: "stale", age_minutes: 95, warning } },
  };
}

type Tier = [display: string, value: number, category: CategoryLabel, severity: Severity, action: SchoolAction, headline: string];

const MODERATE: Tier = ["150", 150, "Moderate", "moderate", "reduce_outdoor_exertion", "Reduce strenuous outdoor activity"];
const POOR: Tier = ["248", 248, "Poor", "high", "move_strenuous_activities_indoors", "Move assembly, PE and sports indoors"];
const SEVERE: Tier = ["401+", 401, "Severe", "critical", "suspend_outdoor_activities", "Suspend all outdoor activities"];

function forecastHour(iso: string, [display, value, category, severity, action, headline]: Tier): ForecastHour {
  return {
    valid_for_hour: iso,
    aqi: { value, display, beyond_scale: display === "401+", category },
    dominant_pollutant: { code: "pm2_5", name: "PM2.5 (fine particulate matter)", sub_index: value, beyond_scale: display === "401+" },
    decision: { action, severity, headline, restricted: true },
  };
}

/**
 * TEST-ONLY fixture shaped like GET /forecast: 73 hours that move Moderate -> Poor -> Severe.
 * Summary fields are set the way the backend computes them for this sequence.
 */
export function makeForecastResponse(overrides: Partial<ForecastResponse> = {}): ForecastResponse {
  const start = Date.parse("2026-10-08T06:00:00Z");
  const iso = (i: number) => new Date(start + i * 3_600_000).toISOString().replace(".000Z", "Z");
  const hours = Array.from({ length: 73 }, (_, i) => forecastHour(iso(i), i < 30 ? MODERATE : i < 50 ? POOR : SEVERE));
  const period = (label: string, part: ForecastPeriod["part"], from: number, to: number, partial = false): ForecastPeriod => ({
    label,
    part,
    date: "2026-10-08",
    start: iso(from),
    end: iso(to),
    hours: to - from,
    school_hours: part !== "night",
    school_day: !label.startsWith("Saturday") && !label.startsWith("Sunday"),
    partial,
    worst: hours[Math.min(to - 1, 72)] ?? null,
  });
  const periods = [
    period("This afternoon", "afternoon", 1, 7),
    period("Tonight", "night", 7, 19),
    period("Tomorrow morning", "morning", 19, 25),
    period("Saturday morning", "morning", 67, 73, true),
  ];
  return {
    data_type: "forecast_model",
    method: "Indian National AQI method (CPCB breakpoints) applied to CAMS model forecast data",
    disclaimer: "Forecast/model estimate for a model grid cell. Not a reading from a CPCB monitoring station.",
    timezone: "Asia/Kolkata",
    location: {
      requested: { lat: 28.6129, lon: 77.2295 },
      query: { lat: 28.61, lon: 77.23 },
      model_grid: { lat: 28.599998, lon: 77.20001 },
    },
    coverage: { start: iso(0), end: iso(72), hours: 73, requested_hours: 73, complete: true },
    hours,
    periods,
    summary: {
      now: hours[0]!,
      worst: hours[50]!,
      next_change: hours[30]!,
      first_restricted: hours[0]!,
      best_school_period: periods[0]!,
      best_school_period_rule: "SaansSafe v1 treats Monday–Friday as school days for best-school-window selection.",
    },
    policy: {
      name: "SaansSafe school safety policy",
      version: "saanssafe-school-v1",
      basis: "SaansSafe school safety policy (a product policy, not a CPCB rule), applied to the CPCB category of a forecast/model AQI. Not medical advice.",
    },
    freshness: { status: "fresh", cache: "hit", fetched_at: "2026-10-08T06:20:00Z", age_minutes: 12, warning: null },
    source: {
      provider: "open-meteo",
      attribution: "Air quality data: Open-Meteo.com, based on CAMS (Copernicus Atmosphere Monitoring Service)",
    },
    ...overrides,
  };
}
