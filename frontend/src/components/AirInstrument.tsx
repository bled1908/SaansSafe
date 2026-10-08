import { Clock } from "lucide-react";
import type { AqiResponse } from "../api/types";
import { POLLUTANT_META, formatAge, formatConcentration, formatSubIndex, severityMeta } from "../lib/format";

/** The hero's "air now" instrument. Every value shown is read from the API response. */
export function AirInstrument({ data }: { data: AqiResponse }) {
  const { aqi, decision, pollutants } = data;
  const dot = severityMeta(decision.severity)?.dot ?? "bg-ink/40";
  const dominant = decision.dominant_pollutant;
  const detail = pollutants[dominant.code];
  const meta = POLLUTANT_META[dominant.code];
  const stale = decision.data_freshness.status === "stale";

  return (
    <aside
      aria-label="Air now"
      className="animate-rise relative overflow-hidden rounded-[28px] border border-white/70 bg-white/70 p-5 shadow-[0_24px_60px_-32px_rgba(14,26,43,0.55)] backdrop-blur-xl sm:p-6"
    >
      <div className="flex items-center justify-between font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink/60">
        <span>Air now</span>
        <span>Forecast/model</span>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-x-5 gap-y-2">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink/55">AQI</p>
          <p data-testid="aqi-display" className="font-mono text-6xl font-semibold leading-none tracking-tight tabular-nums">
            {aqi.display}
          </p>
        </div>
        <div className="pb-1">
          <p className="flex items-center gap-2 font-display text-2xl font-bold leading-tight">
            <span aria-hidden className={`size-3 rounded-full ${dot}`} />
            {aqi.category}
          </p>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink/55">CPCB category</p>
        </div>
      </div>

      <div className="my-5 h-px bg-ink/10" />

      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-display text-3xl font-bold leading-none">{meta?.symbol ?? dominant.code}</p>
          <p className="mt-1 text-sm text-ink/70">{meta?.name ?? dominant.name}</p>
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink/55">Dominant</p>
        </div>
        <div className="text-right">
          {detail && (
            <p className="font-mono text-2xl font-semibold tabular-nums">
              {formatConcentration(detail.concentration)}
              <span className="ml-1 text-sm font-normal text-ink/60">{detail.unit}</span>
            </p>
          )}
          <p className="mt-1 font-mono text-xs text-ink/60">
            {detail && `${detail.averaging_hours}-hr avg · `}sub-index {formatSubIndex(dominant.sub_index, dominant.beyond_scale)}
          </p>
        </div>
      </div>

      <p className={`mt-5 flex items-center gap-2 text-sm font-medium ${stale ? "text-amber-900" : "text-ink/75"}`}>
        <Clock aria-hidden className="size-4" />
        {stale ? "Stale" : "Updated"} {formatAge(decision.data_freshness.age_minutes)}
      </p>
    </aside>
  );
}
