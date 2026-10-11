import { AbsoluteFill, Img, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { toFrames } from '../timeline.js';
import { C, DISPLAY, MONO, TEXT, clamp, drift, easeOut } from '../theme';
import type { Beat, ShotSpec } from '../types';

// ---- Architecture diagram (drawn from backend/template.yaml and infra/web/template.yaml)

interface Node { id: string; x: number; y: number; title: string; sub: string; external?: boolean }
const NW = 250;
const NH = 94;
const NODES: Node[] = [
  { id: 'browser', x: 90, y: 470, title: 'Browser', sub: 'React app · phone or laptop' },
  { id: 'cloudfront', x: 440, y: 290, title: 'CloudFront', sub: 'global CDN · HTTPS' },
  { id: 's3', x: 830, y: 290, title: 'S3 bucket', sub: 'private · OAC only' },
  { id: 'apigw', x: 830, y: 610, title: 'API Gateway', sub: 'HTTP API' },
  { id: 'apifn', x: 1110, y: 520, title: 'ApiFunction', sub: 'Lambda · /aqi /forecast' },
  { id: 'noticefn', x: 1110, y: 710, title: 'NoticeFunction', sub: 'Lambda · POST /notice' },
  { id: 'dynamodb', x: 1370, y: 300, title: 'DynamoDB', sub: 'forecast cache · TTL' },
  { id: 'openmeteo', x: 1662, y: 520, title: 'Open-Meteo', sub: 'CAMS model · external', external: true },
];
const node = (id: string) => NODES.find((n) => n.id === id) as Node;
type Edge = [string, 'r' | 't', string, 'l' | 'b'];
const EDGES: Edge[] = [
  ['browser', 'r', 'cloudfront', 'l'], ['cloudfront', 'r', 's3', 'l'], ['browser', 'r', 'apigw', 'l'],
  ['apigw', 'r', 'apifn', 'l'], ['apigw', 'r', 'noticefn', 'l'], ['apifn', 't', 'dynamodb', 'b'], ['apifn', 'r', 'openmeteo', 'l'],
];

function anchor(n: Node, side: string): [number, number] {
  if (side === 'r') return [n.x + NW, n.y + NH / 2];
  if (side === 'l') return [n.x, n.y + NH / 2];
  if (side === 't') return [n.x + NW / 2, n.y];
  return [n.x + NW / 2, n.y + NH];
}

function curve([a, as, b, bs]: Edge) {
  const [x1, y1] = anchor(node(a), as);
  const [x2, y2] = anchor(node(b), bs);
  const vertical = as === 't';
  const c1 = vertical ? [x1, y1 - (y1 - y2) / 2] : [x1 + (x2 - x1) / 2, y1];
  const c2 = vertical ? [x2, y2 + (y1 - y2) / 2] : [x1 + (x2 - x1) / 2, y2];
  const at = (t: number): [number, number] => {
    const u = 1 - t;
    const p = (i: number) => u * u * u * [x1, y1][i] + 3 * u * u * t * c1[i] + 3 * u * t * t * c2[i] + t * t * t * [x2, y2][i];
    return [p(0), p(1)];
  };
  return { d: `M${x1},${y1} C${c1[0]},${c1[1]} ${c2[0]},${c2[1]} ${x2},${y2}`, at, length: Math.hypot(x2 - x1, y2 - y1) * 1.25 };
}

export function Diagram({ beat, fps }: { beat: Beat; fps: number }) {
  const frame = useCurrentFrame();
  const frames = toFrames(beat.length, fps);
  const out = interpolate(frame, [frames - 12, frames], [1, 0], clamp);
  const head = easeOut(interpolate(frame, [0, 18], [0, 1], clamp));
  const region = easeOut(interpolate(frame, [20, 44], [0, 1], clamp));
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <div style={{ position: 'absolute', left: 110, top: 96, opacity: head, transform: `translateY(${(1 - head) * 16}px)` }}>
        <div style={{ fontFamily: MONO, fontSize: 20, letterSpacing: 3, color: C.accent }}>ARCHITECTURE</div>
        <div style={{ fontFamily: DISPLAY, fontSize: 68, fontWeight: 700, letterSpacing: -1.5, color: C.text, marginTop: 6 }}>Serverless on AWS</div>
      </div>
      <div style={{ position: 'absolute', left: 790, top: 230, width: 850, height: 620, borderRadius: 22, border: '1.5px dashed rgba(242,196,109,0.5)', opacity: region }}>
        <div style={{ position: 'absolute', left: 20, top: 12, fontFamily: MONO, fontSize: 19, color: C.warm }}>AWS REGION · ap-south-1 (MUMBAI)</div>
      </div>
      <svg width={1920} height={1080} style={{ position: 'absolute' }}>
        {EDGES.map((e, i) => {
          const { d, at, length } = curve(e);
          const start = 24 + i * 7;
          const drawn = easeOut(interpolate(frame, [start, start + 22], [0, 1], clamp));
          const phase = (((frame - start - 22) / (fps * 1.6) + i * 0.23) % 1 + 1) % 1;
          const [px, py] = at(phase);
          return (
            <g key={i}>
              <path d={d} fill="none" stroke="rgba(158,164,255,0.55)" strokeWidth={2} strokeDasharray={length} strokeDashoffset={length * (1 - drawn)} />
              {drawn >= 1 ? <circle cx={px} cy={py} r={5} fill={C.accent} style={{ filter: 'drop-shadow(0 0 6px rgba(158,164,255,0.9))' }} /> : null}
            </g>
          );
        })}
      </svg>
      {NODES.map((n, i) => {
        const t = easeOut(interpolate(frame, [8 + i * 6, 24 + i * 6], [0, 1], clamp));
        return (
          <div key={n.id} style={{
            position: 'absolute', left: n.x, top: n.y, width: NW, height: NH, boxSizing: 'border-box', padding: '16px 20px', borderRadius: 16,
            background: n.external ? 'transparent' : C.panelHi, border: `1.5px ${n.external ? 'dashed' : 'solid'} ${n.external ? C.faint : 'rgba(158,164,255,0.45)'}`,
            opacity: t, transform: `translateY(${(1 - t) * 14}px)`,
          }}>
            <div style={{ fontFamily: DISPLAY, fontSize: 28, fontWeight: 650, color: C.text }}>{n.title}</div>
            <div style={{ fontFamily: MONO, fontSize: 15, color: C.muted, marginTop: 6 }}>{n.sub}</div>
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: 110, top: 900, fontFamily: MONO, fontSize: 18, color: C.faint, opacity: region }}>
        Drawn from backend/template.yaml and infra/web/template.yaml · CloudFront is global; everything in the box runs in ap-south-1
      </div>
    </AbsoluteFill>
  );
}

// ---- Console evidence

const RAIL = [
  { id: 'cloudfront', title: 'CloudFront', sub: 'global CDN' },
  { id: 's3', title: 'S3', sub: 'private bucket' },
  { id: 'apigw', title: 'API Gateway', sub: 'HTTP API' },
  { id: 'lambda', title: 'Lambda', sub: 'two Python functions' },
  { id: 'dynamodb', title: 'DynamoDB', sub: 'forecast cache' },
  { id: 'sam', title: 'SAM · CloudFormation', sub: 'two stacks' },
];
const SHOT = { x: 600, y: 150, w: 1210, chrome: 34 };
const IMG = { w: 1920, h: 1020 };
const SHOT_H = (SHOT.w * IMG.h) / IMG.w;
const MAX_ZOOM = 1.7;
const FADE = 9;

interface Placed extends ShotSpec { start: number; length: number }

function placeShots(beats: Beat[], runStart: number): Placed[] {
  return beats.flatMap((beat) => {
    const shots = beat.visual.shots ?? [];
    const each = beat.length / Math.max(1, shots.length);
    return shots.map((s, i) => ({ ...s, start: beat.start - runStart + i * each, length: each }));
  });
}

function Screenshot({ shot, frames }: { shot: Placed; frames: number }) {
  const frame = useCurrentFrame();
  const p = drift(Math.min(1, frame / frames));
  const [fx, fy, fw, fh] = shot.focus;
  const full = SHOT.w / IMG.w;
  const target = Math.min(SHOT.w / fw, SHOT_H / fh, full * MAX_ZOOM);
  const s = full + (target - full) * p;
  const cx = IMG.w / 2 + (fx + fw / 2 - IMG.w / 2) * p;
  const cy = IMG.h / 2 + (fy + fh / 2 - IMG.h / 2) * p;
  const tx = Math.min(0, Math.max(SHOT.w - IMG.w * s, SHOT.w / 2 - cx * s));
  const ty = Math.min(0, Math.max(SHOT_H - IMG.h * s, SHOT_H / 2 - cy * s));
  const o = interpolate(frame, [0, FADE], [0, 1], clamp);
  const box = interpolate(frame, [frames * 0.35, frames * 0.35 + 10], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ opacity: o, transform: `translateX(${(1 - o) * 24}px)` }}>
      <div style={{ position: 'absolute', width: IMG.w, height: IMG.h, transformOrigin: '0 0', transform: `translate(${tx}px, ${ty}px) scale(${s})` }}>
        <Img src={staticFile(`aws/${shot.file}`)} style={{ width: IMG.w, height: IMG.h }} />
        <div style={{ position: 'absolute', left: fx, top: fy, width: fw, height: fh, borderRadius: 10, border: `${3 / s}px solid rgba(242,196,109,${0.9 * box})` }} />
      </div>
    </AbsoluteFill>
  );
}

