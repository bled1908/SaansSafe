import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { C, MONO, TEXT, clamp, easeOut } from '../theme';
import type { Caption, Scene } from '../types';

// Per-scene atmosphere: hazy and warm while the problem is stated, clearer
// and cooler once the product takes over, dawn-warm at the close.
const MOODS: Record<string, [string, string]> = {
  hook: ['#18202e', '#0a0d12'],
  problem: ['#2a2419', '#0c0d10'],
  product: ['#16212e', '#0a0d12'],
  provenance: ['#15202d', '#0a0d12'],
  outlook: ['#172231', '#0a0d12'],
  notices: ['#1a2130', '#0a0d12'],
  aws: ['#121b2c', '#090c12'],
  build: ['#171c28', '#0a0d12'],
  end: ['#2a2232', '#0b0c11'],
};

const hex = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const mix = (a: string, b: string, p: number) => `rgb(${hex(a).map((v, i) => Math.round(v + (hex(b)[i] - v) * p)).join(',')})`;

export function Backdrop({ scenes }: { scenes: Scene[] }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const found = scenes.findIndex((s) => t < s.start + s.length);
  const i = found < 0 ? scenes.length - 1 : found;
  const scene = scenes[i];
  const prev = scenes[i - 1];
  const p = prev ? Math.min(1, (t - scene.start) / 1.2) : 1;
  const [a1, b1] = MOODS[prev?.id ?? scene.id] ?? MOODS.product;
  const [a2, b2] = MOODS[scene.id] ?? MOODS.product;
  const glow = mix(a1, a2, p);
  const base = mix(b1, b2, p);
  const dx = Math.sin(t / 9) * 4;
  const dy = Math.cos(t / 11) * 2;
  return (
    <AbsoluteFill style={{
      background: `radial-gradient(1100px 700px at ${50 + dx}% ${34 + dy}%, ${glow} 0%, transparent 72%),
                   radial-gradient(900px 520px at ${80 - dx}% ${92 - dy}%, ${glow} 0%, transparent 70%)`,
      backgroundColor: base,
    }} />
  );
}

/** Chapter number and title, top-left, for the length of each scene. */
export function ChapterMark({ scene }: { scene: Scene }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const total = scene.length * fps;
  const t = easeOut(interpolate(frame, [6, 24], [0, 1], clamp));
  const out = interpolate(frame, [total - 10, total], [1, 0], clamp);
  if (!scene.chapter) return null;
  return (
    <div style={{ position: 'absolute', left: 200, top: 24, display: 'flex', alignItems: 'center', gap: 14, opacity: t * out, transform: `translateX(${(1 - t) * -16}px)` }}>
      <span style={{ fontFamily: MONO, fontSize: 18, color: C.accent, letterSpacing: 2 }}>{scene.chapter}</span>
      <span style={{ width: 28 * t, height: 1, background: C.accent, opacity: 0.6 }} />
      <span style={{ fontFamily: MONO, fontSize: 18, color: C.muted, letterSpacing: 2.5, textTransform: 'uppercase' }}>{scene.title}</span>
    </div>
  );
}

const HOLD_S = 0.25; // keep a cue up through short gaps so captions don't flicker

const emphasised = (word: string) => /^\d/.test(word) || /^SaansSafe/.test(word) || /^not$/i.test(word);

export function Captions({ captions }: { captions: Caption[] }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const index = captions.findIndex((c, i) => t >= c.start && t < Math.min(c.end + HOLD_S, captions[i + 1]?.start ?? Infinity));
  if (index < 0) return null;
  const cue = captions[index];
  const enter = easeOut(interpolate(t, [cue.start, cue.start + 0.18], [0, 1], clamp));
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, bottom: 40, display: 'flex', justifyContent: 'center' }}>
      <div style={{
        maxWidth: 1360, padding: '10px 26px 12px', borderRadius: 14, background: 'rgba(8,10,14,0.82)',
        boxShadow: '0 10px 30px rgba(0,0,0,0.35)', fontFamily: TEXT, fontSize: 44, fontWeight: 600, lineHeight: 1.25,
        color: '#fff', textAlign: 'center', opacity: 0.4 + 0.6 * enter, transform: `translateY(${(1 - enter) * 6}px)`,
      }}>
        {cue.text.split(' ').map((word, i) => (
          <span key={i} style={{ color: emphasised(word) ? C.warm : '#fff' }}>{i ? ' ' : ''}{word}</span>
        ))}
      </div>
    </div>
  );
}

/** Soft vignette and fine animated grain over the whole frame. */
export function Finish() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,0.38) 100%)' }} />
      <svg width="1920" height="1080" style={{ position: 'absolute', opacity: 0.05, mixBlendMode: 'overlay' }}>
        <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed={frame % 12} /></filter>
        <rect width="1920" height="1080" filter="url(#grain)" />
      </svg>
    </AbsoluteFill>
  );
}

export function DraftBadge({ text }: { text: string }) {
  return (
    <div style={{ position: 'absolute', right: 24, top: 18, fontFamily: MONO, fontSize: 15, letterSpacing: 1, color: '#ffc7b8', background: 'rgba(60,20,20,0.85)', padding: '6px 12px', borderRadius: 8 }}>
      {text}
    </div>
  );
}
