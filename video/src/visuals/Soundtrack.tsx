import { Audio, Sequence, interpolate, staticFile, useVideoConfig } from 'remotion';
import { toFrames } from '../timeline.js';
import { clamp } from '../theme';
import type { Timeline } from '../types';

// Music bed and effects are generated locally by scripts/music.mjs from the
// same timeline, so the score's sections and final chord land on the edit.
const MUSIC_LEVEL = 0.42;   // bed level between lines
const DUCK = 0.38;          // fraction kept under narration
const DUCK_RAMP_S = 0.35;
const MUSIC_ONLY_LEVEL = 0.7; // no voice to duck under: the score carries the film
const DIP_BEATS: Record<string, number> = { 'problem-3': 0.25 }; // near-silence under the turn
const SFX = { whoosh: 0.32, tick: 0.16, shot: 0.12 };

export function Soundtrack({ timeline, withNarration, musicOnly = false }: { timeline: Timeline; withNarration: boolean; musicOnly?: boolean }) {
  const { fps } = useVideoConfig();
  const beats = timeline.scenes.flatMap((s) => s.beats);
  const speech = beats.map((b) => [b.speech.start, b.speech.start + b.speech.duration]);
  const end = timeline.totalSeconds;

  const musicVolume = (frame: number) => {
    const t = frame / fps;
    const gap = Math.min(...speech.map(([a, b]) => (t < a ? a - t : t > b ? t - b : 0)));
    const duck = musicOnly ? 1 : interpolate(gap, [0, DUCK_RAMP_S], [DUCK, 1], clamp);
    const beat = beats.find((b) => t >= b.start && t < b.start + b.length);
    const dip = beat ? DIP_BEATS[beat.id] ?? 1 : 1;
    const fade = interpolate(t, [0, 1.5, end - 1.2, end], [0, 1, 1, 0], clamp);
    return (musicOnly ? MUSIC_ONLY_LEVEL : MUSIC_LEVEL) * duck * dip * fade;
  };

  const whooshes = timeline.scenes.slice(1).map((s) => s.start);
  const ticks = beats.flatMap((b) => (b.visual.type === 'app' ? (b.visual.spots ?? []).map((s) => b.start + s.at * b.length) : []));
  const shotTimes = beats.flatMap((b) => {
    const shots = b.visual.shots ?? [];
    return shots.map((_, i) => b.start + (i * b.length) / shots.length);
  });

  const effect = (file: string, at: number, volume: number, key: string) => (
    <Sequence key={key} from={Math.max(0, toFrames(at, fps))} durationInFrames={toFrames(1.5, fps)} layout="none">
      <Audio src={staticFile(`audio/sfx/${file}.wav`)} volume={volume} />
    </Sequence>
  );

  return (
    <>
      <Audio src={staticFile(withNarration ? 'audio/music-final.wav' : 'audio/music-draft.wav')} volume={musicVolume} />
      {whooshes.map((t, i) => effect('whoosh', t - 0.35, SFX.whoosh, `w${i}`))}
      {ticks.map((t, i) => effect('tick', t, SFX.tick, `t${i}`))}
      {shotTimes.map((t, i) => effect('tick', t, SFX.shot, `s${i}`))}
      {withNarration ? beats.filter((b) => b.speech.file).map((b) => (
        <Sequence key={b.id} from={toFrames(b.speech.audioStart, fps)} durationInFrames={toFrames(b.length, fps)} layout="none">
          <Audio src={staticFile(`audio/v2/${b.speech.file}`)} volume={timeline.gain} />
        </Sequence>
      )) : null}
    </>
  );
}
