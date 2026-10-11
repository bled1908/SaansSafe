import { Composition, Still, staticFile } from 'remotion';
import script from './script.json';
import { buildTimeline, toFrames } from './timeline.js';
import { SaansSafeVideo } from './Video';
import { Thumbnail } from './Thumbnail';
import type { Timeline, VideoProps } from './types';

// Draft: timing estimated from the script (no narration audio yet).
const draft = buildTimeline(script) as Timeline;

export function Root() {
  return (
    <>
      <Composition
        id="SaansSafeDraft"
        component={SaansSafeVideo}
        fps={draft.fps}
        width={1920}
        height={1080}
        durationInFrames={toFrames(draft.totalSeconds, draft.fps)}
        defaultProps={{ timeline: draft, withNarration: false } satisfies VideoProps}
      />
      <Still id="Thumbnail" component={Thumbnail} width={1280} height={720} />
      <Composition
        id="SaansSafeMusicOnly"
        component={SaansSafeVideo}
        fps={draft.fps}
        width={1920}
        height={1080}
        durationInFrames={toFrames(draft.totalSeconds, draft.fps)}
        defaultProps={{ timeline: draft, withNarration: false, musicOnly: true } satisfies VideoProps}
      />
      <Composition
        id="SaansSafeFinal"
        component={SaansSafeVideo}
        fps={draft.fps}
        width={1920}
        height={1080}
        durationInFrames={toFrames(draft.totalSeconds, draft.fps)}
        defaultProps={{ timeline: draft, withNarration: true } satisfies VideoProps}
        calculateMetadata={async () => {
          // Written by scripts/narrate.mjs after an approved Polly synthesis.
          const res = await fetch(staticFile('audio/v2/narration.json'));
          if (!res.ok) throw new Error('public/audio/v2/narration.json missing: synthesize narration first');
          const timeline = buildTimeline(script, await res.json()) as Timeline;
          return {
            durationInFrames: toFrames(timeline.totalSeconds, timeline.fps),
            props: { timeline, withNarration: true },
          };
        }}
      />
    </>
  );
}
