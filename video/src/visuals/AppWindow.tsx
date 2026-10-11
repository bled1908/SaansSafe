import type { CSSProperties, ReactNode } from 'react';
import { AbsoluteFill, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { toFrames } from '../timeline.js';
import { C, CAPTURE, DISPLAY, MONO, WINDOW, clamp, drift, easeInOut, easeOut } from '../theme';
import type { Beat, Region, Spot } from '../types';

const CROSSFADE = 8;          // frames of overlap when footage jumps in source time
const SETTLE_S = 0.7;         // camera move from the previous framing to this beat's
const FULL: Region = [0, 0, CAPTURE.w];
const URL = 'd316zs0sydbi1r.cloudfront.net';

const lerp = (a: Region, b: Region, p: number): Region => [0, 1, 2].map((i) => a[i] + (b[i] - a[i]) * p) as Region;
const same = (a: Region, b: Region) => a.every((v, i) => Math.abs(v - b[i]) < 0.5);

/** Keep the 16:9 view inside the captured page (the canvas beyond it is empty). */
function clampRegion([x, y, w]: Region): Region {
  const width = Math.min(w, CAPTURE.w);
  const height = (width * 9) / 16;
  return [Math.min(Math.max(0, x), CAPTURE.w - width), Math.min(Math.max(0, y), CAPTURE.h - height), width];
}

export const cameraEnd = (beat: Beat): Region => clampRegion(beat.visual.camera?.[1] ?? FULL);

function cameraAt(beat: Beat, previous: Region | null, t: number): Region {
  const [a, b] = (beat.visual.camera ?? [FULL, FULL]).map(clampRegion);
  const settle = previous && !same(previous, a) ? SETTLE_S : 0;
  if (previous && t < settle) return lerp(previous, a, easeInOut(t / settle));
  return lerp(a, b, drift(Math.min(1, (t - settle) / Math.max(0.1, beat.length - settle))));
}

export function WindowFrame({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{
      position: 'absolute', left: WINDOW.x, top: WINDOW.y, width: WINDOW.w, height: WINDOW.h + WINDOW.chrome,
      borderRadius: 16, overflow: 'hidden', background: '#e9e6df',
      boxShadow: '0 40px 120px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.08)', ...style,
    }}>
      <div style={{ height: WINDOW.chrome, display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px', background: '#ece9e2', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
        {['#e4776a', '#e9bd5b', '#76c27a'].map((c) => <span key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c, opacity: 0.85 }} />)}
        <div style={{ margin: '0 auto', padding: '4px 18px', borderRadius: 8, background: 'rgba(0,0,0,0.05)', fontFamily: MONO, fontSize: 15, color: '#5b6070' }}>
          https://{URL}
        </div>
        <span style={{ width: 52 }} />
      </div>
      <div style={{ position: 'relative', width: WINDOW.w, height: WINDOW.h, overflow: 'hidden', background: C.window }}>{children}</div>
    </div>
  );
}

function Spotlight({ spot, next, frames, scale }: { spot: Spot; next?: Spot; frames: number; scale: number }) {
  const frame = useCurrentFrame();
  const start = spot.at * frames;
  const end = next ? next.at * frames : frames - 4;
  const o = interpolate(frame, [start, start + 9, end - 6, end + 2], [0, 1, 1, 0], clamp);
  if (o <= 0) return null;
  const pop = 1 + 0.035 * (1 - easeOut(interpolate(frame, [start, start + 14], [0, 1], clamp)));
  const [x, y, w, h] = spot.rect;
  const pad = 6;
  return (
    <div style={{
      position: 'absolute', left: x - pad, top: y - pad, width: w + 2 * pad, height: h + 2 * pad,
      borderRadius: 12, transform: `scale(${pop})`, transformOrigin: 'center',
      border: `${2.5 / scale}px solid rgba(158,164,255,${o})`,
      boxShadow: `0 0 0 4000px rgba(8,10,14,${0.34 * o}), 0 0 ${26 / scale}px rgba(158,164,255,${0.45 * o})`,
    }} />
  );
}

