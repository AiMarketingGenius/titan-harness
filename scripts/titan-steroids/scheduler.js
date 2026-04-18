#!/usr/bin/env node
// scheduler.js — Titan Steroids C1 MVP scheduler.
//
// Polls the YAML class registry every 60s. For each class whose cadence is
// due AND which passes the kill-switch check, enqueues a BullMQ job on
// `titan-steroids:default`. A single in-process worker consumes the queue and
// executes the class via lib/executor.js. Every state transition is logged as
// an MCP decision (`titan-steroids-execution` tag family).
//
// CLI:
//   node scheduler.js            — daemon mode (polls forever)
//   node scheduler.js --once     — run one poll + drain queue, then exit
//   node scheduler.js --enqueue <class_name>  — force-enqueue one class
//
// Env:
//   SHARED_REDIS_HOST/PORT/PASSWORD   — BullMQ Redis connection
//   SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY — MCP decision logging

'use strict';

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');
const { Queue, Worker, QueueEvents } = require('bullmq');
const IORedis = require('ioredis');
const mcp = require('./lib/mcp_log');
const exec = require('./lib/executor');
const accept = require('./lib/acceptance');

const REGISTRY_PATH = process.env.TITAN_STEROIDS_REGISTRY || path.join(__dirname, 'class-registry.yaml');
const POLL_INTERVAL_MS = Number(process.env.TITAN_STEROIDS_POLL_MS || 60000);
const QUEUE_NAME = 'titan-steroids-default';
const KILL_SWITCH_TAG = 'titan-steroids-disabled';

function redisConnection() {
  return new IORedis({
    host: process.env.SHARED_REDIS_HOST || '127.0.0.1',
    port: Number(process.env.SHARED_REDIS_PORT || 6380),
    password: process.env.SHARED_REDIS_PASSWORD || undefined,
    maxRetriesPerRequest: null,
    enableReadyCheck: false,
  });
}

function loadRegistry() {
  const raw = fs.readFileSync(REGISTRY_PATH, 'utf8');
  const reg = yaml.load(raw);
  if (!reg || !Array.isArray(reg.classes)) {
    throw new Error('invalid registry: classes[] missing');
  }
  return reg;
}

function isDue(cls, lastRunTs) {
  // MVP: use cadence strings + a coarse schedule check.
  // "daily" → run if > 20 hrs since last run
  // "weekly" → > 6 days
  // "monthly" → > 27 days
  // "custom:<cron>" → not implemented for MVP (always skip)
  const lastMs = lastRunTs ? Number(lastRunTs) : 0;
  const now = Date.now();
  const age = now - lastMs;
  switch (cls.cadence) {
    case 'daily': return age >= 20 * 3600 * 1000;
    case 'weekly': return age >= 6 * 86400 * 1000;
    case 'monthly': return age >= 27 * 86400 * 1000;
    default: return false;  // custom cron not wired in MVP
  }
}

async function killSwitchActive() {
  try {
    const rows = await mcp.getRecentDecisionsByTag(KILL_SWITCH_TAG, 3);
    return Array.isArray(rows) && rows.length > 0;
  } catch (err) {
    console.error('[kill-switch-check-failed]', err.message);
    return true;  // fail closed — if we can't check, assume disabled
  }
}

async function classPaused(className) {
  try {
    const rows = await mcp.getRecentDecisionsByTag(`class-paused:${className}`, 1);
    return Array.isArray(rows) && rows.length > 0;
  } catch (_) {
    return false;
  }
}

async function executeClass(cls) {
  const started = Date.now();
  console.log(`[${new Date().toISOString()}] [run] ${cls.name}`);
  const probeOut = await exec.runClass(cls);
  const ok = probeOut.ok && probeOut.result ? accept.evaluate(probeOut.result, cls.acceptance_criteria) : { passed: false, failures: [{ reason: probeOut.error || 'probe failed' }], rows: [] };
  const pass = probeOut.ok && ok.passed;
  const duration = Date.now() - started;

  // Log to MCP
  const status = pass ? 'pass' : 'fail';
  const summary = pass
    ? `PASS ${cls.name} (${duration}ms)`
    : `FAIL ${cls.name} (${duration}ms) — reasons: ${(ok.failures || []).map((f) => f.eval?.reason || f.reason || 'unknown').join('; ') || probeOut.error || 'unknown'}`;
  try {
    await mcp.logDecision({
      text: `TITAN-STEROIDS EXECUTION ${new Date().toISOString()} — ${summary}. Probe output excerpt: ${JSON.stringify(probeOut.result || probeOut).slice(0, 300)}`,
      tags: ['titan-steroids-execution', `class:${cls.name}`, `status:${status}`],
      decision_type: 'execution',
      rationale: `Acceptance eval: ${JSON.stringify(ok).slice(0, 300)}`,
    });
  } catch (err) {
    console.error('[mcp-log-failed]', err.message);
  }

  return { pass, duration, probe: probeOut, accept: ok };
}

