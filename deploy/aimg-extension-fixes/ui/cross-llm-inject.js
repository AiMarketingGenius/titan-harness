/**
 * Cross-LLM Context Injection — content-script module.
 *
 * Fires a floating "Inject vault context?" offer card whenever the user starts
 * a NEW thread on any of the 4 supported AI platforms:
 *   • claude.ai — URL /new or no thread UUID
 *   • chatgpt.com — URL / or /?... with no conversation UUID
 *   • perplexity.ai — URL / or / homepage
 *   • gemini.google.com — URL /app with no chat hash
 * (grok + copilot also supported via same logic.)
 *
 * If the user accepts, a concise markdown context block is written into the
 * platform's input box — pre-prompt, pre-send — so the AI starts the new thread
 * with Revere Chamber / AMG context already loaded. Works independently on each
 * platform; the same vault source-of-truth populates all four.
 *
 * Source of truth for "relevant context":
 *   1. chrome.runtime.sendMessage({ type: 'CROSS_LLM_INJECT_CANDIDATES', platform, url })
 *      — service-worker returns top N memories scoped to the current tenant / project.
 *   2. Fallback: if the service-worker can't respond in <400ms, use a bundled demo
 *      context block (einstein-demo-claims canonical_claim fields) so the Monday
 *      demo doesn't depend on Supabase round-trip latency.
 *
 * UX:
 *   • Card appears bottom-center ~1.5s after new-thread detected (not immediately —
 *     the user needs a beat to see the empty input first).
 *   • Two buttons: "Inject 3 items" (primary green) / "Not now" (ghost).
 *   • Auto-dismisses after 20s untouched.
 *   • Respects user preference: chrome.storage.local.settings.crossLlmInject=false disables.
 *   • Fires once per thread — re-entering same empty-thread URL doesn't re-pop.
 */

