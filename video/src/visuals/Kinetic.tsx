import type { ReactNode } from 'react';
import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { toFrames } from '../timeline.js';
import { C, DISPLAY, HINDI, MONO, TEXT, clamp, easeOut } from '../theme';
import { phraseTime, type Beat } from '../types';

/** 0 → 1 reveal starting at `atSeconds` into the beat. */
function useReveal(atSeconds: number, frames = 16): number {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = atSeconds * fps;
  return easeOut(interpolate(frame, [start, start + frames], [0, 1], clamp));
}

/** A line that slides up out of a mask. */
function MaskLine({ at, children, size, color = C.text, weight = 680 }: { at: number; children: ReactNode; size: number; color?: string; weight?: number }) {
  const t = useReveal(at, 18);
  return (
    <div style={{ overflow: 'hidden', paddingBottom: size * 0.12 }}>
      <div style={{ fontFamily: DISPLAY, fontSize: size, fontWeight: weight, letterSpacing: -0.025 * size, lineHeight: 1.06, color, transform: `translateY(${(1 - t) * 105}%)`, opacity: t }}>
        {children}
      </div>
    </div>
  );
}

/** Lines revealed as the narrator reaches them. */
export function TypeBeat({ beat }: { beat: Beat }) {
  const lines = beat.visual.lines ?? [];
  const accent = beat.visual.accent;
  return (
    <AbsoluteFill style={{ justifyContent: 'center', paddingLeft: 240 }}>
      {lines.map((line, i) => {
        const at = i === 0 ? 0.1 : Math.max(0.1, phraseTime(beat, line.split(' ').slice(0, 2).join(' ')) - 0.15);
        return <MaskLine key={line} at={at} size={112} color={i === accent ? C.warm : C.text}>{line}</MaskLine>;
      })}
    </AbsoluteFill>
  );
}

const CATEGORIES = [
  { name: 'Good', lo: 0, hi: 50, color: '#3f9f5a' },
  { name: 'Satisfactory', lo: 51, hi: 100, color: '#97bf4a' },
  { name: 'Moderate', lo: 101, hi: 200, color: '#e2c04a' },
  { name: 'Poor', lo: 201, hi: 300, color: '#e3893d' },
  { name: 'Very poor', lo: 301, hi: 400, color: '#d14b45' },
  { name: 'Severe', lo: 401, hi: 500, color: '#8f2f35' },
];
const BAR = { x: 260, w: 1400, y: 640 };

/** CPCB's six AQI categories, with the number landing on Moderate. */
export function AqiScale({ beat }: { beat: Beat }) {
  const value = beat.visual.value ?? 145;
  const count = useReveal(phraseTime(beat, String(value)) - 0.5, 26);
  const label = useReveal(phraseTime(beat, 'Moderate') - 0.1, 14);
  const bar = useReveal(0.1, 30);
  const x = BAR.x + (BAR.w * value * count) / 500;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: BAR.x, top: 250, fontFamily: MONO, fontSize: 20, letterSpacing: 2.5, color: C.muted, opacity: bar }}>CPCB NATIONAL AIR QUALITY INDEX · CATEGORIES</div>
      <div style={{ position: 'absolute', left: BAR.x - 8, top: 290, fontFamily: DISPLAY, fontSize: 230, fontWeight: 700, letterSpacing: -8, color: C.text, opacity: count }}>
        {Math.round(value * count)}
      </div>
      <div style={{ position: 'absolute', left: BAR.x + 470, top: 420, fontFamily: DISPLAY, fontSize: 64, fontWeight: 600, color: '#e2c04a', opacity: label, transform: `translateX(${(1 - label) * -20}px)` }}>Moderate</div>
      <div style={{ position: 'absolute', left: BAR.x, top: BAR.y, width: BAR.w, height: 14, display: 'flex', gap: 4, clipPath: `inset(0 ${(1 - bar) * 100}% 0 0)` }}>
        {CATEGORIES.map((c) => <div key={c.name} style={{ flex: c.hi - c.lo + 1, background: c.color, borderRadius: 4, opacity: 0.9 }} />)}
      </div>
      <div style={{ position: 'absolute', left: x - 1, top: BAR.y - 26, width: 2, height: 66, background: C.text, opacity: count }} />
      <div style={{ position: 'absolute', left: BAR.x, top: BAR.y + 40, width: BAR.w, display: 'flex', gap: 4, opacity: bar }}>
        {CATEGORIES.map((c) => (
          <div key={c.name} style={{ flex: c.hi - c.lo + 1, fontFamily: TEXT, color: c.name === 'Moderate' ? C.text : C.muted }}>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{c.name}</div>
            <div style={{ fontFamily: MONO, fontSize: 17, marginTop: 4 }}>{c.lo}–{c.hi}{c.name === 'Severe' ? '+' : ''}</div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
}

/** The three school questions a category doesn't answer. */
export function Questions({ beat }: { beat: Beat }) {
  const items = beat.visual.items ?? [];
    const head = useReveal(0, 14);
  const ask = phraseTime(beat, beat.visual.cue ?? 'They');
  const note = useReveal(phraseTime(beat, 'recess') + 0.4, 16);
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left: 240, top: 210, display: 'flex', alignItems: 'baseline', gap: 22, opacity: head * 0.75 }}>
        <span style={{ fontFamily: DISPLAY, fontSize: 64, fontWeight: 700, color: C.text }}>145</span>
        <span style={{ fontFamily: DISPLAY, fontSize: 34, color: '#e2c04a' }}>Moderate</span>
        <span style={{ fontFamily: MONO, fontSize: 19, color: C.muted, letterSpacing: 1.5 }}>· CPCB CATEGORY</span>
      </div>
      <div style={{ position: 'absolute', left: 240, top: 380, display: 'flex', gap: 36 }}>
        {items.map((item, i) => <QuestionCard key={item} text={item} at={ask + 0.2 + i * 0.45} />)}
      </div>
      <div style={{ position: 'absolute', left: 240, top: 720, fontFamily: TEXT, fontSize: 28, color: C.muted, opacity: note }}>{beat.visual.note}</div>
    </AbsoluteFill>
  );
}

