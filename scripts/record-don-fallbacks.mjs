#!/usr/bin/env node
/**
 * scripts/record-don-fallbacks.mjs
 *
 * Playwright-based fallback-video recorder for CT-0419-05 Don-Demo sprint.
 * Records ~90-second walkthroughs of each of 3 visual surfaces:
 *   - aimg-site (deploy/aimg-site/index.html)
 *   - aimemoryguard-landing (deploy/aimemoryguard-landing/index.html)
 *   - amg-chatbot-widget (deploy/amg-chatbot-widget/demo.html)
 *
 * Voice demo is NOT recorded by this script — it needs real mic audio
 * + real backend round-trip, which is better captured via macOS Screen
 * Recording + Solon's live voice. See FALLBACK_VIDEO_STRATEGY doc.
 *
 * Prereqs:
 *   - Node 18+
 *   - `npm install playwright` (or `npx playwright install chromium`)
 *   - Python3 (for the static-file servers these recordings consume)
 *
 * Output:
 *   /opt/amg/demo-assets/don-backup-YYYYMMDD-{aimg-site,memoryguard-site,chatbot}.mp4
 *
 * Usage:
 *   node scripts/record-don-fallbacks.mjs
 *
 * Tuning: set OUTPUT_DIR env var to override /opt/amg/demo-assets/.
 */

import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const REPO = path.resolve(path.dirname(__filename), '..');
const OUTPUT_DIR = process.env.OUTPUT_DIR || '/opt/amg/demo-assets';
const DATE = new Date().toISOString().slice(0, 10).replace(/-/g, '');
const VIEWPORT = { width: 1280, height: 800 };

