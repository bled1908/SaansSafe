import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { makeAqiResponse, makeForecastResponse } from "./test/fixtures";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

/** Routes fake fetches by endpoint so /aqi and /forecast can be controlled independently. */
function routedFetch(handlers: { aqi: () => Response; forecast: () => Response }) {
  return vi.fn((url: string) =>
    Promise.resolve(String(url).includes("/forecast?") ? handlers.forecast() : handlers.aqi()),
  );
}

describe("App", () => {
  it("does not fetch until a location is chosen, then shows the API decision and outlook", async () => {
    const fetchMock = routedFetch({ aqi: () => json(makeAqiResponse()), forecast: () => json(makeForecastResponse()) });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    expect(screen.getByText("Can students go outside today?")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /Delhi/ }));
    expect(await screen.findByRole("heading", { level: 1, name: /Move assembly, PE and sports indoors/ })).toBeInTheDocument();
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.filter((u) => u.includes("/aqi?lat=28.6129&lon=77.2295"))).toHaveLength(1);
    expect(urls.filter((u) => u.includes("/forecast?lat=28.6129&lon=77.2295"))).toHaveLength(1);
    expect(screen.getByTestId("sky")).toHaveAttribute("data-sky", "high"); // from decision.severity
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Location: Delhi/ })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Next 72 hours" })).toBeInTheDocument();
    expect(screen.getAllByTestId("outlook-hour")).toHaveLength(73);
    expect(document.body.textContent).not.toContain("CPCB AQI");
  });

  it("shows a retryable error and recovers on retry", async () => {
    let aqiCalls = 0;
    const fetchMock = routedFetch({
      aqi: () => (++aqiCalls === 1 ? json({ error: { code: "upstream_unavailable", message: "down" } }, 503) : json(makeAqiResponse())),
      forecast: () => json(makeForecastResponse()),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Mumbai/ }));
    expect(await screen.findByText("Air-quality data is temporarily unavailable")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Move assembly, PE and sports indoors");
    expect(aqiCalls).toBe(2);
  });

  it("keeps today's decision visible when only the outlook fails", async () => {
    vi.stubGlobal(
      "fetch",
      routedFetch({ aqi: () => json(makeAqiResponse()), forecast: () => json({ error: { code: "internal_error", message: "x" } }, 500) }),
    );
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Delhi/ }));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Move assembly, PE and sports indoors");
    expect(await screen.findByText(/The 72-hour outlook couldn't load/)).toBeInTheDocument();
  });
});