function QuestionCard({ text, at }: { text: string; at: number }) {
  const t = useReveal(at, 16);
  return (
    <div style={{
      width: 450, height: 230, borderRadius: 22, background: C.panel, border: `1px solid ${C.line}`, padding: '0 40px',
      display: 'flex', alignItems: 'center', opacity: t, transform: `translateY(${(1 - t) * 30}px)`,
    }}>
      <span style={{ fontFamily: DISPLAY, fontSize: 60, fontWeight: 650, color: C.text, letterSpacing: -1 }}>{text.replace('?', '')}<span style={{ color: C.warm }}>?</span></span>
    </div>
  );
}

function Counter({ to, at, label }: { to: number; at: number; label: string }) {
  const t = useReveal(at, 34);
  return (
    <div style={{ opacity: Math.min(1, t * 3) }}>
      <div style={{ fontFamily: DISPLAY, fontSize: 170, fontWeight: 700, letterSpacing: -6, color: C.text, lineHeight: 1 }}>{Math.round(to * t)}</div>
      <div style={{ fontFamily: MONO, fontSize: 21, letterSpacing: 1.5, color: C.muted, marginTop: 14 }}>{label}</div>
    </div>
  );
}

/** Claude Code + the verified test counts. */
export function BuildBeat({ beat }: { beat: Beat }) {
  const foot = useReveal(phraseTime(beat, '83') + 0.6, 16);
  return (
    <AbsoluteFill style={{ padding: '200px 240px' }}>
      <MaskLine at={0.1} size={30} color={C.accent} weight={500}><span style={{ fontFamily: MONO, letterSpacing: 3 }}>HOW WE BUILT IT</span></MaskLine>
      <MaskLine at={0.2} size={104}>Built with Claude Code.</MaskLine>
      <div style={{ display: 'flex', gap: 140, marginTop: 70 }}>
        <Counter to={637} at={phraseTime(beat, '637') - 0.2} label="BACKEND TESTS PASSING · PYTEST" />
        <Counter to={83} at={phraseTime(beat, '83') - 0.2} label="FRONTEND TESTS PASSING · VITEST" />
      </div>
      <div style={{ fontFamily: TEXT, fontSize: 24, color: C.faint, marginTop: 50, opacity: foot }}>Counts from local test runs on 11 Oct 2026.</div>
    </AbsoluteFill>
  );
}

const ROWS = [
  { cue: 'calculates', what: 'AQI', how: 'Indian National AQI method · CPCB breakpoints · tested code' },
  { cue: 'makes', what: 'School decision', how: 'SaansSafe school policy · saanssafe-school-v1' },
  { cue: 'writes', what: 'Parent notice', how: 'Verified English and Hindi templates' },
];

