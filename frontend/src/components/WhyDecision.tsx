import type { ReactNode } from "react";
import type { AqiResponse } from "../api/types";
import { POLLUTANT_META, formatConcentration, formatGrid, formatValidHour, severityMeta } from "../lib/format";

interface Step {
  kicker: string;
  title: string;
  body: ReactNode;
  source?: string;
}

/** Data → CPCB category → SaansSafe policy → Decision, using the API's own values. */
export function WhyDecision({ data }: { data: AqiResponse }) {
  const { decision, aqi, location } = data;
  const dominant = decision.dominant_pollutant;
  const detail = data.pollutants[dominant.code];
  const meta = POLLUTANT_META[dominant.code];

  const steps: Step[] = [
    {
      kicker: "Data",
      title: "Forecast/model air quality",
      body: (
        <>
          CAMS forecast via Open-Meteo for the model grid cell at{" "}
          <span className="font-mono">{formatGrid(location.model_grid)}</span>, valid {formatValidHour(data.valid_for_hour)}.
          {detail && (
            <>
              {" "}
              Main pollutant {meta?.symbol ?? dominant.code}: {formatConcentration(detail.concentration)} {detail.unit} (
              {detail.averaging_hours}-hr average).
            </>
          )}
        </>
      ),
      source: "Not a CPCB station reading",
    },
    {
      kicker: "CPCB category",
      title: `${aqi.display} · ${aqi.category}`,
      body: (
        <>
          <span className="block">{data.method}.</span>
          <span className="mt-2 block italic">“{decision.cpcb_health_statement.text}”</span>
        </>
      ),
      source: decision.cpcb_health_statement.source,
    },
    {
      kicker: "SaansSafe policy",
      title: decision.policy.name,
      body: (
        <>
          Maps the CPCB category to a school action. A product policy, not a CPCB rule. Version{" "}
          <span className="font-mono">{decision.policy.version}</span>.
        </>
      ),
    },
    {
      kicker: "Decision",
      title: decision.headline,
      body: <>Severity: {severityMeta(decision.severity)?.label ?? decision.severity}. The same inputs always give the same decision.</>,
    },
  ];

  return (
    <section aria-labelledby="why-title" className="grid gap-6 md:grid-cols-12">
      <div className="md:col-span-4">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink/55">Explain</p>
        <h2 id="why-title" className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-3xl">
          Why this decision?
        </h2>
        <p className="mt-3 inline-block rounded-full bg-ink px-3 py-1.5 text-sm font-semibold text-chalk">
          Deterministic. AI never changes this decision.
        </p>
      </div>
      <ol className="relative md:col-span-8">
        {steps.map((step, i) => (
          <li key={step.kicker} className="relative flex gap-4 pb-6 last:pb-0">
            {i < steps.length - 1 && <span aria-hidden className="absolute left-[15px] top-8 bottom-0 w-px bg-ink/15" />}
            <span className="relative z-10 grid size-8 shrink-0 place-items-center rounded-full bg-white font-mono text-xs font-semibold text-brand ring-1 ring-ink/15">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0 flex-1 pt-1">
              <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-brand">{step.kicker}</p>
              <p className="mt-1 font-display text-lg font-bold leading-snug">{step.title}</p>
              <p className="mt-1 text-sm leading-relaxed text-ink/75">{step.body}</p>
              {step.source && <p className="mt-2 font-mono text-[11px] uppercase tracking-wider text-ink/50">{step.source}</p>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
