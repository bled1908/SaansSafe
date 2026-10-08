# Hackathon Master Plan: Environmental Hacks (Bharat Builds Tour, Event 02)

> Status: **Concept locked: SaansSafe (Air track). AWS account 703321058941 confirmed.**
> Day-1 milestones: [x] M0 repo setup · [x] M1 AQI + tests (CPCB-verified, 124 passing) · [ ] M2 provider/API/cache · [ ] M3 SAM deploy + smoke test · [ ] M4 frontend · [ ] M5 S3+CloudFront live URL
> Written 2026-10-08 (Day 1). Sources: `claude_read_this/{overview,rules,schedule,mentors,community_partners}.md` and `claude_read_this/previous_winners/*.html` (First Commit, event 01).
> Future sessions: read this file and `SUBMISSION_CHECKLIST.md` instead of re-reading `claude_read_this/`.

---

## 1. The challenge in one paragraph

Over 4 days (Thu Oct 8 – Sun Oct 11, 2026, online across India, plus an optional build day at DTU Delhi on Oct 10), build **a new project** that helps fix a real environmental problem in India in one of three tracks: **Air**, **Heat & Water**, or **Waste & Energy**. The project **must use AWS**: at least one AWS open-source tool, deployment on AWS services, or both. The demo video must show that AWS use. Judges see only three things: a **public repo**, a **YouTube demo of 3 minutes or less**, and a **short writeup**. There's no live demo and no call. Judging covers Idea & Impact, Built on AWS, Design & Usability, Execution ("working beats polished") and the Demo Video. Each track has a winner (₹2L + $2k AWS credits), four runners-up across all tracks get $1k credits each, the top 5 blogs win AirPods, and up to 10 students (2027/2028 graduates) get Amazon fast-track interviews, decided separately from prizes.

## 2. Current project state

| Aspect | Finding |
|---|---|
| Code | **None.** The only contents are `claude_read_this/` (saved event pages), `CLAUDE.md` and these plan files. |
| Git | **Not a repo yet.** History must match the event dates, so `git init` happens at the start of implementation (see Q2). |
| Dependencies / config | None. |
| Reusable assets | None. Pre-event code would be disallowed anyway. |
| Local toolchain | git 2.53, Node 24.13, npm 11.8, Python 3.14.3, uv 0.12, **AWS CLI 2.37 already authenticated** (IAM user `amazon-ml-cli`, region `ap-south-1`). **Missing: SAM CLI, Docker/Finch.** |
| `claude_read_this/` | Saved third-party web pages that contain other people's names. **Do not publish them.** Add the folder to `.gitignore`. |

## 3. Requirements matrix

Key: R = required for a valid or prize-eligible submission, J = judged (affects score), O = optional.

