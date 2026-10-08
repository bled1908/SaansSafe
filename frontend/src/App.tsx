import { useState } from "react";
import { apiRegion } from "./api/client";
import { TodayChecklist } from "./components/ActivityGuidance";
import { AppShell, type LiveInfo } from "./components/AppShell";
import { DecisionHero } from "./components/DecisionHero";
import { PollutantSection } from "./components/PollutantSection";
import { ProvenanceStrip } from "./components/ProvenanceStrip";
import { OutlookSection } from "./components/OutlookSection";
import { LocationChip, LocationOptions } from "./components/SchoolPicker";
import { Sky } from "./components/Sky";
import { SourceFooter } from "./components/SourceFooter";
import { EmptyState, ErrorState, LoadingState } from "./components/StateViews";
import { WhyDecision } from "./components/WhyDecision";
import { useAqi } from "./hooks/useAqi";
import { useForecast } from "./hooks/useForecast";
import { formatIstTime } from "./lib/format";
import type { SchoolLocation } from "./lib/locations";

const REGION = apiRegion();

export default function App() {
  const [location, setLocation] = useState<SchoolLocation | null>(null);
  const { state, retry } = useAqi(location);
  const forecast = useForecast(location); // fetched in parallel; failures never block today's decision
  const data = state.status === "success" ? state.data : undefined;
  const live: LiveInfo | null = data
    ? {
        status: data.freshness.status,
        region: REGION,
        time: `${formatIstTime(data.freshness.fetched_at)} IST`,
      }
    : null;

  return (
    <AppShell
      locationControl={<LocationChip selected={location} onSelect={setLocation} />}
      live={live}
      footer={<SourceFooter data={data} />}
    >
      <section aria-label="Today's decision" className="relative isolate overflow-hidden">
        <Sky severity={data?.decision.severity ?? null} />
        <div className="mx-auto max-w-6xl px-4 pb-12 pt-6 sm:px-6 sm:pt-12 lg:pb-16">
          {location === null && (
            <div className="grid gap-8 lg:grid-cols-12 lg:gap-12">
              <div className="lg:col-span-7">
                <EmptyState />
              </div>
              <div className="rounded-[28px] bg-white/70 p-4 ring-1 ring-white/70 backdrop-blur-xl sm:p-5 lg:col-span-5">
                <LocationOptions selected={null} onSelect={setLocation} />
              </div>
            </div>
          )}
          {location !== null && state.status === "loading" && <LoadingState slow={state.slow} />}
          {location !== null && state.status === "error" && <ErrorState error={state.error} onRetry={retry} />}
          {location !== null && data && <DecisionHero key={location.id} data={data} location={location} />}
        </div>
      </section>

      {data && (
        <>
          <ProvenanceStrip data={data} region={REGION} />
          <div className="mx-auto max-w-6xl space-y-16 px-4 py-14 sm:px-6 sm:py-20">
            <OutlookSection state={forecast.state} onRetry={forecast.retry} />
            <TodayChecklist decision={data.decision} />
            <PollutantSection data={data} />
            <WhyDecision data={data} />
          </div>
        </>
      )}
    </AppShell>
  );
}
