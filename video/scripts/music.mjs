// Generates an original, restrained music bed and two UI effects locally,
// timed to the edit (no third-party audio, so no licensing questions).
//
//   node scripts/music.mjs           -> public/audio/music-draft.wav (estimated timing)
//   node scripts/music.mjs --final   -> public/audio/music-final.wav (needs audio/v2/narration.json)
// Always (re)writes public/audio/sfx/whoosh.wav and tick.wav.
//
// Score: a slow D-major pad (I-vi-IV-V) whose brightness follows the story:
// dark and sparse for the problem, opening up with soft plucks when the
// product appears, a gentle pulse under the AWS section, and a resolving
// swell on the final title.

import fs from 'node:fs';
import { buildTimeline } from '../src/timeline.js';

const SR = 44100;
const isFinal = process.argv.includes('--final');
const script = JSON.parse(fs.readFileSync('src/script.json', 'utf8'));
const narrationPath = 'public/audio/v2/narration.json';
if (isFinal && !fs.existsSync(narrationPath)) throw new Error(`${narrationPath} missing: synthesize narration first`);
const timeline = buildTimeline(script, isFinal ? JSON.parse(fs.readFileSync(narrationPath, 'utf8')) : null);

const SCENE_MOOD = {
  hook: { bright: 0.12, pluck: 0, bass: 0 },
  problem: { bright: 0.22, pluck: 0, bass: 0.4 },
  product: { bright: 0.55, pluck: 1, bass: 1 },
  provenance: { bright: 0.5, pluck: 1, bass: 1 },
  outlook: { bright: 0.6, pluck: 1, bass: 1 },
  notices: { bright: 0.65, pluck: 1, bass: 1 },
  aws: { bright: 0.68, pluck: 2, bass: 1 },
  build: { bright: 0.58, pluck: 1, bass: 1 },
  end: { bright: 0.85, pluck: 0, bass: 1 },
};

const midi = (m) => 440 * 2 ** ((m - 69) / 12);
const CHORDS = [
  { bass: 38, pad: [57, 62, 66, 69, 76] },  // D add9
  { bass: 47, pad: [54, 57, 62, 66, 73] },  // Bm7
  { bass: 43, pad: [55, 59, 62, 66, 71] },  // Gmaj7
  { bass: 45, pad: [57, 59, 64, 69, 73] },  // Asus2
];
const CHORD_S = 6.4;

const TABLE_SIZE = 8192;
const SINE = Float32Array.from({ length: TABLE_SIZE + 1 }, (_, i) => Math.sin((2 * Math.PI * i) / TABLE_SIZE));
const sin = (cycles) => SINE[Math.floor((cycles - Math.floor(cycles)) * TABLE_SIZE)];

// ---- Timeline-driven parameters
const total = timeline.totalSeconds + 0.4;
const N = Math.ceil(total * SR);
const finalAt = timeline.scenes.at(-1).beats.at(-1).start;
const sceneAt = (t) => timeline.scenes.find((s) => t < s.start + s.length) ?? timeline.scenes.at(-1);

function moodAt(t) {
  const scene = sceneAt(t);
  const prev = timeline.scenes[timeline.scenes.indexOf(scene) - 1];
  const now = SCENE_MOOD[scene.id] ?? SCENE_MOOD.product;
  if (!prev) return now;
  const before = SCENE_MOOD[prev.id] ?? now;
  const p = Math.min(1, (t - scene.start) / 2);
  return { bright: before.bright + (now.bright - before.bright) * p, bass: before.bass + (now.bass - before.bass) * p, pluck: now.pluck };
}
// Sampled at 100 Hz so the per-sample loops stay cheap.
const MOOD_RATE = 100;
const MOODS = Array.from({ length: Math.ceil(total * MOOD_RATE) + 1 }, (_, i) => moodAt(i / MOOD_RATE));
const mood = (t) => MOODS[Math.min(MOODS.length - 1, Math.floor(t * MOOD_RATE))];

/** Chord segments on a fixed grid, with the last one forced to the tonic on the final title. */
function chordSegments() {
  const segs = [];
  for (let t = 0, i = 0; t < finalAt; t += CHORD_S, i += 1) segs.push({ start: t, end: Math.min(t + CHORD_S, finalAt), chord: CHORDS[i % 4] });
  segs.push({ start: finalAt, end: total, chord: CHORDS[0], final: true });
  return segs;
}

