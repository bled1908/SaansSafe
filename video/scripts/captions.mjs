// Exports the caption track as SRT for YouTube upload.
// Draft (no narration yet): out/captions-v2-draft.srt, estimated timing.
// Final: out/captions-v2.srt, timed from the measured narration in
// public/audio/v2/narration.json. Run from video/: node scripts/captions.mjs
// The burned-in captions in the MP4 come from the same timeline, so both match.

import fs from 'node:fs';
import { buildTimeline } from '../src/timeline.js';

const script = JSON.parse(fs.readFileSync('src/script.json', 'utf8'));
const narrationPath = 'public/audio/v2/narration.json';
const narration = fs.existsSync(narrationPath) ? JSON.parse(fs.readFileSync(narrationPath, 'utf8')) : null;
const timeline = buildTimeline(script, narration);

const stamp = (s) => {
  const ms = Math.round(s * 1000);
  const pad = (n, w = 2) => String(n).padStart(w, '0');
  return `${pad(Math.floor(ms / 3600000))}:${pad(Math.floor(ms / 60000) % 60)}:${pad(Math.floor(ms / 1000) % 60)},${pad(ms % 1000, 3)}`;
};

const srt = timeline.captions
  .map((c, i) => `${i + 1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${c.text}\n`)
  .join('\n');

fs.mkdirSync('out', { recursive: true });
const outFile = narration ? 'out/captions-v2.srt' : 'out/captions-v2-draft.srt';
fs.writeFileSync(outFile, srt);
console.log(`${outFile}: ${timeline.captions.length} cues, video ${timeline.totalSeconds.toFixed(2)} s`);
