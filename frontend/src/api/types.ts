/**
 * Types mirroring the GET /aqi, GET /forecast and POST /notice contracts
 * (backend/src/saanssafe/api.py, notice_api.py).
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

/** One hour of GET /forecast. Null fields mean the backend had too little data for that hour. */
export interface ForecastHour {
  valid_for_hour: string;
  aqi: { value: number; display: string; beyond_scale: boolean; category: CategoryLabel } | null;
  dominant_pollutant: { code: PollutantCode; name: string; sub_index: number; beyond_scale: boolean } | null;
  decision: { action: SchoolAction; severity: Severity; headline: string; restricted: boolean } | null;
}

/** A school-facing period (IST morning / afternoon / night) computed by the backend. */
export interface ForecastPeriod {
  label: string;
  part: "morning" | "afternoon" | "night";
  date: string;
  start: string;
  end: string;
  hours: number;
  school_hours: boolean;
  school_day: boolean; // v1: Monday–Friday (IST date), decided by the backend
  partial: boolean;
  worst: ForecastHour | null;
}

export interface ForecastResponse {
  data_type: "forecast_model";
  method: string;
  disclaimer: string;
  timezone: string;
  location: { requested: Coordinates; query: Coordinates; model_grid: Coordinates };
  coverage: { start: string; end: string; hours: number; requested_hours: number; complete: boolean };
  hours: ForecastHour[];
  periods: ForecastPeriod[];
  summary: {
    now: ForecastHour | null;
    worst: ForecastHour | null;
    next_change: ForecastHour | null;
    first_restricted: ForecastHour | null;
    best_school_period: ForecastPeriod | null;
    best_school_period_rule: string;
  };
  policy: { name: string; version: string; basis: string };
  freshness: Freshness;
  source: { provider: string; attribution: string };
}

export type NoticeLanguage = "en" | "hi";

export interface NoticeRequest extends Coordinates {
  language: NoticeLanguage;
  school_name?: string;
}

/** POST /notice: a parent notice written from the backend's verified decision. */
export interface NoticeResponse {
  data_type: "forecast_model";
  language: NoticeLanguage;
  school_name: string | null;
  notice: { title: string; body: string; key_points: string[]; sign_off: string };
  /** Fixed text, never AI-written: verbatim CPCB statement and the disclaimers. */
  footer: { health_label: string; health_statement: string; health_source: string; disclaimer: string };
  share_text: string;
  generated_by: string; // "template" | "bedrock"
  model: string | null;
  fallback_reason: string | null;
  decision: { action: SchoolAction; severity: Severity; headline: string; policy_version: string };
  /** The facts the notice was written from (backend NoticeFacts). */
  grounding: {
    aqi_display: string;
    category: CategoryLabel;
    dominant_pollutant_name: string;
    policy_name: string;
    policy_version: string;
    [key: string]: unknown;
  };
  valid_for_hour: string;
  freshness: { status: "fresh" | "stale"; age_minutes: number; warning: string | null };
  disclaimer: string;
  cache?: string;
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
