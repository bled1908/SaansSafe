import { describe, expect, it, vi } from "vitest";
import { makeAqiResponse } from "../test/fixtures";
import { ApiError, errorFromResponse, fetchAqi, isAqiResponse } from "./client";

const BASE = "https://api.example.test";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

async function expectApiError(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (err) {
    expect(err).toBeInstanceOf(ApiError);
    return err as ApiError;
  }
  throw new Error("expected ApiError");
}

describe("fetchAqi", () => {
  it("requests /aqi with encoded coordinates and returns the typed body", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(200, makeAqiResponse()));
    const data = await fetchAqi({ lat: 28.6129, lon: 77.2295 }, { baseUrl: BASE, fetchImpl });
    expect(fetchImpl).toHaveBeenCalledWith(`${BASE}/aqi?lat=28.6129&lon=77.2295`, expect.anything());
    expect(data.decision.headline).toBe("Move assembly, PE and sports indoors");
  });

  it.each([
    [400, "invalid_coordinates"],
    [422, "insufficient_data"],
    [502, "upstream_rejected"],
    [502, "upstream_invalid"],
    [500, "internal_error"],
  ] as const)("maps SaansSafe error %i %s", async (status, code) => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(status, { error: { code, message: `msg ${code}` } }));
    const err = await expectApiError(fetchAqi({ lat: 1, lon: 1 }, { baseUrl: BASE, fetchImpl }));
    expect(err.kind).toBe(code);
    expect(err.status).toBe(status);
    expect(err.message).toBe(`msg ${code}`);
  });

  it("maps 503 upstream_unavailable with Retry-After as retryable", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse(503, { error: { code: "upstream_unavailable", message: "down" } }, { "Retry-After": "60" }),
    );
    const err = await expectApiError(fetchAqi({ lat: 1, lon: 1 }, { baseUrl: BASE, fetchImpl }));
    expect(err.kind).toBe("upstream_unavailable");
    expect(err.retryAfterSeconds).toBe(60);
    expect(err.retryable).toBe(true);
  });

  it("maps the API Gateway {message} 404 shape to not_found", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(404, { message: "Not Found" }));
    const err = await expectApiError(fetchAqi({ lat: 1, lon: 1 }, { baseUrl: BASE, fetchImpl }));
    expect(err.kind).toBe("not_found");
    expect(err.message).toBe("Not Found");
  });

  it("maps a non-JSON error body to http_error", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502 }));
    const err = await expectApiError(fetchAqi({ lat: 1, lon: 1 }, { baseUrl: BASE, fetchImpl }));
    expect(err.kind).toBe("http_error");
    expect(err.retryable).toBe(true);
  });

  it("maps network/CORS failures to network", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const err = await expectApiError(fetchAqi({ lat: 1, lon: 1 }, { baseUrl: BASE, fetchImpl }));
    expect(err.kind).toBe("network");
  });

  it("reports offline when the browser is offline", async () => {
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const err = await expectApiError(fetchAqi({ lat: 1, lon: 1 }, { baseUrl: BASE, fetchImpl }));
    expect(err.kind).toBe("offline");
  });

  it("times out slow requests", async () => {
    const fetchImpl = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        }),
    );
    const err = await expectApiError(
      fetchAqi({ lat: 1, lon: 1 }, { baseUrl: BASE, fetchImpl: fetchImpl as typeof fetch, timeoutMs: 10 }),
    );
    expect(err.kind).toBe("timeout");
  });

  it("reports caller aborts as aborted", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        }),
    );
    const pending = fetchAqi(
      { lat: 1, lon: 1 },
      { baseUrl: BASE, fetchImpl: fetchImpl as typeof fetch, signal: controller.signal },
    );
    controller.abort();
    const err = await expectApiError(pending);
    expect(err.kind).toBe("aborted");
  });

  it("rejects a 200 body that doesn't match the contract", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse(200, { status: "ok" }));
    const err = await expectApiError(fetchAqi({ lat: 1, lon: 1 }, { baseUrl: BASE, fetchImpl }));
    expect(err.kind).toBe("invalid_response");
  });
});

describe("contract helpers", () => {
  it("accepts the real response shape and rejects non-model data", () => {
    expect(isAqiResponse(makeAqiResponse())).toBe(true);
    expect(isAqiResponse({ ...makeAqiResponse(), data_type: "station" })).toBe(false);
  });

  it("treats unknown SaansSafe error codes as http_error", () => {
    expect(errorFromResponse(418, { error: { code: "teapot", message: "x" } }).kind).toBe("http_error");
  });
});