/** One beat of desktop footage inside the window, retimed to the beat. */
function Footage({ beat, fps, previous, fadeIn }: { beat: Beat; fps: number; previous: Region | null; fadeIn: boolean }) {
  const frame = useCurrentFrame();
  const frames = toFrames(beat.length, fps);
  const [x, y, w] = clampRegion(cameraAt(beat, previous, frame / fps));
  const scale = WINDOW.w / w;
  const { from = 0, to = from + beat.length, spots = [], label } = beat.visual;
  const opacity = fadeIn ? interpolate(frame, [0, CROSSFADE], [0, 1], clamp) : 1;
  return (
    <AbsoluteFill style={{ opacity }}>
      <div style={{ position: 'absolute', width: 1920, height: 1080, transformOrigin: '0 0', transform: `scale(${scale}) translate(${-x}px, ${-y}px)` }}>
        <OffthreadVideo src={staticFile('captures/desktop.webm')} trimBefore={toFrames(from, fps)} playbackRate={(to - from) / beat.length} muted style={{ width: 1920, height: 1080 }} />
        {spots.map((spot, i) => <Spotlight key={i} spot={spot} next={spots[i + 1]} frames={frames} scale={scale} />)}
      </div>
      {label ? (
        <div style={{ position: 'absolute', right: 18, bottom: 16, fontFamily: MONO, fontSize: 17, letterSpacing: 1, color: C.text, background: 'rgba(10,13,18,0.86)', padding: '7px 14px', borderRadius: 8 }}>{label}</div>
      ) : null}
    </AbsoluteFill>
  );
}

/** A contiguous run of app beats: one persistent window, continuous camera. */
export function AppRun({ beats, fps, runStart, runLength }: { beats: Beat[]; fps: number; runStart: number; runLength: number }) {
  const frame = useCurrentFrame();
  const total = toFrames(runLength, fps);
  const enter = easeOut(interpolate(frame, [0, 20], [0, 1], clamp));
  const exit = interpolate(frame, [total - 10, total], [1, 0], clamp);
  return (
    <WindowFrame style={{ opacity: enter * exit, transform: `translateY(${(1 - enter) * 40}px) scale(${0.97 + 0.03 * enter})` }}>
      {beats.map((beat, i) => {
        const prev = beats[i - 1];
        const jump = prev ? Math.abs((prev.visual.to ?? 0) - (beat.visual.from ?? 0)) > 0.3 : false;
        return (
          <Sequence key={beat.id} from={toFrames(beat.start - runStart, fps)} durationInFrames={toFrames(beat.length, fps) + CROSSFADE} layout="none">
            <AbsoluteFill><Footage beat={beat} fps={fps} previous={prev ? cameraEnd(prev) : null} fadeIn={jump} /></AbsoluteFill>
          </Sequence>
        );
      })}
    </WindowFrame>
  );
}

// The app's hero breaks its headline after the third word; match it.
const splitHeadline = (text: string) => { const w = text.split(' '); return [w.slice(0, 3), w.slice(3)]; };
const mixInk = (p: number) => `rgb(${[244, 242, 237].map((v, i) => Math.round(v + ([20, 24, 33][i] - v) * Math.min(1, p * 1.6))).join(',')})`;

