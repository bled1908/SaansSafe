import { AlertTriangle, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import type { ForecastHour, ForecastPeriod, ForecastResponse } from "../api/types";
import type { ResourceState } from "../hooks/useAqi";
import { errorTitle, formatAge, formatIstTime, istDayLabel, severityMeta } from "../lib/format";

const PROVIDER_LABELS: Record<string, string> = { "open-meteo": "CAMS via Open-Meteo" };

function when(iso: string): string {
  return `${istDayLabel(iso)}, ${formatIstTime(iso)}`;
}

function span(period: ForecastPeriod): string {
  return `${formatIstTime(period.start)}–${formatIstTime(period.end)}`;
}

/** An hour's AQI exactly as the API reports it: severity dot, display value, CPCB category. */
function Reading({ hour }: { hour: ForecastHour }) {
  if (!hour.aqi || !hour.decision) return <span className="text-sm text-ink/55">No data</span>;
  return (
    <span className="inline-flex items-center gap-2">
      <span aria-hidden className={`size-2.5 shrink-0 rounded-full ${severityMeta(hour.decision.severity)?.dot ?? "bg-ink/40"}`} />
      <span className="font-mono text-lg font-semibold tabular-nums">{hour.aqi.display}</span>
      <span className="text-sm text-ink/70">{hour.aqi.category}</span>
    </span>
  );
}

function Tile({ kicker, title, children }: { kicker: string; title: string; children?: ReactNode }) {
  return (
    <div className="rounded-3xl bg-white p-5 ring-1 ring-ink/10">
      <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-brand">{kicker}</p>
      <p className="mt-1 font-display text-lg font-bold leading-snug">{title}</p>
      <div className="mt-2 space-y-1 text-sm text-ink/75">{children}</div>
    </div>
  );
}

function SummaryTiles({ data }: { data: ForecastResponse }) {
  const { best_school_period: best, next_change: change, worst } = data.summary;
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <Tile kicker="Best school window" title={best ? best.label : "No full weekday school period in range"}>
        {best?.worst && (
          <>
            <p className="font-mono text-xs text-ink/60">{span(best)} IST</p>
            <Reading hour={best.worst} />
            <p>{best.worst.decision?.headline}</p>
          </>
        )}
        <p className="text-xs text-ink/55">{data.summary.best_school_period_rule}</p>
      </Tile>
      <Tile
        kicker="Next change"
        title={
          change
            ? when(change.valid_for_hour)
            : data.coverage.complete
              ? "No change expected in the next 72 hours"
              : "No change in the available forecast"
        }
      >
        {change && (
          <>
            <Reading hour={change} />
            <p>{change.decision?.headline}</p>
          </>
        )}
      </Tile>
      <Tile kicker="Worst expected" title={worst ? when(worst.valid_for_hour) : "—"}>
        {worst && (
          <>
            <Reading hour={worst} />
            <p>{worst.decision?.headline}</p>
          </>
        )}
      </Tile>
    </div>
  );
}

/** One cell per hour, coloured by the API's policy severity. Purely a visual index. */
function HourStrip({ hours }: { hours: ForecastHour[] }) {
  const last = hours[hours.length - 1];
  return (
    <div>
      <ol aria-label={`Hourly outlook, ${hours.length} hours`} className="flex h-3 gap-px overflow-hidden rounded-full">
        {hours.map((hour) => (
          <li
            key={hour.valid_for_hour}
            data-testid="outlook-hour"
            data-severity={hour.decision?.severity ?? "none"}
            title={`${when(hour.valid_for_hour)} · ${hour.aqi ? `${hour.aqi.display} ${hour.aqi.category}` : "no data"}`}
            className={`flex-1 ${hour.decision ? (severityMeta(hour.decision.severity)?.dot ?? "bg-ink/30") : "bg-ink/10"}`}
          />
        ))}
      </ol>
      <div className="mt-1.5 flex justify-between font-mono text-[11px] uppercase tracking-wider text-ink/55">
        <span>Now</span>
        {last && <span>{when(last.valid_for_hour)}</span>}
      </div>
    </div>
  );
}

