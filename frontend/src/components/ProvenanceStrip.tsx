import type { ReactNode } from "react";
import type { AqiResponse } from "../api/types";
import { formatAge, formatGrid, formatIstTime } from "../lib/format";

const PROVIDER_LABELS: Record<string, string> = { "open-meteo": "CAMS via Open-Meteo" };

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-brand">{title}</p>
      <dl className="space-y-1.5">{children}</dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-dashed border-ink/10 pb-1.5 font-mono text-xs sm:justify-start">
      <dt className="uppercase tracking-wider text-ink/50 sm:w-28 sm:shrink-0">{label}</dt>
      <dd className="text-right text-ink/85 sm:text-left">{value}</dd>
    </div>
  );
}

/** Live proof: every value comes from the API response or the configured API URL. */
export function ProvenanceStrip({ data, region }: { data: AqiResponse; region: string | null }) {
  const { freshness, location, source, decision } = data;
  return (
    <section aria-label="Data provenance" className="border-y border-ink/10 bg-white/60">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 sm:grid-cols-3 sm:gap-8 sm:px-6">
        <Group title="Data">
          <Row label="Source" value={PROVIDER_LABELS[source.provider] ?? source.provider} />
          <Row label="Model grid" value={formatGrid(location.model_grid)} />
          <Row label="Fetched" value={`${formatIstTime(freshness.fetched_at)} IST · ${formatAge(freshness.age_minutes)}`} />
        </Group>
        <Group title="Engine">
          <Row label="Category" value={`CPCB · ${data.aqi.category}`} />
          <Row label="Policy" value={decision.policy.version} />
          <Row label="Decision" value="Deterministic" />
        </Group>
        <Group title="AWS">
          {region && <Row label="Region" value={region} />}
          <Row label="Cache" value={freshness.cache.replace("_", " ")} />
          <Row label="Status" value={freshness.status} />
        </Group>
      </div>
    </section>
  );
}