// ---- Synthesis
const L = new Float32Array(N);
const R = new Float32Array(N);

function addPad(seg) {
  const attack = seg.final ? 0.6 : 1.8;
  const release = 2.6;
  const from = Math.floor(seg.start * SR);
  const to = Math.min(N, Math.floor((seg.end + release) * SR));
  const voices = seg.chord.pad.flatMap((m, n) => [-6, 6].map((cents, side) => ({ f: midi(m) * 2 ** (cents / 1200), side, n })));
  const gain = 0.05 / Math.sqrt(voices.length / 2);
  for (const v of voices) {
    const phases = new Float64Array(6);
    for (let s = from; s < to; s += 1) {
      const t = s / SR;
      const local = t - seg.start;
      const env = Math.min(1, local / attack) * (t > seg.end ? Math.max(0, 1 - (t - seg.end) / release) : 1);
      for (let k = 1; k <= 6; k += 1) phases[k - 1] += (v.f * k) / SR;
      if (env <= 0) continue;
      const bright = mood(t).bright + (seg.final ? 0.15 * Math.min(1, local / 2) : 0);
      let sample = 0;
      for (let k = 1; k <= 6; k += 1) sample += sin(phases[k - 1]) * (1 / k ** 1.4) * Math.exp(-(k - 1) * (1.7 - 1.4 * bright));
      const pan = 0.5 + (v.side ? 0.18 : -0.18) * Math.sin(t * 0.21 + v.n);
      const x = sample * env * gain;
      L[s] += x * (1 - pan);
      R[s] += x * pan;
    }
  }
}

function addBass(seg) {
  const from = Math.floor(seg.start * SR);
  const to = Math.min(N, Math.floor((seg.end + 1.5) * SR));
  const f = midi(seg.chord.bass);
  let phase = 0;
  for (let s = from; s < to; s += 1) {
    const t = s / SR;
    const env = Math.min(1, (t - seg.start) / 1.2) * (t > seg.end ? Math.max(0, 1 - (t - seg.end) / 1.5) : 1);
    phase += f / SR;
    const x = (sin(phase) + 0.25 * sin(phase * 2)) * 0.11 * env * mood(t).bass;
    L[s] += x;
    R[s] += x;
  }
}

function addPluck(at, f, amp, pan) {
  const from = Math.floor(at * SR);
  const to = Math.min(N, from + Math.floor(1.6 * SR));
  for (let s = from; s < to; s += 1) {
    const t = (s - from) / SR;
    const env = Math.min(1, t / 0.006) * Math.exp(-t / 0.55);
    const x = (sin(f * t) + 0.32 * sin(2 * f * t) + 0.08 * sin(3.01 * f * t)) * amp * env;
    L[s] += x * (1 - pan);
    R[s] += x * pan;
  }
}

function addPlucks(segs) {
  const pattern = [0, 2, 1, 3, 2, 4, 3, 1];
  let step = 0;
  for (let t = 0; t < finalAt - 0.5;) {
    const { pluck } = mood(t);
    if (pluck > 0) {
      const seg = segs.find((g) => t >= g.start && t < g.end) ?? segs[0];
      const m = seg.chord.pad[pattern[step % pattern.length]] + 12;
      addPluck(t, midi(m), pluck === 2 && step % 2 ? 0.035 : 0.06, 0.35 + (0.3 * ((step * 3) % 5)) / 4);
      step += 1;
    }
    t += pluck === 2 ? 0.4 : 0.8;
  }
}

let noiseSeed = 12345;
const noise = () => {
  noiseSeed = (noiseSeed * 1664525 + 1013904223) >>> 0;
  return noiseSeed / 2 ** 31 - 1;
};

/** Band-passed noise; `shape(t)` gives [amplitude, centre frequency]. */
function filteredNoise(out, from, length, shape) {
  let low = 0;
  let band = 0;
  for (let s = 0; s < length && from + s < out[0].length; s += 1) {
    const [amp, fc] = shape(s / SR);
    const f = 2 * Math.sin((Math.PI * fc) / SR);
    const high = noise() - low - 0.7 * band;
    band += f * high;
    low += f * band;
    out[0][from + s] += band * amp;
    out[1][from + s] += band * amp * 0.92;
  }
}

