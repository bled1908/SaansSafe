import { Check, ChevronDown, LocateFixed, MapPin } from "lucide-react";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { SAMPLE_LOCATIONS, locationFromPosition, type SchoolLocation } from "../lib/locations";

const GEO_OPTIONS: PositionOptions = { enableHighAccuracy: false, timeout: 10_000, maximumAge: 600_000 };

/** Tailwind's `sm` breakpoint: dropdown at and above it, bottom sheet below it. */
const DESKTOP_QUERY = "(min-width: 40rem)";

function subscribeDesktop(onChange: () => void) {
  const query = window.matchMedia?.(DESKTOP_QUERY);
  query?.addEventListener("change", onChange);
  return () => query?.removeEventListener("change", onChange);
}

function isDesktopViewport(): boolean {
  return window.matchMedia?.(DESKTOP_QUERY).matches ?? false;
}

function geolocationMessage(error: GeolocationPositionError): string {
  switch (error.code) {
    case error.PERMISSION_DENIED:
      return "Location permission was denied. Choose an example location instead.";
    case error.POSITION_UNAVAILABLE:
      return "Your location is unavailable right now.";
    case error.TIMEOUT:
      return "Finding your location took too long. Please try again.";
    default:
      return "Could not get your location.";
  }
}

function useGeolocation(onLocated: (location: SchoolLocation) => void) {
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const supported = typeof navigator !== "undefined" && "geolocation" in navigator;

  function locate() {
    if (!supported) return;
    setLocating(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        onLocated(locationFromPosition(pos.coords.latitude, pos.coords.longitude));
      },
      (err) => {
        setLocating(false);
        setError(geolocationMessage(err));
      },
      GEO_OPTIONS,
    );
  }
  return { locating, error, supported, locate };
}

interface OptionsProps {
  selected: SchoolLocation | null;
  onSelect: (location: SchoolLocation) => void;
  autoFocus?: boolean;
}

/** The location choices: "Use my location" plus example cities. Used in the chip and onboarding. */
export function LocationOptions({ selected, onSelect, autoFocus = false }: OptionsProps) {
  const { locating, error, supported, locate } = useGeolocation(onSelect);
  const firstRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (autoFocus) firstRef.current?.focus();
  }, [autoFocus]);

  return (
    <div className="space-y-4">
      <button
        ref={firstRef}
        type="button"
        onClick={locate}
        disabled={!supported || locating}
        aria-pressed={selected?.kind === "geolocation"}
        className="flex min-h-12 w-full items-center gap-3 rounded-2xl bg-brand px-4 text-left font-semibold text-white shadow-sm transition hover:bg-brand-deep focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-60"
      >
        <LocateFixed aria-hidden className="size-5 shrink-0" />
        {locating ? "Finding your location…" : "Use my location"}
      </button>
      {!supported && <p className="text-sm text-ink/60">Location isn't supported in this browser.</p>}
      {error && (
        <p role="alert" className="text-sm text-rose-800">
          {error}
        </p>
      )}
      <div>
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-ink/60">
          Example locations · not real school records
        </p>
        <ul className="mt-2 overflow-hidden rounded-2xl bg-white ring-1 ring-ink/10">
          {SAMPLE_LOCATIONS.map((loc) => {
            const active = selected?.id === loc.id;
            return (
              <li key={loc.id} className="border-b border-ink/5 last:border-0">
                <button
                  type="button"
                  onClick={() => onSelect(loc)}
                  aria-pressed={active}
                  className="flex min-h-12 w-full items-center gap-3 px-4 py-2.5 text-left transition hover:bg-chalk focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand"
                >
                  <MapPin aria-hidden className="size-4 shrink-0 text-ink/45" />
                  <span className="flex-1">
                    <span className="block font-semibold">{loc.name}</span>
                    <span className="block font-mono text-xs text-ink/55">{loc.area}</span>
                  </span>
                  {active && <Check aria-hidden className="size-4 text-brand" />}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

interface ChipProps {
  selected: SchoolLocation | null;
  onSelect: (location: SchoolLocation) => void;
}

/** Compact header control: a chip that opens a dropdown (desktop) or bottom sheet (mobile). */
export function LocationChip({ selected, onSelect }: ChipProps) {
  const [open, setOpen] = useState(false);
  const isDesktop = useSyncExternalStore(subscribeDesktop, isDesktopViewport, () => false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const close = useCallback((restoreFocus: boolean) => {
    setOpen(false);
    if (restoreFocus) buttonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close(true);
    };
    const onDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (wrapRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      close(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open, close]);

  function choose(location: SchoolLocation) {
    onSelect(location);
    close(true);
  }

  const panel = (
    <div
      ref={panelRef}
      role="dialog"
      aria-label="Choose a location"
      className={
        isDesktop
          ? "animate-rise absolute left-0 top-full z-50 mt-2 max-h-[calc(100dvh-6rem)] w-[22rem] overflow-y-auto rounded-3xl bg-chalk p-4 pb-6 shadow-2xl ring-1 ring-ink/10"
          : "animate-rise fixed inset-x-0 bottom-0 z-50 max-h-[85dvh] overflow-y-auto overscroll-contain rounded-t-3xl bg-chalk p-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-2xl"
      }
    >
      {!isDesktop && <div aria-hidden className="mx-auto mb-4 h-1 w-10 rounded-full bg-ink/20" />}
      <LocationOptions selected={selected} onSelect={choose} autoFocus />
    </div>
  );
  // The sticky header's backdrop-filter makes it the containing block for position: fixed
  // descendants, so the mobile sheet is portaled to <body> to stay fixed to the viewport.
  const mobileSheet = (
    <>
      <div
        aria-hidden
        data-testid="location-backdrop"
        className="fixed inset-0 z-40 bg-ink/30"
        onClick={() => close(false)}
      />
      {panel}
    </>
  );

  return (
    <div ref={wrapRef} className="relative min-w-0">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={selected ? `Location: ${selected.name}. Change location` : "Choose a location"}
        onClick={() => setOpen((v) => !v)}
        className="flex h-11 max-w-[12rem] items-center gap-2 rounded-full border border-ink/15 bg-white/85 pl-3 pr-2.5 text-sm font-semibold shadow-sm transition hover:border-ink/30 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand sm:max-w-xs"
      >
        <MapPin aria-hidden className="size-4 shrink-0 text-brand" />
        <span className="truncate">{selected?.name ?? "Choose location"}</span>
        {selected?.kind === "sample" && (
          <span className="hidden font-mono text-[11px] font-medium uppercase tracking-wider text-ink/55 min-[420px]:inline">
            example
          </span>
        )}
        <ChevronDown aria-hidden className={`size-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (isDesktop ? panel : createPortal(mobileSheet, document.body))}
    </div>
  );
}
