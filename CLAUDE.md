# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Start here

Read `HACKATHON_MASTER_PLAN.md` (requirements matrix, architecture, 4-day plan, risks, open questions) and `SUBMISSION_CHECKLIST.md` **before** re-reading `claude_read_this/`. Both were distilled from it on 2026-10-08. **Implementation is gated on the user approving the master plan.**

Working rules:
- **Never publish `claude_read_this/`** (third-party pages with personal names). Keep it in `.gitignore`.
- **Repo history must start after the official kickoff on Oct 8.** Never import pre-existing code. Commit small and often.
- **Deterministic numbers, LLM words.** AQI calculations and decisions are tested pure functions. The LLM only explains and translates tool outputs.
- Environment: Windows. AWS CLI is authenticated, region `ap-south-1`. SAM CLI and Docker are **not installed**. Free-tier/pay-per-request services only. No NAT/EC2.
- The user has a limited Claude usage budget. Avoid broad re-scans, and keep the plan files updated so context isn't rediscovered.

## Commands

Backend (run from `backend/`; uv manages a Python 3.13 venv, matching the Lambda runtime):
- All tests: `uv run --python 3.13 pytest -q`
- One test: `uv run --python 3.13 pytest tests/test_aqi.py::test_category_boundaries -q`

## Backend layout

- `backend/src/saanssafe/aqi.py`: the CPCB Indian AQI engine. Pure functions, no I/O. It follows CPCB CUPS/82/2014-15 (Table 3.11 and §3.5; decisions and page references are in master plan §12). CO is in mg/m3; everything else is in ug/m3. Data providers must convert to these units first.
  - `rolling_average`: every pollutant needs ≥16 valid hours in the latest 24 (`None` = missing, never filled in). It then averages the latest 24 h, or the **latest** 8 h for O3/CO. "Latest" is our product decision, not a CPCB rule.
  - `sub_index`: CPCB interpolation with I_LO−1 when I_LO > 50. At or above the open-ended Severe threshold it returns 401, with no interpolation.
  - `compute_aqi`: the max sub-index. It needs ≥3 pollutants incl. PM2.5 or PM10, otherwise `InsufficientDataError`. When Severe it sets `beyond_scale=True` and `display="401+"`. **Always show `display`, never a made-up number above 401.**
- `backend/src/saanssafe/readings.py`: `HourlyReading` (UTC hour, 7 pollutants in engine units, `None` = missing) and `ReadingSeries` (consecutive hours only). **Use `series.hourly_until(t)` to build engine input.** It always returns the 24 hours ending at `t`'s hour and pads uncovered hours with `None`, so stale data becomes insufficient instead of passing as current.
- `backend/src/saanssafe/providers/`: `base.py` holds the `AirQualityProvider` protocol, `validate_coordinates`, and errors (`ProviderUnavailableError` = retry later, `ProviderRequestError` = 4xx, `ProviderResponseError` = untrustworthy payload). `open_meteo.py` is the Open-Meteo client. Network I/O lives only in `urllib_transport`, and tests inject a fake transport (never hit the network). It requests past_days=1 + forecast_days=3, `timeformat=unixtime`, GMT. It checks the unit is μg/m³, converts CO to mg/m³, and turns absent or null variables into `None` (NH3 is always null for India). **Open-Meteo data are CAMS model forecasts/analyses on a ~0.1° grid, not CPCB ground-station observations.** Label them as "forecast/model AQI" everywhere, including the UI, README and video.

## Current state

This is the SaansSafe entry for **Environmental Hacks** (WeMakeDevs × AWS, Bharat Builds Tour event 02, Oct 8–11, 2026). `claude_read_this/` holds the event's web pages, saved as text. It is the source of truth for the rules.

- **Implemented and tested:** M0 (repo setup) and M1 (`backend/src/saanssafe/aqi.py`, the CPCB AQI engine, with `backend/tests/test_aqi.py`).
- **Implemented and tested (M2, part 1):** Open-Meteo data layer (`readings.py`, `providers/`).
- **Not implemented yet:** the rest of M2 (Lambda routing, DynamoDB cache, SAM template/deploy, frontend, hosting). There is no AWS infrastructure and nothing is deployed.
- Milestone progress is tracked at the top of `HACKATHON_MASTER_PLAN.md`.
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
