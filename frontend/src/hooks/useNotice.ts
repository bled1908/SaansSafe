import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, postNotice } from "../api/client";
import type { Coordinates, NoticeLanguage, NoticeResponse } from "../api/types";
import { SLOW_AFTER_MS, type ResourceState } from "./useAqi";

export interface NoticeInput {
  language: NoticeLanguage;
  schoolName: string;
}

/**
 * POST /notice for the given coordinates, only when the user asks (`generate`).
 * Aborts superseded requests, flags slow loads and supports retry of the last input.
 * Callers remount it per location (React `key`), so a notice never outlives its location.
 */
export function useNotice(coords: Coordinates | null): {
  state: ResourceState<NoticeResponse>;
  generate: (input: NoticeInput) => void;
  retry: () => void;
} {
  const [state, setState] = useState<ResourceState<NoticeResponse>>({ status: "idle" });
  const controllerRef = useRef<AbortController | null>(null);
  const lastInput = useRef<NoticeInput | null>(null);
  const lat = coords?.lat;
  const lon = coords?.lon;

  useEffect(() => () => controllerRef.current?.abort(), []);

  const generate = useCallback(
    (input: NoticeInput) => {
      if (lat === undefined || lon === undefined) return;
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      lastInput.current = input;
      setState({ status: "loading", slow: false });
      const slowTimer = setTimeout(
        () => setState((s) => (s.status === "loading" ? { status: "loading", slow: true } : s)),
        SLOW_AFTER_MS,
      );
      postNotice(
        { lat, lon, language: input.language, school_name: input.schoolName },
        { signal: controller.signal },
      )
        .then((data) => {
          if (!controller.signal.aborted) setState({ status: "success", data });
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return; // superseded by a newer request
          const error = err instanceof ApiError ? err : new ApiError("network", "Something went wrong.");
          setState({ status: "error", error });
        })
        .finally(() => clearTimeout(slowTimer));
    },
    [lat, lon],
  );

  const retry = useCallback(() => {
    if (lastInput.current) generate(lastInput.current);
  }, [generate]);

  return { state, generate, retry };
}