export function ShotsRun({ beats, fps, runStart, runLength }: { beats: Beat[]; fps: number; runStart: number; runLength: number }) {
  const frame = useCurrentFrame();
  const t = frame / fps;
  const shots = placeShots(beats, runStart);
  const current = shots.reduce((found, s) => (t >= s.start ? s : found), shots[0]);
  const reached = RAIL.findIndex((r) => r.id === current.node);
  const total = toFrames(runLength, fps);
  const enter = easeOut(interpolate(frame, [0, 18], [0, 1], clamp));
  const exit = interpolate(frame, [total - 10, total], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ opacity: enter * exit }}>
      <div style={{ position: 'absolute', left: 110, top: 150, width: 440 }}>
        <div style={{ fontFamily: MONO, fontSize: 18, letterSpacing: 2.5, color: C.accent }}>AWS CONSOLE EVIDENCE</div>
        <div style={{ marginTop: 26 }}>
          {RAIL.map((r, i) => {
            const active = r.id === current.node;
            const color = active ? C.text : i < reached ? C.muted : C.faint;
            return (
              <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 18, height: 76 }}>
                <span style={{ width: 4, height: active ? 46 : 14, borderRadius: 2, background: active ? C.warm : C.line }} />
                <div>
                  <div style={{ fontFamily: DISPLAY, fontSize: active ? 34 : 28, fontWeight: 650, color }}>{r.title}</div>
                  {active ? <div style={{ fontFamily: MONO, fontSize: 16, color: C.muted, marginTop: 2 }}>{r.sub}</div> : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div style={{ position: 'absolute', left: SHOT.x, top: SHOT.y - SHOT.chrome, width: SHOT.w, height: SHOT_H + SHOT.chrome, borderRadius: 14, overflow: 'hidden', background: '#0f141a', boxShadow: '0 40px 120px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.08)' }}>
        <div style={{ height: SHOT.chrome, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', fontFamily: MONO, fontSize: 15, color: C.muted, background: '#151b23' }}>
          <span>AWS Management Console · screenshot</span><span>Account details redacted</span>
        </div>
        <div style={{ position: 'relative', width: SHOT.w, height: SHOT_H, overflow: 'hidden' }}>
          {shots.map((s) => (
            <Sequence key={s.file + s.start} from={toFrames(s.start, fps)} durationInFrames={toFrames(s.length, fps) + FADE} layout="none">
              <Screenshot shot={s} frames={toFrames(s.length, fps)} />
            </Sequence>
          ))}
        </div>
      </div>
      <div style={{ position: 'absolute', left: SHOT.x, top: SHOT.y + SHOT_H + 22, width: SHOT.w, fontFamily: TEXT, fontSize: 26, color: C.text }}>
        {current.label}
      </div>
    </AbsoluteFill>
  );
}
