import type { Coordinates } from "../api/types";

export interface SchoolLocation extends Coordinates {
  id: string;
  name: string;
  area: string;
  kind: "sample" | "geolocation";
}

/**
 * EXAMPLE locations for demonstration (one per city, on different model grid cells).
 * These are NOT real school records: they only provide coordinates.
 * All AQI and decision data comes from the API.
 */
export const SAMPLE_LOCATIONS: readonly SchoolLocation[] = [
  { id: "delhi", name: "Delhi", area: "Central Delhi", lat: 28.6129, lon: 77.2295, kind: "sample" },
  { id: "mumbai", name: "Mumbai", area: "Central Mumbai", lat: 19.076, lon: 72.8777, kind: "sample" },
  { id: "bengaluru", name: "Bengaluru", area: "Central Bengaluru", lat: 12.9716, lon: 77.5946, kind: "sample" },
  { id: "kolkata", name: "Kolkata", area: "Central Kolkata", lat: 22.5726, lon: 88.3639, kind: "sample" },
];

/** Rounded to ~100 m: enough for a model grid lookup, without sending precise positions. */
export function locationFromPosition(lat: number, lon: number): SchoolLocation {
  const round = (v: number) => Math.round(v * 1000) / 1000;
  return {
    id: "geolocation",
    name: "Your location",
    area: `${round(lat).toFixed(3)}, ${round(lon).toFixed(3)}`,
    lat: round(lat),
    lon: round(lon),
    kind: "geolocation",
  };
}
