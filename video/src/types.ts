// Shapes produced by timeline.js (plain JS) and consumed by the components.

export type Region = [number, number, number]; // x, y, width in capture px (16:9)
export type Rect = [number, number, number, number];

export interface Spot { at: number; rect: Rect }
export interface ShotSpec { file: string; node: string; label: string; focus: Rect }

export interface Visual {
  type: 'type' | 'matchcut' | 'scale' | 'questions' | 'app' | 'phone' | 'diagram' | 'shots' | 'build' | 'deterministic' | 'closing' | 'end';
  lines?: string[];
  accent?: number;
  text?: string;
  from?: number;
  to?: number;
  camera?: [Region, Region];
  spots?: Spot[];
  label?: string;
  value?: number;
  items?: string[];
  note?: string;
  cue?: string;   // phrase that triggers the visual's main reveal
  still?: number;
  shots?: ShotSpec[];
}

export interface Caption { start: number; end: number; text: string }

export interface Beat {
  id: string;
  say: string;
  ssml: string;
  visual: Visual;
  start: number;
  length: number;
  speech: { file: string | null; audioStart: number; start: number; duration: number };
  captions: Caption[];
}

export interface Scene { id: string; chapter: string; title: string; start: number; length: number; beats: Beat[] }

export interface Timeline { fps: number; totalSeconds: number; gain: number; scenes: Scene[]; captions: Caption[] }

// A type alias (not an interface) so it satisfies Remotion's Record<string, unknown> props constraint.
export type VideoProps = { timeline: Timeline; withNarration: boolean; musicOnly?: boolean };

/** Seconds into a beat at which the given phrase is (roughly) spoken. */
export function phraseTime(beat: Beat, phrase: string): number {
  const index = beat.say.toLowerCase().indexOf(phrase.toLowerCase());
  const share = index < 0 ? 0 : index / beat.say.length;
  return beat.speech.start - beat.start + share * beat.speech.duration;
}
