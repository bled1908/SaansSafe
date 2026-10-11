// Single source of timing for the video, the SRT export, the music bed and
// validation. Plain JS (ESM) so Remotion (TSX) and Node scripts share it.
//
// The film is a list of scenes; each scene is a list of beats. A beat is one
// narration unit (one or two sentences) plus the visual it plays over, so
// every spotlight, footage segment and screenshot lands on the words that
// describe it. Beat length follows the narration; footage is retimed to fit.
//
// narration.json (after synthesis, v2):
//   { version: 2, gain, beats: { [beatId]: { file, audioSeconds, leading, pauses: [[start, end], ...] } } }

export const FPS = 30;
const LEAD_S = 0.3;             // silence before a beat's narration starts
const TAIL_S = 0.35;            // default breathing room after it
const CHARS_PER_S = 15;         // Kajal's measured pace (1,773 chars in 117.7 s)
const MIN_SHOT_S = 2.6;         // shortest time an AWS screenshot is on screen
const MAX_CUE_CHARS = 46;       // one comfortable caption line on a phone
const PAUSE_SNAP_S = 0.6;       // how far a caption break may move to meet a real pause
const MIN_CUE_CHARS = 12;       // shorter fragments ("145.") join a neighbour so cues never flash

export const plainText = (ssml) => ssml.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
const breakSeconds = (ssml) => [...ssml.matchAll(/<break time="(\d+)ms"\/>/g)].reduce((s, m) => s + Number(m[1]) / 1000, 0);

/** Draft estimate for a beat with no audio yet: spoken characters plus explicit breaks. */
export const estimateSeconds = (beat) => plainText(beat.ssml).length / CHARS_PER_S + breakSeconds(beat.ssml);

/** Split caption text into cues of at most MAX_CUE_CHARS, preferring sentence and clause breaks. */
export function chunkCaption(text) {
  return mergeShort(splitCaption(text));
}

function mergeShort(chunks) {
  return chunks.reduce((out, chunk) => {
    const last = out[out.length - 1];
    const joined = last ? `${last} ${chunk}` : chunk;
    const tooShort = chunk.length < MIN_CUE_CHARS || (last && last.length < MIN_CUE_CHARS);
    return last && tooShort && joined.length <= MAX_CUE_CHARS ? [...out.slice(0, -1), joined] : [...out, chunk];
  }, []);
}

function splitCaption(text) {
  const sentences = text.match(/[^.?!]+[.?!]+|[^.?!]+$/g).map((s) => s.trim());
  return sentences.flatMap((sentence) => {
    if (sentence.length <= MAX_CUE_CHARS) return [sentence];
    const parts = Math.ceil(sentence.length / MAX_CUE_CHARS);
    const target = sentence.length / parts;
    const out = [];
    let current = '';
    for (const word of sentence.split(' ')) {
      const next = current ? `${current} ${word}` : word;
      const clauseBreak = /[,:;]$/.test(word) && next.length >= target * 0.55;
      if (next.length > MAX_CUE_CHARS && current) {
        out.push(current);
        current = word;
      } else if (clauseBreak || next.length >= target * 1.05) {
        out.push(next);
        current = '';
      } else {
        current = next;
      }
    }
    if (current) out.push(current);
    return out;
  });
}

/** Caption cues across one beat's speech; breaks snap to measured pauses when available. */
function beatCues(text, start, duration, pauses = []) {
  const chunks = chunkCaption(text);
  const total = chunks.reduce((n, c) => n + c.length, 0);
  let acc = 0;
  const bounds = chunks.slice(0, -1).map((chunk) => {
    acc += chunk.length;
    const estimate = (duration * acc) / total;
    const near = pauses
      .map(([a, b]) => (a + b) / 2)
      .filter((mid) => Math.abs(mid - estimate) <= PAUSE_SNAP_S)
      .sort((a, b) => Math.abs(a - estimate) - Math.abs(b - estimate))[0];
    return near ?? estimate;
  });
  const edges = [0, ...bounds, duration];
  return chunks.map((chunk, i) => ({ start: start + edges[i], end: start + edges[i + 1], text: chunk }));
}

function beatMinimum(beat) {
  const shots = beat.visual.type === 'shots' ? beat.visual.shots.length * MIN_SHOT_S : 0;
  return Math.max(beat.min ?? 0, shots);
}

/** Build the full timeline. narration is the parsed narration.json (v2) or null for the draft. */
export function buildTimeline(script, narration = null) {
  let t = 0;
  const scenes = script.scenes.map((scene) => {
    const sceneStart = t;
    const beats = scene.beats.map((beat) => {
      const audio = narration?.beats?.[beat.id] ?? null;
      const leading = audio?.leading ?? 0;
      const speech = audio ? audio.audioSeconds - leading : estimateSeconds(beat);
      const length = Math.max(beatMinimum(beat), LEAD_S + speech + (beat.tail ?? TAIL_S));
      const speechStart = t + LEAD_S;
      const pauses = (audio?.pauses ?? []).map(([a, b]) => [a - leading, b - leading]);
      const entry = {
        ...beat,
        start: t,
        length,
        speech: { file: audio?.file ?? null, audioStart: speechStart - leading, start: speechStart, duration: speech },
        captions: beatCues(beat.say, speechStart, speech, pauses),
      };
      t += length;
      return entry;
    });
    return { ...scene, start: sceneStart, length: t - sceneStart, beats };
  });
  const beats = scenes.flatMap((s) => s.beats);
  return {
    fps: script.fps ?? FPS,
    totalSeconds: t,
    gain: narration?.gain ?? 1,
    scenes,
    captions: beats.flatMap((b) => b.captions),
  };
}

export const toFrames = (seconds, fps = FPS) => Math.round(seconds * fps);
