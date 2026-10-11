import { AbsoluteFill, OffthreadVideo, staticFile, useVideoConfig } from 'remotion';
import { C, DISPLAY, HINDI, MONO } from './theme';

// YouTube thumbnail (1280x720): the real decision screen from the capture,
// with the question the film opens on. Text is sized to read on a phone.
const FRAME_S = 12.5; // desktop capture: Delhi decision with activity cards

export function Thumbnail() {
  const { fps } = useVideoConfig(); // stills run at 1 fps, so convert seconds via the config
  return (
    <AbsoluteFill style={{ background: `radial-gradient(900px 600px at 30% 40%, #1b2534 0%, ${C.ink} 75%)` }}>
      <div style={{
        position: 'absolute', left: 560, top: 92, width: 900, height: 536, borderRadius: 18, overflow: 'hidden',
        transform: 'perspective(1600px) rotateY(-12deg)', transformOrigin: 'left center',
        boxShadow: '0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.1)', background: C.window,
      }}>
        <div style={{ position: 'absolute', width: 1920, height: 1080, transformOrigin: '0 0', transform: `scale(${900 / 1100}) translate(-60px, -60px)` }}>
          <OffthreadVideo src={staticFile('captures/desktop.webm')} trimBefore={Math.round(FRAME_S * fps)} muted style={{ width: 1920, height: 1080 }} />
        </div>
      </div>
      <AbsoluteFill style={{ background: 'linear-gradient(90deg, rgba(10,13,18,0.96) 0%, rgba(10,13,18,0.85) 42%, rgba(10,13,18,0) 62%)' }} />
      <div style={{ position: 'absolute', left: 64, top: 70, width: 620, color: C.text }}>
        <div style={{ fontFamily: DISPLAY, fontSize: 44, fontWeight: 700 }}>
          SaansSafe <span style={{ fontFamily: HINDI, color: C.accent, fontWeight: 600 }}>साँस</span>
        </div>
        <div style={{ fontFamily: DISPLAY, fontSize: 96, fontWeight: 750, lineHeight: 1.0, letterSpacing: -3, marginTop: 34 }}>
          Can students go <span style={{ color: C.warm }}>outside</span> today?
        </div>
        <div style={{ fontFamily: DISPLAY, fontSize: 32, color: C.muted, marginTop: 30, lineHeight: 1.25 }}>
          Air-quality forecasts turned into clear school decisions
        </div>
        <div style={{ display: 'flex', gap: 12, marginTop: 34 }}>
          {['Built on AWS', 'English + हिंदी'].map((chip) => (
            <span key={chip} style={{ fontFamily: MONO, fontSize: 22, color: C.text, padding: '8px 16px', borderRadius: 10, border: `1px solid ${C.line}`, background: 'rgba(255,255,255,0.06)' }}>{chip}</span>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
}
