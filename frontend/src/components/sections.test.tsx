import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { apiRegion } from "../api/client";
import { makeAqiResponse, makeSevereResponse } from "../test/fixtures";
import { PollutantSection } from "./PollutantSection";
import { ProvenanceStrip } from "./ProvenanceStrip";
import { LocationChip } from "./SchoolPicker";
import { Sky } from "./Sky";
import { WhyDecision } from "./WhyDecision";

describe("Sky", () => {
  it.each([
    ["minimal", "minimal"],
    ["moderate", "moderate"],
    ["high", "high"],
    ["very_high", "veryhigh"],
    ["critical", "critical"],
  ])("uses the API severity %s for the atmosphere", (severity, sky) => {
    render(<Sky severity={severity} />);
    expect(screen.getByTestId("sky")).toHaveAttribute("data-sky", sky);
  });

  it("is neutral without data or for unknown severities", () => {
    const { rerender } = render(<Sky severity={null} />);
    expect(screen.getByTestId("sky")).toHaveAttribute("data-sky", "neutral");
    rerender(<Sky severity="unexpected" />);
    expect(screen.getByTestId("sky")).toHaveAttribute("data-sky", "neutral");
  });
});

describe("ProvenanceStrip", () => {
  it("shows only API-provided provenance values", () => {
    render(<ProvenanceStrip data={makeAqiResponse()} region="ap-south-1" />);
    expect(screen.getByText("CAMS via Open-Meteo")).toBeInTheDocument();
    expect(screen.getByText("28.60°N 77.20°E")).toBeInTheDocument();
    expect(screen.getByText("CPCB · Poor")).toBeInTheDocument();
    expect(screen.getByText("saanssafe-school-v1")).toBeInTheDocument();
    expect(screen.getByText("ap-south-1")).toBeInTheDocument();
    expect(screen.getByText("hit")).toBeInTheDocument();
  });

  it("omits the region when it isn't known", () => {
    render(<ProvenanceStrip data={makeAqiResponse()} region={null} />);
    expect(screen.queryByText("Region")).not.toBeInTheDocument();
  });

  it("derives the region only from an AWS API Gateway URL", () => {
    expect(apiRegion("https://abc.execute-api.ap-south-1.amazonaws.com")).toBe("ap-south-1");
    expect(apiRegion("http://localhost:3000")).toBeNull();
  });
});

describe("PollutantSection", () => {
  it("features the dominant pollutant with concentration, unit, window and sub-index", () => {
    render(<PollutantSection data={makeAqiResponse()} />);
    const dominant = screen.getAllByTestId("pollutant-o3")[0]!;
    expect(dominant).toHaveAttribute("data-dominant", "true");
    expect(within(dominant).getByText("O₃")).toBeInTheDocument();
    expect(within(dominant).getByText("Ground-level ozone")).toBeInTheDocument();
    expect(within(dominant).getByText(/185/)).toBeInTheDocument();
    expect(within(dominant).getByText(/8-hr avg · sub-index 242/)).toBeInTheDocument();
    expect(screen.getByTestId("pollutant-pm2_5")).toHaveTextContent("24-hr avg");
  });

  it("shows the API sub-index without re-rounding it (162.5 never becomes 163)", () => {
    const base = makeAqiResponse();
    const data = {
      ...base,
      pollutants: { ...base.pollutants, o3: { ...base.pollutants.o3!, sub_index: 162.5 } },
      decision: { ...base.decision, dominant_pollutant: { ...base.decision.dominant_pollutant, sub_index: 162.5 } },
    };
    render(<PollutantSection data={data} />);
    const dominant = screen.getAllByTestId("pollutant-o3")[0]!;
    expect(dominant).toHaveTextContent("sub-index 162.5");
    expect(dominant).not.toHaveTextContent("sub-index 163");
  });

  it("shows 401+ for a beyond-scale pollutant", () => {
    render(<PollutantSection data={makeSevereResponse()} />);
    expect(screen.getByTestId("pollutant-pm2_5")).toHaveTextContent("sub-index 401+");
  });

  it("collapses the other pollutants behind a toggle", async () => {
    render(<PollutantSection data={makeAqiResponse()} />);
    const toggle = screen.getByRole("button", { name: /show 1 other pollutants/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });
});

describe("WhyDecision", () => {
  it("separates model data, CPCB category and SaansSafe policy", () => {
    const { container } = render(<WhyDecision data={makeAqiResponse()} />);
    expect(screen.getByText("Deterministic. AI never changes this decision.")).toBeInTheDocument();
    expect(screen.getByText(/CAMS forecast via Open-Meteo/)).toBeInTheDocument();
    expect(screen.getByText("Not a CPCB station reading")).toBeInTheDocument();
    expect(screen.getByText(/May cause breathing discomfort to people on prolonged exposure/)).toBeInTheDocument();
    expect(screen.getByText("CPCB National AQI report CUPS/82/2014-15, Table 3.12")).toBeInTheDocument();
    expect(screen.getByText(/A product policy, not a CPCB rule/)).toBeInTheDocument();
    expect(screen.getByText("Move assembly, PE and sports indoors")).toBeInTheDocument();
    expect(container.textContent).not.toContain("CPCB AQI");
  });
});

describe("LocationChip", () => {
  it("opens a compact chooser and selects an example city", async () => {
    const onSelect = vi.fn();
    render(<LocationChip selected={null} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: /choose a location/i }));
    const dialog = screen.getByRole("dialog", { name: /choose a location/i });
    expect(within(dialog).getByText(/not real school records/i)).toBeInTheDocument();
    for (const city of ["Delhi", "Mumbai", "Bengaluru", "Kolkata"]) {
      expect(within(dialog).getByRole("button", { name: new RegExp(city) })).toBeInTheDocument();
    }
    await userEvent.click(within(dialog).getByRole("button", { name: /Kolkata/ }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: "kolkata", lat: 22.5726, lon: 88.3639 }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    render(<LocationChip selected={null} onSelect={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /choose a location/i }));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
