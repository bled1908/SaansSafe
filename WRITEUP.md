# SaansSafe — writeup

**Team Shadow Protocol** (Subhadeep Roy, Sneha Singha) · Environmental Hacks, Air track

- Live app: https://d316zs0sydbi1r.cloudfront.net
- Demo video (2:44): https://www.youtube.com/watch?v=7fcaFbYrZwM
- Code: https://github.com/bled1908/SaansSafe

## The problem

Every school morning in an Indian city, a principal or PE teacher decides whether children line up outside for assembly, run in PE, or play at recess. Air quality is published as a number and a CPCB category ("145, Moderate"), and CPCB's health statements describe effects on health, including on children, but no official source says what a school should do about assembly, PE or recess. Each school is left to translate a number into a decision, usually in a hurry.

SaansSafe is for the person at the school who makes that call, on the phone they already carry.

## What we built

SaansSafe turns an air-quality forecast into a clear, explainable school decision:

- **Today's decision:** one headline action (e.g. "Reduce strenuous outdoor activity") with guidance for assembly, PE & sports and recess (Allowed / Limited / Move indoors).
- **Next 72 hours:** the same policy applied hour by hour: the best school window (Monday–Friday school hours only), the next change in advice and the worst expected hour.
- **Parent notice:** one tap turns the decision into a notice in English or Hindi from fixed, verified templates. It repeats the decision and never changes it; nothing is sent until a teacher shares it.
- **Provenance on every screen:** data source, model grid cell, fetch time, cache status and policy version.

**How a decision is made.** CAMS air-quality model forecasts, accessed through Open-Meteo, go into our AQI engine, which implements India's National AQI method with CPCB breakpoints (sub-indices, 16-of-24-hour validity, 24 h/8 h averages, "401+" above Severe). The CPCB category then maps to an action through SaansSafe's own published school policy (`saanssafe-school-v1`). That policy is ours, not a CPCB rule, and the app says so. Every number and decision comes from tested, deterministic Python: **no language model calculates the AQI, makes the decision or writes the notices.**

**Honest data labelling.** The inputs are model forecasts for a grid cell, not readings from CPCB monitoring stations. The app, API, README and video label them "forecast/model" everywhere.

## Where AWS fits

Everything is serverless, defined as code with the **AWS SAM CLI** (an AWS open-source tool) in two stacks, and deployed to AWS:

| Service | Role |
|---|---|
| **Amazon CloudFront** (global) + **private Amazon S3** (Origin Access Control) | Serves the React app over HTTPS; the bucket blocks all public access. Stack `saanssafe-web`. |
| **Amazon API Gateway** (HTTP API) | Public JSON API (`/aqi`, `/forecast`, `/notice`) with CORS limited to the site and throttling. |
| **AWS Lambda** (2 Python 3.13 functions, arm64, ap-south-1) | `ApiFunction` computes AQI, decisions and the 72-hour outlook; `NoticeFunction` builds parent notices. No third-party runtime dependencies. |
| **Amazon DynamoDB** (on-demand) | Caches forecasts per grid cell (fresh for 60 min, TTL cleanup), cutting calls to the provider; if the provider is briefly down, data up to 6 h old is served, clearly marked stale. |
| **Amazon CloudWatch Logs** | Function logs with 14-day retention. |

The regional resources run in **ap-south-1 (Mumbai)**. The video shows the architecture and redacted console screenshots of each service and both CloudFormation stacks.

## AI coding tools used

**Claude Code (Anthropic)** was used throughout, under the team's direction: planning, writing code and tests, code review, AWS deployment commands (every change set reviewed before execution), browser QA, the demo-video pipeline and documentation. Each milestone was reviewed and approved by the team before it was committed. The running app uses no AI.

## What fought back

- **Getting the AQI rules right.** We implemented the CPCB method from the National AQI report (CUPS/82/2014-15) and verified edge cases — validity thresholds, averaging windows and the open-ended Severe band — before trusting any number. The backend now has 637 passing tests; the frontend has 83.
- **Model data vs station data.** Open-Meteo provides CAMS model forecasts, not CPCB station readings. We relabelled everything as forecast/model AQI and kept school actions separate from CPCB's health statements, so nothing overstates what the data are.
- **AI we chose not to ship.** An optional Strands Agents + Amazon Bedrock notice writer exists in the code, but Bedrock access wasn't authorized on our account, and a deterministic template is safer for messages to parents. Production uses verified templates only (`NOTICE_AI_ENABLED=false`).
- **Small things that matter on a phone.** We fixed a location picker that overflowed narrow screens and an IST clock and freshness label that could mislead; the layout is checked at 320–1440 px.
- **No Docker.** Keeping the backend free of third-party runtime dependencies let us deploy with SAM without a container build.

## What's next

Real school calendars and holidays, alerts the evening before a restricted day, and, where available, station readings shown alongside the forecast.
