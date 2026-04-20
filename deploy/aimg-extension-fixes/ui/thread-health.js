/**
 * Thread Health Meter — "Hallucinometer" per Doc 10 thresholds.
 *
 * Canonical zone boundaries (Chamber AI Advantage Encyclopedia v1.4.1 §22 +
 * Sunday Playbook 2026-04-19 Item 4c):
 *   🟢 FRESH   1-15
 *   🟡 WARM    16-25
 *   🟠 HOT     26-35
 *   🔴 DANGER  36+
 *
 * Two modal-style interventions tied to specific thresholds:
 *   • Depth 26 warning popup (first time hitting 26):
 *     "⚠ Thread depth 26. Hallucination risk rising. Start new thread —
 *      AMG will carry context."
 *   • Depth 36 urgent modal (first time hitting 36):
 *     "🔴 Thread depth 36. Hallucinations likely. New thread NOW."
 *
 * Both interventions include a "Start new thread" CTA + "Dismiss" button.
 * Triggered once per thread (keyed by thread_id in chrome.storage.session)
 * so re-renders of the content script on SPA nav don't re-pop.
 *
 * Upstream input: service-worker sends THREAD_HEALTH_UPDATE { exchanges }
 * per new assistant turn. Each per-platform content script (claude.js,
 * chatgpt.js, gemini.js, grok.js, perplexity.js, copilot.js) increments the
 * count and dispatches.
 */