(function () {
  'use strict';

  const OFFER_DELAY_MS = 1500;
  const AUTO_DISMISS_MS = 20000;
  const SW_RESPONSE_TIMEOUT_MS = 400;

  const PLATFORM_CONFIG = {
    claude: {
      isNewThreadUrl: (u) => /claude\.ai\/(new|\/?$)/.test(u) || !/\/chat\/[a-f0-9-]{36}/i.test(u),
      inputSelectors: ['div[contenteditable="true"]', 'textarea'],
      displayName: 'Claude',
    },
    chatgpt: {
      isNewThreadUrl: (u) => !/chatgpt\.com\/c\/[a-f0-9-]{36}/i.test(u) && !/chat\.openai\.com\/(c|chat)\/[a-f0-9-]{36}/i.test(u),
      inputSelectors: ['#prompt-textarea', 'textarea'],
      displayName: 'ChatGPT',
    },
    gemini: {
      isNewThreadUrl: (u) => /gemini\.google\.com\/app\/?$/.test(u) || !/gemini\.google\.com\/app\/[a-f0-9]+/i.test(u),
      inputSelectors: ['.ql-editor[contenteditable="true"]', 'rich-textarea [contenteditable="true"]', 'textarea'],
      displayName: 'Gemini',
    },
    perplexity: {
      isNewThreadUrl: (u) => /perplexity\.ai\/?(?:\?.*)?$/.test(u) || !/perplexity\.ai\/search\//i.test(u),
      inputSelectors: ['textarea[placeholder*="Ask"]', 'textarea', 'div[contenteditable="true"]'],
      displayName: 'Perplexity',
    },
    grok: {
      isNewThreadUrl: (u) => /grok\.com\/?$/.test(u) || !/grok\.com\/chat\//i.test(u),
      inputSelectors: ['textarea', 'div[contenteditable="true"]'],
      displayName: 'Grok',
    },
    copilot: {
      isNewThreadUrl: (u) => /copilot\.microsoft\.com\/?$/.test(u),
      inputSelectors: ['textarea', 'div[contenteditable="true"]'],
      displayName: 'Copilot',
    },
  };

  function getPlatform() {
    const p = window.__AIMEMORY_PLATFORM;
    return p?.platform || null;
  }

  function currentThreadKey() {
    return `aimg-inject-offered:${window.location.pathname}`;
  }

  async function alreadyOfferedThisThread() {
    try {
      const key = currentThreadKey();
      const r = await new Promise((resolve) => chrome.storage.session.get(key, resolve));
      return !!r?.[key];
    } catch (_) { return false; }
  }

  async function markOfferedThisThread() {
    try {
      const key = currentThreadKey();
      await new Promise((resolve) => chrome.storage.session.set({ [key]: Date.now() }, resolve));
    } catch (_) { /* best-effort */ }
  }

  async function loadDemoContextFallback() {
    try {
      const url = chrome.runtime.getURL('einstein-demo-claims.json');
      const res = await fetch(url);
      if (!res.ok) return [];
      const data = await res.json();
      return (data.claims || [])
        .filter((c) => c.state === 'verified')
        .slice(0, 3)
        .map((c) => ({
          id: c.id,
          content: c.canonical_claim,
          type: 'fact',
          confidence: c.confidence,
          badge_copy: c.badge_copy,
          sources: c.sources || [],
        }));
    } catch (_) {
      return [];
    }
  }

  async function requestCandidates(platform) {
    return new Promise((resolve) => {
      let done = false;
      const timeout = setTimeout(() => { if (!done) { done = true; resolve(null); } }, SW_RESPONSE_TIMEOUT_MS);
      try {
        chrome.runtime.sendMessage(
          { type: 'CROSS_LLM_INJECT_CANDIDATES', platform, url: window.location.href },
          (resp) => {
            if (done) return;
            done = true;
            clearTimeout(timeout);
            resolve(resp?.candidates || null);
          }
        );
      } catch (_) {
        clearTimeout(timeout);
        if (!done) { done = true; resolve(null); }
      }
    });
  }

  function buildInjectionBlock(items, platformName) {
    const lines = [];
    lines.push(`**Context from my AI Memory Guard vault (verified across ${platformName}):**`);
    lines.push('');
    items.forEach((it, i) => {
      lines.push(`${i + 1}. ${it.content}`);
      if (it.sources && it.sources.length > 0 && it.sources[0].title) {
        lines.push(`   _source: ${it.sources[0].title}_`);
      }
    });
    lines.push('');
    lines.push('Please use the context above as background — reply as if you already knew it.');
    lines.push('');
    lines.push('---');
    lines.push('');
    return lines.join('\n');
  }

  async function injectIntoInput(text, cfg) {
    for (const sel of cfg.inputSelectors) {
      const el = document.querySelector(sel);
      if (!el) continue;
      try {
        if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
          const proto = Object.getPrototypeOf(el);
          const descr = Object.getOwnPropertyDescriptor(proto, 'value');
          if (descr && descr.set) {
            descr.set.call(el, text + (el.value || ''));
          } else {
            el.value = text + (el.value || '');
          }
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.focus();
        } else if (el.isContentEditable) {
          // contenteditable — insert text as plain first, preserving any existing user input after.
          const existing = el.innerText || '';
          el.focus();
          // Use document.execCommand insertText for contenteditable (broadly supported, triggers native events)
          document.execCommand('selectAll', false, null);
          document.execCommand('delete', false, null);
          document.execCommand('insertText', false, text + existing);
          el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText' }));
        } else {
          continue;
        }
        return true;
      } catch (e) {
        console.warn('[AIMG] injectIntoInput failed on selector', sel, e);
      }
    }
    return false;
  }

  function renderOfferCard(items, cfg) {
    const existing = document.querySelector('.mg-inject-offer');
    if (existing) return;

    const el = document.createElement('div');
    el.className = 'mg-inject-offer mg-extension';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-live', 'polite');

    const previewLines = items.slice(0, 3).map((it, i) => {
      const badge = it.badge_copy || it.content.slice(0, 72) + (it.content.length > 72 ? '…' : '');
      return `<li>${i + 1}. ${escapeHtml(badge)}</li>`;
    }).join('');

    el.innerHTML = `
      <div class="mg-inject-card">
        <div class="mg-inject-header">
          <span class="mg-inject-eyebrow">AI Memory Guard</span>
          <button class="mg-inject-dismiss" aria-label="Dismiss">×</button>
        </div>
        <div class="mg-inject-headline">Inject ${items.length} verified context item${items.length === 1 ? '' : 's'} into this new ${cfg.displayName} thread?</div>
        <ul class="mg-inject-preview">${previewLines}</ul>
        <div class="mg-inject-body">Your vault carries over. Start this new thread with the context you already captured.</div>
        <div class="mg-inject-actions">
          <button class="mg-inject-btn mg-inject-primary" type="button">Inject ${items.length} item${items.length === 1 ? '' : 's'}</button>
          <button class="mg-inject-btn mg-inject-ghost" type="button">Not now</button>
        </div>
      </div>
    `;

    document.body.appendChild(el);

    const close = () => { if (el.parentElement) el.remove(); };
    el.querySelector('.mg-inject-dismiss').addEventListener('click', close);
    el.querySelector('.mg-inject-ghost').addEventListener('click', close);
    el.querySelector('.mg-inject-primary').addEventListener('click', async () => {
      const text = buildInjectionBlock(items, cfg.displayName);
      const ok = await injectIntoInput(text, cfg);
      try {
        chrome.runtime.sendMessage({
          type: 'CROSS_LLM_CONTEXT_INJECTED',
          platform: getPlatform(),
          url: window.location.href,
          count: items.length,
          item_ids: items.map((i) => i.id),
          ok,
        }, () => { /* best-effort */ });
      } catch (_) { /* ignore */ }
      close();
    });

    setTimeout(close, AUTO_DISMISS_MS);
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  async function maybeOffer() {
    try {
      const platform = getPlatform();
      if (!platform || !PLATFORM_CONFIG[platform]) return;
      const cfg = PLATFORM_CONFIG[platform];
      if (!cfg.isNewThreadUrl(window.location.href)) return;
      const { settings } = await new Promise((resolve) => chrome.storage.local.get('settings', resolve));
      if (settings?.crossLlmInject === false) return;
      if (await alreadyOfferedThisThread()) return;

      // Try service-worker first, fall back to bundled demo claims.
      let items = await requestCandidates(platform);
      if (!items || items.length === 0) items = await loadDemoContextFallback();
      if (!items || items.length === 0) return;

      await markOfferedThisThread();
      // Small delay so the user sees the empty thread for a beat before the offer appears.
      setTimeout(() => renderOfferCard(items, cfg), OFFER_DELAY_MS);
    } catch (e) {
      console.warn('[AIMG] cross-llm-inject maybeOffer failed:', e);
    }
  }

  // Inject base CSS once.
  if (!document.getElementById('mg-inject-style')) {
    const style = document.createElement('style');
    style.id = 'mg-inject-style';
    style.textContent = `
      .mg-inject-offer {
        position: fixed;
        left: 50%;
        bottom: 32px;
        transform: translateX(-50%);
        z-index: 99998;
        max-width: 460px;
        width: calc(100vw - 48px);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        animation: mgInjectIn 280ms cubic-bezier(0.16, 1, 0.3, 1);
      }
      .mg-inject-card {
        background: #0F172A;
        border: 1px solid rgba(38, 198, 168, 0.45);
        box-shadow: 0 24px 64px -12px rgba(38, 198, 168, 0.35), 0 0 0 1px rgba(38, 198, 168, 0.18);
        border-radius: 16px;
        padding: 18px 20px 16px;
        color: #F8FAFC;
      }
      .mg-inject-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
      .mg-inject-eyebrow { font-size: 11px; font-weight: 800; letter-spacing: 1.6px; text-transform: uppercase; color: #26C6A8; }
      .mg-inject-dismiss { background: transparent; border: 0; color: #64748B; font-size: 20px; line-height: 1; cursor: pointer; padding: 0 4px; }
      .mg-inject-dismiss:hover { color: #F1F5F9; }
      .mg-inject-headline { font-size: 15px; font-weight: 700; line-height: 1.4; color: #F1F5F9; margin-bottom: 10px; }
      .mg-inject-preview { list-style: none; padding: 0; margin: 0 0 10px 0; }
      .mg-inject-preview li { padding: 6px 10px; margin-bottom: 4px; background: rgba(38, 198, 168, 0.08); border-radius: 8px; font-size: 12.5px; color: #CBD5F5; line-height: 1.4; }
      .mg-inject-body { font-size: 12.5px; color: #94A3B8; line-height: 1.5; margin-bottom: 14px; }
      .mg-inject-actions { display: flex; gap: 8px; }
      .mg-inject-btn { flex: 1; border-radius: 10px; padding: 9px 12px; font-size: 13px; font-weight: 700; cursor: pointer; transition: transform 120ms ease, background 120ms ease; border: 1px solid rgba(148, 163, 184, 0.25); }
      .mg-inject-btn:hover { transform: translateY(-1px); }
      .mg-inject-primary { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); color: #F0FDF4; border-color: rgba(34, 197, 94, 0.55); }
      .mg-inject-ghost { background: #1A2234; color: #E2E8F0; }
      @keyframes mgInjectIn { from { opacity: 0; transform: translateX(-50%) translateY(16px) scale(0.97); } to { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); } }
    `;
    document.head.appendChild(style);
  }

  // Fire on initial load + on SPA navigation (pushState + popstate).
  let lastPath = window.location.pathname;
  function onNavigate() {
    const now = window.location.pathname;
    if (now === lastPath) return;
    lastPath = now;
    maybeOffer();
  }

  window.addEventListener('popstate', onNavigate);
  const origPush = history.pushState;
  const origReplace = history.replaceState;
  history.pushState = function () {
    const r = origPush.apply(this, arguments);
    setTimeout(onNavigate, 100);
    return r;
  };
  history.replaceState = function () {
    const r = origReplace.apply(this, arguments);
    setTimeout(onNavigate, 100);
    return r;
  };

  // Initial probe (platform-detector loads before this, so __AIMEMORY_PLATFORM should be set).
  // Small delay to let platform-detector.js + the platform-specific capture script initialize.
  setTimeout(maybeOffer, 1200);

  window.__AIMEMORY_CROSS_LLM_INJECT = {
    offer: maybeOffer,
    buildInjectionBlock,
  };
})();