/** Presentation of the API's own school_day / school_hours flags (no client-side rules). */
function periodTag(period: ForecastPeriod): string {
  if (!period.school_day) return "Weekend · not a school day";
  return period.school_hours ? "School hours" : "Outside school hours";
}

function PeriodCards({ periods }: { periods: ForecastPeriod[] }) {
  return (
    <ul
      aria-label="School periods"
      className="-mx-4 flex snap-x scroll-px-4 gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:grid sm:scroll-px-0 sm:grid-cols-3 sm:overflow-visible sm:px-0 lg:grid-cols-5"
    >
      {periods.map((period) => (
        <li
          key={period.start}
          data-testid="outlook-period"
          className={`w-60 shrink-0 snap-start rounded-2xl p-4 ring-1 ring-ink/10 sm:w-auto ${period.school_hours ? "bg-white" : "bg-ink/[0.04]"}`}
        >
          <p className="font-display font-bold leading-tight">{period.label}</p>
          <p className="font-mono text-[11px] text-ink/55">
            {span(period)} IST{period.partial && " · partial"}
          </p>
          <p className="mt-1 font-mono text-[11px] uppercase tracking-wider text-ink/55">
            {periodTag(period)}
          </p>
          {period.worst && (
            <div className="mt-3 space-y-1">
              <Reading hour={period.worst} />
              <p className="text-sm leading-snug text-ink/75">{period.worst.decision?.headline}</p>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

function OutlookBody({ data }: { data: ForecastResponse }) {
  const { freshness, coverage } = data;
  return (
    <div className="space-y-6">
      {freshness.status === "stale" && (
        <p role="alert" className="flex gap-2 rounded-2xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
          {freshness.warning ?? "Based on older forecast data."}
        </p>
      )}
      <SummaryTiles data={data} />
      <HourStrip hours={data.hours} />
      <PeriodCards periods={data.periods} />
      <p className="font-mono text-[11px] uppercase tracking-wider text-ink/55">
        Forecast/model · {PROVIDER_LABELS[data.source.provider] ?? data.source.provider} · fetched{" "}
        {formatAge(freshness.age_minutes)} · {data.policy.version}
        {!coverage.complete && ` · covers ${coverage.hours} of ${coverage.requested_hours} hours`}
      </p>
    </div>
  );
}

interface Props {
  state: ResourceState<ForecastResponse>;
  onRetry: () => void;
}

/** "Next 72 hours": the backend's deterministic outlook, grouped into school periods. */
export function OutlookSection({ state, onRetry }: Props) {
  if (state.status === "idle") return null;
  return (
    <section aria-labelledby="outlook-title" className="space-y-6">
      <div>
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink/55">Plan</p>
        <h2 id="outlook-title" className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-3xl">
          Next 72 hours
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-ink/65">
          Forecast/model outlook, with the same SaansSafe school safety policy applied hour by hour.
        </p>
      </div>

      {state.status === "loading" && (
        <div aria-busy="true" aria-live="polite" className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-32 animate-pulse rounded-3xl bg-ink/[0.06]" />
            ))}
          </div>
          <div className="h-3 animate-pulse rounded-full bg-ink/[0.06]" />
          <p className="text-sm text-ink/65">
            {state.slow ? "Fetching the 72-hour outlook… this can take a few seconds." : "Loading the outlook…"}
          </p>
        </div>
      )}

      {state.status === "error" && (
        <div role="alert" className="rounded-3xl border border-rose-200 bg-white p-5">
          <p className="font-display font-bold text-rose-950">{errorTitle(state.error)}</p>
          <p className="text-sm text-rose-900">The 72-hour outlook couldn't load. Today's decision above is unaffected.</p>
          {state.error.retryable && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-full bg-ink px-4 text-sm font-semibold text-chalk focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              <RefreshCw aria-hidden className="size-4" />
              Try again
            </button>
          )}
        </div>
      )}

      {state.status === "success" && <OutlookBody data={state.data} />}
    </section>
  );
}