/** Hook: the question set as type, then dissolved onto the app's own headline. */
export function MatchCut({ beat, fps }: { beat: Beat; fps: number }) {
  const frame = useCurrentFrame();
  const frames = toFrames(beat.length, fps);
  const lines = splitHeadline(beat.visual.text ?? '');
  const move = easeInOut(interpolate(frame, [frames * 0.36, frames * 0.62], [0, 1], clamp));
  const windowIn = easeOut(interpolate(frame, [frames * 0.63, frames * 0.77], [0, 1], clamp));
  const textOut = interpolate(frame, [frames * 0.6, frames * 0.66], [1, 0], clamp);
  const { from = 0, to = from + 1 } = beat.visual;
  const font = 104 + (57 - 104) * move;
  return (
    <AbsoluteFill>
      <WindowFrame style={{ opacity: windowIn, transform: `scale(${1.04 - 0.04 * windowIn})` }}>
        <OffthreadVideo src={staticFile('captures/desktop.webm')} trimBefore={toFrames(from, fps)} playbackRate={(to - from) / beat.length} muted
          style={{ position: 'absolute', width: 1920, height: 1080, transformOrigin: '0 0', transform: `scale(${WINDOW.w / CAPTURE.w})` }} />
      </WindowFrame>
      <div style={{
        position: 'absolute', left: 520 + (380 - 520) * move, top: 400 + (252 - 400) * move, width: 1100,
        fontFamily: DISPLAY, fontWeight: 700, fontSize: font, lineHeight: 1.04, letterSpacing: -0.02 * font,
        color: mixInk(windowIn), opacity: textOut,
      }}>
        {lines.map((line, l) => (
          <div key={l}>
            {line.map((word, i) => {
              const k = l * 3 + i;
              const t = easeOut(interpolate(frame, [4 + k * 4, 18 + k * 4], [0, 1], clamp));
              return <span key={i} style={{ display: 'inline-block', marginRight: '0.24em', opacity: t, transform: `translateY(${(1 - t) * 24}px)` }}>{word}</span>;
            })}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
}

/** Same app on a phone: the desktop window steps back as the phone rises. */
export function PhoneBeat({ beat, fps }: { beat: Beat; fps: number }) {
  const frame = useCurrentFrame();
  const p = easeInOut(interpolate(frame, [0, 24], [0, 1], clamp));
  const rise = easeOut(interpolate(frame, [8, 34], [0, 1], clamp));
  const { from = 0, to = from + 1, still = 66 } = beat.visual;
  const k = 800 / 844;
  const scale = 1 - 0.5 * p;
  return (
    <AbsoluteFill>
      <WindowFrame style={{ transformOrigin: '0 0', transform: `translate(${(120 - WINDOW.x) * p}px, ${(220 - WINDOW.y) * p}px) scale(${scale})`, opacity: 1 - 0.25 * p }}>
        <OffthreadVideo src={staticFile('captures/desktop.webm')} trimBefore={toFrames(still, fps)} playbackRate={0.05} muted
          style={{ position: 'absolute', width: 1920, height: 1080, transformOrigin: '0 0', transform: `scale(${WINDOW.w / CAPTURE.w})` }} />
      </WindowFrame>
      <div style={{ position: 'absolute', left: 120, top: 700, fontFamily: DISPLAY, color: C.text, opacity: rise, transform: `translateY(${(1 - rise) * 20}px)` }}>
        <div style={{ fontFamily: MONO, fontSize: 19, letterSpacing: 2, color: C.accent }}>PHONE · 390 PX WIDE</div>
        <div style={{ fontSize: 60, fontWeight: 650, letterSpacing: -1, marginTop: 10 }}>Works on a teacher&apos;s phone.</div>
      </div>
      <div style={{
        position: 'absolute', left: 1180, top: 96 + (1 - rise) * 120, width: 390 * k + 28, height: 844 * k + 28, borderRadius: 54,
        background: '#05070a', boxShadow: '0 40px 120px rgba(0,0,0,0.6), 0 0 0 2px #2b313b', opacity: rise,
      }}>
        <div style={{ position: 'absolute', left: 14, top: 14, width: 390 * k, height: 844 * k, borderRadius: 42, overflow: 'hidden', background: C.window }}>
          <div style={{ width: 780, height: 1688, transformOrigin: '0 0', transform: `scale(${k})` }}>
            <OffthreadVideo src={staticFile('captures/mobile.webm')} trimBefore={toFrames(from, fps)} playbackRate={(to - from) / beat.length} muted style={{ width: 780, height: 1688 }} />
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}
