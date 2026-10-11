// Narration with Amazon Polly: one SSML request per beat, cached by content.
//
//   node scripts/narrate.mjs                                  dry run: characters and cost (free)
//   node scripts/narrate.mjs --sample --confirm               PAID: SAMPLE_BEATS with both engines, for listening tests
//   node scripts/narrate.mjs --confirm [--engine neural] [--only id,id]
//                                                             PAID: synthesize beats not already cached
//   node scripts/narrate.mjs --measure [--engine neural]      free: re-measure cached files, rewrite narration.json
//
// Every Polly call needs --confirm (billing approval). Files are named
// <beat>-<engine>-<hash>.mp3, so an unchanged beat is never synthesized twice.
// After synthesis each file is measured locally (ffmpeg): length, leading
// silence and internal pauses (for caption timing) and loudness (for gain).

import fs from 'node:fs';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { plainText } from '../src/timeline.js';

const USD_PER_MILLION = { neural: 16, generative: 30 }; // AWS Polly pricing page, checked 2026-10-11
const SAMPLE_BEATS = ['hook-1', 'product-3', 'provenance-2', 'end-2'];
const TARGET_RMS_DB = -19;   // voiced-speech RMS after gain
const PEAK_CEILING_DB = -2;
const OUT = 'public/audio/v2';

const args = process.argv.slice(2);
const flag = (name) => args.includes(name);
const option = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : null; };

const script = JSON.parse(fs.readFileSync('src/script.json', 'utf8'));
const voice = script.voice;
const engineName = option('--engine') ?? voice.engine;
const engineFor = (name) => (name === voice.engine ? { engine: voice.engine, region: voice.region } : { engine: voice.fallback.engine, region: voice.fallback.region });

const beats = script.scenes.flatMap((s) => s.beats);
const only = option('--only')?.split(',') ?? null;
const ssmlOf = (beat) => `<speak>${beat.ssml}</speak>`;
const fileOf = (beat, engine) => `${beat.id}-${engine}-${crypto.createHash('sha1').update(`${voice.voiceId}|${engine}|${beat.ssml}`).digest('hex').slice(0, 8)}.mp3`;
const billable = (list) => list.reduce((n, b) => n + plainText(b.ssml).length, 0);
const cost = (chars, engine) => (chars * USD_PER_MILLION[engine]) / 1e6;

