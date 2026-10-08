import type { ApiError } from "../api/client";
import type { ActivityKey, Coordinates, Guidance, PollutantCode, Severity } from "../api/types";

const IST = "Asia/Kolkata";

const timeFormat = new Intl.DateTimeFormat("en-IN", {
  timeZone: IST,
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});

const dayFormat = new Intl.DateTimeFormat("en-IN", {
  timeZone: IST,
  weekday: "short",
  day: "numeric",
  month: "short",
});

const dateKeyFormat = new Intl.DateTimeFormat("en-CA", { timeZone: IST });

/** "4:30 pm" in IST. */
export function formatIstTime(iso: string): string {
  return timeFormat.format(new Date(iso)).toLowerCase();
}

/** "Thu, 8 Oct, 4:30–5:30 pm IST" for an hour that starts at `iso`. */
export function formatValidHour(iso: string): string {
  return `${dayFormat.format(new Date(iso))}, ${formatHourRange(iso)}`;
}

/** "4:30–5:30 pm IST" for an hour that starts at `iso`. */
export function formatHourRange(iso: string): string {
  const start = formatIstTime(iso);
  const end = formatIstTime(new Date(new Date(iso).getTime() + 3_600_000).toISOString());
  const [startTime, startSuffix] = start.split(" ");
  const sameSuffix = startSuffix !== undefined && end.endsWith(startSuffix);
  return `${sameSuffix ? startTime : start}–${end} IST`;
}

/** "Today" when the hour falls on today's IST date, otherwise "Thu, 8 Oct". */
export function istDayLabel(iso: string, now: Date = new Date()): string {
  const same = dateKeyFormat.format(new Date(iso)) === dateKeyFormat.format(now);
  return same ? "Today" : dayFormat.format(new Date(iso));
}

export function formatAge(minutes: number): string {
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min ago` : `${hours} h ago`;
}

/** "28.60°N 77.20°E" for the model grid point reported by the API. */
export function formatGrid({ lat, lon }: Coordinates): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(2)}°${ns} ${Math.abs(lon).toFixed(2)}°${ew}`;
}

/** Presentation for the API-provided severity. Never derived from AQI in the browser. */
export interface SeverityMeta {
  label: string;
  sky: "minimal" | "low" | "moderate" | "high" | "veryhigh" | "critical";
  dot: string;
}

export const SEVERITY_META: Record<Severity, SeverityMeta> = {
  minimal: { label: "Minimal", sky: "minimal", dot: "bg-sev-minimal" },
  low: { label: "Low", sky: "low", dot: "bg-sev-low" },
  moderate: { label: "Moderate", sky: "moderate", dot: "bg-sev-moderate" },
  high: { label: "High", sky: "high", dot: "bg-sev-high" },
  very_high: { label: "Very high", sky: "veryhigh", dot: "bg-sev-veryhigh" },
  critical: { label: "Critical", sky: "critical", dot: "bg-sev-critical" },
};

export function severityMeta(severity: string): SeverityMeta | undefined {
  return SEVERITY_META[severity as Severity];
}

export const ACTIVITY_LABELS: Record<ActivityKey, string> = {
  morning_assembly: "Assembly",
  pe_and_sports: "PE & sports",
  recess_and_breaks: "Recess",
};

export const ACTIVITY_ORDER: readonly ActivityKey[] = [
  "morning_assembly",
  "pe_and_sports",
  "recess_and_breaks",
];

/** Display text for the API's guidance value (the value itself comes from the API). */
export const GUIDANCE_DISPLAY: Record<Guidance, { label: string; tone: string }> = {
  allowed: { label: "Allowed", tone: "bg-emerald-50 text-emerald-900 ring-emerald-200" },
  limited: { label: "Limited", tone: "bg-amber-50 text-amber-950 ring-amber-200" },
  move_indoors: { label: "Indoors", tone: "bg-rose-50 text-rose-950 ring-rose-200" },
};

/** Plain-language names and chemical symbols for the API's pollutant codes. */
export const POLLUTANT_META: Record<PollutantCode, { name: string; symbol: string }> = {
  pm2_5: { name: "Fine particles", symbol: "PM₂.₅" },
  pm10: { name: "Coarse particles", symbol: "PM₁₀" },
  no2: { name: "Nitrogen dioxide", symbol: "NO₂" },
  so2: { name: "Sulphur dioxide", symbol: "SO₂" },
  o3: { name: "Ground-level ozone", symbol: "O₃" },
  co: { name: "Carbon monoxide", symbol: "CO" },
  nh3: { name: "Ammonia", symbol: "NH₃" },
};

/**
 * A sub-index as text; "401+" when beyond the published scale.
 * Shows the API's value as sent (already rounded to 1 dp server-side). Never re-round in
 * the browser: Math.round(162.5) = 163 would contradict the API's own AQI of 162.
 */
export function formatSubIndex(subIndex: number, beyondScale: boolean): string {
  if (beyondScale) return "401+";
  return Number.isInteger(subIndex) ? String(subIndex) : subIndex.toFixed(1);
}

export function formatConcentration(value: number): string {
  return value >= 100 ? String(Math.round(value)) : value.toFixed(value >= 10 ? 1 : 2);
}

export function errorTitle(error: ApiError): string {
  switch (error.kind) {
    case "invalid_coordinates":
      return "That location can't be used";
    case "insufficient_data":
      return "Not enough forecast data here";
    case "upstream_unavailable":
      return "Air-quality data is temporarily unavailable";
    case "upstream_rejected":
    case "upstream_invalid":
      return "The air-quality data source had a problem";
    case "offline":
      return "You're offline";
    case "network":
      return "Can't reach SaansSafe";
    case "timeout":
      return "This is taking too long";
    case "invalid_response":
      return "Unexpected response from SaansSafe";
    case "invalid_school_name":
      return "Check the school name";
    case "invalid_request":
    case "invalid_language":
    case "payload_too_large":
      return "That request couldn't be used";
    case "not_found":
      return "This feature isn't available yet";
    default:
      return "Something went wrong";
  }
}