const SURFACES = [
  {
    key: 'aimg-site',
    dir: 'deploy/aimg-site',
    port: 8848,
    file: `don-backup-${DATE}-aimg-site.mp4`,
    walkthrough: async (page) => {
      await page.goto(`http://127.0.0.1:8848/index.html`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(3500); // settle hero + ambient gradient
      // scroll through in ~85s
      const sections = ['#agents', '#pricing', '#chamber', '#cases', '.guarantee', '#contact'];
      for (const sel of sections) {
        const el = await page.$(sel);
        if (el) {
          await el.scrollIntoViewIfNeeded();
          await page.waitForTimeout(13500);
        }
      }
      await page.waitForTimeout(2000);
    },
  },
  {
    key: 'memoryguard-site',
    dir: 'deploy/aimemoryguard-landing',
    port: 8847,
    file: `don-backup-${DATE}-memoryguard-site.mp4`,
    walkthrough: async (page) => {
      await page.goto(`http://127.0.0.1:8847/index.html`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(3000); // settle hero
      // let the live demo cycle through cycle 1 + 2 (~20s)
      await page.waitForTimeout(20000);
      // scroll to features
      const features = await page.$('#features');
      if (features) { await features.scrollIntoViewIfNeeded(); await page.waitForTimeout(12000); }
      const how = await page.$('#how');
      if (how) { await how.scrollIntoViewIfNeeded(); await page.waitForTimeout(12000); }
      const pricing = await page.$('#pricing');
      if (pricing) { await pricing.scrollIntoViewIfNeeded(); await page.waitForTimeout(15000); }
      // click the billing toggle
      const toggle = await page.$('#billingToggle');
      if (toggle) { await toggle.click(); await page.waitForTimeout(5000); }
      // scroll to closing
      const closing = await page.$('.closing');
      if (closing) { await closing.scrollIntoViewIfNeeded(); await page.waitForTimeout(8000); }
    },
  },
  {
    key: 'chatbot',
    dir: 'deploy/amg-chatbot-widget',
    port: 8846,
    file: `don-backup-${DATE}-chatbot.mp4`,
    walkthrough: async (page) => {
      await page.goto(`http://127.0.0.1:8846/demo.html`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(2500);
      // inject the demo fetch-interceptor so submit returns rich content
      await page.evaluate(() => {
        window.__origFetch = window.fetch;
        window.fetch = async () => ({
          ok: true, status: 200, headers: { get: () => 'application/json' },
          json: async () => ({
            reply: "Atlas tiers — here's what most Chamber partners land on:",
            pricing: [
              { name: 'Lite',       price: '$995/mo',   unit: 'founding rate $497' },
              { name: 'Core',       price: '$2,500/mo', unit: 'most common', featured: true },
              { name: 'Enterprise', price: '$10K/mo',   unit: 'metro + state' },
            ],
            cards: [{
              meta: 'Guarantee', title: '3-month satisfaction',
              body: "If after 3 months you're not completely satisfied, we work a **full month FREE**. No asterisks."
            }],
            buttons: [
              { label: 'Book a 15-min audit', value: "I'd like to book an audit", primary: true },
              { label: 'Chamber program', value: 'Tell me about the Chamber program' }
            ]
          })
        });
      });
      // open panel
      await page.click('.amg-widget-fab');
      await page.waitForTimeout(2500);
      // type + submit
      await page.fill('.amg-widget-input', 'What are your prices?');
      await page.waitForTimeout(800);
      await page.click('.amg-widget-send');
      await page.waitForTimeout(6000);
      // scroll transcript so pricing + buttons are visible
      await page.evaluate(() => {
        const m = document.querySelector('.amg-widget-messages');
        if (m) m.scrollTop = m.scrollHeight;
      });
      await page.waitForTimeout(8000);
      // type 2nd question
      await page.fill('.amg-widget-input', 'Tell me about the Chamber program');
      await page.waitForTimeout(800);
      await page.click('.amg-widget-send');
      await page.waitForTimeout(8000);
      // scroll to show reply
      await page.evaluate(() => {
        const m = document.querySelector('.amg-widget-messages');
        if (m) m.scrollTop = m.scrollHeight;
      });
      await page.waitForTimeout(15000);
      // close panel
      await page.click('.amg-widget-close');
      await page.waitForTimeout(4000);
    },
  },
];

async function ensureOutputDir() {
  try {
    await fs.mkdir(OUTPUT_DIR, { recursive: true });
  } catch (err) {
    console.error(`FAIL: cannot create ${OUTPUT_DIR}. Maybe run with sudo or set OUTPUT_DIR env.`);
    console.error(err.message);
    process.exit(1);
  }
}

function startStaticServer(dir, port) {
  const abs = path.resolve(REPO, dir);
  const srv = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1', '--directory', abs], {
    stdio: ['ignore', 'ignore', 'ignore'],
    detached: false,
  });
  return srv;
}

async function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

async function recordOne(surface) {
  console.log(`\n=== Recording ${surface.key} → ${surface.file} ===`);
  const srv = startStaticServer(surface.dir, surface.port);
  await wait(800); // let python http.server bind

  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  try {
    const context = await browser.newContext({
      viewport: VIEWPORT,
      recordVideo: { dir: OUTPUT_DIR, size: VIEWPORT },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();

    await surface.walkthrough(page);

    const videoPath = await page.video().path();
    await context.close();
    await browser.close();

    // rename recorded video to deterministic filename
    const targetPath = path.join(OUTPUT_DIR, surface.file);
    try { await fs.unlink(targetPath); } catch {}
    await fs.rename(videoPath, targetPath);
    console.log(`  wrote ${targetPath}`);
  } finally {
    try { srv.kill('SIGTERM'); } catch {}
  }
}

async function main() {
  await ensureOutputDir();
  console.log(`Output dir: ${OUTPUT_DIR}`);
  console.log(`Date tag: ${DATE}`);
  for (const surface of SURFACES) {
    try {
      await recordOne(surface);
    } catch (err) {
      console.error(`FAIL ${surface.key}: ${err.message}`);
    }
  }
  console.log(`\nDone. Expected files:`);
  for (const s of SURFACES) console.log(`  ${path.join(OUTPUT_DIR, s.file)}`);
  console.log(`\nVoice demo: record manually via macOS Screen Recording per FALLBACK_VIDEO_STRATEGY doc.`);
}

main().catch((err) => {
  console.error('FATAL:', err);
  process.exit(1);
});
