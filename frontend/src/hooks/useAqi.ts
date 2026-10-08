import { useCallback, useEffect, useState } from "react";
import { ApiError, fetchAqi } from "../api/client";
import type { AqiResponse, Coordinates } from "../api/types";

export const SLOW_AFTER_MS = 1_500;

export type AqiState =
  | { status: "idle" }
  | { status: "loading"; slow: boolean }
  | { status: "success"; data: AqiResponse }
  | { status: "error"; error: ApiError };

/** Fetches /aqi for the selected coordinates. Does nothing until coordinates exist. */
export function useAqi(coords: Coordinates | null): { state: AqiState; retry: () => void } {
  const [state, setState] = useState<AqiState>({ status: "idle" });
  const [attempt, setAttempt] = useState(0);
  const lat = coords?.lat;
  const lon = coords?.lon;

  useEffect(() => {
    if (lat === undefined || lon === undefined) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ status: "loading", slow: false });
    const slowTimer = setTimeout(
      () => setState((s) => (s.status === "loading" ? { status: "loading", slow: true } : s)),
      SLOW_AFTER_MS,
    );

    fetchAqi({ lat, lon }, { signal: controller.signal })
      .then((data) => setState({ status: "success", data }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return; // superseded by a newer request
        const error =
          err instanceof ApiError ? err : new ApiError("network", "Something went wrong.");
        setState({ status: "error", error });
      })
      .finally(() => clearTimeout(slowTimer));

    return () => {
      clearTimeout(slowTimer);
      controller.abort();
    };
  }, [lat, lon, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, retry };
}
