import { Easing } from 'remotion';

// Shared look for the film. Footage is never colour-graded: only the
// backgrounds and graphics around it use this palette, so the product's
// real colours (AQI categories, decision states) stay exactly as captured.

export const C = {
  ink: '#0a0d12',
  panel: '#121821',
  panelHi: '#18202b',
  line: 'rgba(255,255,255,0.09)',
  text: '#f4f2ed',
  muted: '#9aa3b2',
  faint: '#5d6676',
  accent: '#9ea4ff',
  warm: '#f2c46d',
  sky: '#7cc4e8',
  window: '#f7f5f0',
};

export const DISPLAY = '"Segoe UI Variable Display", "Segoe UI", system-ui, sans-serif';
export const TEXT = '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif';
export const MONO = '"Cascadia Mono", Consolas, monospace';
export const HINDI = '"Nirmala UI", "Segoe UI", sans-serif';

// App window: a 16:9 viewport onto the 1440x810 desktop capture.
export const CAPTURE = { w: 1440, h: 810 };
export const WINDOW = { x: 200, y: 70, w: 1520, h: 855, chrome: 36 };

export const easeInOut = Easing.bezier(0.45, 0, 0.2, 1);
export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const drift = Easing.bezier(0.3, 0.1, 0.3, 1);

export const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
