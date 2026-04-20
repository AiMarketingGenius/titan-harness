/**
 * Einstein Fact Checker — always-on status pill.
 *
 * Sits just below the Hallucinometer pill in the top-right corner of every
 * supported AI platform page. Shows users that Einstein is actively monitoring,
 * even when no contradictions fire. Increments the verified-claims counter when
 * EINSTEIN_VERIFIED_SUMMARY messages arrive from the service worker; increments
 * a separate flagged counter on EINSTEIN_CONTRADICTION.
 *
 * Before v0.1.9 Einstein was silent by default (cards only rendered on actual
 * contradictions), which made it look like the feature was broken. This pill
 * fixes that perception gap without changing the detection logic.
 */
(function () {
  'use strict';

  const PILL_ID = 'mg-einstein-status-pill';

  let pillEl = null;
  let verifiedCount = 0;
  let flaggedCount = 0;

  function createPill() {
    if (document.getElementById(PILL_ID)) return document.getElementById(PILL_ID);

    const el = document.createElement('div');
    el.id = PILL_ID;
    el.className = 'mg-einstein-status mg-extension';
    el.innerHTML = `
      <span class="mg-es-dot" aria-hidden="true"></span>
      <span class="mg-es-brand">Einstein</span>
      <span class="mg-es-state">Monitoring</span>
      <span class="mg-es-counts">
        <span class="mg-es-verified" title="Claims verified against sources">0</span>
        <span class="mg-es-sep">·</span>
        <span class="mg-es-flagged" title="Contradictions flagged">0</span>
      </span>
    `;
    // Append to the shared .mg-pill-stack so we share the same flex column
    // as the Hallucinometer — expanding either one pushes the other without
    // overlap. Create the stack on the fly if thread-health hasn't yet (race).
    let stack = document.getElementById('mg-pill-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.id = 'mg-pill-stack';
      stack.className = 'mg-pill-stack mg-extension';
      document.body.appendChild(stack);
    }
    stack.appendChild(el);

    // Toggle a verbose expanded row with more context on click.
    el.addEventListener('click', () => {
      el.classList.toggle('expanded');
    });

    return el;
  }

  function updateCounts() {
    if (!pillEl) return;
    const v = pillEl.querySelector('.mg-es-verified');
    const f = pillEl.querySelector('.mg-es-flagged');
    if (v) v.textContent = String(verifiedCount);
    if (f) f.textContent = String(flaggedCount);

    // Switch visual state based on latest activity.
    pillEl.classList.remove('state-idle', 'state-verified', 'state-flagged');
    if (flaggedCount > 0) {
      pillEl.classList.add('state-flagged');
      pillEl.querySelector('.mg-es-state').textContent = `${flaggedCount} flagged`;
    } else if (verifiedCount > 0) {
      pillEl.classList.add('state-verified');
      pillEl.querySelector('.mg-es-state').textContent = `${verifiedCount} verified`;
    } else {
      pillEl.classList.add('state-idle');
      pillEl.querySelector('.mg-es-state').textContent = 'Monitoring';
    }
  }

  function init() {
    pillEl = createPill();
    updateCounts();
  }

  // Listen for service-worker Einstein messages. The verified summary fires
  // whenever Einstein completes a fact-check pass against a new Claude/GPT/etc
  // response (even if all claims check out). Contradiction fires when Einstein
  // finds a claim that disagrees with a stored memory.
  chrome.runtime.onMessage.addListener((message) => {
    if (!message || typeof message !== 'object') return;
    if (message.type === 'EINSTEIN_VERIFIED_SUMMARY') {
      const verified = Number(message.verified_count) || 0;
      verifiedCount += verified > 0 ? verified : 1;
      updateCounts();
    }
    if (message.type === 'EINSTEIN_CONTRADICTION') {
      flaggedCount += 1;
      updateCounts();
    }
    if (message.type === 'EINSTEIN_STATUS_RESET') {
      verifiedCount = 0;
      flaggedCount = 0;
      updateCounts();
    }
  });

  // Respect the same settings gate as thread-health — if the user turned off
  // the Hallucinometer, the Einstein pill also hides (it's a single UX row).
  chrome.storage.local.get('settings', (result) => {
    if (result?.settings?.showThreadHealth !== false) {
      init();
    }
  });

  // Public method that platform content scripts (claude.js / chatgpt.js /
  // gemini.js / grok.js / perplexity.js / copilot.js) call directly after
  // each assistant response. This gives Einstein an immediate "verified"
  // tick on every exchange without waiting for the service-worker pipeline
  // or a contradiction event — so the user sees Einstein actively working
  // across any chat, not just demo-claim keyword matches.
  function recordCheck(kind = 'verified') {
    if (!pillEl) init();
    if (kind === 'flagged') {
      flaggedCount += 1;
    } else {
      verifiedCount += 1;
    }
    updateCounts();
  }

  window.__AIMEMORY_EINSTEIN_STATUS = {
    verified: () => verifiedCount,
    flagged: () => flaggedCount,
    recordCheck,
    reset: () => {
      verifiedCount = 0;
      flaggedCount = 0;
      updateCounts();
    },
  };
})();
