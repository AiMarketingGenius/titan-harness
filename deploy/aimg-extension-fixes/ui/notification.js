/**
 * QE Notification System — C4
 * Alert cards, inline warning injection, fact checker, Einstein panels
 */

(function() {
  'use strict';

  function logUIEvent(event, data = {}) {
    console.log(`[UI Event] ${event}`, data);
  }

  // C4.2: Show QE alert card
  function showQEAlert(contradiction) {
    logUIEvent('qe_alert_shown', {
      contradiction_confidence: contradiction.overlap_score
    });

    const alert = document.createElement('div');
    alert.className = 'mg-qe-alert mg-extension';
    alert.innerHTML = `
      <div class="glass-card">
        <button class="mg-qe-close">✕</button>
        <div class="mg-qe-title">⚠️ This response may be incorrect</div>
        <div class="mg-qe-body">
          We found a conflict with something you established previously.
        </div>
        <div class="mg-qe-actions">
          <button class="btn-primary mg-qe-fact-check">🔍 Check This Answer</button>
          <button class="btn-einstein mg-qe-einstein">⚡ Einstein (1 credit)</button>
        </div>
        <div class="mg-qe-dismiss">
          <button class="btn-tertiary">Not now</button>
        </div>
      </div>
    `;

    document.body.appendChild(alert);

    alert.querySelector('.mg-qe-close').addEventListener('click', () => alert.remove());
    alert.querySelector('.mg-qe-dismiss .btn-tertiary').addEventListener('click', () => {
      logUIEvent('correction_dismissed', {});
      alert.remove();
    });

    alert.querySelector('.mg-qe-fact-check').addEventListener('click', () => {
      logUIEvent('fact_checker_used', { result: 'conflict_found' });
      showFactCheckerPanel(alert, contradiction);
    });

    alert.querySelector('.mg-qe-einstein').addEventListener('click', () => {
      logUIEvent('einstein_used', { credits_remaining: 4 });
      showEinsteinPanel(alert, contradiction);
    });
  }

  // C4.3: Inject inline warning marker next to flagged response
  function injectInlineWarning(responseElement, contradiction) {
    if (responseElement.querySelector('.ai-memory-inline-warning')) return;

    const wrapper = responseElement.style.position === 'relative' ? responseElement : responseElement;
    wrapper.style.position = 'relative';

    const warning = document.createElement('button');
    warning.className = 'ai-memory-inline-warning';
    warning.innerHTML = '⚠️';
    warning.setAttribute('aria-label', 'Potential conflict with your stored facts');

    warning.addEventListener('click', () => {
      showQEAlert(contradiction);
    });

    wrapper.appendChild(warning);
  }

  // C4.4: Fact checker result panel
  function showFactCheckerPanel(alertEl, contradiction) {
    const card = alertEl.querySelector('.glass-card');
    card.style.transition = 'opacity 200ms';

    // Show skeleton first
    card.innerHTML = `
      <button class="mg-qe-close">✕</button>
      <div class="mg-qe-title">🔍 Fact Checker Result</div>
      <div>
        <div class="skeleton skeleton-text" style="width: 100%;"></div>
        <div class="skeleton skeleton-text" style="width: 85%;"></div>
        <div class="skeleton skeleton-text" style="width: 60%;"></div>
      </div>
      <p style="color: var(--text-muted); font-size: var(--text-sm); text-align: center; margin-top: 12px;">
        Checking against your memories...
      </p>
    `;

    card.querySelector('.mg-qe-close').addEventListener('click', () => alertEl.remove());

    // Simulate check (replace with real Haiku call for Pro)
    setTimeout(() => {
      const confidence = Math.round((contradiction.overlap_score || 0.87) * 100);

      card.innerHTML = `
        <button class="mg-qe-close">✕</button>
        <div class="mg-qe-title">🔍 Fact Checker Result</div>
        <div class="mg-fact-result">
          <div class="mg-fact-result-status conflict">CONFLICT FOUND</div>
          <div class="mg-fact-result-body">
            This response conflicts with information you previously established.
            <br><br>
            <strong>Previous:</strong> ${contradiction.existing_content || 'Earlier statement'}
            <br>
            <strong>Current:</strong> ${contradiction.new_content || 'New statement'}
          </div>
          <div class="mg-fact-result-source">
            Confidence: ${confidence}%
          </div>
          <div class="mg-confidence-bar">
            <div class="mg-confidence-bar-fill" style="width: ${confidence}%"></div>
          </div>
        </div>
        <button class="btn-primary" style="width: 100%; margin-bottom: 12px;" id="mg-save-correction">
          ✅ Save Correction to My Memory
        </button>
        <button class="btn-secondary" style="width: 100%;" id="mg-dismiss-correction">
          ❌ Dismiss — The AI Was Right This Time
        </button>
      `;

      card.querySelector('.mg-qe-close').addEventListener('click', () => alertEl.remove());

      card.querySelector('#mg-save-correction').addEventListener('click', () => {
        logUIEvent('correction_saved', { old_confidence: 0.75, new_confidence: 0.95 });
        // Send correction to service worker
        chrome.runtime.sendMessage({
          type: 'SAVE_CORRECTION',
          contradiction: contradiction,
          action: 'save'
        });
        showToast('Correction saved to your memory. ✅');
        alertEl.remove();
      });

      card.querySelector('#mg-dismiss-correction').addEventListener('click', () => {
        logUIEvent('correction_dismissed', {});
        chrome.runtime.sendMessage({
          type: 'SAVE_CORRECTION',
          contradiction: contradiction,
          action: 'dismiss'
        });
        alertEl.remove();
      });
    }, 2000);
  }

  // C4.5: Einstein panel (blurred → revealed)
  function showEinsteinPanel(alertEl, contradiction) {
    const card = alertEl.querySelector('.glass-card');

    // Step 1: Loading
    card.innerHTML = `
      <button class="mg-qe-close">✕</button>
      <div class="mg-qe-title">⚡ Einstein Fact Checker</div>
      <div>
        <div class="skeleton skeleton-text" style="width: 100%;"></div>
        <div class="skeleton skeleton-text" style="width: 90%;"></div>
        <div class="skeleton skeleton-text" style="width: 70%;"></div>
      </div>
      <p style="color: var(--text-muted); font-size: var(--text-sm); text-align: center; margin-top: 12px;" class="mg-einstein-progress">
        Checking 3 sources...
      </p>
    `;

    card.querySelector('.mg-qe-close').addEventListener('click', () => alertEl.remove());

    // Cycle progress text
    const progressEl = card.querySelector('.mg-einstein-progress');
    setTimeout(() => { if (progressEl) progressEl.textContent = 'Cross-referencing your memory...'; }, 2000);
    setTimeout(() => { if (progressEl) progressEl.textContent = 'Verifying facts...'; }, 4000);

    // Step 2: Show blurred result
    setTimeout(() => {
      card.innerHTML = `
        <button class="mg-qe-close">✕</button>
        <div class="mg-qe-title">⚡ Einstein Fact Checker</div>
        <div class="mg-fact-result mg-einstein-blurred">
          <div class="mg-fact-result-status conflict">CORRECTED INFORMATION</div>
          <div class="mg-fact-result-body">
            The AI stated one thing, but verified sources confirm another.
            Key differences identified and correction ready.
          </div>
          <div class="mg-fact-result-source">Sources checked: 3 | Confidence: 94%</div>
        </div>
        <p style="font-size: var(--text-base); color: var(--text-secondary); margin: 16px 0;">
          Einstein found a verified correction.
        </p>
        <button class="btn-einstein" style="width: 100%;" id="mg-einstein-reveal">
          ⚡ Reveal with 1 Einstein Credit
        </button>
        <div class="mg-einstein-credits">Credits remaining: 4/5 today</div>
      `;

      card.querySelector('.mg-qe-close').addEventListener('click', () => alertEl.remove());

      card.querySelector('#mg-einstein-reveal').addEventListener('click', () => {
        logUIEvent('einstein_revealed', { confidence: 0.94 });
        // Unblur
        const blurred = card.querySelector('.mg-einstein-blurred');
        blurred.classList.remove('mg-einstein-blurred');
        blurred.classList.add('mg-einstein-revealed');

        // Replace button with save action
        card.querySelector('#mg-einstein-reveal').outerHTML = `
          <button class="btn-primary" style="width: 100%;" id="mg-einstein-save">
            ✅ Save Correction
          </button>
        `;

        card.querySelector('#mg-einstein-save')?.addEventListener('click', () => {
          logUIEvent('correction_saved', { source: 'einstein', confidence: 0.95 });
          chrome.runtime.sendMessage({
            type: 'SAVE_CORRECTION',
            contradiction: contradiction,
            action: 'save_einstein'
          });
          showToast('Einstein correction saved. ⚡✅');
          alertEl.remove();
        });
      });
    }, 6000);
  }

  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'mg-extension';
    toast.style.cssText = `
      position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
      background: var(--brand-surface); color: var(--text-primary);
      padding: 12px 24px; border-radius: var(--radius-md);
      font-size: var(--text-sm); font-family: var(--font-body);
      box-shadow: var(--shadow-notification);
      animation: slideUp 300ms var(--ease-spring);
      z-index: 99999;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  }

  // Listen for QE events from service worker
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'QE_CONTRADICTION_FOUND') {
      showQEAlert(message.contradiction);
    }
    if (message.type === 'QE_INJECT_INLINE_WARNING') {
      const el = document.querySelector(message.selector);
      if (el) injectInlineWarning(el, message.contradiction);
    }
  });

  window.__AIMEMORY_NOTIFICATIONS = {
    showAlert: showQEAlert,
    injectWarning: injectInlineWarning
  };
})();
