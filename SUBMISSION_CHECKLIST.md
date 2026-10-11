# Submission Checklist: Environmental Hacks

Deadline: **Sun Oct 11, 2026**. The form opens 08:00 IST; the exact closing time is TBA (watch the schedule page and Discord). Late = rejected. Submit once per team, team leader only.

## Eligibility (Day 1)
- [ ] Every member has their own WeMakeDevs account, registered for the tour and **checked in** to Environmental Hacks
- [ ] Every member has an AWS Builder Center profile with **student enrollment verified** (SheerID)
- [ ] Team roster final (1–4). It can't change after submission
- [ ] Interview eligibility: graduating 2027/2028, registration details correct

## Repository (public)
- [ ] First commit is after the kickoff. The first commit (`a523bc3`) is 2026-10-08 10:36 IST; confirm against the official kickoff time once it's published
- [x] Repo is **public**: https://github.com/bled1908/SaansSafe (HTTP 200 signed out, 11 Oct). Push the final docs/video source before submitting
- [x] README: problem, who it's for, features, screenshots, **live URL**, **architecture diagram**, AWS services and why, setup and deploy (`sam deploy` per stack; no `sam build` step), **video link**, team name
- [x] LICENSE file (MIT)
- [x] Credits: every third-party library, API and data source (Open-Meteo, Copernicus CAMS, CPCB report, npm/Python libraries, fonts) in the README
- [x] AI coding tools disclosed (Claude Code) in the README
- [ ] No secrets in the tree or history. `claude_read_this/` never committed (checked). No keys or `.env` files in history. Account ID and IAM user name were redacted from `HACKATHON_MASTER_PLAN.md` at HEAD but remain in commit `a523bc3`; decide whether that's acceptable before going public
- [x] IaC in the repo: `backend/template.yaml`, `infra/web/template.yaml`

## AWS usage
- [x] Uses ≥1 AWS open-source tool (SAM CLI; Strands Agents SDK is in code but not active in production) **and** is deployed on AWS
- [x] Live URL works on mobile (checked at 320–390 px in a clean browser profile); recheck on a real phone in incognito before submitting
- [ ] Budgets alarm set. Free-tier and credits usage checked

## Demo video
Link: **https://www.youtube.com/watch?v=7fcaFbYrZwM** · source and build steps in [`video/`](video/README.md)
- [x] **≤ 3:00**: 2:43.9 (validated: H.264, 1920×1080, 30 fps, AAC)
- [x] Uploaded to **YouTube**, **public or unlisted**
- [x] Link opens signed out (YouTube oEmbed and watch page reachable without login, 11 Oct); still worth one incognito playback at 1080p
- [x] Shows: the problem, who it's for, the working core flow end to end (decision, Mumbai, data source, 72-hour outlook, English/Hindi notice, phone)
- [x] **Shows the AWS use on screen**: architecture diagram plus redacted console screenshots (CloudFront, S3, API Gateway, Lambda, DynamoDB, CloudFormation/SAM)
- [x] Every feature claimed in the writeup appears in the video (decision, 72-hour outlook, English/Hindi notice, provenance, phone, AWS)
- [x] Captions burned in (music only, no narration); SRT available
- [ ] YouTube description: add the live and repo links once the channel is verified for links

## Writeup ([WRITEUP.md](WRITEUP.md); paste into the form, trimming if it has a length limit)
- [x] The problem (a specific user, a specific place)
- [x] What we built and how
- [x] Where AWS fits (each service and why)
- [x] AI coding tools used
- [x] What fought back / what we learned
- [x] Links: repo, live URL, video (blog optional; add if published)

## Submission form
- [ ] Final smoke test on the live URL just before submitting
- [ ] Submitted by the team leader. Confirmation screenshot saved
- [ ] (Optional) AWS Builder Center blog published and linked
