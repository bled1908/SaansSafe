// Records genuine footage of the deployed SaansSafe site (ui-demo workflow:
// discover -> rehearse -> record). Nothing on the page is altered except an
// injected cursor overlay so viewers can follow the pointer.
//
//   node scripts/record.mjs --rehearse   # verify every selector, no video
//   node scripts/record.mjs              # record desktop + mobile sessions
//
// Output (git-ignored): public/captures/{desktop,mobile}.webm and
// public/captures/markers.json with clip start/end offsets in seconds.

import { chromium } from 'playwright-core';
import fs from 'node:fs/promises';
import path from 'node:path';

const SITE = 'https://d316zs0sydbi1r.cloudfront.net/';
const API = 'https://paqffn4eq5.execute-api.ap-south-1.amazonaws.com/aqi?lat=28.61&lon=77.21';
const OUT_DIR = path.resolve('public/captures');
const REHEARSE = process.argv.includes('--rehearse');

// 1440x810 CSS px rendered at 4/3 scale = crisp 1920x1080 frames.
const DESKTOP = { viewport: { width: 1440, height: 810 }, deviceScaleFactor: 4 / 3, video: { width: 1920, height: 1080 } };
const MOBILE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, video: { width: 780, height: 1688 }, isMobile: true, hasTouch: true };

const failures = [];

async function injectCursor(page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-cursor')) return;
    const cursor = document.createElement('div');
    cursor.id = 'demo-cursor';
    cursor.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5 3L19 12L12 13L9 20L5 3Z" fill="white" stroke="black" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    cursor.style.cssText = 'position:fixed;z-index:999999;pointer-events:none;width:26px;height:26px;left:-40px;top:-40px;transition:left .08s,top .08s;filter:drop-shadow(1px 1px 2px rgba(0,0,0,.3));';
    document.body.appendChild(cursor);
    document.addEventListener('mousemove', (e) => {
      cursor.style.left = e.clientX + 'px';
      cursor.style.top = e.clientY + 'px';
    });
  });
}

async function ensureVisible(locator, label) {
  const visible = await locator.first().isVisible().catch(() => false);
  console.log(`${visible ? 'OK  ' : 'FAIL'} ${label}`);
  if (!visible) failures.push(label);
  return visible;
}

async function moveTo(page, locator, label) {
  const el = locator.first();
  if (!(await ensureVisible(el, label))) return null;
  await el.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  const box = await el.boundingBox();
  if (box) await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 });
  await page.waitForTimeout(350);
  return box;
}

async function moveAndClick(page, locator, label, after = 1200) {
  const box = await moveTo(page, locator, label);
  if (!box) return false;
  await locator.first().click();
  await page.waitForTimeout(after);
  return true;
}

async function smoothScrollTo(page, locator, label, offset = 90) {
  const el = locator.first();
  if (!(await ensureVisible(el, label))) return;
  await page.evaluate(([y]) => window.scrollTo({ top: y, behavior: 'smooth' }),
    [await el.evaluate((n, o) => n.getBoundingClientRect().top + window.scrollY - o, offset)]);
  await page.waitForTimeout(1600);
}

async function panAcross(page, locator, label) {
  const box = await moveTo(page, locator, label);
  if (!box) return;
  const y = box.y + box.height / 2;
  await page.mouse.move(box.x + 8, y, { steps: 20 });
  await page.waitForTimeout(300);
  await page.mouse.move(box.x + box.width - 8, y, { steps: 90 });
  await page.waitForTimeout(600);
}

async function waitForDecision(page) {
  await page.getByText('SaansSafe school safety policy').first().waitFor({ timeout: 20000 });
  await page.waitForTimeout(800);
}