function run(cmd, cmdArgs, shell = false) {
  const r = spawnSync(cmd, cmdArgs, { shell, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (r.status !== 0) throw new Error(`${cmd} failed: ${(r.stderr || '').trim().slice(-400)}`);
  return `${r.stdout}${r.stderr}`;
}
const ffmpeg = (ffArgs) => run('npx', ['remotion', 'ffmpeg', ...ffArgs], true);

function synthesize(beat, engine, region, outPath) {
  run('aws', ['polly', 'synthesize-speech', '--region', region, '--engine', engine, '--voice-id', voice.voiceId,
    '--language-code', voice.languageCode, '--text-type', 'ssml', '--output-format', 'mp3', '--sample-rate', '24000',
    '--text', ssmlOf(beat), outPath]);
}

/** Length, leading/trailing silence, internal pauses and loudness of one file. */
function measure(path) {
  const log = ffmpeg(['-hide_banner', '-nostats', '-i', path, '-af', 'silencedetect=n=-40dB:d=0.12', '-f', 'null', '-']);
  const duration = /Duration: (\d+):(\d+):([\d.]+)/.exec(log).slice(1).reduce((acc, v, i) => acc + Number(v) * [3600, 60, 1][i], 0);
  const starts = [...log.matchAll(/silence_start: ([\d.]+)/g)].map((m) => Number(m[1]));
  const ends = [...log.matchAll(/silence_end: ([\d.]+)/g)].map((m) => Number(m[1]));
  const silences = starts.map((s, i) => [s, ends[i] ?? duration]);
  const leading = silences[0]?.[0] <= 0.02 ? silences[0][1] : 0;
  const trailing = silences.at(-1)?.[1] >= duration - 0.05 ? silences.at(-1)[0] : duration;
  const pauses = silences.filter(([a, b]) => a > 0.02 && b < duration - 0.05);
  const wav = `${path}.tmp.wav`;
  ffmpeg(['-v', 'error', '-y', '-i', path, '-ac', '1', '-c:a', 'pcm_s16le', wav]);
  const buf = fs.readFileSync(wav);
  fs.unlinkSync(wav);
  let o = 12;
  while (buf.toString('ascii', o, o + 4) !== 'data') o += 8 + buf.readUInt32LE(o + 4);
  let peak = 0; let sum = 0; let n = 0;
  for (let i = o + 8; i + 1 < buf.length; i += 2) {
    const x = Math.abs(buf.readInt16LE(i)) / 32768;
    peak = Math.max(peak, x);
    if (x > 0.006) { sum += x * x; n += 1; }
  }
  return { duration, leading, audioSeconds: trailing, pauses, peak, sum, n };
}

function writeNarration(engine) {
  const entries = {};
  let peak = 0; let sum = 0; let n = 0;
  for (const beat of beats) {
    const file = fileOf(beat, engine);
    if (!fs.existsSync(`${OUT}/${file}`)) throw new Error(`Missing ${OUT}/${file}: synthesize first`);
    const m = measure(`${OUT}/${file}`);
    entries[beat.id] = { file, audioSeconds: m.audioSeconds, leading: m.leading, pauses: m.pauses };
    peak = Math.max(peak, m.peak); sum += m.sum; n += m.n;
    console.log(`  ${beat.id.padEnd(14)} ${m.audioSeconds.toFixed(2)} s  lead ${m.leading.toFixed(2)}  pauses ${m.pauses.length}`);
  }
  const rmsDb = 10 * Math.log10(sum / n);
  const peakDb = 20 * Math.log10(peak);
  const gainDb = Math.min(TARGET_RMS_DB - rmsDb, PEAK_CEILING_DB - peakDb);
  const gain = 10 ** (gainDb / 20);
  fs.writeFileSync(`${OUT}/narration.json`, JSON.stringify({ version: 2, engine, voiceId: voice.voiceId, gain, beats: entries }, null, 2));
  console.log(`\nSpeech RMS ${rmsDb.toFixed(1)} dBFS, peak ${peakDb.toFixed(1)} dBFS -> gain ${gainDb.toFixed(1)} dB. Wrote ${OUT}/narration.json`);
}

// ---- Dry run (always printed)
const targets = flag('--sample') ? beats.filter((b) => SAMPLE_BEATS.includes(b.id)) : beats.filter((b) => !only || only.includes(b.id));
const chars = billable(targets);
console.log(`Voice ${voice.voiceId} (${voice.languageCode}); ${targets.length} beats, ${chars} billable characters (SSML tags are not billed)`);
for (const engine of ['generative', 'neural']) {
  const { region } = engineFor(engine);
  console.log(`  ${engine.padEnd(10)} ${region.padEnd(10)} $${cost(chars, engine).toFixed(4)} at $${USD_PER_MILLION[engine]}/1M`);
}

if (flag('--measure')) {
  writeNarration(engineName);
} else if (!flag('--confirm')) {
  console.log('\nDry run only. Polly is called only with --confirm (after billing approval).');
} else if (flag('--sample')) {
  for (const engine of ['generative', 'neural']) {
    const { region } = engineFor(engine);
    const dir = `${OUT}/samples/${engine}`;
    fs.mkdirSync(dir, { recursive: true });
    for (const beat of targets) {
      const path = `${dir}/${fileOf(beat, engine)}`;
      if (fs.existsSync(path)) { console.log(`  cached ${path}`); continue; }
      synthesize(beat, engine, region, path);
      console.log(`  ${path}`);
    }
  }
} else {
  const { engine, region } = engineFor(engineName);
  fs.mkdirSync(OUT, { recursive: true });
  let spent = 0;
  for (const beat of targets) {
    const path = `${OUT}/${fileOf(beat, engine)}`;
    if (fs.existsSync(path)) { console.log(`  cached ${beat.id}`); continue; }
    synthesize(beat, engine, region, path);
    spent += plainText(beat.ssml).length;
    console.log(`  synthesized ${beat.id}`);
  }
  console.log(`Billed characters this run: ${spent} ($${cost(spent, engine).toFixed(4)})`);
  if (!only) writeNarration(engine);
}
