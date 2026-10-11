import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs';
import { Config } from '@remotion/cli/config';

// Reuse Playwright's already-cached Chrome Headless Shell instead of
// downloading another browser. Falls back to Remotion's default if absent.
const cachedShell = path.join(
  os.homedir(), 'AppData', 'Local', 'ms-playwright',
  'chromium_headless_shell-1243', 'chrome-headless-shell-win64', 'chrome-headless-shell.exe',
);
if (fs.existsSync(cachedShell)) Config.setBrowserExecutable(cachedShell);

// PNG intermediate frames: JPEG frames make ffmpeg emit full-range yuvj420p,
// which YouTube may display with shifted contrast. PNG + yuv420p + bt709 is safe.
Config.setVideoImageFormat('png');
Config.setPixelFormat('yuv420p');
Config.setColorSpace('bt709');
Config.setOverwriteOutput(true);