async function desktopSession(page, mark) {
  await page.goto(SITE, { waitUntil: 'networkidle' });
  await injectCursor(page);
  await page.waitForTimeout(1500);

  mark('R1_start');
  await moveAndClick(page, page.getByRole('button', { name: /^Delhi/ }), 'Example location: Delhi', 400);
  await waitForDecision(page);
  await page.waitForTimeout(1500);
  for (const name of ['Assembly', 'PE & sports', 'Recess']) {
    await moveTo(page, page.getByText(name, { exact: true }), `Activity card: ${name}`);
    await page.waitForTimeout(700);
  }
  await page.waitForTimeout(1200);
  mark('R1_end');

  mark('R2_start');
  await moveAndClick(page, page.getByRole('button', { name: /Choose a location|Delhi/ }).first(), 'Location picker', 900);
  await moveAndClick(page, page.getByRole('button', { name: /^Mumbai/ }), 'Picker option: Mumbai', 400);
  await waitForDecision(page);
  await page.waitForTimeout(2500);
  mark('R2_end');
  await moveAndClick(page, page.getByRole('button', { name: /Choose a location|Mumbai/ }).first(), 'Location picker (back)', 900);
  await moveAndClick(page, page.getByRole('button', { name: /^Delhi/ }), 'Picker option: Delhi', 400);
  await waitForDecision(page);
  await page.waitForTimeout(1200);

  mark('R3_start');
  await moveTo(page, page.getByText('Forecast/model', { exact: false }).nth(1), 'Forecast/model label');
  await page.waitForTimeout(900);
  await moveTo(page, page.getByText('AIR NOW', { exact: false }), 'Air now card');
  await page.waitForTimeout(1200);
  await smoothScrollTo(page, page.getByText('CAMS via Open-Meteo').first(), 'Data panel', 260);
  await moveTo(page, page.getByText('CAMS via Open-Meteo').first(), 'Data source row');
  await page.waitForTimeout(2200);
  mark('R3_end');

  mark('R4_start');
  await smoothScrollTo(page, page.getByRole('heading', { name: 'Next 72 hours' }), 'Next 72 hours heading', 80);
  await page.waitForTimeout(1200);
  const strip = page.locator('ol[aria-label^="Hourly outlook"]');
  await panAcross(page, strip, 'Hourly outlook strip');
  for (const label of ['BEST SCHOOL WINDOW', 'NEXT CHANGE', 'WORST EXPECTED']) {
    await moveTo(page, page.getByText(label, { exact: false }), `Outlook summary: ${label}`);
    await page.waitForTimeout(900);
  }
  await page.waitForTimeout(1000);
  mark('R4_end');

  mark('R5_start');
  await smoothScrollTo(page, page.getByRole('heading', { name: 'Parent notice' }), 'Parent notice heading', 80);
  await moveAndClick(page, page.getByRole('button', { name: /Generate notice/ }), 'Generate notice (English)', 2500);
  await page.waitForTimeout(2000);
  await moveAndClick(page, page.locator('label').filter({ hasText: 'हिंदी' }), 'Language: Hindi', 900);
  await moveAndClick(page, page.getByRole('button', { name: /Generate notice/ }), 'Generate notice (Hindi)', 2500);
  await page.waitForTimeout(2500);
  await moveTo(page, page.getByText('Verified template', { exact: false }), 'Verified template label');
  await page.waitForTimeout(900);
  for (const name of [/Copy message/, /Print notice/]) {
    await moveTo(page, page.getByRole('button', { name }), `Notice action: ${name}`);
    await page.waitForTimeout(500);
  }
  await page.waitForTimeout(1200);
  mark('R5_end');

  mark('R7_start');
  await page.goto(API, { waitUntil: 'load' });
  await page.waitForTimeout(800);
  const pretty = page.getByText('Pretty-print', { exact: false });
  if (await pretty.first().isVisible().catch(() => false)) await pretty.first().click();
  console.log('OK   API /aqi response loaded');
  await page.waitForTimeout(4000);
  mark('R7_end');
}

async function mobileSession(page, mark) {
  await page.goto(SITE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  mark('R6_start');
  const delhi = page.getByRole('button', { name: /^Delhi/ });
  if (await ensureVisible(delhi, 'Mobile: Delhi')) await delhi.first().tap();
  await waitForDecision(page);
  await page.waitForTimeout(2500);
  for (const y of [500, 1000, 1500]) {
    await page.evaluate((top) => window.scrollTo({ top, behavior: 'smooth' }), y);
    await page.waitForTimeout(1500);
  }
  mark('R6_end');
}

async function run(browser, profile, name, session) {
  const context = await browser.newContext({
    viewport: profile.viewport,
    deviceScaleFactor: profile.deviceScaleFactor,
    isMobile: profile.isMobile ?? false,
    hasTouch: profile.hasTouch ?? false,
    locale: 'en-IN',
    timezoneId: 'Asia/Kolkata',
    ...(REHEARSE ? {} : { recordVideo: { dir: OUT_DIR, size: profile.video } }),
  });
  const page = await context.newPage();
  const t0 = Date.now();
  const markers = {};
  const mark = (key) => { markers[key] = +((Date.now() - t0) / 1000).toFixed(2); };
  try {
    await session(page, mark);
  } catch (err) {
    failures.push(`${name}: ${err.message.split('\n')[0]}`);
    console.error(`FAIL ${name}: ${err.message.split('\n')[0]}`);
  }
  if (REHEARSE) await page.screenshot({ path: path.join(OUT_DIR, `rehearse-${name}.png`) });
  const video = page.video();
  await context.close();
  if (!video) return { markers };
  const file = `${name}.webm`;
  await fs.rename(await video.path(), path.join(OUT_DIR, file));
  return { file, markers };
}

await fs.mkdir(OUT_DIR, { recursive: true });
const browser = await chromium.launch();
const result = {
  recordedAt: new Date().toISOString(),
  site: SITE,
  desktop: await run(browser, DESKTOP, 'desktop', desktopSession),
  mobile: await run(browser, MOBILE, 'mobile', mobileSession),
};
await browser.close();
if (!REHEARSE) await fs.writeFile(path.join(OUT_DIR, 'markers.json'), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
if (failures.length) {
  console.error(`\n${failures.length} step(s) failed:\n- ${failures.join('\n- ')}`);
  process.exit(1);
}
console.log(REHEARSE ? '\nREHEARSAL PASSED' : '\nRECORDING COMPLETE');
