import { CheckCircle2, Dumbbell, Home, Sun, TriangleAlert, Users } from "lucide-react";
import type { ActivityKey, Decision, Guidance } from "../api/types";
import { ACTIVITY_LABELS, ACTIVITY_ORDER, GUIDANCE_DISPLAY } from "../lib/format";

const ACTIVITY_ICONS: Record<ActivityKey, typeof Sun> = {
  morning_assembly: Users,
  pe_and_sports: Dumbbell,
  recess_and_breaks: Sun,
};

const GUIDANCE_ICONS: Record<Guidance, typeof Sun> = {
  allowed: CheckCircle2,
  limited: TriangleAlert,
  move_indoors: Home,
};

/** Three compact tiles straight from decision.activities. Nothing is inferred. */
export function ActivityPills({ decision }: { decision: Decision }) {
  return (
    <ul aria-label="Activity guidance" className="grid grid-cols-3 gap-2 sm:gap-3">
      {ACTIVITY_ORDER.map((key, i) => {
        const guidance = decision.activities[key];
        if (!guidance) return null;
        const display = GUIDANCE_DISPLAY[guidance];
        const ActivityIcon = ACTIVITY_ICONS[key];
        const StatusIcon = GUIDANCE_ICONS[guidance] ?? TriangleAlert;
        return (
          <li
            key={key}
            data-testid={`activity-${key}`}
            style={{ animationDelay: `${120 + i * 70}ms` }}
            className="animate-rise rounded-2xl bg-white/75 p-3 ring-1 ring-ink/10 backdrop-blur-sm sm:p-4"
          >
            <p className="flex items-start gap-1.5 text-xs font-medium leading-tight text-ink/70 sm:text-sm">
              <ActivityIcon aria-hidden className="size-4 shrink-0" />
              <span>{ACTIVITY_LABELS[key]}</span>
            </p>
            <p
              className={`mt-2 inline-flex max-w-full items-center gap-1 rounded-full px-2 py-1 text-[13px] font-semibold ring-1 sm:gap-1.5 sm:px-2.5 sm:text-sm ${display?.tone ?? "bg-white ring-ink/10"}`}
            >
              <StatusIcon aria-hidden className="size-4 shrink-0" />
              {display?.label ?? guidance}
            </p>
          </li>
        );
      })}
    </ul>
  );
}

/** decision.recommendations as a numbered checklist. */
export function TodayChecklist({ decision }: { decision: Decision }) {
  return (
    <section aria-labelledby="checklist-title" className="grid gap-6 md:grid-cols-12">
      <div className="md:col-span-4">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink/55">Act</p>
        <h2 id="checklist-title" className="mt-1 font-display text-2xl font-bold tracking-tight sm:text-3xl">
          Today's checklist
        </h2>
        <p className="mt-2 text-sm text-ink/65">From the {decision.policy.name}.</p>
      </div>
      <ol className="space-y-3 md:col-span-8">
        {decision.recommendations.map((rec, i) => (
          <li key={rec} className="flex gap-4 border-b border-ink/10 pb-3 last:border-0">
            <span className="font-mono text-sm font-medium text-brand">{String(i + 1).padStart(2, "0")}</span>
            <span className="leading-relaxed">{rec}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
