import { useEffect, useState, type ReactNode } from "react";
import { formatIstTime } from "../lib/format";

const MINUTE_MS = 60_000;

/** The browser's current time, re-rendered at each minute boundary. */
function useCurrentMinute(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      timer = setTimeout(() => {
        setNow(new Date());
        schedule();
      }, MINUTE_MS - (Date.now() % MINUTE_MS));
    };
    schedule();
    return () => clearTimeout(timer);
  }, []);
  return now;
}

/** Data freshness and the API's AWS region. The time shown is the current clock, not the data time. */
export interface LiveInfo {
  status: "fresh" | "stale";
  region: string | null;
}

interface Props {
  locationControl: ReactNode;
  live: LiveInfo | null;
  children: ReactNode;
  footer: ReactNode;
}

function LiveIndicator({ live }: { live: LiveInfo }) {
  const fresh = live.status === "fresh";
  const now = useCurrentMinute();
  return (
    <p className="flex shrink-0 items-center gap-2 font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-ink/70">
      <span className={`live-dot inline-block size-2 rounded-full ${fresh ? "bg-sev-minimal text-sev-minimal" : "bg-amber-500 text-amber-500"}`} />
      <span>{fresh ? "Fresh" : "Stale"}</span>
      {live.region && <span className="hidden md:inline">· {live.region}</span>}
      <time dateTime={now.toISOString()} className="hidden md:inline">
        · {formatIstTime(now.toISOString())} IST
      </time>
    </p>
  );
}

export function AppShell({ locationControl, live, children, footer }: Props) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-ink/10 bg-chalk/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <p className="flex shrink-0 items-baseline gap-1.5" aria-label="SaansSafe">
            <span className="font-display text-lg font-bold tracking-tight">SaansSafe</span>
            <span lang="hi" className="hidden font-deva text-sm font-semibold text-brand min-[380px]:inline">
              साँस
            </span>
          </p>
          <div className="flex min-w-0 flex-1 justify-end sm:justify-start sm:pl-4">{locationControl}</div>
          {live && <LiveIndicator live={live} />}
        </div>
      </header>
      <main className="flex-1">{children}</main>
      {footer}
    </div>
  );
}
