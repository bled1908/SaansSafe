import { ChevronDown } from "lucide-react";
import { useState } from "react";
import type { AqiResponse, PollutantCode, PollutantDetail } from "../api/types";
import { POLLUTANT_META, formatConcentration, formatSubIndex } from "../lib/format";

interface Entry {
  code: PollutantCode;
  detail: PollutantDetail;
}

function PollutantRow({ entry }: { entry: Entry }) {
  const meta = POLLUTANT_META[entry.code];
  return (
    <li data-testid={`pollutant-${entry.code}`} className="flex items-center gap-4 border-b border-ink/10 py-3 last:border-0">
      <span className="w-14 shrink-0 font-display text-xl font-bold">{meta?.symbol ?? entry.code}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{meta?.name ?? entry.code}</span>
        <span className="block font-mono text-xs text-ink/55">{entry.detail.averaging_hours}-hr avg</span>
      </span>
      <span className="text-right font-mono text-sm tabular-nums">
        {formatConcentration(entry.detail.concentration)} <span className="text-ink/55">{entry.detail.unit}</span>
        <span className="block text-xs text-ink/55">
          sub-index {formatSubIndex(entry.detail.sub_index, entry.detail.beyond_scale)}
        </span>
      </span>
    </li>
  );
}

/** "What's in the air": the API's pollutant data, dominant pollutant first. */
export function PollutantSection({ data }: { data: AqiResponse }) {
  const [expanded, setExpanded] = useState(false);
  const dominantCode = data.decision.dominant_pollutant.code;
  const entries = (Object.entries(data.pollutants) as [PollutantCode, PollutantDetail | undefined][])
    .filter((e): e is [PollutantCode, PollutantDetail] => e[1] !== undefined)
    .map(([code, detail]) => ({ code, detail }));
  const dominant = entries.find((e) => e.code === dominantCode);
  const others = entries
    .filter((e) => e.code !== dominantCode)
    .sort((a, b) => b.detail.sub_index - a.detail.sub_index); // display order only
  const meta = POLLUTANT_META[dominantCode];

  return (
    <section aria-labelledby="air-title" className="grid gap-6 md:grid-cols-12">
      <div className="md:col-span-4">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink/55">Measure</p>
        <h2 id="air-title" className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-3xl">
          What's in the air
        </h2>
        <p className="mt-2 text-sm text-ink/65">
          Forecast/model concentrations, averaged over each pollutant's CPCB window.
        </p>
      </div>

      <div className="space-y-4 md:col-span-8">
        {dominant && (
          <div data-testid={`pollutant-${dominant.code}`} data-dominant="true" className="rounded-3xl bg-ink p-5 text-chalk sm:p-6">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-chalk/60">Dominant pollutant</p>
            <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="font-display text-5xl font-extrabold leading-none">{meta?.symbol ?? dominant.code}</p>
                <p className="mt-1 text-chalk/80">{meta?.name ?? dominant.code}</p>
              </div>
              <div className="text-right font-mono tabular-nums">
                <p className="text-3xl font-semibold">
                  {formatConcentration(dominant.detail.concentration)}
                  <span className="ml-1 text-base font-normal text-chalk/60">{dominant.detail.unit}</span>
                </p>
                <p className="text-xs text-chalk/60">
                  {dominant.detail.averaging_hours}-hr avg · sub-index{" "}
                  {formatSubIndex(dominant.detail.sub_index, dominant.detail.beyond_scale)}
                </p>
              </div>
            </div>
          </div>
        )}

        {others.length > 0 && (
          <>
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              aria-expanded={expanded}
              aria-controls="other-pollutants"
              className="flex min-h-11 w-full items-center justify-between rounded-2xl bg-white px-4 text-sm font-semibold ring-1 ring-ink/10 focus-visible:outline-2 focus-visible:outline-brand sm:hidden"
            >
              {expanded ? "Hide" : "Show"} {others.length} other pollutants
              <ChevronDown aria-hidden className={`size-4 transition-transform ${expanded ? "rotate-180" : ""}`} />
            </button>
            <ul
              id="other-pollutants"
              className={`${expanded ? "block" : "hidden"} rounded-3xl bg-white px-5 ring-1 ring-ink/10 sm:block`}
            >
              {others.map((entry) => (
                <PollutantRow key={entry.code} entry={entry} />
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
