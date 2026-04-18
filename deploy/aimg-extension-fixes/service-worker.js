/**
 * MV3 Service Worker — background processing hub
 * Receives messages from content scripts, processes extraction,
 * syncs with Supabase backend, manages Hot/Warm tier cache
 *
 * CT-0416-07 fix (2026-04-16): Memory persistence is now durable across auth gaps.
 *   - Sync failures (no token, 401, 4xx/5xx) do NOT drop memories — they go to a
 *     chrome.storage.local-backed `pending_memories` queue and drain when auth recovers.
 *   - Every sync attempt writes last_sync_at / last_sync_status / last_sync_error so the
 *     popup can show a truthful indicator instead of a silent "Connected" lie.
 *   - On 401, we trigger an immediate token refresh and retry once before queueing.
 */

const SUPABASE_URL = 'https://gaybcxzrzfgvcqpkbeiq.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdheWJjeHpyemZndmNxcGtiZWlxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0MzA4MDEsImV4cCI6MjA5MTAwNjgwMX0.1sNlNDkvJ3n6Y9ZDkxBa1c8el_2Gre6lCFdN7wMvJdA';

let hotCache = [];
const HOT_CACHE_MAX = 200;
const HOT_CACHE_TTL_MS = 72 * 60 * 60 * 1000;

let pendingExtractions = [];
const BATCH_INTERVAL_MS = 30000;

const PENDING_QUEUE_KEY = 'pending_memories';
const PENDING_QUEUE_MAX = 5000; // hard cap — beyond this, oldest entries are trimmed
const SYNC_STATUS_KEY = 'sync_status';

/**
 * Sync status shape persisted to chrome.storage.local under SYNC_STATUS_KEY.
 * The popup polls this via GET_SYNC_STATUS to render an honest indicator.
 */
const defaultSyncStatus = () => ({
  last_sync_at: null,
  last_sync_status: 'idle', // idle | success | queued | error | no_auth
  last_sync_error: null,
  last_attempted_at: null,
  pending_queue_size: 0
});

// ─── MESSAGE HANDLERS ───────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case 'PLATFORM_DETECTED':
      handlePlatformDetected(message);
      break;

    case 'THREAD_CHANGED':
      handleThreadChanged(message);
      break;

    case 'NEW_RESPONSE':
      handleNewResponse(message);
      break;

    case 'SEARCH_MEMORIES':
      handleSearch(message).then(sendResponse);
      return true;

    case 'GET_HOT_CACHE':
      sendResponse({ memories: hotCache.slice(0, 20) });
      break;

    case 'GET_STATS':
      getStats().then(sendResponse);
      return true;

    case 'GET_SYNC_STATUS':
      getSyncStatus().then(sendResponse);
      return true;

    case 'DRAIN_QUEUE_NOW':
      drainPendingQueue().then(sendResponse);
      return true;

    case 'AUTH_RESTORED':
      // Called by popup.js after a successful sign-in so queued writes can drain immediately.
      drainPendingQueue().then(sendResponse);
      return true;
  }
});

// ─── CORE HANDLERS ──────────────────────────────────────────

function handlePlatformDetected(msg) {
  console.log(`[SW] Platform: ${msg.platform}, Thread: ${msg.threadId}`);
  logSession(msg.platform, msg.threadId, msg.threadUrl);
}

function handleThreadChanged(msg) {
  console.log(`[SW] Thread changed: ${msg.threadId}`);
  logSession(msg.platform, msg.threadId, msg.threadUrl);
}

function handleNewResponse(msg) {
  console.log(`[SW] New response from ${msg.platform}, ${msg.contentLength} chars`);

  pendingExtractions.push({
    content: msg.content,
    provenance: msg.provenance,
    platform: msg.platform,
    receivedAt: Date.now()
  });

  // Demo selective-mock pass — runs FIRST, before the real Haiku call. If incoming content
  // matches a pre-scripted Chamber demo claim, the summary badge fires immediately with a
  // canned verified/flagged result. Ensures the Monday Don demo gets deterministic Einstein
  // badges on Beat 2b even if the live Haiku/Sonar round-trip stalls. Per Solon directive
  // 2026-04-18T19:58Z (selective-mock permitted on demo hero beats).
  runEinsteinDemoCheck(msg).catch(err => console.warn('[SW] Einstein demo check error:', err));

  // Einstein Fact Checker — fire-and-forget. The function self-gates on settings, auth, and
  // daily cap, so calling it on every response is safe; a no-op costs ~0ms.
  runEinsteinFactCheck(msg).catch(err => console.warn('[SW] Einstein check error:', err));
}

