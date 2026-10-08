import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError, fetchForecast, isForecastResponse } from "../api/client";
import { makeForecastResponse } from "../test/fixtures";
import { OutlookSection } from "./OutlookSection";

const success = (data = makeForecastResponse()) => ({ status: "success" as const, data });

describe("OutlookSection", () => {
  it("renders nothing before a location is chosen", () => {
    const { container } = render(<OutlookSection state={{ status: "idle" }} onRetry={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a loading state with a slow-load message", () => {
    render(<OutlookSection state={{ status: "loading", slow: true }} onRetry={() => {}} />);
    expect(screen.getByText(/Fetching the 72-hour outlook/)).toBeInTheDocument();
    expect(document.querySelector("[aria-busy=true]")).not.toBeNull();
  });

  it("summarises the best school window, next change and worst period from the API", () => {
    render(<OutlookSection state={success()} onRetry={() => {}} />);
    expect(screen.getByRole("heading", { name: "Next 72 hours" })).toBeInTheDocument();
    const best = screen.getByText("Best school window").parentElement!;
    expect(within(best).getByText("This afternoon")).toBeInTheDocument();
    expect(within(best).getByText("150")).toBeInTheDocument();
    const change = screen.getByText("Next change").parentElement!;
    expect(within(change).getByText("248")).toBeInTheDocument();
    expect(within(change).getByText("Move assembly, PE and sports indoors")).toBeInTheDocument();
    const worst = screen.getByText("Worst expected").parentElement!;
    expect(within(worst).getByText("401+")).toBeInTheDocument();
    expect(within(worst).getByText("Severe")).toBeInTheDocument();
  });

  it("states the weekday rule and handles no weekday school window", () => {
    const base = makeForecastResponse();
    render(<OutlookSection state={success({ ...base, summary: { ...base.summary, best_school_period: null } })} onRetry={() => {}} />);
    const best = screen.getByText("Best school window").parentElement!;
    expect(within(best).getByText("No full weekday school period in range")).toBeInTheDocument();
    expect(within(best).getByText(/treats Monday–Friday as school days/)).toBeInTheDocument();
  });

  it("colours the hourly strip from the API severity, in order", () => {
    render(<OutlookSection state={success()} onRetry={() => {}} />);
    const cells = screen.getAllByTestId("outlook-hour");
    expect(cells).toHaveLength(73);
    expect(cells[0]).toHaveAttribute("data-severity", "moderate");
    expect(cells[30]).toHaveAttribute("data-severity", "high");
    expect(cells[72]).toHaveAttribute("data-severity", "critical");
  });

  it("renders school periods with labels, partial flags and school-hours tags", () => {
    render(<OutlookSection state={success()} onRetry={() => {}} />);
    const periods = screen.getAllByTestId("outlook-period");
    expect(periods.map((p) => p.querySelector("p")?.textContent)).toEqual([
      "This afternoon", "Tonight", "Tomorrow morning", "Saturday morning",
    ]);
    expect(periods[1]).toHaveTextContent("Outside school hours");
    expect(periods[0]).toHaveTextContent("School hours");
    expect(periods[3]).toHaveTextContent("partial");
    expect(periods[3]).toHaveTextContent("401+");
  });

  it("tags weekend periods from the API's school_day flag, never as school hours", () => {
    const base = makeForecastResponse();
    const weekday = { ...base.periods[0]!, label: "Friday morning", school_day: true, school_hours: true };
    const weekdayNight = { ...base.periods[1]!, label: "Friday night", school_day: true, school_hours: false };
    const saturday = { ...base.periods[0]!, label: "Saturday morning", start: "2026-10-10T01:00:00Z", school_day: false, school_hours: true };
    const sundayNight = { ...base.periods[1]!, label: "Sunday night", start: "2026-10-11T13:00:00Z", school_day: false, school_hours: false };
    render(<OutlookSection state={success({ ...base, periods: [weekday, weekdayNight, saturday, sundayNight] })} onRetry={() => {}} />);
    const [fri, friNight, sat, sunNight] = screen.getAllByTestId("outlook-period");
    expect(fri).toHaveTextContent("School hours");
    expect(friNight).toHaveTextContent("Outside school hours");
    for (const weekend of [sat!, sunNight!]) {
      expect(weekend).toHaveTextContent("Weekend · not a school day");
      expect(weekend).not.toHaveTextContent("School hours");
    }
    // The Monday–Friday policy sentence is unchanged.
    expect(screen.getByText(/treats Monday–Friday as school days/)).toBeInTheDocument();
  });

  it("shows API values without recalculating them in the browser", () => {
    const base = makeForecastResponse();
    // Deliberately inconsistent payload: the UI must echo it, not "correct" it.
    const odd = { ...base.hours[0]!, aqi: { value: 10, display: "10", beyond_scale: false, category: "Severe" as const } };
    const data = { ...base, summary: { ...base.summary, worst: odd } };
    render(<OutlookSection state={success(data)} onRetry={() => {}} />);
    const worst = screen.getByText("Worst expected").parentElement!;
    expect(within(worst).getByText("10")).toBeInTheDocument();
    expect(within(worst).getByText("Severe")).toBeInTheDocument();
  });

  it("labels the data as forecast/model with source, freshness and policy version", () => {
    const { container } = render(<OutlookSection state={success()} onRetry={() => {}} />);
    expect(screen.getByText(/Forecast\/model · CAMS via Open-Meteo · fetched 12 min ago · saanssafe-school-v1/)).toBeInTheDocument();
    expect(container.textContent).not.toContain("CPCB AQI");
  });

  it("flags partial coverage and stale data honestly", () => {
    const base = makeForecastResponse();
    const data = {
      ...base,
      coverage: { ...base.coverage, hours: 66, complete: false },
      freshness: { ...base.freshness, status: "stale" as const, cache: "stale_fallback" as const, warning: "Showing forecast data fetched 95 minutes ago." },
      summary: { ...base.summary, next_change: null },
    };
    render(<OutlookSection state={success(data)} onRetry={() => {}} />);
    expect(screen.getByText(/covers 66 of 73 hours/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("fetched 95 minutes ago");
    expect(screen.getByText("No change in the available forecast")).toBeInTheDocument();
  });

  it("shows a contained error with retry", async () => {
    const onRetry = vi.fn();
    render(
      <OutlookSection state={{ status: "error", error: new ApiError("upstream_unavailable", "down", 503) }} onRetry={onRetry} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Today's decision above is unaffected");
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("fetchForecast", () => {
  it("calls /forecast and validates the contract", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify(makeForecastResponse()), { status: 200 }));
    const data = await fetchForecast({ lat: 28.6129, lon: 77.2295 }, { baseUrl: "https://api.test", fetchImpl });
    expect(fetchImpl).toHaveBeenCalledWith("https://api.test/forecast?lat=28.6129&lon=77.2295", expect.anything());
    expect(data.coverage.hours).toBe(73);
  });

  it("rejects payloads that are not forecast/model outlooks", async () => {
    expect(isForecastResponse({ ...makeForecastResponse(), data_type: "station" })).toBe(false);
    expect(isForecastResponse({ ...makeForecastResponse(), hours: [] })).toBe(false);
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    await expect(fetchForecast({ lat: 1, lon: 1 }, { baseUrl: "https://api.test", fetchImpl })).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });
});
