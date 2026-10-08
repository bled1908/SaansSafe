import type { AqiResponse, Coordinates, ForecastResponse } from "./types";

export const DEFAULT_API_BASE_URL = "https://paqffn4eq5.execute-api.ap-south-1.amazonaws.com";
export const DEFAULT_TIMEOUT_MS = 15_000;

export type ApiErrorKind =
  | "invalid_coordinates"
  | "insufficient_data"
  | "upstream_rejected"
  | "upstream_invalid"
  | "upstream_unavailable"
  | "internal_error"
  | "not_found"
  | "http_error"
  | "network"
  | "offline"
  | "timeout"
  | "invalid_response"
  | "aborted";

const KNOWN_API_CODES: ReadonlySet<string> = new Set([
  "invalid_coordinates",
  "insufficient_data",
  "upstream_rejected",
  "upstream_invalid",
  "upstream_unavailable",
  "internal_error",
]);

const RETRYABLE: ReadonlySet<ApiErrorKind> = new Set([
  "upstream_unavailable",
  "upstream_invalid",
  "internal_error",
  "http_error",
  "network",
  "offline",
  "timeout",
]);

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly retryAfterSeconds?: number;

  constructor(kind: ApiErrorKind, message: string, status?: number, retryAfterSeconds?: number) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }

  get retryable(): boolean {
    return RETRYABLE.has(this.kind);
  }
}

export interface FetchAqiOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  return (configured || DEFAULT_API_BASE_URL).replace(/\/+$/, "");
}

/** AWS region of the configured API Gateway endpoint, e.g. "ap-south-1"; null if not an AWS URL. */
export function apiRegion(baseUrl: string = apiBaseUrl()): string | null {
  return /\.execute-api\.([a-z0-9-]+)\.amazonaws\.com/.exec(baseUrl)?.[1] ?? null;
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseRetryAfter(header: string | null): number | undefined {
  if (!header) return undefined;
  const seconds = Number.parseInt(header, 10);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined;
}

/** Map a non-2xx response (either API error shape) to an ApiError. */
export function errorFromResponse(status: number, body: unknown, retryAfter?: number): ApiError {
  // SaansSafe shape: {"error": {"code", "message"}}
  if (isRecord(body) && isRecord(body.error)) {
    const code = typeof body.error.code === "string" ? body.error.code : "";
    const message =
      typeof body.error.message === "string" ? body.error.message : `Request failed (${status})`;
    const kind: ApiErrorKind = KNOWN_API_CODES.has(code) ? (code as ApiErrorKind) : "http_error";
    return new ApiError(kind, message, status, retryAfter);
  }
  // API Gateway shape: {"message": "Not Found"}
  if (status === 404) {
    const message = isRecord(body) && typeof body.message === "string" ? body.message : "Not Found";
    return new ApiError("not_found", message, status);
  }
  return new ApiError("http_error", `Request failed (${status})`, status, retryAfter);
}

/** Minimal runtime check that a 200 body has the fields the UI depends on. */
export function isAqiResponse(body: unknown): body is AqiResponse {
  if (!isRecord(body) || body.data_type !== "forecast_model") return false;
  const { aqi, decision, freshness, source } = body;
  if (!isRecord(aqi) || typeof aqi.display !== "string" || typeof aqi.category !== "string") {
    return false;
  }
  if (!isRecord(freshness) || !isRecord(source) || typeof body.valid_for_hour !== "string") {
    return false;
  }
  if (!isRecord(decision)) return false;
  return (
    typeof decision.headline === "string" &&
    typeof decision.severity === "string" &&
    Array.isArray(decision.recommendations) &&
    isRecord(decision.activities) &&
    isRecord(decision.aqi_context) &&
    isRecord(decision.dominant_pollutant) &&
    isRecord(decision.policy) &&
    isRecord(decision.data_freshness) &&
    isRecord(decision.cpcb_health_statement)
  );
}

/** Minimal runtime check for the GET /forecast fields the outlook UI depends on. */
export function isForecastResponse(body: unknown): body is ForecastResponse {
  if (!isRecord(body) || body.data_type !== "forecast_model") return false;
  const { coverage, summary, freshness, source } = body;
  return (
    Array.isArray(body.hours) &&
    body.hours.length > 0 &&
    Array.isArray(body.periods) &&
    isRecord(coverage) &&
    typeof coverage.complete === "boolean" &&
    isRecord(summary) &&
    isRecord(freshness) &&
    isRecord(source)
  );
}

export function fetchAqi(coords: Coordinates, options: FetchAqiOptions = {}): Promise<AqiResponse> {
  return requestJson("/aqi", coords, isAqiResponse, options);
}

export function fetchForecast(coords: Coordinates, options: FetchAqiOptions = {}): Promise<ForecastResponse> {
  return requestJson("/forecast", coords, isForecastResponse, options);
}

/** Shared GET with timeout, abort, error-shape mapping and a runtime contract check. */
async function requestJson<T>(
  path: string,
  { lat, lon }: Coordinates,
  validate: (body: unknown) => body is T,
  { signal, timeoutMs = DEFAULT_TIMEOUT_MS, baseUrl = apiBaseUrl(), fetchImpl = fetch }: FetchAqiOptions,
): Promise<T> {
  const url = `${baseUrl}${path}?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onAbort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener("abort", onAbort);

  let response: Response;
  let text: string;
  try {
    response = await fetchImpl(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    text = await response.text();
  } catch {
    if (timedOut) throw new ApiError("timeout", "The request took too long. Please try again.");
    if (signal?.aborted) throw new ApiError("aborted", "Request cancelled.");
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      throw new ApiError("offline", "You appear to be offline.");
    }
    throw new ApiError("network", "Could not reach the SaansSafe service.");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }

  const body = parseJson(text);
  if (!response.ok) {
    throw errorFromResponse(response.status, body, parseRetryAfter(response.headers.get("Retry-After")));
  }
  if (!validate(body)) {
    throw new ApiError("invalid_response", "The service returned an unexpected response.", response.status);
  }
  return body;
}
