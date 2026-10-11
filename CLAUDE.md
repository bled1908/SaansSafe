# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Start here

Read `HACKATHON_MASTER_PLAN.md` (requirements matrix, architecture, 4-day plan, risks, open questions) and `SUBMISSION_CHECKLIST.md` **before** re-reading `claude_read_this/`. Both were distilled from it on 2026-10-08. **Implementation is gated on the user approving the master plan.**

Working rules:
- **Never publish `claude_read_this/`** (third-party pages with personal names). Keep it in `.gitignore`.
- **Repo history must start after the official kickoff on Oct 8.** Never import pre-existing code. Commit small and often.
- **Deterministic numbers, LLM words.** AQI calculations and decisions are tested pure functions. The LLM only explains and translates tool outputs.
- Environment: Windows. AWS CLI is authenticated, region `ap-south-1`. SAM CLI is installed as a uv tool (see Commands); Docker is **not installed**. Use pay-per-request services only (AWS charges may apply, but demo usage is expected to be low). No NAT/EC2.
- The user has a limited Claude usage budget. Avoid broad re-scans, and keep the plan files updated so context isn't rediscovered.

## Commands

Backend (run from `backend/`; uv manages a Python 3.13 venv, matching the Lambda runtime):
- All tests: `uv run --python 3.13 pytest -q`
- One test: `uv run --python 3.13 pytest tests/test_aqi.py::test_category_boundaries -q`

Frontend (run from `frontend/`; React 19 + Vite + TypeScript + Tailwind v4; talks to the deployed API by default, override with `VITE_API_BASE_URL`):
- Dev server: `npm run dev` (port 5173, the only CORS origin allowed by the API today)
- Tests: `npm test` · one file: `npx vitest run src/components/outlook.test.tsx` · typecheck: `npm run typecheck` · production build: `npm run build`
- SAM CLI is a uv tool at `~/.local/bin/sam` (not on PATH in bash). Validate: `~/.local/bin/sam validate --lint` (from `backend/`; settings in `samconfig.toml`: stack `saanssafe-dev`, ap-south-1). There's no `sam build` step: the code has no third-party dependencies, so `CodeUri: src/` is packaged as-is.
- Deploy (two-step, from `backend/`): `~/.local/bin/sam deploy --no-execute-changeset`, then review the change set and run `aws cloudformation execute-change-set --region ap-south-1 --change-set-name <arn>`, then `aws cloudformation wait stack-update-complete --stack-name saanssafe-dev` (`stack-create-complete` on the first deploy). Stack outputs: `aws cloudformation describe-stacks --stack-name saanssafe-dev --query "Stacks[0].Outputs"`.
- On Windows Git Bash, prefix AWS commands that take `/aws/lambda/...` log-group names with `MSYS_NO_PATHCONV=1`. Otherwise the path gets rewritten and the AWS CLI rejects it.

## Backend layout

- `backend/src/saanssafe/aqi.py`: the CPCB Indian AQI engine. Pure functions, no I/O. It follows CPCB CUPS/82/2014-15 (Table 3.11 and §3.5; decisions and page references are in master plan §12). CO is in mg/m3; everything else is in ug/m3. Data providers must convert to these units first.
  - `rolling_average`: every pollutant needs ≥16 valid hours in the latest 24 (`None` = missing, never filled in). It then averages the latest 24 h, or the **latest** 8 h for O3/CO. "Latest" is our product decision, not a CPCB rule.
  - `sub_index`: CPCB interpolation with I_LO−1 when I_LO > 50. At or above the open-ended Severe threshold it returns 401, with no interpolation.
  - `compute_aqi`: the max sub-index. It needs ≥3 pollutants incl. PM2.5 or PM10, otherwise `InsufficientDataError`. When Severe it sets `beyond_scale=True` and `display="401+"`. **Always show `display`, never a made-up number above 401.**
