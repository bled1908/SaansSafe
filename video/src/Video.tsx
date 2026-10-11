import type { ReactNode } from 'react';
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { toFrames } from './timeline.js';
import { C, clamp, easeOut } from './theme';
import type { Beat, VideoProps } from './types';
import { AppRun, MatchCut, PhoneBeat } from './visuals/AppWindow';
import { Diagram, ShotsRun } from './visuals/Aws';
import { AqiScale, BuildBeat, Closing, Deterministic, EndCard, Questions, TypeBeat } from './visuals/Kinetic';
import { Backdrop, Captions, ChapterMark, DraftBadge, Finish } from './visuals/Overlays';
import { Soundtrack } from './visuals/Soundtrack';

export type { VideoProps } from './types';

const FADE = 10;
const RUN_TYPES = new Set(['app', 'shots']);

/** Group consecutive beats of the same run type so one window persists across them. */
function runs(beats: Beat[]): Beat[][] {
  return beats.reduce<Beat[][]>((out, beat) => {
    const last = out[out.length - 1];
    if (last && RUN_TYPES.has(beat.visual.type) && last[0].visual.type === beat.visual.type) return [...out.slice(0, -1), [...last, beat]];
    return [...out, [beat]];
  }, []);
}

/** Fade a standalone graphic beat in and out. */
function Graphic({ frames, children }: { frames: number; children: ReactNode }) {
  const frame = useCurrentFrame();
  const t = easeOut(interpolate(frame, [0, FADE + 4], [0, 1], clamp));
  const out = interpolate(frame, [frames - FADE, frames], [1, 0], clamp);
  return <AbsoluteFill style={{ opacity: t * out, transform: `scale(${1.012 - 0.012 * t})` }}>{children}</AbsoluteFill>;
}

function BeatVisual({ beat, fps }: { beat: Beat; fps: number }) {
  switch (beat.visual.type) {
    case 'type': return <TypeBeat beat={beat} />;
    case 'scale': return <AqiScale beat={beat} />;
    case 'questions': return <Questions beat={beat} />;
    case 'build': return <BuildBeat beat={beat} />;
    case 'deterministic': return <Deterministic beat={beat} />;
    case 'closing': return <Closing beat={beat} fps={fps} />;
    case 'end': return <EndCard />;
    default: return null;
  }
}

function Run({ group, fps }: { group: Beat[]; fps: number }) {
  const first = group[0];
  const start = first.start;
  const length = group.reduce((n, b) => n + b.length, 0);
  const frames = toFrames(length, fps);
  const type = first.visual.type;
  let body: ReactNode;
  if (type === 'app') body = <AppRun beats={group} fps={fps} runStart={start} runLength={length} />;
  else if (type === 'shots') body = <ShotsRun beats={group} fps={fps} runStart={start} runLength={length} />;
  else if (type === 'matchcut') body = <MatchCut beat={first} fps={fps} />;
  else if (type === 'phone') body = <PhoneBeat beat={first} fps={fps} />;
  else if (type === 'diagram') body = <Diagram beat={first} fps={fps} />;
  else body = <Graphic frames={frames}><BeatVisual beat={first} fps={fps} /></Graphic>;
  return <Sequence from={toFrames(start, fps)} durationInFrames={frames}>{body}</Sequence>;
}

export function SaansSafeVideo({ timeline, withNarration, musicOnly = false }: VideoProps) {
  const { fps } = useVideoConfig();
  const beats = timeline.scenes.flatMap((s) => s.beats);
  return (
    <AbsoluteFill style={{ background: C.ink }}>
      <Backdrop scenes={timeline.scenes} />
      {runs(beats).map((group) => <Run key={group[0].id} group={group} fps={fps} />)}
      {timeline.scenes.map((scene) => (
        <Sequence key={scene.id} from={toFrames(scene.start, fps)} durationInFrames={toFrames(scene.length, fps)} layout="none">
          <ChapterMark scene={scene} />
        </Sequence>
      ))}
      <Captions captions={timeline.captions} />
      <Finish />
      {withNarration || musicOnly ? null : <DraftBadge text="Review draft · narration not yet synthesized · timing estimated from script" />}
      <Soundtrack timeline={timeline} withNarration={withNarration} musicOnly={musicOnly} />
    </AbsoluteFill>
  );
}
