/**
 * Types mirroring the deployed GET /aqi contract (backend/src/saanssafe/api.py).
 * The API is the source of truth: the frontend never calculates AQI, categories,
 * severity or school actions.
 */

export type Severity = "minimal" | "low" | "moderate" | "high" | "very_high" | "critical";

export type SchoolAction =
  | "normal_outdoor_activities"
  | "outdoor_ok_protect_sensitive_students"
  | "reduce_outdoor_exertion"
  | "move_strenuous_activities_indoors"
  | "suspend_outdoor_activities";

export type ActivityKey = "morning_assembly" | "pe_and_sports" | "recess_and_breaks";

export type Guidance = "allowed" | "limited" | "move_indoors";

export type PollutantCode = "pm2_5" | "pm10" | "no2" | "so2" | "o3" | "co" | "nh3";

export type CategoryLabel =
  | "Good"
  | "Satisfactory"
  | "Moderate"
  | "Poor"
  | "Very Poor"
  | "Severe";

export interface Coordinates {
  lat: number;
  lon: number;
}

export interface PollutantDetail {
  sub_index: number;
  beyond_scale: boolean;
  concentration: number;
  unit: string;
  averaging_hours: number;
}

export interface Freshness {
  status: "fresh" | "stale";
  cache: "hit" | "miss" | "refreshed" | "stale_fallback" | "bypassed";
  fetched_at: string;
  age_minutes: number;
  warning: string | null;
}

export interface Decision {
  action: SchoolAction;
  severity: Severity;
  headline: string;
  short_reason: string;
  recommendations: string[];
  activities: Record<ActivityKey, Guidance>;
  aqi_context: {
    value: number;
    display: string; // "401+" beyond the published scale; always display this
    beyond_scale: boolean;
    category: CategoryLabel;
    data_type: "forecast_model";
  };
  cpcb_health_statement: { category: CategoryLabel; text: string; source: string };
  dominant_pollutant: {
    code: PollutantCode;
    name: string;
    sub_index: number;
    beyond_scale: boolean;
  };
  policy: { name: string; version: string; basis: string };
  data_freshness: { status: "fresh" | "stale"; age_minutes: number; warning: string | null };
}

export interface AqiResponse {
  data_type: "forecast_model";
  method: string;
  disclaimer: string;
  valid_for_hour: string; // ISO 8601 UTC, start of the hour
  location: { requested: Coordinates; query: Coordinates; model_grid: Coordinates };
  aqi: {
    value: number; // never display directly; use `display`
    display: string;
    beyond_scale: boolean;
    category: CategoryLabel;
    health_impact: string;
    dominant_pollutant: PollutantCode;
  };
  pollutants: Partial<Record<PollutantCode, PollutantDetail>>;
  freshness: Freshness;
  source: { provider: string; attribution: string };
  notes: string[];
  decision: Decision;
}