async function pollOnce(queue) {
  const reg = loadRegistry();
  const killed = await killSwitchActive();
  if (killed) {
    console.log('[kill-switch] titan-steroids-disabled tag detected — skipping all classes');
    return { enqueued: 0, killed: true };
  }
  let enqueued = 0;
  for (const cls of reg.classes) {
    if (!cls.enabled) continue;
    if (await classPaused(cls.name)) {
      console.log(`[paused] ${cls.name}`);
      continue;
    }
    // MVP: track last_run in a file next to the registry (simple state).
    // Future: move to MCP `titan-steroids-last-run:<class>` tag for shared state.
    const stateFile = path.join(path.dirname(REGISTRY_PATH), `.state.${cls.name}.json`);
    let lastRun = 0;
    if (fs.existsSync(stateFile)) {
      try { lastRun = JSON.parse(fs.readFileSync(stateFile, 'utf8')).last_run || 0; } catch (_) {}
    }
    if (!isDue(cls, lastRun)) continue;
    await queue.add(cls.name, { className: cls.name, enqueued_at: Date.now() }, { attempts: 1, removeOnComplete: 50, removeOnFail: 50 });
    enqueued += 1;
    console.log(`[enqueued] ${cls.name}`);
  }
  return { enqueued, killed: false };
}

async function forceEnqueue(queue, name) {
  const reg = loadRegistry();
  const cls = reg.classes.find((c) => c.name === name);
  if (!cls) throw new Error(`class not found: ${name}`);
  await queue.add(name, { className: name, enqueued_at: Date.now(), forced: true }, { attempts: 1 });
  console.log(`[force-enqueued] ${name}`);
}

async function main() {
  const args = process.argv.slice(2);
  const once = args.includes('--once');
  const enqueueIdx = args.indexOf('--enqueue');
  const forcedName = enqueueIdx >= 0 ? args[enqueueIdx + 1] : null;

  const connection = redisConnection();
  const queue = new Queue(QUEUE_NAME, { connection });

  // Single in-process worker so MVP stays self-contained.
  const worker = new Worker(QUEUE_NAME, async (job) => {
    const reg = loadRegistry();
    const cls = reg.classes.find((c) => c.name === job.data.className);
    if (!cls) throw new Error(`class missing at execution time: ${job.data.className}`);
    const out = await executeClass(cls);
    // Update last-run state file after execution completes.
    try {
      const stateFile = path.join(path.dirname(REGISTRY_PATH), `.state.${cls.name}.json`);
      fs.writeFileSync(stateFile, JSON.stringify({ last_run: Date.now(), last_pass: out.pass }));
    } catch (err) {
      console.error('[state-write-failed]', err.message);
    }
    return out;
  }, { connection });

  worker.on('completed', (job) => console.log(`[completed] ${job.name} result=${JSON.stringify(job.returnvalue).slice(0, 200)}`));
  worker.on('failed', (job, err) => console.error(`[failed] ${job?.name}: ${err.message}`));

  if (forcedName) {
    await forceEnqueue(queue, forcedName);
  }

  // --enqueue implies one-shot semantics (drain + exit)
  if (once || forcedName) {
    if (once) {
      const res = await pollOnce(queue);
      console.log(`[once] poll result:`, res);
    }
    // Wait for queue to drain — poll active/waiting counts
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 500));
      const counts = await queue.getJobCounts('active', 'waiting', 'delayed');
      if ((counts.active || 0) + (counts.waiting || 0) + (counts.delayed || 0) === 0) break;
    }
    await worker.close();
    await queue.close();
    await connection.quit();
    process.exit(0);
  }

  console.log(`[scheduler] daemon mode — polling every ${POLL_INTERVAL_MS}ms`);
  await pollOnce(queue);
  setInterval(async () => {
    try {
      await pollOnce(queue);
    } catch (err) {
      console.error('[poll-error]', err.message);
    }
  }, POLL_INTERVAL_MS);
}

main().catch((err) => {
  console.error('[scheduler-fatal]', err);
  process.exit(1);
});