function addRiserAndHit() {
  const rise = 1.8;
  filteredNoise([L, R], Math.floor((finalAt - rise) * SR), Math.floor(rise * SR), (t) => [0.05 * (t / rise) ** 2, 300 + 2600 * (t / rise) ** 2]);
  const from = Math.floor(finalAt * SR);
  for (let s = from; s < Math.min(N, from + 3 * SR); s += 1) {
    const t = (s - from) / SR;
    const x = Math.sin(2 * Math.PI * (52 * t + 6 * (1 - Math.exp(-t * 8)))) * Math.exp(-t / 0.9) * 0.22;
    L[s] += x;
    R[s] += x;
  }
}

/** Small stereo reverb: parallel damped combs into allpasses. */
function reverb(input, delays, wet) {
  const out = new Float32Array(input.length);
  for (const d of delays) {
    const buf = new Float32Array(d);
    let idx = 0;
    let damp = 0;
    for (let s = 0; s < input.length; s += 1) {
      const y = buf[idx];
      damp = y * 0.6 + damp * 0.4;
      buf[idx] = input[s] + damp * 0.8;
      out[s] += y / delays.length;
      idx = (idx + 1) % d;
    }
  }
  for (const d of [556, 225]) {
    const buf = new Float32Array(d);
    let idx = 0;
    for (let s = 0; s < out.length; s += 1) {
      const y = buf[idx];
      const x = out[s] + y * 0.5;
      buf[idx] = x;
      out[s] = y - x * 0.5;
      idx = (idx + 1) % d;
    }
  }
  return input.map((x, s) => x * (1 - wet) + out[s] * wet * 2.2);
}

function writeWav(path, channels) {
  const frames = channels[0].length;
  const bytes = frames * channels.length * 2;
  const buf = Buffer.alloc(44 + bytes);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + bytes, 4); buf.write('WAVE', 8);
  buf.write('fmt ', 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(channels.length, 22);
  buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * channels.length * 2, 28); buf.writeUInt16LE(channels.length * 2, 32); buf.writeUInt16LE(16, 34);
  buf.write('data', 36); buf.writeUInt32LE(bytes, 40);
  let o = 44;
  for (let s = 0; s < frames; s += 1) {
    for (const ch of channels) { buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, ch[s])) * 32767), o); o += 2; }
  }
  fs.writeFileSync(path, buf);
}

function normalise(channels, peakDb) {
  const peak = Math.max(...channels.map((ch) => ch.reduce((m, x) => Math.max(m, Math.abs(x)), 0)));
  const k = 10 ** (peakDb / 20) / (peak || 1);
  return channels.map((ch) => ch.map((x) => x * k));
}

// ---- Render score
const segs = chordSegments();
segs.forEach(addPad);
segs.forEach(addBass);
addPlucks(segs);
addRiserAndHit();
const wl = reverb(L, [1557, 1617, 1491, 1422], 0.32);
const wr = reverb(R, [1580, 1640, 1514, 1445], 0.32);
const fadeIn = Math.floor(2 * SR);
for (let s = 0; s < fadeIn; s += 1) { wl[s] *= s / fadeIn; wr[s] *= s / fadeIn; }
fs.mkdirSync('public/audio/sfx', { recursive: true });
const musicPath = `public/audio/music-${isFinal ? 'final' : 'draft'}.wav`;
writeWav(musicPath, normalise([wl, wr], -3).map((ch) => ch.map(Math.tanh)));

// ---- Effects
const whoosh = [new Float32Array(Math.floor(0.9 * SR)), new Float32Array(Math.floor(0.9 * SR))];
filteredNoise(whoosh, 0, whoosh[0].length, (t) => [Math.sin(Math.PI * Math.min(1, t / 0.75)) ** 2 * 0.5, 250 + 2200 * Math.sin(Math.PI * Math.min(1, t / 0.75))]);
writeWav('public/audio/sfx/whoosh.wav', normalise(whoosh, -6));
const tick = [0, 1].map(() => Float32Array.from({ length: Math.floor(0.15 * SR) }, (_, s) => {
  const t = s / SR;
  return (Math.sin(2 * Math.PI * 1760 * t) + 0.3 * Math.sin(2 * Math.PI * 3520 * t)) * Math.min(1, t / 0.003) * Math.exp(-t / 0.035);
}));
writeWav('public/audio/sfx/tick.wav', normalise(tick, -6));

console.log(`Wrote ${musicPath} (${total.toFixed(2)} s) and public/audio/sfx/{whoosh,tick}.wav`);
