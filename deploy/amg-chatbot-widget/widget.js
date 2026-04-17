/**
 * AMG Alex Chatbot Widget — aimarketinggenius.io embedded chatbot
 * CT-0417-01 staging build (text-only; voice layer deferred to next phase)
 *
 * Integration: <script src="https://amg-cdn.example.com/widget.js" data-mode="auto"></script>
 * Backend: /api/alex/message on atlas-api (project-backed Alex via agent_context_loader)
 *
 * Design tokens match Revere brand audit style (navy + gold) with AMG-specific shifts.
 * Trade-secret compliant per plans/agents/kb/titan/01_trade_secrets.md.
 */
(function () {
  'use strict';
  if (window.__AMG_WIDGET_LOADED__) return;
  window.__AMG_WIDGET_LOADED__ = true;

  const ENDPOINT = window.AMG_CHATBOT_ENDPOINT || 'https://atlas.aimarketinggenius.io/api/alex/message';
  const RATE_LIMIT_MSGS = 20; // per session
  const STORAGE_KEY = 'amg_widget_session';

  const CSS = `
    .amg-widget-fab {
      position: fixed; right: 24px; bottom: 24px; z-index: 9999;
      width: 64px; height: 64px; border-radius: 50%;
      background: linear-gradient(135deg, #0B2572 0%, #1a3a94 100%);
      box-shadow: 0 8px 24px rgba(11,37,114,.3);
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; border: none; color: #d4a627;
      transition: transform .2s cubic-bezier(.22,1,.36,1), box-shadow .2s;
      font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .amg-widget-fab:hover { transform: translateY(-2px); box-shadow: 0 12px 32px rgba(11,37,114,.4); }
    .amg-widget-fab:focus-visible { outline: 3px solid #d4a627; outline-offset: 3px; }
    .amg-widget-fab svg { width: 28px; height: 28px; fill: currentColor; }

    .amg-widget-panel {
      position: fixed; right: 24px; bottom: 100px; z-index: 9999;
      width: 380px; max-width: calc(100vw - 32px); height: 560px; max-height: calc(100vh - 140px);
      background: #ffffff; border-radius: 16px;
      box-shadow: 0 16px 48px rgba(11,37,114,.18);
      display: none; flex-direction: column; overflow: hidden;
      font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .amg-widget-panel.open { display: flex; }
    @media (max-width: 560px) {
      .amg-widget-panel { right: 8px; left: 8px; width: auto; bottom: 88px; }
    }

    .amg-widget-header {
      background: linear-gradient(135deg, #0B2572 0%, #1a3a94 100%);
      color: #fff; padding: 20px 20px 16px;
    }
    .amg-widget-title { font-size: 17px; font-weight: 600; line-height: 1.2; }
    .amg-widget-subtitle { font-size: 13px; color: rgba(255,255,255,.78); margin-top: 3px; font-weight: 500; }
    .amg-widget-close {
      position: absolute; top: 14px; right: 14px; width: 32px; height: 32px;
      border: 0; background: transparent; color: #fff; cursor: pointer; border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
    }
    .amg-widget-close:hover { background: rgba(255,255,255,.12); }

    .amg-widget-messages {
      flex: 1; overflow-y: auto; padding: 16px 20px;
      display: flex; flex-direction: column; gap: 12px; background: #fbf9f3;
    }
    .amg-msg { max-width: 84%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45; }
    .amg-msg.user {
      align-self: flex-end; background: #0B2572; color: #fff;
      border-bottom-right-radius: 4px;
    }
    .amg-msg.agent {
      align-self: flex-start; background: #fff; color: #1c2433;
      border: 1px solid #e6e2d4; border-bottom-left-radius: 4px;
    }
    .amg-msg.typing { color: #6c7687; font-style: italic; }

    .amg-widget-form {
      border-top: 1px solid #e6e2d4; padding: 14px 16px; background: #fff;
      display: flex; gap: 8px;
    }
    .amg-widget-input {
      flex: 1; border: 1px solid #e6e2d4; border-radius: 10px;
      padding: 10px 14px; font-size: 14px; font-family: inherit;
      background: #fbf9f3; color: #1c2433;
    }
    .amg-widget-input:focus { outline: none; border-color: #0B2572; box-shadow: 0 0 0 3px rgba(11,37,114,.08); }
    .amg-widget-send {
      background: #d4a627; color: #0B2572; border: 0; border-radius: 10px;
      padding: 0 16px; font-weight: 600; font-size: 14px; cursor: pointer;
      font-family: inherit;
    }
    .amg-widget-send:hover { background: #e3b838; }
    .amg-widget-send:disabled { opacity: .5; cursor: not-allowed; }

    .amg-widget-footer {
      padding: 8px 16px; background: #fff; border-top: 1px solid #f0ecda;
      font-size: 11px; color: #6c7687; text-align: center;
    }

    @media (prefers-reduced-motion: reduce) {
      .amg-widget-fab { transition: none; }
    }
  `;

  function injectStyles() {
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function getSession() {
    try {
      const s = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');
      if (!s.id) {
        s.id = 'amg-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);
        s.count = 0;
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(s));
      }
      return s;
    } catch { return { id: 'fallback', count: 0 }; }
  }

  function saveSession(s) {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
  }

  const session = getSession();

  function buildUI() {
    // Floating action button
    const fab = document.createElement('button');
    fab.className = 'amg-widget-fab';
    fab.setAttribute('aria-label', 'Open AMG chat');
    fab.setAttribute('aria-expanded', 'false');
    fab.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C6.48 2 2 5.58 2 10c0 2.64 1.52 4.96 3.86 6.41L4 22l5.74-2.12c.72.08 1.5.12 2.26.12 5.52 0 10-3.58 10-8s-4.48-10-10-10z"/></svg>`;
    document.body.appendChild(fab);

    // Panel
    const panel = document.createElement('div');
    panel.className = 'amg-widget-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Chat with AMG');
    panel.innerHTML = `
      <div class="amg-widget-header">
        <div class="amg-widget-title">Hi, I'm Alex — your AMG strategist.</div>
        <div class="amg-widget-subtitle">Ask me about our AI marketing platform, pricing, or the Chamber program.</div>
        <button class="amg-widget-close" aria-label="Close chat">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M18.3 5.71L12 12.01l-6.3-6.3-1.4 1.4 6.3 6.3-6.3 6.3 1.4 1.4 6.3-6.3 6.3 6.3 1.4-1.4-6.3-6.3 6.3-6.3z"/></svg>
        </button>
      </div>
      <div class="amg-widget-messages" role="log" aria-live="polite"></div>
      <form class="amg-widget-form">
        <input class="amg-widget-input" type="text" placeholder="Ask Alex…" aria-label="Your message" autocomplete="off" maxlength="500" />
        <button class="amg-widget-send" type="submit">Send</button>
      </form>
      <div class="amg-widget-footer">Powered by AMG · responses in-platform only</div>
    `;
    document.body.appendChild(panel);

    const msgs = panel.querySelector('.amg-widget-messages');
    const form = panel.querySelector('.amg-widget-form');
    const input = panel.querySelector('.amg-widget-input');
    const send = panel.querySelector('.amg-widget-send');
    const closeBtn = panel.querySelector('.amg-widget-close');

    function openPanel() {
      panel.classList.add('open');
      fab.setAttribute('aria-expanded', 'true');
      setTimeout(() => input.focus(), 100);
      // Greeting on first open
      if (!msgs.querySelector('.amg-msg')) {
        addAgent("Hi, I'm Alex. Ask me anything about AMG's AI marketing platform — pricing, the Chamber program, how it works. I can also route you to the right agent in our seven-agent team when you need something specific.");
      }
    }
    function closePanel() {
      panel.classList.remove('open');
      fab.setAttribute('aria-expanded', 'false');
      fab.focus();
    }
    function addAgent(text) {
      const el = document.createElement('div');
      el.className = 'amg-msg agent';
      el.textContent = text;
      msgs.appendChild(el);
      msgs.scrollTop = msgs.scrollHeight;
    }
    function addUser(text) {
      const el = document.createElement('div');
      el.className = 'amg-msg user';
      el.textContent = text;
      msgs.appendChild(el);
      msgs.scrollTop = msgs.scrollHeight;
    }
    function addTyping() {
      const el = document.createElement('div');
      el.className = 'amg-msg agent typing';
      el.textContent = 'Alex is typing…';
      msgs.appendChild(el);
      msgs.scrollTop = msgs.scrollHeight;
      return el;
    }

    fab.addEventListener('click', () => panel.classList.contains('open') ? closePanel() : openPanel());
    closeBtn.addEventListener('click', closePanel);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && panel.classList.contains('open')) closePanel(); });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      if (session.count >= RATE_LIMIT_MSGS) {
        addAgent("You've hit the rate limit for this session. Want me to connect you with our team directly? Email solon@aimarketinggenius.io");
        return;
      }
      session.count++; saveSession(session);
      addUser(text);
      input.value = '';
      send.disabled = true;
      const typing = addTyping();
      try {
        const res = await fetch(ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, session_id: session.id, agent: 'alex', client_id: null }),
        });
        typing.remove();
        if (!res.ok) {
          addAgent("Something hiccuped on our end. Try again, or email solon@aimarketinggenius.io.");
        } else {
          const data = await res.json();
          addAgent(data.reply || "Thanks — I'll circle back.");
        }
      } catch (err) {
        typing.remove();
        addAgent("Can't reach our server right now. Try again in a moment, or email solon@aimarketinggenius.io.");
      } finally {
        send.disabled = false;
        input.focus();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { injectStyles(); buildUI(); });
  } else {
    injectStyles(); buildUI();
  }
})();
