import { AlertTriangle, MessageSquareText, ShieldCheck } from "lucide-react";
import type { AqiResponse } from "../api/types";
import { formatHourRange, istDayLabel } from "../lib/format";
import type { SchoolLocation } from "../lib/locations";
import { ActivityPills } from "./ActivityGuidance";
import { AirInstrument } from "./AirInstrument";

interface Props {
  data: AqiResponse;
  location: SchoolLocation;
  /** Secondary action: jump to the parent notice. The decision stays the primary content. */
  onCreateNotice?: () => void;
}

/** The decision-first hero. Sits on top of the Sky band rendered by App. */
export function DecisionHero({ data, location, onCreateNotice }: Props) {
  const { decision } = data;
  const stale = decision.data_freshness.status === "stale";
  const headline = /[.!?]$/.test(decision.headline) ? decision.headline : `${decision.headline}.`;

  return (
    <div className="grid items-start gap-8 lg:grid-cols-12 lg:gap-12">
      <div className="space-y-5 lg:col-span-7">
        <div className="animate-rise space-y-1">
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink/70">
            {istDayLabel(data.valid_for_hour)} · {formatHourRange(data.valid_for_hour)} · Forecast/model
          </p>
          <p className="text-sm text-ink/70">
            {location.name}
            {location.kind === "sample" && " · example location"}
          </p>
        </div>

        {stale && (
          <div role="alert" className="flex gap-3 rounded-2xl border border-amber-300 bg-amber-50/90 p-3 text-sm text-amber-950">
            <AlertTriangle aria-hidden className="mt-0.5 size-5 shrink-0" />
            <div>
              <p className="font-semibold">Based on older data</p>
              <p>{decision.data_freshness.warning ?? "Live data could not be refreshed."}</p>
            </div>
          </div>
        )}

        <h1
          id="decision-headline"
          className="animate-rise font-display text-[2.15rem] font-extrabold leading-[1.04] tracking-tight text-balance sm:text-5xl lg:text-[3.6rem]"
        >
          {headline}
        </h1>

        <p className="max-w-xl leading-relaxed text-ink/80">{decision.short_reason}</p>
        {data.notes.map((note) => (
          <p key={note} className="max-w-xl text-sm text-ink/70">
            {note}
          </p>
        ))}

        <ActivityPills decision={decision} />

        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink/75">
          <ShieldCheck aria-hidden className="size-4 text-brand" />
          <span className="font-medium">{decision.policy.name}</span>
          <span className="font-mono text-xs">{decision.policy.version}</span>
          <span aria-hidden>·</span>
          <span>not a CPCB rule</span>
        </p>

        {onCreateNotice && (
          <button
            type="button"
            onClick={onCreateNotice}
            className="inline-flex min-h-11 items-center gap-2 rounded-full bg-white/70 px-4 text-sm font-semibold text-ink ring-1 ring-ink/15 backdrop-blur-sm hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            <MessageSquareText aria-hidden className="size-4" />
            Create parent notice
          </button>
        )}
      </div>

      <div className="lg:col-span-5 lg:pt-8">
        <AirInstrument data={data} />
      </div>
    </div>
  );
}
