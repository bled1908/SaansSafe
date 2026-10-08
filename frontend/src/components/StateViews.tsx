import { CloudOff, RefreshCw } from "lucide-react";
import type { ApiError } from "../api/client";
import { errorTitle } from "../lib/format";

export function EmptyState() {
  return (
    <div className="space-y-3">
      <p className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink/70">
        School air decisions · forecast/model
      </p>
      <h1 className="font-display text-[2.15rem] font-extrabold leading-[1.04] tracking-tight text-balance sm:text-5xl lg:text-[3.6rem]">
        Can students go outside today?
      </h1>
      <p className="max-w-xl leading-relaxed text-ink/80">
        Pick your school's location. SaansSafe turns forecast air quality into a clear plan for assembly, PE and
        recess.
      </p>
    </div>
  );
}

export function LoadingState({ slow }: { slow: boolean }) {
  return (
    <div aria-busy="true" aria-live="polite" className="grid gap-8 lg:grid-cols-12 lg:gap-12">
      <div className="space-y-5 lg:col-span-7">
        <div className="shimmer h-3 w-56 rounded-full" />
        <div className="space-y-3">
          <div className="shimmer h-10 w-full rounded-xl" />
          <div className="shimmer h-10 w-3/4 rounded-xl" />
        </div>
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="shimmer h-20 rounded-2xl" />
          ))}
        </div>
        <p className="text-sm text-ink/70">
          {slow ? "Fetching the latest forecast… this can take a few seconds." : "Loading…"}
        </p>
      </div>
      <div className="shimmer h-72 rounded-[28px] lg:col-span-5" />
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div role="alert" className="max-w-2xl rounded-3xl border border-rose-200 bg-white/85 p-6 backdrop-blur">
      <div className="flex items-start gap-3">
        <CloudOff aria-hidden className="mt-0.5 size-6 shrink-0 text-rose-800" />
        <div className="space-y-1">
          <h2 className="font-display text-xl font-bold text-rose-950">{errorTitle(error)}</h2>
          <p className="text-sm text-rose-900">{error.message}</p>
          {error.retryAfterSeconds !== undefined && (
            <p className="text-sm text-rose-900">Please try again in about {error.retryAfterSeconds} seconds.</p>
          )}
        </div>
      </div>
      {error.retryable && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-full bg-ink px-5 text-sm font-semibold text-chalk hover:bg-ink/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          <RefreshCw aria-hidden className="size-4" />
          Try again
        </button>
      )}
    </div>
  );
}