async function handleSearch(msg) {
  try {
    const hotResults = hotCache.filter(m =>
      m.content.toLowerCase().includes(msg.query.toLowerCase())
    ).slice(0, 5);

    const warmResults = await searchSupabase(msg.query, msg.limit || 10);

    return {
      results: [...hotResults, ...warmResults],
      source: hotResults.length > 0 ? 'hot+warm' : 'warm'
    };
  } catch (err) {
    console.error('[SW] Search error:', err);
    return { results: [], error: err.message };
  }
}

// ─── BATCH PROCESSING ───────────────────────────────────────

chrome.alarms.create('process-batch', { periodInMinutes: 0.5 });
chrome.alarms.create('evict-hot-cache', { periodInMinutes: 60 });
chrome.alarms.create('drain-pending-queue', { periodInMinutes: 5 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'process-batch') processBatch();
  if (alarm.name === 'evict-hot-cache') evictHotCache();
  if (alarm.name === 'drain-pending-queue') drainPendingQueue();
});

async function processBatch() {
  if (pendingExtractions.length === 0) return;

  const batch = pendingExtractions.splice(0, 20);
  console.log(`[SW] Processing batch of ${batch.length} responses`);

  for (const item of batch) {
    try {
      const memories = extractMemories(item.content, item.provenance);

      if (memories.length === 0) continue;

      for (const memory of memories) {
        hotCache.unshift(memory);
        if (hotCache.length > HOT_CACHE_MAX) hotCache.pop();
      }

      await syncToSupabase(memories);
      await logExtraction(item.platform, item.provenance.thread_id, memories.length);

    } catch (err) {
      console.error('[SW] Extraction error:', err);
    }
  }
}


// ─── QE CONTRADICTION DETECTION ─────────────────────────────

function detectContradictionsQE(newMemory, existingMemories) {
  const contradictions = [];
  const newTokens = tokenizeQE(newMemory.content);

  for (const existing of existingMemories) {
    // Only compare same types
    if (existing.type !== newMemory.type && existing.memory_type !== newMemory.type) continue;

    const existingContent = existing.content;
    const existingTokens = tokenizeQE(existingContent);
    const overlap = newTokens.filter(t => existingTokens.includes(t));

    if (overlap.length >= 3) {
      const similarity = overlap.length / Math.max(newTokens.length, existingTokens.length);
      if (similarity > 0.3 && similarity < 0.9) {
        contradictions.push({
          existing_memory_id: existing.id || null,
          existing_content: existingContent,
          new_content: newMemory.content,
          overlap_score: similarity,
          overlap_tokens: overlap,
          action: newMemory.type === "correction" ? "supersede" : "flag_for_review"
        });
      }
    }
  }

  return contradictions;
}

function tokenizeQE(text) {
  return text.toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .split(/\s+/)
    .filter(t => t.length > 3);
}

