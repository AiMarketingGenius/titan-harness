/**
 * Einstein Fact Checker — SUMMARY OVERLAY
 *
 * Top-right floating badge that fires when the service-worker finishes an Einstein
 * verification pass on a captured AI message. Three variants per Sunday Playbook
 * Item 4b spec:
 *   GREEN  "✓ Einstein verified N claims, saved to vault"
 *   AMBER  "⚠ N claims need source"
 *   RED    "✗ X unverified — not saved"
 *
 * Works in concert with ui/einstein-warning.js (per-claim contradiction cards).
 * The summary badge is the hero-beat signal during the Monday Don Martelli demo
 * (Beat 2b); the detail cards surface individual contradictions.
 *
 * Message listened for (from service-worker):
 *   { type: 'EINSTEIN_VERIFIED_SUMMARY',
 *     verified: <int>, flagged: <int>, unverified: <int>,
 *     claims: [{ id, canonical_claim, state, badge_copy, confidence, ... }],
 *     source: 'live-check' | 'demo-mock',
 *     platform: 'claude' | 'chatgpt' | 'gemini' | 'perplexity' | ...
 *   }
 *
 * Badge state precedence (one variant shown, not stacked):
 *   unverified > 0  →  red
 *   flagged > 0     →  amber
 *   verified > 0    →  green
 */
(function () {
  'use strict';

  const WRAPPER_ID = 'mg-einstein-summary-wrapper';
  const AUTO_DISMISS_MS = 9000;

  function ensureWrapper() {
    let el = document.getElementById(WRAPPER_ID);
    if (!el) {
      el = document.createElement('div');
      el.id = WRAPPER_ID;
      el.className = 'mg-extension';
      el.style.cssText = `
        position: fixed;
        right: 24px;
        top: 24px;
        z-index: 99999;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-width: 400px;
        pointer-events: none;
      `;
      document.body.appendChild(el);
    }
    return el;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  function chooseVariant(summary) {
    if ((summary.unverified || 0) > 0) return 'red';
    if ((summary.flagged || 0) > 0) return 'amber';
    if ((summary.verified || 0) > 0) return 'green';
    return null;
  }

  function headline(summary, variant) {
    const v = summary.verified || 0;
    const f = summary.flagged || 0;
    const u = summary.unverified || 0;
    if (variant === 'red') {
      return `\u2717 ${u} unverified — not saved`;
    }
    if (variant === 'amber') {
      return `\u26A0 ${f} claim${f === 1 ? '' : 's'} need source`;
    }
    return `\u2713 Einstein verified ${v} claim${v === 1 ? '' : 's'}, saved to vault`;
  }

  function subhead(summary, variant) {
    const parts = [];
    if ((summary.verified || 0) > 0 && variant !== 'green') parts.push(`${summary.verified} verified`);
    if ((summary.flagged || 0) > 0 && variant !== 'amber') parts.push(`${summary.flagged} flagged`);
    if ((summary.unverified || 0) > 0 && variant !== 'red') parts.push(`${summary.unverified} unverified`);
    const plat = summary.platform ? ` · ${summary.platform}` : '';
    const src = summary.source === 'demo-mock' ? ' · demo-scripted' : '';
    if (parts.length === 0) return `Ready for agent retrieval${plat}${src}`;
    return `${parts.join(' · ')}${plat}${src}`;
  }

  function renderSummary(summary) {
    const variant = chooseVariant(summary);
    if (!variant) return;

    const wrapper = ensureWrapper();
    const card = document.createElement('div');
    card.className = `mg-einstein-summary mg-extension variant-${variant}`;
    card.style.cssText = `
      pointer-events: auto;
      display: flex;
      align-items: flex-start;
      gap: 14px;
      padding: 16px 18px;
      border-radius: 14px;
      box-shadow: 0 20px 60px -10px rgba(0,0,0,0.45), 0 0 0 1px var(--mg-einstein-border, rgba(38,198,168,0.3));
      background: #0F172A;
      color: #F8FAFC;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 13px;
      line-height: 1.5;
      animation: mgEinsteinSummaryIn 260ms cubic-bezier(0.16, 1, 0.3, 1);
      max-width: 400px;
    `;

    const colors = {
      green: { accent: '#26C6A8', tint: 'rgba(38, 198, 168, 0.18)', border: 'rgba(38, 198, 168, 0.45)' },
      amber: { accent: '#F3B24C', tint: 'rgba(243, 178, 76, 0.18)', border: 'rgba(243, 178, 76, 0.50)' },
      red:   { accent: '#E85960', tint: 'rgba(232, 89, 96, 0.18)', border: 'rgba(232, 89, 96, 0.50)' },
    };
    const c = colors[variant];
    card.style.setProperty('--mg-einstein-border', c.border);
    card.style.boxShadow = `0 20px 60px -10px rgba(0,0,0,0.45), 0 0 0 1px ${c.border}`;
    card.style.border = `1px solid ${c.border}`;

    const hl = headline(summary, variant);
    const sh = subhead(summary, variant);

    card.innerHTML = `
      <div style="flex:0 0 auto;width:40px;height:40px;border-radius:12px;background:${c.tint};display:flex;align-items:center;justify-content:center;color:${c.accent};font-weight:900;font-size:20px;">
        ${variant === 'green' ? '\u2713' : variant === 'amber' ? '\u26A0' : '\u2717'}
      </div>
      <div style="flex:1 1 auto;min-width:0;">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:${c.accent};margin-bottom:4px;">Einstein Fact Checker</div>
        <div style="font-size:14px;font-weight:700;line-height:1.3;color:#F1F5F9;margin-bottom:4px;">${escapeHtml(hl)}</div>
        <div style="font-size:12px;color:#94A3B8;">${escapeHtml(sh)}</div>
      </div>
      <button class="mg-einstein-summary-close" aria-label="Dismiss" style="flex:0 0 auto;background:transparent;border:0;color:#64748B;cursor:pointer;font-size:18px;line-height:1;padding:2px 4px;">\u00D7</button>
    `;

    card.querySelector('.mg-einstein-summary-close').addEventListener('click', () => card.remove());

    // Clicking the card opens the Vault Portal filtered to this platform.
    card.addEventListener('click', (e) => {
      if (e.target.closest('.mg-einstein-summary-close')) return;
      try {
        chrome.runtime.sendMessage({
          type: 'OPEN_VAULT_PORTAL',
          platform: summary.platform || null,
          filter: { source: 'einstein-summary', variant },
        }, () => { /* best-effort */ });
      } catch (_) { /* ignore */ }
    });
    card.style.cursor = 'pointer';

    wrapper.appendChild(card);
    // Auto-dismiss green variant faster; red variant stays until user acts.
    const dismissIn = variant === 'red' ? 30000 : variant === 'amber' ? 15000 : AUTO_DISMISS_MS;
    setTimeout(() => { if (card.parentElement) card.remove(); }, dismissIn);
  }

  // Inject animation keyframes once.
  if (!document.getElementById('mg-einstein-summary-style')) {
    const style = document.createElement('style');
    style.id = 'mg-einstein-summary-style';
    style.textContent = `
      @keyframes mgEinsteinSummaryIn {
        0%   { opacity: 0; transform: translateY(-14px) scale(0.97); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
      }
    `;
    document.head.appendChild(style);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message && message.type === 'EINSTEIN_VERIFIED_SUMMARY') {
      renderSummary(message);
    }
  });

  // Export for test harness + demo button wiring.
  window.__AIMEMORY_EINSTEIN_SUMMARY = { render: renderSummary };
})();
