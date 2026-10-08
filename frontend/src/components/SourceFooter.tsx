import type { AqiResponse } from "../api/types";

const FALLBACK_DISCLAIMER =
  "Forecast/model estimates for a model grid cell. Not readings from CPCB monitoring stations.";
const FALLBACK_ATTRIBUTION =
  "Air quality data: Open-Meteo.com, based on CAMS (Copernicus Atmosphere Monitoring Service)";

const LINKS = [
  { label: "Open-Meteo", href: "https://open-meteo.com/" },
  { label: "Copernicus CAMS", href: "https://atmosphere.copernicus.eu/" },
  {
    label: "CPCB National AQI report (CUPS/82/2014-15)",
    href: "https://cpcb.nic.in/upload/national-air-quality-index/FINAL-REPORT_AQI_.pdf",
  },
];

export function SourceFooter({ data }: { data?: AqiResponse }) {
  return (
    <footer className="border-t border-ink/10">
      <div className="mx-auto max-w-6xl space-y-3 px-4 py-8 text-[13px] leading-relaxed text-ink/70 sm:px-6">
        <p>
          {data?.disclaimer ?? FALLBACK_DISCLAIMER} AQI categories and health statements follow CPCB; school actions
          are SaansSafe's own policy. Not medical advice; follow instructions from local and education authorities.
        </p>
        <nav aria-label="Sources" className="flex flex-wrap gap-x-5">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-brand"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <p className="font-mono text-xs text-ink/55">
          {data?.source.attribution ?? FALLBACK_ATTRIBUTION} · Built on AWS: API Gateway, Lambda, DynamoDB, SAM
        </p>
      </div>
    </footer>
  );
}