/** Where the language model is not. */
export function Deterministic({ beat }: { beat: Beat }) {
  return (
    <AbsoluteFill style={{ padding: '230px 240px' }}>
      <MaskLine at={0.05} size={30} color={C.warm} weight={500}><span style={{ fontFamily: MONO, letterSpacing: 3 }}>NO LANGUAGE MODEL IN THE DECISION PATH</span></MaskLine>
      <div style={{ marginTop: 50, display: 'flex', flexDirection: 'column', gap: 26 }}>
        {ROWS.map((row) => <DetRow key={row.what} what={row.what} how={row.how} at={phraseTime(beat, row.cue) - 0.1} />)}
      </div>
    </AbsoluteFill>
  );
}

function DetRow({ what, how, at }: { what: string; how: string; at: number }) {
  const t = useReveal(at, 16);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 40, padding: '30px 40px', borderRadius: 20, background: C.panel, border: `1px solid ${C.line}`, opacity: t, transform: `translateX(${(1 - t) * -30}px)` }}>
      <div style={{ width: 420, fontFamily: DISPLAY, fontSize: 52, fontWeight: 650, color: C.text, letterSpacing: -1 }}>{what}</div>
      <div style={{ flex: 1, fontFamily: MONO, fontSize: 24, color: C.muted }}>{how}</div>
      <div style={{ fontFamily: MONO, fontSize: 18, letterSpacing: 2, color: C.ink, background: C.warm, padding: '8px 16px', borderRadius: 8 }}>DETERMINISTIC</div>
    </div>
  );
}

/** Bookend: the decision screen, softened, under the closing line. */
export function Closing({ beat, fps }: { beat: Beat; fps: number }) {
  const frame = useCurrentFrame();
  const push = interpolate(frame, [0, toFrames(beat.length, fps)], [1.06, 1.12]);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ opacity: 0.32, filter: 'blur(14px) saturate(0.9)', transform: `scale(${push})` }}>
        <div style={{ position: 'absolute', width: 1920, height: 1080, transformOrigin: '0 0', transform: 'scale(1.3333)' }}>
          <OffthreadVideo src={staticFile('captures/desktop.webm')} trimBefore={toFrames(11, fps)} playbackRate={0.3} muted style={{ width: 1920, height: 1080 }} />
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ background: 'linear-gradient(180deg, rgba(10,13,18,0.55) 0%, rgba(10,13,18,0.85) 100%)' }} />
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', textAlign: 'center' }}>
        <MaskLine at={0.15} size={104}>Every school morning,</MaskLine>
        <MaskLine at={phraseTime(beat, 'starts') - 0.1} size={104} color={C.warm}>a clear plan.</MaskLine>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}

/** Title card: name, line, links, team and the standing disclaimers. */
export function EndCard() {
  const logo = useReveal(0.2, 30);
  const line = useReveal(1.4, 20);
  const links = useReveal(2.3, 20);
  const team = useReveal(3.0, 20);
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', textAlign: 'center', fontFamily: DISPLAY, color: C.text }}>
      <div style={{ fontSize: 150, fontWeight: 750, letterSpacing: -4 + 6 * (1 - logo), opacity: logo, transform: `scale(${0.96 + 0.04 * logo})` }}>
        SaansSafe <span style={{ fontFamily: HINDI, color: C.accent, fontWeight: 600 }}>साँस</span>
      </div>
      <div style={{ fontSize: 46, color: C.muted, marginTop: 6, opacity: line }}>Clearer air decisions for schools.</div>
      <div style={{ fontFamily: MONO, fontSize: 30, marginTop: 64, lineHeight: 1.75, opacity: links }}>
        <div><span style={{ color: C.faint }}>Live</span>&nbsp; d316zs0sydbi1r.cloudfront.net</div>
        <div><span style={{ color: C.faint }}>Code</span>&nbsp; github.com/bled1908/SaansSafe</div>
      </div>
      <div style={{ fontFamily: TEXT, fontSize: 26, color: C.muted, marginTop: 44, opacity: team }}>
        Team <span style={{ color: C.text, fontWeight: 600 }}>Shadow Protocol</span> · Subhadeep Roy &amp; Sneha Singha
      </div>
      <div style={{ position: 'absolute', bottom: 120, fontFamily: TEXT, fontSize: 20, color: C.faint, opacity: team }}>
        Forecast/model AQI (CAMS via Open-Meteo), not CPCB station readings · School actions follow SaansSafe policy, not CPCB · Not medical advice
      </div>
    </AbsoluteFill>
  );
}
