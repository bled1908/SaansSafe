// Validates a rendered MP4 against the submission requirements.
//   node scripts/validate.mjs out/saanssafe-v2-draft.mp4           (music bed, no narration yet)
//   node scripts/validate.mjs out/saanssafe-v2-final.mp4 --final   (narration + music)
// Exits non-zero if any check fails.

import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { buildTimeline } from '../src/timeline.js';

const file = process.argv[2];
const isFinal = process.argv.includes('--final');
const HARD_LIMIT_S = 179;            // absolute maximum 2:59
const WINDOW_S = [140, 170];         // requested 2:20-2:50
const SYNC_TOLERANCE_S = 0.05;

if (!file || !fs.existsSync(file)) {
  console.error(`Usage: node scripts/validate.mjs <file.mp4> [--final] (missing: ${file})`);
  process.exit(2);
}

const probe = spawnSync('npx', ['remotion', 'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', file], { shell: true, encoding: 'utf8' });
if (probe.status !== 0) {
  console.error('ffprobe failed:', probe.stderr);
  process.exit(2);
}
const info = JSON.parse(probe.stdout.slice(probe.stdout.indexOf('{')));
const video = info.streams.find((s) => s.codec_type === 'video');
const audio = info.streams.find((s) => s.codec_type === 'audio');
const duration = Number(info.format.duration);
const [num, den] = video.avg_frame_rate.split('/').map(Number);
const fps = num / den;

const script = JSON.parse(fs.readFileSync('src/script.json', 'utf8'));
const narrationPath = 'public/audio/v2/narration.json';
const narration = isFinal && fs.existsSync(narrationPath) ? JSON.parse(fs.readFileSync(narrationPath, 'utf8')) : null;
const timeline = buildTimeline(script, narration);

const checks = [
  ['Container is MP4', /mp4/.test(info.format.format_name)],
  ['Video codec H.264', video.codec_name === 'h264'],
  ['Resolution 1920x1080', video.width === 1920 && video.height === 1080],
  ['Frame rate 30 fps', Math.abs(fps - 30) < 0.01],
  ['Pixel format yuv420p (YouTube-safe)', video.pix_fmt === 'yuv420p'],
  [`Duration under ${HARD_LIMIT_S} s (2:59)`, duration < HARD_LIMIT_S],
  [`Duration inside requested ${WINDOW_S[0]}-${WINDOW_S[1]} s window`, duration >= WINDOW_S[0] && duration <= WINDOW_S[1]],
  ['Duration matches timeline (±0.5 s)', Math.abs(duration - timeline.totalSeconds) <= 0.5],
  ['Audio track present (AAC)', audio?.codec_name === 'aac'],
];

if (isFinal) {
  checks.push(['narration.json present (v2)', narration?.version === 2]);
  for (const scene of timeline.scenes) {
    for (const beat of scene.beats) {
      const fileOk = Boolean(beat.speech.file) && fs.existsSync(`public/audio/v2/${beat.speech.file}`);
      const fits = beat.speech.start + beat.speech.duration <= beat.start + beat.length + 0.001;
      const first = beat.captions[0];
      const last = beat.captions.at(-1);
      const synced = Math.abs(first.start - beat.speech.start) < SYNC_TOLERANCE_S
        && Math.abs(last.end - (beat.speech.start + beat.speech.duration)) < SYNC_TOLERANCE_S;
      checks.push([`${beat.id}: audio present, fits its beat, captions span its speech`, fileOk && fits && synced]);
    }
  }
}

let failed = 0;
for (const [label, ok] of checks) {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`);
  if (!ok) failed += 1;
}
const mb = (Number(info.format.size) / 1e6).toFixed(1);
console.log(`\n${file}: ${duration.toFixed(2)} s, ${video.width}x${video.height} @ ${fps} fps, ${video.codec_name}/${video.pix_fmt}, audio: ${audio ? `${audio.codec_name} ${audio.sample_rate} Hz` : 'none'}, ${mb} MB`);
process.exit(failed ? 1 : 0);
