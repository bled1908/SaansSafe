# SaansSafe demo video

**Published:** https://www.youtube.com/watch?v=7fcaFbYrZwM (2:44, 1920×1080, 30 fps, captions burned in, music only).

This folder builds the video reproducibly. It is separate from the app: nothing here is deployed, and the app is not modified.

## How it is made

| Step | Tool | What it does |
|---|---|---|
| Capture | `scripts/record.mjs` (Playwright) | Records the live site (desktop 1440×810 and a 390 px phone) and the live `GET /aqi` response in one session. Real data, real clicks; only a visible cursor is added. Writes `public/captures/` (git-ignored). |
| AWS evidence | `scripts/redact-aws.ps1` | Copies the AWS Console screenshots from `assets/aws/` to `public/aws/` with solid boxes over the account ID, user name and ARNs (both folders git-ignored). |
| Story | `src/script.json` | Scenes → beats. Each beat pairs one caption line with its visual: a footage segment with camera framing and spotlights, a kinetic-type card, the architecture diagram, or console screenshots. |
| Timing | `src/timeline.js` | Lays out every beat (from real narration audio if present, otherwise a reading-pace estimate) and builds the caption cues. Shared by the render, SRT export, music and validator. |
| Edit | `src/Video.tsx`, `src/visuals/` (Remotion) | Persistent app window, spotlights, kinetic type, AQI scale, AWS diagram and evidence rail, captions, grain. Footage is never colour-graded or altered. |
| Music | `scripts/music.mjs` | Synthesises an original ambient score and two UI effects from the timeline (no third-party or AI audio). |
| Checks | `scripts/validate.mjs` | Container, H.264, 1920×1080, 30 fps, yuv420p, AAC, duration under 2:59 and in the 2:20–2:50 window, length matches the timeline. |

## Commands (run from `video/`)

```bash
npm ci
npm run render:music      # generate the score, render out/saanssafe-final-music-only.mp4 (the published cut)
node scripts/validate.mjs out/saanssafe-final-music-only.mp4
node scripts/captions.mjs # SRT of the burned-in captions
npx remotion still src/index.ts Thumbnail out/youtube/saanssafe-thumbnail.jpg --image-format=jpeg
npm run studio            # Remotion Studio for previewing
npm run typecheck
```

Rendering uses Playwright's cached Chrome Headless Shell (see `remotion.config.ts`) and `--concurrency=3` to stay within memory on a 16 GB laptop (about 20 minutes).

Compositions: `SaansSafeMusicOnly` (published), `SaansSafeDraft` (review draft with badge), `SaansSafeFinal` (narrated variant; needs `public/audio/v2/narration.json`, not used), `Thumbnail` (1280×720).

`scripts/narrate.mjs` can synthesize narration with Amazon Polly, but every call needs `--confirm`; the published video has no narration.

## Accuracy rules the edit follows

- AQI inputs are CAMS model forecasts via Open-Meteo, never presented as CPCB station readings.
- The AQI uses India's National AQI method with CPCB breakpoints.
- School actions are SaansSafe's own policy (`saanssafe-school-v1`), not a CPCB rule.
- Parent notices come from deterministic templates; no language model makes AQI or school decisions.
- CloudFront is global; the regional resources run in ap-south-1.

## Generated files (git-ignored)

`public/captures/`, `public/aws/`, `public/audio/`, `assets/aws/`, `recordings/`, `out/` (renders, stills, SRT, `out/youtube/` upload kit and thumbnail).

## Licences

[Remotion](https://www.remotion.dev/license) is free for individuals and teams of up to three; this is an independent two-person student project. Playwright is Apache-2.0.
