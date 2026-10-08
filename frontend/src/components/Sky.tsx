import { severityMeta } from "../lib/format";

const LAYERS = ["neutral", "minimal", "low", "moderate", "high", "veryhigh", "critical"] as const;

/**
 * Atmospheric backdrop for the hero. Purely visual: the mood is chosen from the API's
 * decision.severity (or neutral before data). Layers cross-fade via CSS opacity.
 */
export function Sky({ severity }: { severity: string | null }) {
  const active = (severity && severityMeta(severity)?.sky) || "neutral";
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" data-testid="sky" data-sky={active}>
      {LAYERS.map((layer) => (
        <div
          key={layer}
          data-sky-layer={layer}
          className={`sky-layer sky-${layer} absolute inset-0 ${layer === active ? "opacity-100" : "opacity-0"}`}
        />
      ))}
    </div>
  );
}
