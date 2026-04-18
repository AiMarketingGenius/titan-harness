/**
 * titan-harness/scripts/ct0418_chamber_stagehand_shots.mjs
 *
 * Full-page screenshots of https://memory.aimarketinggenius.io/chamber-partners/
 * for Solon's Monday browser-confirm (per 21:20Z UI-ship rule).
 *
 * Outputs to /opt/amg-demo-backup/chamber-partners-screenshots/:
 *   desktop-1440.png — desktop viewport, full page
 *   desktop-1920.png — wide desktop, full page
 *   mobile-iphone.png — iPhone 14 Pro viewport, full page
 *   mobile-pixel.png  — Pixel 7 viewport, full page
 *   _manifest.json — metadata for each capture
 *
 * Run on VPS: node ct0418_chamber_stagehand_shots.mjs
 */
import { chromium, devices } from "/opt/persistent-browser/node_modules/playwright/index.mjs";
import { mkdir, writeFile } from "fs/promises";
import { join } from "path";

const URL = "https://memory.aimarketinggenius.io/chamber-partners/";
const OUT_DIR = "/opt/amg-demo-backup/chamber-partners-screenshots";

const VIEWPORTS = [
  {
    name: "desktop-1440",
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    isMobile: false,
    userAgent: undefined,
  },
  {
    name: "desktop-1920",
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 2,
    isMobile: false,
    userAgent: undefined,
  },
  {
    name: "mobile-iphone",
    viewport: devices["iPhone 14 Pro"].viewport,
    deviceScaleFactor: devices["iPhone 14 Pro"].deviceScaleFactor,
    isMobile: true,
    userAgent: devices["iPhone 14 Pro"].userAgent,
  },
  {
    name: "mobile-pixel",
    viewport: devices["Pixel 7"].viewport,
    deviceScaleFactor: devices["Pixel 7"].deviceScaleFactor,
    isMobile: true,
    userAgent: devices["Pixel 7"].userAgent,
  },
];

async function run() {
  await mkdir(OUT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const manifest = {
    url: URL,
    captured_at: new Date().toISOString(),
    captures: [],
  };

  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: vp.viewport,
      deviceScaleFactor: vp.deviceScaleFactor,
      isMobile: vp.isMobile,
      hasTouch: vp.isMobile,
      userAgent: vp.userAgent,
    });
    const page = await context.newPage();
    const t0 = Date.now();
    await page.goto(URL, { waitUntil: "networkidle", timeout: 45_000 });
    // wait for fonts + hero count-up animations to settle
    await page.waitForTimeout(2500);
    const path = join(OUT_DIR, `${vp.name}.png`);
    await page.screenshot({ path, fullPage: true, type: "png" });
    const { width, height } = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    }));
    manifest.captures.push({
      name: vp.name,
      viewport: vp.viewport,
      deviceScaleFactor: vp.deviceScaleFactor,
      isMobile: vp.isMobile,
      page_size: { width, height },
      path,
      elapsed_ms: Date.now() - t0,
    });
    console.log(`${vp.name}: ${path} (${width}x${height}, ${Date.now() - t0}ms)`);
    await context.close();
  }

  await browser.close();
  const manifestPath = join(OUT_DIR, "_manifest.json");
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2));
  console.log(`manifest: ${manifestPath}`);
}

run().catch((err) => {
  console.error("FAIL:", err);
  process.exit(1);
});