async function flagMemoryContradicted(memoryId, supersedingMemory, groupId) {
  if (!memoryId) return;
  const { token } = await chrome.storage.local.get("token");
  if (!token) return;

  const now = new Date().toISOString();
  const qeFlags = {
    contradicted: true,
    detected_at: now,
    related_memory_id: supersedingMemory.id || null,
    reasons: ["token_overlap_contradiction"],
    last_checked_at: now,
    checks: {
      local_memory: "fail",
      haiku_self_critique: "not_run",
      einstein_fact_check: "not_run"
    }
  };

  try {
    await fetch(`${SUPABASE_URL}/rest/v1/consumer_memories?id=eq.${memoryId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": `Bearer ${token}`,
        "Prefer": "return=minimal"
      },
      body: JSON.stringify({
        qe_status: "superseded",
        qe_flags: qeFlags,
        contradiction_group_id: groupId || null
      })
    });
    // A3: Lower older memory confidence by 0.15 (floor at 0.1)
    await fetch(`${SUPABASE_URL}/rest/v1/rpc/adjust_confidence_down`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ memory_id_param: memoryId, amount: 0.15 })
    }).catch(err => console.warn("[SW] A3: confidence adjust failed (func may not exist yet):", err));

    console.log("[SW] A2: Flagged memory", memoryId, "as contradicted, group:", groupId);
  } catch (err) {
    console.error("[SW] QE flag error:", err);
  }
}

async function updateContradictionBadge(count) {
  try {
    // Get current badge count and add
    const current = await chrome.action.getBadgeText({});
    const existing = parseInt(current) || 0;
    const total = existing + count;

    await chrome.action.setBadgeText({ text: String(total) });
    await chrome.action.setBadgeBackgroundColor({ color: "#EF4444" });

    console.log(`[SW] QE badge updated: ${total} contradictions`);
  } catch (err) {
    console.error("[SW] Badge update error:", err);
  }
}

// ─── SYNC STATUS / PENDING QUEUE ────────────────────────────

async function updateSyncStatus(patch) {
  const existing = (await chrome.storage.local.get(SYNC_STATUS_KEY))[SYNC_STATUS_KEY] || defaultSyncStatus();
  const next = { ...existing, ...patch, last_attempted_at: patch.last_attempted_at ?? new Date().toISOString() };
  await chrome.storage.local.set({ [SYNC_STATUS_KEY]: next });
  return next;
}

async function getSyncStatus() {
  const status = (await chrome.storage.local.get(SYNC_STATUS_KEY))[SYNC_STATUS_KEY] || defaultSyncStatus();
  const queue = (await chrome.storage.local.get(PENDING_QUEUE_KEY))[PENDING_QUEUE_KEY] || [];
  return { ...status, pending_queue_size: queue.length };
}

async function enqueuePending(rows, reason) {
  const existing = (await chrome.storage.local.get(PENDING_QUEUE_KEY))[PENDING_QUEUE_KEY] || [];
  const combined = existing.concat(rows);
  // Trim from the front if we exceed the cap — we'd rather lose the oldest than stop accepting new writes.
  const trimmed = combined.length > PENDING_QUEUE_MAX
    ? combined.slice(combined.length - PENDING_QUEUE_MAX)
    : combined;
  await chrome.storage.local.set({ [PENDING_QUEUE_KEY]: trimmed });
  await updateSyncStatus({
    last_sync_status: 'queued',
    last_sync_error: reason,
    pending_queue_size: trimmed.length
  });
  console.log(`[SW] Queued ${rows.length} rows (total pending: ${trimmed.length}). Reason: ${reason}`);
}

/**
 * Drain the pending queue to Supabase when auth is available.
 * Called on 5-min alarm, on AUTH_RESTORED message, and after a successful token refresh.
 */
async function drainPendingQueue() {
  const { token } = await chrome.storage.local.get('token');
  if (!token) {
    return { drained: 0, reason: 'no_auth' };
  }
  const queue = (await chrome.storage.local.get(PENDING_QUEUE_KEY))[PENDING_QUEUE_KEY] || [];
  if (queue.length === 0) {
    return { drained: 0, reason: 'empty' };
  }

  console.log(`[SW] Draining ${queue.length} queued memories...`);
  // POST in chunks of 100 to avoid PostgREST payload limits.
  const CHUNK = 100;
  let sent = 0;
  let failed = null;

  for (let i = 0; i < queue.length; i += CHUNK) {
    const chunk = queue.slice(i, i + CHUNK);
    const res = await fetch(`${SUPABASE_URL}/rest/v1/consumer_memories`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': `Bearer ${token}`,
        'Prefer': 'return=minimal'
      },
      body: JSON.stringify(chunk)
    });

    if (!res.ok) {
      failed = { status: res.status, body: await res.text() };
      // Keep the chunk (and everything after it) queued. Drop what we've already sent.
      const remaining = queue.slice(i);
      await chrome.storage.local.set({ [PENDING_QUEUE_KEY]: remaining });
      await updateSyncStatus({
        last_sync_status: 'error',
        last_sync_error: `drain_failed_${failed.status}: ${failed.body?.slice(0, 200)}`,
        pending_queue_size: remaining.length
      });
      console.error('[SW] Drain chunk failed:', failed);
      return { drained: sent, remaining: remaining.length, error: failed };
    }
    sent += chunk.length;
  }

  // All drained successfully.
  await chrome.storage.local.set({ [PENDING_QUEUE_KEY]: [] });
  await updateSyncStatus({
    last_sync_at: new Date().toISOString(),
    last_sync_status: 'success',
    last_sync_error: null,
    pending_queue_size: 0
  });
  console.log(`[SW] Drain complete: ${sent} memories synced.`);
  return { drained: sent, remaining: 0 };
}

// ─── SUPABASE SYNC ──────────────────────────────────────────

/**
 * Sync a batch of memories to Supabase.
 *
 * If auth is missing or the request fails, we do NOT silently drop — we push the
 * serialized rows onto the pending queue so the next successful auth cycle can drain them.
 * On 401, we attempt an immediate token refresh + single retry before queueing.
 */
async function syncToSupabase(memories) {
  const rows = memories.map(m => ({
    content: m.content,
    memory_type: m.type,
    confidence: m.confidence,
    platform: m.provenance.platform,
    thread_id: m.provenance.thread_id,
    thread_url: m.provenance.thread_url,
    exchange_number: m.provenance.exchange_number,
    source_timestamp: m.provenance.timestamp,
    project_id: m.provenance.project_id || null
  }));

  const { token } = await chrome.storage.local.get('token');
  if (!token) {
    console.warn('[SW] No auth token — queuing memories for later sync');
    await enqueuePending(rows, 'no_auth');
    await updateSyncStatus({ last_sync_status: 'no_auth', last_sync_error: 'not_signed_in' });
    return;
  }

  const attempt = async (bearer) => fetch(`${SUPABASE_URL}/rest/v1/consumer_memories`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': SUPABASE_ANON_KEY,
      'Authorization': `Bearer ${bearer}`,
      'Prefer': 'return=minimal'
    },
    body: JSON.stringify(rows)
  });

  try {
    let res = await attempt(token);

    if (res.status === 401) {
      // Token expired mid-session. Refresh once, retry once.
      console.warn('[SW] Sync got 401, refreshing token and retrying...');
      const refreshed = await refreshToken();
      if (refreshed) {
        const { token: newToken } = await chrome.storage.local.get('token');
        res = await attempt(newToken);
      }
    }

    if (!res.ok) {
      const body = await res.text();
      console.error('[SW] Supabase sync failed:', res.status, body);
      await enqueuePending(rows, `http_${res.status}`);
      await updateSyncStatus({
        last_sync_status: 'error',
        last_sync_error: `sync_failed_${res.status}: ${body.slice(0, 200)}`
      });
      return;
    }

    // Success. Update status + opportunistically drain any backlog.
    await updateSyncStatus({
      last_sync_at: new Date().toISOString(),
      last_sync_status: 'success',
      last_sync_error: null
    });
    // If there's a backlog from an earlier auth outage, flush it now.
    const queue = (await chrome.storage.local.get(PENDING_QUEUE_KEY))[PENDING_QUEUE_KEY] || [];
    if (queue.length > 0) drainPendingQueue();
  } catch (err) {
    console.error('[SW] Supabase sync threw:', err);
    await enqueuePending(rows, `network_error: ${err.message}`);
    await updateSyncStatus({
      last_sync_status: 'error',
      last_sync_error: `network_error: ${err.message}`
    });
  }
}

async function searchSupabase(query, limit) {
  const { token } = await chrome.storage.local.get('token');
  if (!token) return [];

  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/consumer_memories?content=ilike.*${encodeURIComponent(query)}*&order=source_timestamp.desc&limit=${limit}`,
    {
      headers: {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': `Bearer ${token}`
      }
    }
  );

  if (!res.ok) return [];
  return res.json();
}

async function logSession(platform, threadId, threadUrl) {
  const { token } = await chrome.storage.local.get('token');
  if (!token) return;

  await fetch(`${SUPABASE_URL}/rest/v1/sessions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': SUPABASE_ANON_KEY,
      'Authorization': `Bearer ${token}`,
      'Prefer': 'return=minimal'
    },
    body: JSON.stringify({
      platform,
      thread_id: threadId,
      thread_url: threadUrl,
      started_at: new Date().toISOString()
    })
  });
}

async function logExtraction(platform, threadId, memoryCount) {
  const { token } = await chrome.storage.local.get('token');
  if (!token) return;

  await fetch(`${SUPABASE_URL}/rest/v1/extraction_log`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': SUPABASE_ANON_KEY,
      'Authorization': `Bearer ${token}`,
      'Prefer': 'return=minimal'
    },
    body: JSON.stringify({
      platform,
      thread_id: threadId,
      memories_extracted: memoryCount,
      method: 'rule_based',
      extracted_at: new Date().toISOString()
    })
  });
}

async function getStats() {
  const queue = (await chrome.storage.local.get(PENDING_QUEUE_KEY))[PENDING_QUEUE_KEY] || [];
  return {
    hotCacheSize: hotCache.length,
    pendingExtractions: pendingExtractions.length,
    pendingQueueSize: queue.length,
    oldestHotMemory: hotCache.length > 0 ? hotCache[hotCache.length - 1]?.provenance?.timestamp : null,
    contradictionCount: hotCache.filter(m => m.qe_status === "contradicted").length
  };
}

async function getContradictions() {
  const contradicted = hotCache.filter(m =>
    m.contradiction_flags && m.contradiction_flags.length > 0
  );
  return { contradictions: contradicted.slice(0, 20) };
}


// --- A4: CACHE INVALIDATION ON WRITE ---

function invalidateHotCacheEntry(memoryId, updatedData) {
  const idx = hotCache.findIndex(m => m.id === memoryId);
  if (idx !== -1) {
    if (updatedData) {
      Object.assign(hotCache[idx], updatedData);
      console.log("[SW] A4: Hot cache entry updated:", memoryId);
    } else {
      hotCache.splice(idx, 1);
      console.log("[SW] A4: Hot cache entry invalidated:", memoryId);
    }
  }
}

function invalidateHotCacheByContent(content) {
  const contentPrefix = content.substring(0, 50).toLowerCase();
  const idx = hotCache.findIndex(m =>
    m.content && m.content.substring(0, 50).toLowerCase() === contentPrefix
  );
  if (idx !== -1) {
    hotCache.splice(idx, 1);
    console.log("[SW] A4: Hot cache entry invalidated by content match");
    return true;
  }
  return false;
}

// ─── HOT CACHE MANAGEMENT ───────────────────────────────────

function evictHotCache() {
  const cutoff = Date.now() - HOT_CACHE_TTL_MS;
  const before = hotCache.length;
  hotCache = hotCache.filter(m => {
    const ts = new Date(m.provenance?.timestamp || m.extracted_at).getTime();
    return ts > cutoff;
  });
  console.log(`[SW] Hot cache eviction: ${before} → ${hotCache.length}`);
}

// ─── INLINE EXTRACTOR (bundled at build) ─────────────────────

function extractMemories(text, provenance) {
  const RULES = {
    decisions: [
      /(?:I(?:'ve|'ll| will| have))?\s*(?:decided?|chosen?|going with|settled on)\s+(.{10,150})/gi,
      /(?:let(?:'s| us) go with|I(?:'m| am) going to)\s+(.{10,150})/gi
    ],
    facts: [
      /(?:I (?:am|work|live|use|prefer|have|own|manage|run))\s+(.{10,150})/gi,
      /(?:my (?:name|job|role|company|team|project) is)\s+(.{10,150})/gi
    ],
    corrections: [
      /(?:actually|correction|no,? that(?:'s| is) wrong|update:?)\s+(.{10,200})/gi
    ],
    actions: [
      /(?:TODO|TASK|ACTION|next step|I need to|remind me to)\s*:?\s*(.{10,150})/gi
    ]
  };

  const memories = [];
  const seen = new Set();

  for (const [type, patterns] of Object.entries(RULES)) {
    for (const pattern of patterns) {
      pattern.lastIndex = 0;
      let match;
      while ((match = pattern.exec(text)) !== null) {
        const extracted = match[1]?.trim();
        if (!extracted || extracted.length < 10) continue;
        const key = extracted.substring(0, 50).toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);

        memories.push({
          type: type === 'decisions' ? 'decision' :
                type === 'facts' ? 'fact' :
                type === 'corrections' ? 'correction' : 'action',
          content: extracted.replace(/[,;:]\s*$/, '').trim(),
          confidence: type === 'corrections' ? 0.9 : 0.65,
          provenance: { ...provenance },
          extracted_at: new Date().toISOString()
        });
      }
    }
  }
  return memories;
}

// ─── TOKEN REFRESH ──────────────────────────────────────────

chrome.alarms.create("refresh-token", { periodInMinutes: 45 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "refresh-token") refreshToken();
});

/**
 * Refresh the Supabase access token. Returns true on success so callers (e.g. syncToSupabase
 * on a 401) know whether retrying is viable.
 */
async function refreshToken() {
  const { refresh_token } = await chrome.storage.local.get("refresh_token");
  if (!refresh_token) return false;

  try {
    const res = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY
      },
      body: JSON.stringify({ refresh_token })
    });

    if (!res.ok) {
      console.error("[SW] Token refresh failed:", res.status);
      await updateSyncStatus({
        last_sync_status: 'no_auth',
        last_sync_error: `token_refresh_${res.status}`
      });
      return false;
    }

    const data = await res.json();
    await chrome.storage.local.set({
      token: data.access_token,
      refresh_token: data.refresh_token
    });

    console.log("[SW] Token refreshed successfully");
    // Opportunistically drain any queued writes now that we have a fresh token.
    drainPendingQueue();
    return true;
  } catch (err) {
    console.error("[SW] Token refresh error:", err);
    await updateSyncStatus({
      last_sync_status: 'error',
      last_sync_error: `token_refresh_network: ${err.message}`
    });
    return false;
  }
}

// ─── A6: QE COST MONITORING ─────────────────────────────────

const QE_METRICS = {
  contradictions_detected: 0,
  fact_checks_run: 0,
  einstein_checks_run: 0,
  embeddings_generated: 0,
  memories_stored: 0,
  avg_qe_latency_ms: 0,
  _latency_samples: 0
};

function trackQEMetric(metric, value) {
  if (metric === 'avg_qe_latency_ms') {
    QE_METRICS._latency_samples++;
    QE_METRICS.avg_qe_latency_ms =
      (QE_METRICS.avg_qe_latency_ms * (QE_METRICS._latency_samples - 1) + value) / QE_METRICS._latency_samples;
  } else {
    QE_METRICS[metric] = (QE_METRICS[metric] || 0) + (value || 1);
  }
}

function estimateDailyCost(metrics) {
  const costs = {
    haiku_per_call: 0.0003,
    einstein_per_call: 0.005,
    embedding_per_call: 0.00002,
  };
  return (
    metrics.fact_checks_run * costs.haiku_per_call +
    metrics.einstein_checks_run * costs.einstein_per_call +
    metrics.embeddings_generated * costs.embedding_per_call
  );
}

// Flush metrics daily at midnight UTC
chrome.alarms.create('flush-qe-metrics', { periodInMinutes: 1440 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'flush-qe-metrics') flushQEMetrics();
});

// ─── EINSTEIN DEMO SELECTIVE-MOCK INTERCEPTOR ───────────────
//
// Loads /einstein-demo-claims.json (bundled with the extension), tests incoming
// captured-message content against each claim's pattern_keywords + require_any gates,
// and fires EINSTEIN_VERIFIED_SUMMARY to the originating tab when matches found.
// Deterministic, no API round-trip, <10ms. Used to guarantee Monday Don demo's Beat 2b
// Einstein badge ("Einstein verified 3 claims, saved to vault") fires reliably on
// captures from the Revere Chamber page, regardless of live Haiku/Sonar latency.
// Runs in parallel with the real runEinsteinFactCheck(); both paths coexist safely.

let _einsteinDemoClaimsCache = null;

async function loadEinsteinDemoClaims() {
  if (_einsteinDemoClaimsCache) return _einsteinDemoClaimsCache;
  try {
    const url = chrome.runtime.getURL('einstein-demo-claims.json');
    const res = await fetch(url);
    if (!res.ok) return (_einsteinDemoClaimsCache = { claims: [] });
    _einsteinDemoClaimsCache = await res.json();
    return _einsteinDemoClaimsCache;
  } catch (e) {
    console.warn('[SW] loadEinsteinDemoClaims failed:', e);
    return (_einsteinDemoClaimsCache = { claims: [] });
  }
}

function _claimMatches(claim, text) {
  const lower = (text || '').toLowerCase();
  const requireAny = claim.require_any || [];
  if (requireAny.length === 0) return false;
  // Every inner group must have ≥1 keyword hit.
  for (const group of requireAny) {
    const gLower = (group || []).map(k => String(k).toLowerCase());
    const hit = gLower.some(k => lower.includes(k));
    if (!hit) return false;
  }
  return true;
}

async function runEinsteinDemoCheck(msg) {
  try {
    if (!msg?.content || msg.content.length < 20) return;
    const { settings } = await chrome.storage.local.get('settings');
    if (settings?.disableDemoMock === true) return;

    const db = await loadEinsteinDemoClaims();
    if (!db?.claims?.length) return;

    const matches = [];
    for (const claim of db.claims) {
      if (_claimMatches(claim, msg.content)) {
        matches.push(claim);
      }
    }
    if (matches.length === 0) return;

    const verified = matches.filter(c => c.state === 'verified');
    const flagged  = matches.filter(c => c.state === 'flagged');
    const unverified = matches.filter(c => c.state === 'unverified');

    // Persist demo-matched items into the hot cache so agent_context_loader / agent retrieval
    // surfaces them on the next query. Mirrors the real Einstein pipeline's vault-write
    // behavior, tagged source='einstein-demo-mock' for audit.
    const now = new Date().toISOString();
    for (const c of matches) {
      hotCache.push({
        id: `einstein-demo-${c.id}-${Date.now()}`,
        content: c.canonical_claim,
        type: 'fact',
        confidence: c.confidence || 0.85,
        verification_status: c.state,
        qe_status: c.state === 'verified' ? 'verified' : (c.state === 'flagged' ? 'flagged' : 'unverified'),
        sources: c.sources || [],
        provenance: {
          platform: msg.platform,
          thread_id: msg.provenance?.thread_id,
          captured_at: now,
          verified_by: 'einstein-demo-mock',
          demo_claim_id: c.id,
        },
      });
    }
    trackQEMetric('einstein_checks_run', 1);

    // Fire the summary badge to the originating tab.
    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      for (const tab of tabs) {
        try {
          await chrome.tabs.sendMessage(tab.id, {
            type: 'EINSTEIN_VERIFIED_SUMMARY',
            verified: verified.length,
            flagged:  flagged.length,
            unverified: unverified.length,
            claims: matches.map(c => ({
              id: c.id,
              canonical_claim: c.canonical_claim,
              state: c.state,
              badge_copy: c.badge_copy,
              confidence: c.confidence,
              flag_reason: c.flag_reason || null,
            })),
            source: 'demo-mock',
            platform: msg.platform,
          });
        } catch { /* tab may not have content script yet */ }
      }
    } catch (e) { /* ignore */ }

    console.log(`[SW] Einstein demo-mock matched ${matches.length} claim(s):`,
                matches.map(c => `${c.id}(${c.state})`).join(', '));
  } catch (err) {
    console.warn('[SW] runEinsteinDemoCheck threw:', err);
  }
}

// ─── EINSTEIN FACT CHECKER CLIENT ───────────────────────────
//
// Calls the server-side Edge Function that proxies Anthropic Haiku 4.5 and enforces
// the per-tier daily cap. We never ship the Anthropic key — that lives only on the server.
// When the server reports contradictions, we push them to the originating tab's UI.

async function runEinsteinFactCheck(msg) {
  try {
    const { token, settings } = await chrome.storage.local.get(['token', 'settings']);
    if (!token) return; // signed-out users get nothing — caps + JWT live together
    if (settings && settings.enableFactChecker === false) return;
    if (!msg?.content || msg.content.length < 40) return; // don't spend a check on one-liners

    // Build the small memory pack we send to Haiku — prefer recent + high-confidence
    // hot cache entries tagged to this thread to keep the prompt cheap.
    const relevant = hotCache
      .filter(m => (m.provenance?.thread_id === msg.provenance?.thread_id) ||
                   (m.type === 'fact' || m.type === 'decision' || m.type === 'correction'))
      .slice(0, 40)
      .map(m => ({
        id: m.id || `hot-${Math.random().toString(36).slice(2, 10)}`,
        content: m.content,
        memory_type: m.type || m.memory_type || 'fact',
        confidence: m.confidence
      }));

    // Nothing to contradict against yet → skip this call.
    if (relevant.length === 0) return;

    const res = await fetch(`${SUPABASE_URL}/functions/v1/einstein-fact-check`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'apikey': SUPABASE_ANON_KEY
      },
      body: JSON.stringify({
        response_text: msg.content,
        thread_id: msg.provenance?.thread_id,
        platform: msg.platform,
        memories: relevant
      })
    });

    if (res.status === 429) {
      // Daily cap reached. Notify the popup/content script once per day so Solon sees it.
      const body = await res.json().catch(() => ({}));
      await chrome.storage.local.set({
        einstein_last_status: {
          ok: false,
          reason: 'daily_cap_reached',
          tier: body.tier,
          cap: body.cap,
          used: body.used,
          resets_at: body.resets_at,
          at: new Date().toISOString()
        }
      });
      return;
    }
    if (!res.ok) return;

    const body = await res.json();
    trackQEMetric('einstein_checks_run', 1);

    await chrome.storage.local.set({
      einstein_last_status: {
        ok: true,
        tier: body.tier,
        remaining: body.remaining,
        cap: body.cap,
        resets_at: body.resets_at,
        contradictions: body.contradictions || [],
        at: new Date().toISOString()
      }
    });

    if (Array.isArray(body.contradictions) && body.contradictions.length > 0) {
      trackQEMetric('contradictions_detected', body.contradictions.length);
      // Push into the originating tab so the user sees the warning in-page.
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      for (const tab of tabs) {
        try {
          await chrome.tabs.sendMessage(tab.id, {
            type: 'EINSTEIN_CONTRADICTION',
            contradictions: body.contradictions,
            platform: msg.platform
          });
        } catch { /* tab may not have the content script yet — OK */ }
      }
      // Global badge stays in sync with popup expectations.
      updateContradictionBadge(body.contradictions.length);
    }
  } catch (err) {
    console.warn('[SW] Einstein fact check threw:', err);
  }
}

async function flushQEMetrics() {
  const { token } = await chrome.storage.local.get('token');
  if (!token) return;

  const estimated_cost = estimateDailyCost(QE_METRICS);
  const today = new Date().toISOString().split('T')[0];

  try {
    await fetch(`${SUPABASE_URL}/rest/v1/qe_usage_metrics`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': `Bearer ${token}`,
        'Prefer': 'resolution=merge-duplicates'
      },
      body: JSON.stringify({
        date: today,
        contradictions_detected: QE_METRICS.contradictions_detected,
        fact_checks_run: QE_METRICS.fact_checks_run,
        einstein_checks_run: QE_METRICS.einstein_checks_run,
        embeddings_generated: QE_METRICS.embeddings_generated,
        memories_stored: QE_METRICS.memories_stored,
        avg_qe_latency_ms: Math.round(QE_METRICS.avg_qe_latency_ms),
        estimated_cost_usd: Math.round(estimated_cost * 10000) / 10000
      })
    });

    console.log(`[SW] A6: QE metrics flushed. Cost: $${estimated_cost.toFixed(4)}`);

    // Reset counters
    Object.keys(QE_METRICS).forEach(k => {
      if (!k.startsWith('_')) QE_METRICS[k] = 0;
    });
    QE_METRICS._latency_samples = 0;
  } catch (err) {
    console.error('[SW] A6: Metrics flush error:', err);
  }
}