- `backend/src/saanssafe/readings.py`: `HourlyReading` (UTC hour, 7 pollutants in engine units, `None` = missing) and `ReadingSeries` (consecutive hours only). **Use `series.hourly_until(t)` to build engine input.** It always returns the 24 hours ending at `t`'s hour and pads uncovered hours with `None`, so stale data becomes insufficient instead of passing as current.
- `backend/src/saanssafe/providers/`: `base.py` holds the `AirQualityProvider` protocol, `validate_coordinates`, and errors (`ProviderUnavailableError` = retry later, `ProviderRequestError` = 4xx, `ProviderResponseError` = untrustworthy payload). `open_meteo.py` is the Open-Meteo client. Network I/O lives only in `urllib_transport`, and tests inject a fake transport (never hit the network). It requests past_days=1 + forecast_days=4 (so ≥72 h ahead is always covered), `timeformat=unixtime`, GMT. It checks the unit is μg/m³, converts CO to mg/m³, and turns absent or null variables into `None` (NH3 is always null for India). **Open-Meteo data are CAMS (global) model forecasts on a coarse model grid, not CPCB ground-station observations.** Label them as "forecast/model AQI" everywhere, including the UI, README and video.
- `backend/src/saanssafe/cache.py`: `ReadingCache` protocol + `DynamoReadingCache` (injected low-level boto3 client). Item: `pk` = `open-meteo#<lat 2dp>#<lon 2dp>`, `fetched_at`, `expires_at` (DynamoDB TTL, 24 h, cleanup only), `schema_version`, `payload` (JSON series). Any client or corrupt-item failure becomes `CacheError`.
- `backend/src/saanssafe/service.py`: `AqiService.current_aqi(lat, lon)` → `AqiReport`. It's cache-first with no HTTP/AWS code. Data up to 60 min old is a hit. Otherwise it refetches. Only on a **transient** provider failure (`ProviderUnavailableError`: 429/5xx/timeout/network) does it serve a cached copy of up to 6 h, marked `stale` with its age and a warning. 4xx (`ProviderRequestError`) and malformed responses (`ProviderResponseError`) never fall back; they propagate. Cache errors never block a response.
- `backend/src/saanssafe/api.py`: the Lambda entry point `saanssafe.api.handler` (API Gateway HTTP API, payload v2). It serves `GET /health` and `GET /aqi?lat=&lon=`. Error mapping: 400 invalid_coordinates, 422 insufficient_data, 502 upstream_rejected/upstream_invalid, 503 upstream_unavailable (Retry-After), 500 internal_error. Config comes from env (`AQI_CACHE_TABLE` required; `CACHE_FRESH_MINUTES`, `CACHE_MAX_STALE_HOURS`, `OPEN_METEO_BASE_URL`, `OPEN_METEO_TIMEOUT_S`). boto3 is imported lazily (it's in the Lambda runtime, not a project dependency).
- `backend/src/saanssafe/decision.py`: `decide_school_safety(AqiResult) -> SafetyDecision`. A pure, deterministic mapping from the CPCB AQI category to a school action, a severity, per-activity guidance (assembly, PE/sports, recess) and recommendations. **These school thresholds are SaansSafe product policy (`POLICY_VERSION` saanssafe-school-v1), not CPCB rules**; CPCB defines no school actions. An LLM may only explain a decision, never make one. Exposed as the `decision` block of the `/aqi` 200 response via `api.decision_body`, which keeps the CPCB health statement, the SaansSafe policy and the forecast/model data freshness separate. Deployed to the live `saanssafe-dev` Lambda and live-verified on 2026-10-08 (commit `72b0b1a`).
- `backend/src/saanssafe/outlook.py`: `build_outlook(series, now, hours=72)`. For every hour from the current hour to +72 h it reuses `aqi_from_hourly(series.hourly_until(h))` and `decide_school_safety`, so there's no second AQI implementation. It groups hours into IST school periods (morning 06–12, afternoon 12–18, night 18–06; labels such as "This morning", "Tonight", "Saturday afternoon") and computes deterministic summaries: worst hour (policy severity rank, then AQI, earliest on ties), next action change, first restricted hour (any activity not `allowed`), and the best full school-hours period. **That period is chosen from school days only: SaansSafe v1 treats Monday–Friday (IST date) as school days for best-school-window selection (`SCHOOL_WEEKDAYS`, not configurable). It's `null` if no weekday period qualifies, and weekends never qualify even with cleaner air.** `worst`, `next_change` and `first_restricted` still span the full 72 h. It truncates honestly (`complete: false`) when data ends early. Served by `GET /forecast` (`api.forecast_body`): `coverage`, `hours[]` (`aqi`/`dominant_pollutant`/`decision` or nulls), `periods[]`, `summary`, `policy`, `freshness`, `source`, `data_type: forecast_model`. `AqiService.forecast` refetches when fresh cached data doesn't reach now+72 h; a stale fallback (transient failures only) may be partial and is flagged. **No LLM is involved.**
- Tests share fakes in `backend/tests/support.py` (`FakeProvider`, `FakeCache`, `FakeDynamoClient`, `make_series`).

## Current state

This is the SaansSafe entry for **Environmental Hacks** (WeMakeDevs × AWS, Bharat Builds Tour event 02, Oct 8–11, 2026). `claude_read_this/` holds the event's web pages, saved as text. It is the source of truth for the rules.

- **Implemented and tested:** M0 (repo setup) and M1 (`backend/src/saanssafe/aqi.py`, the CPCB AQI engine, with `backend/tests/test_aqi.py`).
- **Implemented and tested (M2):** the Open-Meteo data layer (`readings.py`, `providers/`) plus the `/aqi` API, service and DynamoDB cache (`api.py`, `service.py`, `cache.py`), all against fakes.
- **M3 (deployed and verified, 2026-10-08):** stack **`saanssafe-dev`** in ap-south-1. API base URL: `https://paqffn4eq5.execute-api.ap-south-1.amazonaws.com` (`/health`, `/aqi?lat=&lon=`). Smoke tests passed, and DynamoDB cache miss → fetch → hit was verified. AWS charges may apply; demo usage is expected to be low.
- **Decision engine (backend part of M4, deployed and live-verified 2026-10-08, commit `72b0b1a`):** the deterministic school safety Decision Engine is integrated into `/aqi`. The live `saanssafe-dev` Lambda returns the `decision` block (SaansSafe school safety policy `saanssafe-school-v1`, current hour only).
- **F2 frontend (committed `1637f17`):** decision-first "sky" UI in `frontend/`; the API is the single source of truth (the browser never calculates AQI, category, severity or actions).
- **F3 72-hour outlook (committed `ca2c761`, deployed):** `backend/src/saanssafe/outlook.py` + `GET /forecast`, rendered by `frontend/src/components/OutlookSection.tsx`. The provider requests `forecast_days=4` (`past_days=1`, GMT), which guarantees ≥72 h beyond the current UTC hour.
- **Parent notice (deployed):** deterministic English/Hindi notices via `POST /notice` (`NoticeFunction`, `notice_*.py`) and `frontend/src/components/ParentNotice.tsx`. The optional Strands/Bedrock writer (`notice_bedrock.py`) is in code but **not active**: Bedrock access is not authorized, Strands isn't packaged, and the stack sets `NOTICE_AI_ENABLED=false`.
- **M5 hosting (deployed, commit `9e1b356`):** stack **`saanssafe-web`** (`infra/web/`): private S3 + CloudFront OAC, live at `https://d316zs0sydbi1r.cloudfront.net`. Deploy and upload steps are in `README.md`. Remove `backend/src/**/__pycache__` before any backend `sam deploy`, so local bytecode isn't packaged.
- **Demo video (published 2026-10-11):** https://www.youtube.com/watch?v=7fcaFbYrZwM (2:44, music only, captions burned in). Source in `video/` (Remotion + Playwright captures + locally generated score; see `video/README.md`). Render with `npm run render:music` from `video/` (about 20 min at `--concurrency=3`). Generated media, captures and the AWS screenshots are git-ignored; never commit them. Amazon Polly needs explicit cost approval before any call.
- **Team:** Shadow Protocol (Subhadeep Roy, Sneha Singha), an independent student team.
- **Not implemented:** Ask SaansSafe (Strands/Bedrock Q&A).
- `README.md` is the judge-facing source of truth; `HACKATHON_MASTER_PLAN.md` is historical.
- Milestone history is at the top of `HACKATHON_MASTER_PLAN.md`.
- The AQI engine's rules were verified against CPCB's report and decided (master plan §12). Change them only with a cited CPCB source.

- `claude_read_this/overview.md`: tracks, prizes, the AWS tool menu, judging criteria
- `claude_read_this/rules.md`: eligibility, what counts as new work, submission requirements
- `claude_read_this/schedule.md`: Thu Oct 8 kickoff → Sun Oct 11 submissions (submission form opens Oct 11, 8:00 AM; exact deadline TBA on the event page)
- `claude_read_this/previous_winners/`: saved HTML of the previous tour event (First Commit). To read it, strip the tags with a script; don't open the raw HTML (the `_files/` folders are assets only)

## Hard constraints that shape any build

- **Must use AWS, and the demo video must show it.** Use at least one AWS open-source tool (local "Build It": Strands Agents SDK, PartyRock, Finch, EKS Distro/Anywhere, SAM CLI, LocalStack, Firecracker, Corretto, OpenSearch, Cedar), deploy on AWS ("Ship It": Lambda, API Gateway, Step Functions, ECS/EKS/Fargate, EC2, Lightsail, App Runner, Amplify, S3, DynamoDB, RDS/Aurora, Cognito, SageMaker, etc.), or both. Mentioning AWS only in the writeup doesn't count. Keep everything on the AWS Free Tier.
- **All code must be new, written after the Oct 8 kickoff.** If the repo history doesn't match the event dates, the whole team is disqualified. Don't import or rewrite pre-existing project code. Open-source libraries and starter templates are allowed, with credit and a compatible licence.
- **The deliverables are a public repo, a YouTube demo of 3 minutes or less (public or unlisted), and a short writeup** (problem, build, where AWS fits, and the AI coding tools used). There's no live demo. A feature that doesn't appear in the video doesn't count.
- **Pick a track:** Air (AQI, exposure, stubble burning, indoor air, school safety), Heat & Water (heatwaves, floods, waterlogging, drought, tankers, leaks, groundwater), or Waste & Energy (segregation, recycling, e-waste, informal recyclers, rooftop solar, EV nudges, public transport). The listed topics are starting points, not a fixed list.

## Judging criteria (optimise for these)

1. Idea & impact: a real environmental problem for a specific group of people. A small problem solved well beats a big one solved vaguely.
2. Built on AWS.
3. Design & usability: someone outside the team must be able to use it, in the setting where the affected people actually are.
4. Execution: one feature that works beats five that almost do.
5. Demo video: what it does, who it's for, and where AWS fits.

Separate prize: the top 5 blogs published on AWS Builder Center and linked in the submission.

## Signal from the previous event (First Commit)

The winners were mostly agentic and AI-driven apps aimed at a specific user, and they had live deployments: 1st was "Suraksha", an agentic companion for an aging parent (Ship It); 2nd was a voice on-call agent; 3rd, for Best UI, was "CampusEvac". Almost every winner had both a **Live** URL and a **Code** link. Plan for a deployed URL.
