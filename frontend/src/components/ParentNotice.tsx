import { Check, Copy, MessageSquareText, Printer, RefreshCw, Share2, ShieldCheck, Sparkles } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ApiError } from "../api/client";
import type { Coordinates, Decision, NoticeLanguage, NoticeResponse } from "../api/types";
import { useNotice } from "../hooks/useNotice";
import { errorTitle, formatAge, formatHourRange, istDayLabel } from "../lib/format";
import { canWebShare, copyText, ensureDevanagariFont, printNotice, selectContents } from "../lib/notice";

const MAX_SCHOOL_NAME = 60;
const FOCUS_RING = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
const LANGUAGES: { value: NoticeLanguage; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिंदी" },
];

interface Props {
  coords: Coordinates;
  decision: Decision;
}

/** "Tell parents": words the backend's already-made decision as a parent-ready message. */
export function ParentNotice({ coords, decision }: Props) {
  const { state, generate, retry } = useNotice(coords);
  const [language, setLanguage] = useState<NoticeLanguage>("en");
  const [schoolName, setSchoolName] = useState("");
  const loading = state.status === "loading";

  useEffect(() => {
    if (language === "hi") ensureDevanagariFont();
  }, [language]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    generate({ language, schoolName });
  };
  const chooseLanguage = (next: NoticeLanguage) => {
    setLanguage(next);
    // A notice is already on screen: show it in the new language straight away.
    if (state.status === "success" && state.data.language !== next) generate({ language: next, schoolName });
  };

  return (
    <section id="parent-notice" aria-labelledby="notice-title" className="grid scroll-mt-24 gap-8 md:grid-cols-12">
      <div className="space-y-5 md:col-span-5 lg:col-span-4">
        <div>
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink/55">Tell parents</p>
          <h2
            id="notice-title"
            tabIndex={-1}
            className="mt-1 font-display text-2xl font-bold tracking-tight outline-none sm:text-3xl"
          >
            Parent notice
          </h2>
          <p className="mt-2 text-ink/75">Turn today's verified safety decision into a message parents can understand.</p>
          <p className="mt-3 border-l-2 border-brand/40 pl-3 text-sm text-ink/70">
            Decision already made: <span className="font-semibold text-ink">{decision.headline}</span>
            <span className="text-ink/60">
              {" "}· AQI {decision.aqi_context.display} {decision.aqi_context.category}
            </span>
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4" aria-describedby="notice-help">
          <fieldset disabled={loading}>
            <legend className="text-sm font-medium">Language</legend>
            <div className="mt-2 inline-grid grid-cols-2 rounded-full bg-ink/[0.06] p-1">
              {LANGUAGES.map((option) => (
                <label key={option.value} className="relative">
                  <input
                    type="radio"
                    name="notice-language"
                    value={option.value}
                    checked={language === option.value}
                    onChange={() => chooseLanguage(option.value)}
                    className="peer sr-only"
                  />
                  <span
                    lang={option.value}
                    className={`flex min-h-11 min-w-24 cursor-pointer items-center justify-center rounded-full px-4 text-sm font-semibold text-ink/70 peer-checked:bg-white peer-checked:text-ink peer-checked:shadow-sm peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand ${option.value === "hi" ? "font-deva" : ""}`}
                  >
                    {option.label}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label htmlFor="notice-school" className="text-sm font-medium">
              School name <span className="font-normal text-ink/55">(optional)</span>
            </label>
            <input
              id="notice-school"
              type="text"
              value={schoolName}
              onChange={(event) => setSchoolName(event.target.value)}
              maxLength={MAX_SCHOOL_NAME}
              autoComplete="organization"
              disabled={loading}
              placeholder="e.g. Govt. Sr. Sec. School"
              className={`mt-2 block min-h-11 w-full rounded-2xl bg-white px-4 text-base ring-1 ring-ink/15 placeholder:text-ink/40 disabled:opacity-60 ${FOCUS_RING}`}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-full bg-ink px-5 text-sm font-semibold text-chalk hover:bg-ink/85 disabled:cursor-wait disabled:opacity-70 sm:w-auto ${FOCUS_RING}`}
          >
            <MessageSquareText aria-hidden className="size-4" />
            {loading ? "Writing notice…" : "Generate notice"}
          </button>
          <p id="notice-help" className="text-xs text-ink/55">
            The notice repeats SaansSafe's decision and data; it never changes them. Nothing is sent to parents
            until you share it.
          </p>
        </form>
      </div>

      <div aria-live="polite" aria-busy={loading} className="min-h-[22rem] md:col-span-7 lg:col-span-8">
        {state.status === "idle" && <Placeholder />}
        {state.status === "loading" && <Skeleton slow={state.slow} />}
        {state.status === "error" && <NoticeError error={state.error} onRetry={retry} />}
        {state.status === "success" && <NoticeResult data={state.data} />}
      </div>
    </section>
  );
}

function Placeholder() {
  return (
    <div className="flex h-full min-h-[22rem] items-center justify-center rounded-[28px] border border-dashed border-ink/15 p-6 text-center text-sm text-ink/55">
      Your parent notice will appear here, ready to copy or share.
    </div>
  );
}

function Skeleton({ slow }: { slow: boolean }) {
  return (
    <div data-testid="notice-skeleton" className="rounded-[28px] bg-[#ece5dc] p-3 sm:p-5">
      <div className="space-y-3 rounded-2xl rounded-tl-md bg-white p-4">
        <div className="h-5 w-2/3 animate-pulse rounded bg-ink/10" />
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="h-3.5 animate-pulse rounded bg-ink/[0.07]" style={{ width: `${92 - i * 9}%` }} />
        ))}
        <div className="h-24 animate-pulse rounded-xl bg-ink/[0.05]" />
      </div>
      <p className="mt-3 text-sm text-ink/65">
        {slow ? "Writing the notice from today's decision… this can take a few seconds." : "Writing the notice…"}
      </p>
    </div>
  );
}

function NoticeError({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  const message =
    error.kind === "not_found" ? "The parent notice service isn't available on this server yet." : error.message;
  return (
    <div role="alert" className="rounded-[28px] border border-rose-200 bg-white p-5">
      <p className="font-display font-bold text-rose-950">{errorTitle(error)}</p>
      <p className="mt-1 text-sm text-rose-900">{message} Today's decision above is unaffected.</p>
      {error.retryable && (
        <button
          type="button"
          onClick={onRetry}
          className={`mt-3 inline-flex min-h-11 items-center gap-2 rounded-full bg-ink px-4 text-sm font-semibold text-chalk ${FOCUS_RING}`}
        >
          <RefreshCw aria-hidden className="size-4" />
          Try again
        </button>
      )}
    </div>
  );
}

type CopyStatus = { ok: boolean; text: string } | null;

function NoticeResult({ data }: { data: NoticeResponse }) {
  const bubble = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<CopyStatus>(null);
  const shareable = canWebShare();
  const hindi = data.language === "hi";

  const copy = async () => {
    if (await copyText(data.share_text)) {
      setStatus({ ok: true, text: "Copied. Paste it into WhatsApp, SMS or your school app." });
      return;
    }
    selectContents(bubble.current);
    setStatus({
      ok: false,
      text: "Couldn't copy automatically. The message is selected: copy it with Ctrl+C, or long-press and choose Copy.",
    });
  };
  const share = async () => {
    try {
      await navigator.share({ title: data.notice.title, text: data.share_text });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return; // user closed the sheet
      setStatus({ ok: false, text: "Sharing didn't work here. Use Copy message instead." });
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-[28px] bg-[#ece5dc] p-3 sm:p-5">
        <div
          ref={bubble}
          data-testid="notice-bubble"
          lang={data.language}
          className={`max-w-[34rem] space-y-3 rounded-2xl rounded-tl-md bg-white p-4 text-[15px] leading-relaxed shadow-sm ${hindi ? "font-deva" : ""}`}
        >
          <NoticeText data={data} />
        </div>
      </div>

      <p className="flex items-start gap-2 text-sm text-ink/70">
        {data.generated_by === "template" ? (
          <>
            <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-brand" />
            <span>
              <span className="font-medium text-ink">Verified template</span> · SaansSafe's standard wording of
              today's decision
            </span>
          </>
        ) : (
          <>
            <Sparkles aria-hidden className="mt-0.5 size-4 shrink-0 text-brand" />
            <span>
              <span className="font-medium text-ink">Worded by Amazon Bedrock</span> · checked against SaansSafe's
              decision before showing
            </span>
          </>
        )}
      </p>

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <ActionButton primary={!shareable} onClick={copy} icon={Copy}>
          Copy message
        </ActionButton>
        {shareable && (
          <ActionButton primary onClick={share} icon={Share2}>
            Share
          </ActionButton>
        )}
        <ActionButton onClick={() => printNotice()} icon={Printer}>
          Print notice
        </ActionButton>
      </div>
      <p role="status" className={`min-h-5 text-sm ${status?.ok ? "text-emerald-800" : "text-amber-900"}`}>
        {status && (
          <span className="inline-flex items-center gap-1.5">
            {status.ok && <Check aria-hidden className="size-4 shrink-0" />}
            {status.text}
          </span>
        )}
      </p>

      <FactsUsed data={data} />
      {createPortal(
        <div data-print-notice lang={data.language} className={hindi ? "font-deva" : ""}>
          <NoticeText data={data} />
        </div>,
        document.body,
      )}
    </div>
  );
}

/** The notice exactly as the API returned it: writer fields, then the fixed footer. */
function NoticeText({ data }: { data: NoticeResponse }) {
  const { notice, footer } = data;
  return (
    <>
      <p className="font-semibold">{notice.title}</p>
      {notice.body.split(/\n\s*\n/).map((paragraph, i) => (
        <p key={i}>{paragraph}</p>
      ))}
      <ul className="list-disc space-y-1 pl-5">
        {notice.key_points.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
      <p className="text-sm text-ink/75">
        <span className="font-medium">{footer.health_label}:</span> <span lang="en">{footer.health_statement}</span>
      </p>
      <p className="text-xs text-ink/60">{footer.disclaimer}</p>
      <p>{notice.sign_off}</p>
    </>
  );
}

function FactsUsed({ data }: { data: NoticeResponse }) {
  const { grounding, decision, freshness } = data;
  const wording = data.generated_by === "template" ? "Verified template" : `Amazon Bedrock${data.model ? ` (${data.model})` : ""}`;
  const rows: [string, string][] = [
    ["Valid for", `${istDayLabel(data.valid_for_hour)} · ${formatHourRange(data.valid_for_hour)}`],
    ["Decision", decision.headline],
    ["Forecast/model AQI", `${grounding.aqi_display} · ${grounding.category}`],
    ["Main pollutant", grounding.dominant_pollutant_name],
    ["Policy", `${grounding.policy_name} · ${decision.policy_version}`],
    ["Data", `${freshness.status === "stale" ? "Older data" : "Fresh"} · fetched ${formatAge(freshness.age_minutes)}`],
    ["Wording", wording],
  ];
  return (
    <details className="rounded-2xl bg-white/70 ring-1 ring-ink/10">
      <summary className={`flex min-h-11 cursor-pointer items-center rounded-2xl px-4 text-sm font-semibold ${FOCUS_RING}`}>
        Facts used
      </summary>
      <dl className="grid gap-x-4 gap-y-2 px-4 pb-4 text-sm sm:grid-cols-[10rem_1fr]">
        {rows.map(([term, value]) => (
          <div key={term} className="contents">
            <dt className="text-ink/55">{term}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

function ActionButton({
  primary = false,
  onClick,
  icon: Icon,
  children,
}: {
  primary?: boolean;
  onClick: () => void;
  icon: typeof Copy;
  children: string;
}) {
  const tone = primary ? "bg-ink text-chalk hover:bg-ink/85" : "bg-white text-ink ring-1 ring-ink/15 hover:bg-ink/[0.04]";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold ${tone} ${FOCUS_RING}`}
    >
      <Icon aria-hidden className="size-4" />
      {children}
    </button>
  );
}
