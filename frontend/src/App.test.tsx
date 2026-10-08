import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { makeAqiResponse } from "./test/fixtures";

describe("App", () => {
  it("does not fetch until a location is chosen, then shows the API decision", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(makeAqiResponse()), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    expect(screen.getByText("Can students go outside today?")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /Delhi/ }));
    expect(await screen.findByRole("heading", { level: 1, name: /Move assembly, PE and sports indoors/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/aqi?lat=28.6129&lon=77.2295");
    expect(screen.getByTestId("sky")).toHaveAttribute("data-sky", "high"); // from decision.severity
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Location: Delhi/ })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("CPCB AQI");
  });

  it("shows a retryable error and recovers on retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { code: "upstream_unavailable", message: "down" } }), { status: 503 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(makeAqiResponse()), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Mumbai/ }));
    expect(await screen.findByText("Air-quality data is temporarily unavailable")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Move assembly, PE and sports indoors");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