(function () {
  'use strict';

  // Doc 10 canonical zones (v1.4.1 §22). Max display cap 40.
  const ZONES = {
    fresh:  { min: 1,  max: 15, color: 'fresh',  label: 'Fresh',  fill: 0.33 },
    warm:   { min: 16, max: 25, color: 'warm',   label: 'Warm',   fill: 0.55 },
    hot:    { min: 26, max: 35, color: 'hot',    label: 'Hot',    fill: 0.80 },
    danger: { min: 36, max: 999, color: 'danger', label: 'Danger', fill: 1.0 },
  };
  const DISPLAY_CAP = 40;
  const WARN_DEPTH = 26;
  const URGENT_DEPTH = 36;

  const ZONE_HINTS = {
    fresh:  '',
    warm:   'Thread getting long. Quality may decrease soon.',
    hot:    'Consider starting a fresh thread — AMG will carry context.',
    danger: 'Hallucinations likely. Start a new thread now.',
  };

  let meterEl = null;
  let currentExchanges = 0;
  let currentZone = 'fresh';
  let dangerAlertPlayed = false;

  function logUIEvent(event, data = {}) {
    try {
      console.log(`[AIMG UI] ${event}`, data);
      if (chrome?.runtime?.id) {
        chrome.runtime.sendMessage({ type: 'UI_EVENT', event, data }, () => {
          if (chrome.runtime.lastError) { /* best effort */ }
        });
      }
    } catch (_) { /* SPA teardown safe */ }
  }

  function getZone(count) {
    if (count <= 15) return 'fresh';
    if (count <= 25) return 'warm';
    if (count <= 35) return 'hot';
    return 'danger';
  }

  function getFillPercent(count) {
    if (count <= 15) return (count / 15) * 33;
    if (count <= 25) return 33 + ((count - 15) / 10) * 22;
    if (count <= 35) return 55 + ((count - 25) / 10) * 25;
    return Math.min(80 + ((count - 35) / 5) * 20, 100);
  }

  function currentThreadKey() {
    const p = (window.__AIMEMORY_PLATFORM || {});
    const tid = p.threadId || p.thread_id || window.location.pathname;
    return `aimg-depth-fired:${tid || 'anon'}`;
  }

  function createMeter() {
    if (meterEl) return;

    // Shared stack container — both pills live inside it so flex-column flow
    // handles the expand-without-overlap problem structurally.
    let stack = document.getElementById('mg-pill-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.id = 'mg-pill-stack';
      stack.className = 'mg-pill-stack mg-extension';
      document.body.appendChild(stack);
    }

    meterEl = document.createElement('div');
    meterEl.className = 'mg-thread-health mg-extension';
    meterEl.innerHTML = `
      <div class="mg-th-fill zone-fresh" style="height: 0%"></div>
      <div class="mg-th-content">
        <div class="mg-th-title">Hallucinometer</div>
        <div class="mg-th-zone">
          <span class="mg-th-zone-dot fresh"></span>
          <span class="mg-th-zone-name">Fresh</span>
        </div>
        <div class="mg-th-zones">
          <div class="mg-th-zone-label" data-zone="danger">🔴 Danger (36+)</div>
          <div class="mg-th-zone-label" data-zone="hot">🟠 Hot (26–35)</div>
          <div class="mg-th-zone-label" data-zone="warm">🟡 Warm (16–25)</div>
          <div class="mg-th-zone-label active" data-zone="fresh">🟢 Fresh (1–15)</div>
        </div>
        <div class="mg-th-stats">
          <div class="mg-th-stat">Exchange: <span class="mg-th-exchange-count">0</span>/${DISPLAY_CAP}</div>
          <div class="mg-th-hint"></div>
        </div>
      </div>
    `;

    stack.appendChild(meterEl);

    // Click to toggle expanded state (hover also expands via :hover CSS; click
    // locks it open on mobile / touch / when the user wants a stable read).
    meterEl.addEventListener('click', (e) => {
      if (e.target.closest('.mg-hp-btn')) return; // let popup buttons bubble normally
      meterEl.classList.toggle('expanded');
    });

    // Initialize the collapsed-pill count chip to 0/cap.
    const zoneEl = meterEl.querySelector('.mg-th-zone');
    if (zoneEl) zoneEl.setAttribute('data-count', `0/${DISPLAY_CAP}`);
  }

  function updateMeter(exchanges) {
    if (!meterEl) createMeter();

    const prevExchanges = currentExchanges;
    currentExchanges = exchanges;
    const newZone = getZone(exchanges);
    const fillPct = getFillPercent(exchanges);

    const fill = meterEl.querySelector('.mg-th-fill');
    fill.style.height = fillPct + '%';
    fill.className = 'mg-th-fill zone-' + newZone;

    const zoneDot = meterEl.querySelector('.mg-th-zone-dot');
    zoneDot.className = 'mg-th-zone-dot ' + newZone;
    meterEl.querySelector('.mg-th-zone-name').textContent = ZONES[newZone].label;
    // Collapsed-pill exchange-count chip reads the data-count attribute via CSS ::after.
    const zoneEl = meterEl.querySelector('.mg-th-zone');
    if (zoneEl) zoneEl.setAttribute('data-count', `${exchanges}/${DISPLAY_CAP}`);

    meterEl.querySelectorAll('.mg-th-zone-label').forEach((el) => {
      el.classList.toggle('active', el.dataset.zone === newZone);
    });

    meterEl.querySelector('.mg-th-exchange-count').textContent = exchanges;
    meterEl.querySelector('.mg-th-hint').textContent = ZONE_HINTS[newZone];

    if (newZone !== currentZone) {
      logUIEvent('thread_health_zone_changed', { from: currentZone, to: newZone, exchange: exchanges });
      currentZone = newZone;
    }

    if (prevExchanges < WARN_DEPTH && exchanges >= WARN_DEPTH) {
      maybeShowDepthPopup('warn');
    }
    if (prevExchanges < URGENT_DEPTH && exchanges >= URGENT_DEPTH) {
      maybeShowDepthPopup('urgent');
    }

    if (newZone === 'danger' && !dangerAlertPlayed) {
      logUIEvent('thread_health_danger_entered', { exchange: exchanges });
      dangerAlertPlayed = true;
      playDangerAlert();
    }
  }

  async function maybeShowDepthPopup(kind) {
    try {
      const key = currentThreadKey();
      const state = await new Promise((resolve) => {
        chrome.storage.session.get(key, (r) => resolve(r?.[key] || {}));
      });
      if (state[kind]) return;
      state[kind] = Date.now();
      await new Promise((resolve) => chrome.storage.session.set({ [key]: state }, resolve));
    } catch (_) {
      if (window['__aimg_depth_' + kind + '_shown']) return;
      window['__aimg_depth_' + kind + '_shown'] = true;
    }
    renderDepthPopup(kind);
    logUIEvent(kind === 'warn' ? 'hallucinometer_warn_shown' : 'hallucinometer_urgent_shown', {
      exchange: currentExchanges,
    });
  }

  function renderDepthPopup(kind) {
    const existing = document.querySelector(`.mg-hallucino-popup[data-kind="${kind}"]`);
    if (existing) return;

    const isUrgent = kind === 'urgent';
    const el = document.createElement('div');
    el.className = `mg-hallucino-popup mg-extension${isUrgent ? ' urgent' : ''}`;
    el.dataset.kind = kind;
    el.setAttribute('role', isUrgent ? 'alertdialog' : 'alert');
    el.setAttribute('aria-live', 'assertive');

    const icon = isUrgent ? '🔴' : '⚠';
    const headline = isUrgent ? 'Thread depth 36. Hallucinations likely.' : 'Thread depth 26.';
    const subhead = isUrgent
      ? 'New thread NOW.'
      : 'Hallucination risk rising. Start new thread — AMG will carry context.';
    const primaryLabel = isUrgent ? 'Start new thread now' : 'Start a new thread';

    el.innerHTML = `
      <div class="mg-hp-card">
        <div class="mg-hp-icon" aria-hidden="true">${icon}</div>
        <div class="mg-hp-headline">${headline}</div>
        <div class="mg-hp-subhead">${subhead}</div>
        <div class="mg-hp-actions">
          <button class="mg-hp-btn mg-hp-primary" type="button">${primaryLabel}</button>
          <button class="mg-hp-btn mg-hp-dismiss" type="button">Dismiss</button>
        </div>
        <div class="mg-hp-footer">AI Memory Guard · carryover: your context survives the new thread.</div>
      </div>
    `;

    document.body.appendChild(el);

    el.querySelector('.mg-hp-dismiss').addEventListener('click', () => el.remove());
    el.querySelector('.mg-hp-primary').addEventListener('click', () => {
      logUIEvent('hallucinometer_cta_new_thread', { kind, exchange: currentExchanges });
      try {
        chrome.runtime.sendMessage({
          type: 'HALLUCINOMETER_NEW_THREAD',
          kind,
          exchange: currentExchanges,
          thread_key: currentThreadKey(),
          platform: (window.__AIMEMORY_PLATFORM && window.__AIMEMORY_PLATFORM.platform) || null,
          url: window.location.href,
        }, () => { /* best-effort */ });
      } catch (_) { /* ignore */ }
      el.remove();
    });

    if (!isUrgent) setTimeout(() => { el.remove(); }, 12_000);
  }

  async function playDangerAlert() {
    try {
      const settings = await new Promise((resolve) => {
        chrome.storage.local.get('settings', (r) => resolve(r?.settings || {}));
      });
      if (settings?.soundAlert === false) return;
      await chrome.offscreen.createDocument({
        url: 'offscreen.html',
        reasons: ['AUDIO_PLAYBACK'],
        justification: 'Hallucinometer depth-36 chime',
      });
    } catch (_) { /* offscreen already open or muted */ }
  }

  function removeMeter() {
    if (meterEl) {
      meterEl.remove();
      meterEl = null;
    }
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message && message.type === 'THREAD_HEALTH_UPDATE') {
      updateMeter(message.exchanges);
    }
    if (message && message.type === 'HALLUCINOMETER_SIMULATE') {
      if (message.exchange != null) updateMeter(message.exchange);
    }
  });

  chrome.storage.local.get('settings', (result) => {
    if (result?.settings?.showThreadHealth !== false) {
      createMeter();
    }
  });

  window.__AIMEMORY_THREAD_HEALTH = {
    update: updateMeter,
    remove: removeMeter,
    getState: () => ({ exchanges: currentExchanges, zone: currentZone }),
    thresholds: { WARN_DEPTH, URGENT_DEPTH, DISPLAY_CAP, ZONES },
  };
})();
