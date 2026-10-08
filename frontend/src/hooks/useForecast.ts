import { fetchForecast } from "../api/client";
import type { Coordinates, ForecastResponse } from "../api/types";
import { type ResourceState, useCoordsResource } from "./useAqi";

/** Fetches the backend's deterministic 72-hour outlook for the selected coordinates. */
export function useForecast(coords: Coordinates | null): {
  state: ResourceState<ForecastResponse>;
  retry: () => void;
} {
  return useCoordsResource(coords, fetchForecast);
}
