import type { AqiResponse } from "../api/types";

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