| # | Requirement | Source | R/J/O | How we'll satisfy it | Verification |
|---|---|---|---|---|---|
| 1 | Every member is a university student in India, aged 18+ | rules §01 | R | Already true (team leader is registered) | Each member confirms |
| 2 | Every member has their own WeMakeDevs account, registered for the tour and checked in to this hackathon | rules §01–02 | R | Each teammate registers themselves (the captain can't do it for them) | Team page shows each member |
| 3 | AWS Builder Center profile with verified enrollment (SheerID) | rules §01, §06 | R (for rewards and the interview) | Verify **today**. An open SheerID case doesn't block submitting | Builder Center profile shows "verified" |
| 4 | Team of 1–4. One submission per team. One team per person. Team locked after submit | rules §02, overview | R | Finalize the roster before submitting | Team page |
| 5 | Project built new, after the clock starts. Repo history must match the event dates | rules §03, §05 | R (DQ risk) | `git init` after kickoff, small frequent commits, nothing pre-written copied in | `git log --reverse` shows first commit ≥ kickoff |
| 6 | Open-source libraries, public APIs and templates are allowed, with credit and a compatible licence | rules §03 | R | `CREDITS` section in the README, plus a LICENSE (MIT) | README review |
| 7 | **Project uses AWS**: ≥1 AWS open-source tool **or** deployed on AWS | overview "Two ways", judging #2, rules §03 | R (prize eligibility) | **Both**: Strands Agents SDK and SAM CLI (open source) **plus** Lambda, API Gateway, DynamoDB, Bedrock, EventBridge, SNS, Amplify/CloudFront (deployed) | Live URL works; `template.yaml` in repo |
| 8 | **The demo video shows the AWS use.** Naming AWS in the writeup alone isn't enough | rules §03 | R | A ~25s segment in the video: architecture diagram plus console/CloudWatch shots of the live stack | Watch the final cut |
| 9 | Stay within the Free Tier and $200 credits (+$25 on request) | overview Resources | O / practical | Serverless, pay-per-request, a Bedrock model with low cost per token, AWS Budgets alarm at $20 | AWS Budgets |
| 10 | Pick a track: Air, Heat & Water, or Waste & Energy | overview Tracks | R | **Recommended: Air** (§5). Decision needed (Q1) | Shown in the writeup and the submission form |
| 11 | **Public repository** | rules §04 | R | GitHub public repo with README, LICENSE, architecture, setup and deploy steps | Open it in a signed-out browser |
| 12 | **Demo video ≤ 3 min on YouTube, public or unlisted, link opens signed out** | rules §04 | R | Target **2:40–2:50**, unlisted, checked in an incognito window | Incognito check plus duration check |
| 13 | **Short writeup**: problem, build, where AWS fits | rules §04 | R | `WRITEUP.md` drafted Day 3, pasted into the form | Checklist |
| 14 | **List the AI coding tools used** in the writeup | rules §03 | R | "Built with Claude Code (Anthropic)" plus any others used | Present in the writeup |
| 15 | Submit via the hackathon's own form, once per team, before the deadline. Late = rejected | rules §04, schedule | R | Team leader submits **Oct 11 morning**, as soon as the form opens at 8:00 AM IST (the exact deadline is TBA) | Confirmation email/screenshot |
| 16 | Judges score only what's submitted. A feature not in the video doesn't count | rules §04 | R / J | Script the video around the P0/P1 features. Leave out anything that isn't fully working | Storyboard review |
| 17 | Judging 1: **Idea & Impact**, a real problem for a specific group of people | overview Judging | J | A specific user (school principals in Delhi-NCR during stubble season), a concrete before/after | Problem statement passes a "who exactly, what changes" test |
| 18 | Judging 2: **Built on AWS** | overview Judging | J | A sensible serverless architecture, with cost and design rationale in the README | Architecture diagram |
| 19 | Judging 3: **Design & usability**, a stranger can use it where they are | overview Judging | J | Mobile-first, Hindi + English, one-screen answer ("Can kids go out today?") | Hallway test with someone outside the team |
| 20 | Judging 4: **Execution**, it works | overview Judging | J | A walking skeleton deployed on Day 1, a data cache so the demo never breaks | Smoke-test script against the live URL |
| 21 | Judging 5: **Demo video**: what it does, who it's for, where AWS fits | overview Judging | J | Storyboard in §8 | Peer review of the cut |
| 22 | The work is your own. Third-party work is credited | rules §03 | R | Credits section (data sources: Open-Meteo, CPCB/data.gov.in, etc.) | README |
| 23 | Rights: WeMakeDevs/AWS may showcase the project | rules §03 | Info | No action needed | — |
| 24 | Blog on AWS Builder Center, linked in the submission (top 5 win AirPods) | overview Prizes | O | Publish Day 4 from `WRITEUP.md` (problem, stack, what fought back) | Link in the form |
| 25 | Fast-track interview: 2027/2028 graduates, profile verified before the event | rules §06, §08 | O | Builder Center details correct and verified | Profile check |
| 26 | Code of conduct | rules §07 | R | — | — |
| 27 | Optional DTU build day, Oct 10 (separate Luma signup). Attending doesn't affect score | overview, schedule | O | Worth attending if in Delhi: AWS mentor feedback mid-build | Luma confirmation |
| 28 | Request $25 credits: one form per team, leader only, after the free credits run out | overview Resources | O | Only if needed | — |

## 4. Every submission deliverable

1. **Public GitHub repo** (code, README, LICENSE, architecture diagram, IaC `template.yaml`, credits, AI-tools disclosure)
2. **YouTube demo video** ≤ 3:00, public or unlisted, link checked signed out, AWS visibly shown
3. **Writeup** (problem → build → where AWS fits → AI tools used → what fought back)
4. **Submission form** entry by the team leader, before the deadline
5. *(Optional, recommended)* **Live deployed URL**. Every previous winner had one
6. *(Optional)* **AWS Builder Center blog post**, linked in the form
7. *(Pre-condition)* every member registered, checked in, and with a verified Builder Center profile

## 5. Recommended concept (decision needed: Q1)

Signal from event 01: the winners were **agentic AI apps with a sharply defined user**, nearly all with a **Live URL**. The Ship It winner beat the Build It winner. "Best UI" was its own prize. Judges reward a specific user, a working core and a clear demo.

### ⭐ Recommendation: Air track, "school safety on bad days" (working title **SaansSafe**)
- **User:** school principals and PE teachers in Delhi-NCR, plus the parents they notify.
- **Problem:** in October and November (stubble burning, the GRAP stages), schools decide every morning whether to hold outdoor assembly, PE or sports, often from a headline AQI number with no forecast or per-hour detail. Children are the most exposed group.
- **What it does:** you pick your school or location. It shows the Indian AQI now and the AQI forecast for the next 72 hours, by hour. A **deterministic rules engine** (CPCB AQI breakpoints, CPCB health advisories, GRAP stage) outputs a clear **decision card**, for example "Outdoor PE: shift 10:00 → 15:00" or "Cancel outdoor assembly Tue". An agent built with the **Strands Agents SDK**, using a Bedrock model, writes a **parent notice in Hindi and English** that can be shared on WhatsApp, and answers questions like "Can we hold sports day Friday?". Scheduled alerts arrive by email the evening before a bad day.
- **Why it wins:** the problem is timely (the event happens in Delhi, in October, during peak AQI), the user is specific, the before/after is visible in one screen, it fits the "School safety on bad days" topic the organizers listed themselves, and it makes heavy, meaningful use of AWS.

### Alternatives (if you prefer)
- **Heat & Water:** a heat-stress shift planner for outdoor workers or gig workers (heat index forecast → safe work windows plus a Hindi voice alert). Same architecture.
- **Waste & Energy:** photo-based waste segregation helper plus a finder for nearby e-waste and kabadiwala (informal scrap dealer) drop-offs (a Bedrock vision model). Harder to make data-reliable in 4 days.

The architecture below transfers to the Heat alternative with little change.

## 6. Recommended solution architecture (Ship It + Build It together)

```
[Mobile-first web app: React + Vite + Tailwind, Hindi/EN]
        │  hosted on Amplify Hosting (or S3 + CloudFront)
        ▼
[API Gateway HTTP API] ──► [Lambda (Python): /aqi /decision /notice /ask]
                               │        │
                               │        └─► Strands Agents SDK agent ──► Amazon Bedrock (Claude Haiku / Nova Lite)
                               │              tools: get_forecast, get_decision, cpcb_advisory, grap_stage
                               ▼
                         [DynamoDB]  (schools/subscriptions, cached readings and forecasts with TTL)
                               ▲
[EventBridge Scheduler: hourly] ─► [Lambda ingest] ◄── Open-Meteo Air Quality API (72h PM2.5/PM10/NO2/O3/CO/SO2, no key)
                                                   ◄── CPCB real-time via data.gov.in (observed, free API key)
[EventBridge Scheduler: 18:00 IST] ─► [Lambda alerts] ─► SNS email (SMS to India needs DLT: avoid)
Observability: CloudWatch logs/alarms. IaC: AWS SAM (`template.yaml`), deployed with `sam deploy`.
```

Design principles:
- **Numbers are deterministic, words come from the LLM.** AQI calculation (CPCB sub-index method) and decisions are pure Python functions with unit tests. The LLM only explains, translates and answers questions, based on tool outputs. This prevents hallucinated AQI values from appearing in the demo.
- **Cache first.** The ingest Lambda writes to DynamoDB, and the API reads from the cache. If an upstream API is flaky, the demo still works. A seeded "demo snapshot" acts as a last-resort fallback.
- **Region:** `ap-south-1`. If the chosen model isn't available there, use Bedrock cross-region inference (APAC profile). Check this on Day 1.
- **Cost:** everything is pay-per-request. Bedrock is the only metered item (cents per day at demo volumes). Set a Budgets alarm.
- **Tooling to install:** SAM CLI (via `winget`/MSI). Docker is optional, since we deploy with `sam deploy` and test logic with pytest locally instead of `sam local`.

## 7. Prioritized backlog

| Pri | Item |
|---|---|
| **P0** | Git repo created after kickoff + public GitHub remote + LICENSE + `.gitignore` (excluding `claude_read_this/`) |
| P0 | SAM stack deployed: API Gateway → Lambda → DynamoDB, live URL (walking skeleton, **Day 1**) |
| P0 | AQI ingest (Open-Meteo forecast) + CPCB Indian AQI calculation (unit-tested) |
| P0 | Decision engine: per-hour outdoor-activity verdict for a school day |
| P0 | Frontend: location/school picker → AQI now, 72h strip, decision card. Deployed |
| P0 | Strands agent on Bedrock generating the parent notice (EN + Hindi) |
| P0 | Video ≤3 min showing AWS · writeup with AI-tools disclosure · README · form submitted |
| **P1** | "Ask" chat backed by agent tools (grounded Q&A, e.g. sports-day planning) |
| P1 | Evening alert email (EventBridge Scheduler + SNS) |
| P1 | Observed CPCB station data next to the forecast + GRAP stage banner |
| P1 | Architecture diagram + cost note in the README. Polished mobile UI, Hindi toggle |
| P1 | Share-to-WhatsApp / printable notice |
| **P2** | Map of nearby stations · multi-school dashboard for a district officer · Cognito login |
| P2 | AWS Builder Center blog post |
| P2 | Accessibility pass, PWA install |
| **P3** | NASA FIRMS stubble-fire overlay · voice notice (Amazon Polly, Hindi) · indoor-air checklist |

## 8. 4-day execution plan

**Day 1 (Thu Oct 8): Foundations and walking skeleton**
- Team: everyone checks in, Builder Center verification, settle the concept and track (Q1).
- Install SAM CLI. `git init` after kickoff. Public GitHub repo.
- Check that the Bedrock model works from ap-south-1. Set up a Budgets alarm.
- Scaffold `backend/` (SAM, Python, pytest) and `frontend/` (Vite React TS, Tailwind).
- Implement and test the CPCB AQI calculator. Ingest Lambda for Open-Meteo. DynamoDB cache.
- **Exit criterion:** the live URL shows real AQI for one Delhi location, end to end on AWS.

**Day 2 (Fri Oct 9): Core value**
- Decision engine + tests. Decision card UI. 72h forecast strip.
- Strands agent + tools. Notice generation in EN/Hindi.
- Location search (geocoding via Open-Meteo), with a list of sample schools seeded.
- **Exit criterion:** the full P0 flow works on the live URL. Smoke test passes.

**Day 3 (Sat Oct 10): P1, polish, outside feedback** (DTU build day optional)
- Ask chat, evening alerts, CPCB observed data, GRAP banner.
- UI polish, mobile pass, test with someone outside the team. Mentor feedback if attending.
- Architecture diagram, README, `WRITEUP.md` draft, video storyboard.
- **Feature freeze at 20:00.** Afterwards, only bug fixes.

**Day 4 (Sun Oct 11): Ship**
- Morning: final smoke test, record the video (2:40–2:50), upload unlisted, check signed out.
- Finalize the writeup, then the team leader **submits as early as possible after the form opens at 08:00**.
- Afterwards: Builder Center blog post (it can still be linked if the form allows edits; otherwise publish before submitting).

**Video storyboard (≤3:00):** 0:00 hook (a real Delhi AQI headline + a principal's morning dilemma) → 0:20 who it's for → 0:35 live demo: pick school → decision card → 72h strip → Hindi notice → WhatsApp share → ask "sports day Friday?" → 1:55 evening alert email → 2:10 **AWS: architecture diagram + console (Lambda, DynamoDB, Bedrock, EventBridge) + `sam deploy`** → 2:35 impact + close.

## 9. Highest-impact features (where to spend effort)
1. **The decision card.** One glance answers "can kids go outside, and when?" This drives Impact, Usability and the demo at the same time.
2. **The Hindi/English parent notice, shareable on WhatsApp.** This is how schools in India actually communicate, so it's a strong usability point.
3. **The hourly 72h forecast that finds safe windows.** Better than a single AQI number; it turns data into a plan.
4. **Live deployment with visible AWS architecture.** Covers the "Built on AWS" criterion and matches every previous winner.
5. **A grounded agent with tools, not a chatbot.** It shows the Strands SDK being used properly.

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Repo history before kickoff, or reused old code | **DQ of whole team** | `git init` only after the official start. Commit often. Nothing pre-written goes in except these planning docs (planning is explicitly allowed) |
| Deadline time not yet published | Missed submission | Watch the schedule page and Discord. Submit Sunday morning |
| Video >3 min, private, or AWS not shown | Rejection / lost points | 2:45 target, incognito check, AWS segment in the storyboard |
| Feature only in the writeup or README | Not counted | The video shows every feature claimed |
| Upstream AQI API down or slow during recording | Broken demo | DynamoDB cache + seeded snapshot fallback |
| Bedrock model not enabled or not in ap-south-1 | Agent blocked | Check on Day 1. Cross-region profile. Fall back to Nova Lite |
| LLM hallucinates numbers or health advice | Credibility | Deterministic engine. LLM limited to tool outputs. Disclaimer citing CPCB advisories |
| AWS costs or credit overrun | Account issues | Budgets alarm, pay-per-request only, no NAT/EC2 |
| SMS alerts to India blocked (DLT) | Feature fails | Use email (SNS) |
| Scope creep across 3 days of building | Nothing finished | Freeze P0 by Day 2 night, features by Day 3 at 20:00 |
| Teammate not registered or verified | Ineligible member | Check on Day 1 |
| Publishing `claude_read_this/` (third-party pages, names) | Licence and privacy | `.gitignore` |
| Secrets committed (data.gov.in key) | Security | SSM Parameter Store / env, `.gitignore`, pre-commit scan |
| Windows-specific tooling friction (SAM without Docker) | Time lost | `sam build` without a container (pure Python deps), pytest locally |

## 11. Ambiguities and open questions (need your decision)
- **Q1. Track and concept.** Go with Air / SaansSafe (recommended), the Heat alternative, or your own idea?
- **Q2. Kickoff time.** When does the clock officially start today? `git init` must come after it. Should these planning docs go into the repo's first commit? (Recommended: yes. Planning is allowed, and they're dated today.)
- **Q3. Team.** Who are the members, and what are their skills (frontend, backend, video)? The roster showed 2 of 4 seats filled at the last capture. Is everyone 2027/2028 graduating and verified on Builder Center?
- **Q4. Build It vs Ship It weighting.** The FAQ "What happened to Build It and Ship It?" wasn't captured (collapsed). Please expand it on the site and paste the answer. Also paste "Can I start building before the event?". The plan does both regardless, which is the safe choice.
- **Q5. Writeup format.** Is it a field in the form (with a length limit) or a link? Unknown until the form opens on Oct 11.
- **Q6. Bedrock model choice and budget comfort.** OK to spend a few dollars of the $200 credits on Bedrock (Claude Haiku-class)?
- **Q7. DTU Oct 10.** Is anyone attending in person? If so, plan a mentor-feedback checkpoint.
- **Q8. GitHub account/org** for the public repo, and is the `gh` CLI authenticated?

## 12. AQI assumptions: CPCB verification and final decisions (resolved 2026-10-08)

> **Final decisions (implemented in `aqi.py`, 124 tests passing):**
> - **V1:** every pollutant, O3/CO included, needs ≥16 valid hours in the latest 24 (CPCB §3.7, p.46 [44]). The unsupported 6/8 rule is removed.
> - **V2:** O3/CO use the **latest 8-hour window**. This is a **SaansSafe product decision, not a CPCB requirement**. CPCB confirms the 8-hour period and describes running 8-hour averages (Table 3.11; §3.5, p.40–41 [38–39]) but doesn't prescribe latest vs. maximum. We chose "latest" because the product answers "what is the air like now / in the next hours".
> - **V3:** no interpolation above the published Severe threshold. At or above it the sub-index is **401**, the category is Severe, `beyond_scale=True`, and the AQI is shown as **"401+"** with an explanatory note (Table 3.11 Severe row, p.37 [35]).
> - **V4:** the CPCB rule "subtract one from I_LO if I_LO > 50" is implemented (§3.5, p.39 [37]), so PM2.5 = 31 gives AQI 50.
> - **V5:** NH3 Very Poor is 1201–1800 (Table 3.11).
>
> The original assumptions and evidence are kept below for traceability.

These are implemented in `backend/src/saanssafe/aqi.py` and covered by tests, but **not yet verified against an authoritative CPCB source** (the National AQI technical document and calculator). Verify each one before building the data-provider layer. Change the code only with a cited source.

| ID | Assumption as implemented | Alternative to check | Where in code |
|---|---|---|---|
| V1 | 24 h averages need ≥16/24 valid hours, 8 h averages ≥6/8 | A different completeness threshold, or none | `MIN_VALID_HOURS` |
| V2 | O3 and CO use the **latest** 8 h rolling average | The **maximum** 8 h average within the past 24 h | `rolling_average` / `AVERAGING_HOURS` |
| V3 | Open-ended Severe band ("X+") extended by the Very Poor band's width (PM2.5 → 379, PM10 → 509), AQI capped at 500 | Officially published Severe upper breakpoints (e.g. PM2.5 380, PM10 510?) | `_build_bands` |

### Verification results (2026-10-08). Code NOT changed yet. Awaiting decision.

**Source:** CPCB, *National Air Quality Index*, Control of Urban Pollution Series CUPS/82/2014-15 (the final report; its foreword says the draft was launched in Oct 2014 for public comment). URL: https://cpcb.nic.in/upload/national-air-quality-index/FINAL-REPORT_AQI_.pdf (58 pp; sha256 prefix d2b0fd754a8f9fb3). Page numbers below are PDF pages, with the printed page number in brackets.

| ID | Official finding | Status |
|---|---|---|
| V1 | §3.7, p.46 [44]: "a minimum of 16 hours' data is considered necessary for calculating subindex." The rule is stated once, for every sub-index. **There is no separate threshold for 8-hour O3/CO.** | 16/24 **confirmed**. 6/8 **unsupported, must change** |
| V2 | Table 3.11, p.37 [35]: O3 and CO use an "8-hr" averaging time. §3.5 worked example, p.40–41 [38–39]: "The AQI for CO and O3 has been calculated for running 8-hr averages. This will give 23 AQI values; here maximum and min AQI of CO and O3 are presented." This is an illustration, not a rule. | **Unresolved.** The source doesn't say whether to use the latest or the maximum 8-hour average |
| V3 | Table 3.11, p.37 [35], Severe (401–500) row: PM10 "430 +", PM2.5 "250+", NO2 "400+", O3 "748+*", CO "34+", SO2 "1600+", NH3 "1800+". **No upper concentration is published.** The formula (§3.5, p.39 [37]) needs B_HI, so the official method can't interpolate within Severe. The report says the Excel calculator "can be obtained from CPCB"; it isn't public, and we didn't obtain it. | Our 379/509 extension is **not official, must redesign** |
| V4 (new) | §3.5, p.39 [37], formula definitions: "I_LO = AQI value corresponding to B_LO; **subtract one from I_LO, if I_LO is greater than 50**". So for Satisfactory and above, interpolation starts at 50/100/200/300/400, not at 51/101/201/301/401. Example: PM2.5 = 31 gives 50, not 51. | Our implementation **differs, must change** |
| V5 (new) | Table 3.11: NH3 Very Poor is "1201-1800" (we use 1200). The O3 "209-748*" footnote reads "*One hourly monitoring (for mathematical calculation only)". | Minor fix (NH3 isn't used for India via Open-Meteo) |
