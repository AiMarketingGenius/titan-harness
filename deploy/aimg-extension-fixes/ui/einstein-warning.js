/**
 * Einstein Fact Checker — content script UI
 *
 * Listens for EINSTEIN_CONTRADICTION messages from the service worker and renders a
 * dismissible badge in the bottom-right corner of the AI platform page. Each contradiction
 * shows the conflicting claim, the original memory it contradicts, and a "Got it" dismissal.
 *
 * Visual language matches the site mockup (pink accent = Einstein Fact Checker) so the
 * in-page alert and the website hero feel like the same product.
 */
(function() {
  'use strict';

  const WRAPPER_ID = 'mg-einstein-warning-wrapper';

  function ensureWrapper() {
    let el = document.getElementById(WRAPPER_ID);
    if (!el) {
      el = document.createElement('div');
      el.id = WRAPPER_ID;
      el.className = 'mg-extension';
      el.style.cssText = `
        position: fixed;
        right: 24px;
        bottom: 24px;
        z-index: 99999;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-width: 360px;
        pointer-events: none;
      `;
      document.body.appendChild(el);
    }
    return el;
  }

  function renderContradiction(contradiction) {
    const wrapper = ensureWrapper();
    const card = document.createElement('div');
    card.className = 'mg-einstein-card mg-extension';
    card.style.cssText = `
      pointer-events: auto;
      background: #111827;
      border: 1px solid rgba(236, 72, 153, 0.45);
      box-shadow: 0 18px 60px -20px rgba(236, 72, 153, 0.45), 0 0 0 1px rgba(236, 72, 153, 0.15);
      border-radius: 14px;
      padding: 16px 18px;
      color: #f1f5f9;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 13px;
      line-height: 1.55;
      animation: mgEinsteinIn 240ms cubic-bezier(0.16, 1, 0.3, 1);
    `;

    const confidence = typeof contradiction.confidence === 'number'
      ? Math.round(contradiction.confidence * 100) + '%'
      : '—';

    card.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;background:rgba(236,72,153,0.18);color:#ec4899;font-weight:700;font-size:12px;">!</span>
        <span style="font-weight:700;letter-spacing:0.6px;text-transform:uppercase;font-size:11px;color:#ec4899;">Einstein Fact Check</span>
        <span style="margin-left:auto;font-size:10px;color:#94a3b8;">${confidence} confidence</span>
      </div>
      <div style="margin-bottom:10px;">
        <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:#94a3b8;margin-bottom:4px;">Conflicting claim</div>
        <div style="color:#fecaca;">${escapeHtml(contradiction.conflicting_claim || '(no excerpt)')}</div>
      </div>
      <div style="padding:10px 12px;border-radius:10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);">
        <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:#94a3b8;margin-bottom:4px;">Your memory</div>
        <div style="color:#cbd5f5;">${escapeHtml(contradiction.memory_content || '(unknown)')}</div>
      </div>
      ${contradiction.explanation ? `
        <div style="margin-top:10px;font-size:12px;color:#94a3b8;">${escapeHtml(contradiction.explanation)}</div>
      ` : ''}
      <div style="display:flex;gap:8px;margin-top:12px;">
        <button class="mg-einstein-dismiss" style="flex:1;background:#1a2234;border:1px solid #334155;color:#e2e8f0;border-radius:8px;padding:8px 10px;font-size:12px;font-weight:600;cursor:pointer;">Got it</button>
        <button class="mg-einstein-remember" style="flex:1;background:rgba(236,72,153,0.15);border:1px solid rgba(236,72,153,0.4);color:#fbcfe8;border-radius:8px;padding:8px 10px;font-size:12px;font-weight:600;cursor:pointer;">Trust the memory</button>
      </div>
    `;

    card.querySelector('.mg-einstein-dismiss').addEventListener('click', () => card.remove());
    card.querySelector('.mg-einstein-remember').addEventListener('click', () => {
      // Future: reinforce the memory confidence. For now, just dismiss.
      card.remove();
    });

    wrapper.appendChild(card);

    // Auto-dismiss after 30s if user ignores.
    setTimeout(() => { if (card.parentElement) card.remove(); }, 30000);
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  // Keyframes can't be inlined — inject once.
  if (!document.getElementById('mg-einstein-style')) {
    const style = document.createElement('style');
    style.id = 'mg-einstein-style';
    style.textContent = `
      @keyframes mgEinsteinIn {
        0% { opacity: 0; transform: translateY(20px) scale(0.96); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
      }
    `;
    document.head.appendChild(style);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type !== 'EINSTEIN_CONTRADICTION') return;
    const list = Array.isArray(message.contradictions) ? message.contradictions : [];
    for (const c of list.slice(0, 3)) renderContradiction(c);
  });
})();
