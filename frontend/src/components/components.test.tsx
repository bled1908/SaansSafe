import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { SAMPLE_LOCATIONS } from "../lib/locations";
import { makeAqiResponse, makeSevereResponse, makeStaleResponse } from "../test/fixtures";
import { ActivityPills, TodayChecklist } from "./ActivityGuidance";
import { AppShell } from "./AppShell";
import { DecisionHero } from "./DecisionHero";
import { ErrorState } from "./StateViews";

const DELHI = SAMPLE_LOCATIONS[0]!;

describe("DecisionHero", () => {
  it("leads with the decision headline and shows API context", () => {
    render(<DecisionHero data={makeAqiResponse()} location={DELHI} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Move assembly, PE and sports indoors.");
    expect(screen.getByTestId("aqi-display")).toHaveTextContent("242");
    expect(screen.getByText("Poor")).toBeInTheDocument();
    expect(screen.getByText("CPCB category")).toBeInTheDocument();
    expect(screen.getByText("O₃")).toBeInTheDocument();
    expect(screen.getByText("Ground-level ozone")).toBeInTheDocument();
    expect(screen.getByText(/^185/)).toBeInTheDocument();
    expect(screen.getByText(/8-hr avg · sub-index 242/)).toBeInTheDocument();
    expect(screen.getAllByText(/Forecast\/model/i).length).toBeGreaterThan(0);
    expect(screen.getByText("SaansSafe school safety policy")).toBeInTheDocument();
    expect(screen.getByText("saanssafe-school-v1")).toBeInTheDocument();
    expect(screen.getByText("not a CPCB rule")).toBeInTheDocument();
    expect(screen.getByText(/Updated 33 min ago/)).toBeInTheDocument();
    expect(screen.getByText(/Delhi · example location/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders 401+ verbatim and never as a plain number", () => {
    render(<DecisionHero data={makeSevereResponse()} location={DELHI} />);
    expect(screen.getByTestId("aqi-display")).toHaveTextContent(/^401\+$/);
    expect(screen.getByText(/sub-index 401\+/)).toBeInTheDocument();
    expect(screen.getByText(/no exact AQI above 401 is given/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Suspend all outdoor activities");
  });

  it("shows the stale warning prominently", () => {
    render(<DecisionHero data={makeStaleResponse()} location={DELHI} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Based on older data");
    expect(alert).toHaveTextContent("fetched 95 minutes ago");
    expect(screen.getByText(/Stale 1 h 35 min ago/)).toBeInTheDocument();
  });

  it("never uses the phrase 'CPCB AQI'", () => {
    const { container } = render(<DecisionHero data={makeAqiResponse()} location={DELHI} />);
    expect(container.textContent).not.toContain("CPCB AQI");
  });
});

describe("ActivityPills and TodayChecklist", () => {
  it("renders each activity status straight from decision.activities", () => {
    render(<ActivityPills decision={makeAqiResponse().decision} />);
    expect(within(screen.getByTestId("activity-morning_assembly")).getByText("Indoors")).toBeInTheDocument();
    expect(within(screen.getByTestId("activity-pe_and_sports")).getByText("Indoors")).toBeInTheDocument();
    expect(within(screen.getByTestId("activity-recess_and_breaks")).getByText("Limited")).toBeInTheDocument();
  });

  it("renders allowed statuses and the recommendations checklist", () => {
    const decision = {
      ...makeAqiResponse().decision,
      activities: { morning_assembly: "allowed", pe_and_sports: "allowed", recess_and_breaks: "allowed" } as const,
      recommendations: ["Outdoor assembly, PE, sports and recess can go ahead as normal."],
    };
    render(
      <>
        <ActivityPills decision={decision} />
        <TodayChecklist decision={decision} />
      </>,
    );
    expect(screen.getAllByText("Allowed")).toHaveLength(3);
    expect(screen.getByText("Outdoor assembly, PE, sports and recess can go ahead as normal.")).toBeInTheDocument();
    expect(screen.getByText("01")).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("shows the error and retries", async () => {
    const onRetry = vi.fn();
    const error = new ApiError("upstream_unavailable", "The air-quality data source is temporarily unavailable.", 503, 60);
    render(<ErrorState error={error} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Air-quality data is temporarily unavailable");
    expect(screen.getByText(/about 60 seconds/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("hides retry for non-retryable errors", () => {
    render(<ErrorState error={new ApiError("invalid_coordinates", "bad", 400)} onRetry={() => {}} />);
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });
});

describe("AppShell live indicator", () => {
  it("shows the current IST time, advances every minute and clears its timer on unmount", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-09T04:23:40Z")); // 9:53 am IST
    try {
      const { unmount } = render(
        <AppShell locationControl={null} live={{ status: "fresh", region: "ap-south-1" }} footer={null}>
          {null}
        </AppShell>,
      );
      const banner = screen.getByRole("banner");
      expect(banner).toHaveTextContent("Fresh· ap-south-1· 9:53 am IST");
      expect(within(banner).queryByText("Live")).not.toBeInTheDocument();

      act(() => vi.advanceTimersByTime(20_000)); // reaches 9:54:00
      expect(banner).toHaveTextContent("9:54 am IST");
      act(() => vi.advanceTimersByTime(60_000));
      expect(banner).toHaveTextContent("9:55 am IST");

      unmount();
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("labels stale data as stale", () => {
    render(
      <AppShell locationControl={null} live={{ status: "stale", region: null }} footer={null}>
        {null}
      </AppShell>,
    );
    expect(screen.getByRole("banner")).toHaveTextContent("Stale");
  });
});
