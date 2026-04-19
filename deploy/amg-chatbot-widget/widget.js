/**
 * AMG Alex Chatbot Widget — v2.0 elite-tier rebuild (CT-0419-05 Lane E)
 *
 * First Lumina-v2.0-executed artifact. Built under the execution authority
 * framework in plans/agents/kb/lumina/11_execution_authority.md — elite
 * visual standard + rich content components + progressive SSE-ready
 * architecture + proactive page-context greeting + intent routing hints.
 * Rolls in Item 4 polish (fair rate-limit + AbortController timeout) from
 * the Sunday runway work.
 *
 * Integration: <script src="https://amg-cdn.aimarketinggenius.io/widget.js" defer></script>
 * Backend: /api/alex/message on atlas-api (project-backed Alex via
 *          agent_context_loader). SSE-capable path is /api/alex/stream (forward-
 *          compatible; widget falls back to POST JSON if SSE not reachable).
 *
 * Design tokens aligned with AMG live-site tokens — elite SaaS launch-
 * page aesthetic tier. Navy #131825 base + cyan #00A6FF accent + green
 * #10B77F CTA + DM Sans (display) + Inter fallback.
 *
 * Trade-secret compliant per plans/agents/kb/titan/01_trade_secrets.md.
 * No underlying-vendor names exposed in UI or outgoing payloads.
 */
(function () {
  'use strict';
  if (window.__AMG_WIDGET_LOADED__) return;
  window.__AMG_WIDGET_LOADED__ = true;

  const ENDPOINT = window.AMG_CHATBOT_ENDPOINT || 'https://atlas.aimarketinggenius.io/api/alex/message';
  const STREAM_ENDPOINT = window.AMG_CHATBOT_STREAM_ENDPOINT || ENDPOINT.replace(/\/message$/, '/stream');
  const RATE_LIMIT_MSGS = 20;
  const STORAGE_KEY = 'amg_widget_session';
  const FETCH_TIMEOUT_MS = 20000;
  const STREAM_FIRST_CHUNK_TIMEOUT_MS = 3500;

  // Intent keywords for client-side routing hint. Server is authoritative;
  // these are hints only and fall through to Alex by default.
  const INTENT_HINTS = [
    { pattern: /\b(seo|content|blog|keyword|rank|google)\b/i, agent: 'alex' },
    { pattern: /\b(chamber|outbound|member|partnership|revere)\b/i, agent: 'maya' },
    { pattern: /\b(review|reputation|yelp|glassdoor|star)\b/i, agent: 'sam' },
    { pattern: /\b(nurture|onboard|email|drip)\b/i, agent: 'nadia' },
    { pattern: /\b(voice|orb|call|phone)\b/i, agent: 'alex' },
    { pattern: /\b(social|instagram|linkedin|facebook|twitter)\b/i, agent: 'jordan' },
    { pattern: /\b(price|pricing|cost|how much|plan|tier)\b/i, agent: 'alex' },
  ];

  // Proactive page-context greeting map. First URL match wins.
  const PAGE_CONTEXT_GREETINGS = [
    { test: /\/pricing/i,        greeting: "Saw you're exploring pricing. Want the short version — Atlas Lite through Enterprise, $995 to $10K/mo, with our Chamber-founder rate if you're from a partner chamber?" },
    { test: /\/chamber/i,        greeting: "Chamber partnership curious? Happy to walk you through the revenue share + how founding partners get their first month at 50% off." },
    { test: /\/case-stud|case_stud|clients/i, greeting: "Looking at case studies? I can pull the specific results from Shop UNIS, Paradise Park, or Revel & Roll if you name the vertical." },
    { test: /\/faq|faq\.html/i,  greeting: "Common questions — ask anything about how the platform works, onboarding timelines, or why we guarantee satisfaction." },
    { test: /\/about/i,          greeting: "Want the AMG story? Or skip to the specifics — pricing, Chamber program, seven-agent team, any of it." },
    { test: /aimemoryguard\.com/i, greeting: "Curious about AI Memory Guard? I can walk you through Thread Health, Einstein Fact Checker, and why it works across five LLMs." },
    { test: /.*/, greeting: "Hey — I'm Alex, AMG's lead strategist. Ask me anything: pricing, the Chamber program, how our seven-agent team works together. I'll route you to the right specialist if you need depth." },
  ];

  // ────────────────────────────────────────────────────────────────────
  // STYLES — Lumina v2 elite-tier specs
  // Navy base + cyan accent + green CTA, DM Sans display, Inter fallback.
  // Layered shadows, refined focus rings, cubic-bezier easing throughout.
  // ────────────────────────────────────────────────────────────────────

  const CSS = `
    .amg-widget-fab {
      position: fixed; right: 24px; bottom: 24px; z-index: 9999;
      width: 64px; height: 64px; border-radius: 50%;
      background:
        radial-gradient(120% 120% at 30% 20%, rgba(0,166,255,.25) 0%, transparent 55%),
        linear-gradient(135deg, #131825 0%, #1A2033 100%);
      box-shadow:
        0 1px 0 rgba(255,255,255,.06) inset,
        0 8px 24px rgba(0,0,0,.45),
        0 2px 6px rgba(0,166,255,.15);
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; border: none; color: #00A6FF;
      transition:
        transform .22s cubic-bezier(.22,1,.36,1),
        box-shadow .22s cubic-bezier(.22,1,.36,1);
      font-family: "DM Sans", "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }
    .amg-widget-fab:hover {
      transform: translateY(-3px);
      box-shadow:
        0 1px 0 rgba(255,255,255,.08) inset,
        0 14px 36px rgba(0,0,0,.55),
        0 4px 12px rgba(0,166,255,.32);
    }
    .amg-widget-fab:focus-visible {
      outline: 2px solid #00A6FF; outline-offset: 3px;
    }
    .amg-widget-fab svg { width: 28px; height: 28px; fill: currentColor; }
    .amg-widget-fab-pulse {
      position: absolute; inset: -2px; border-radius: 50%;
      border: 2px solid #00A6FF;
      opacity: 0; pointer-events: none;
      animation: amg-fab-pulse 2.8s cubic-bezier(.22,1,.36,1) infinite;
    }
    @keyframes amg-fab-pulse {
      0%   { opacity: .55; transform: scale(1);   }
      70%  { opacity: 0;   transform: scale(1.45);}
      100% { opacity: 0;   transform: scale(1.45);}
    }

    .amg-widget-panel {
      position: fixed; right: 24px; bottom: 100px; z-index: 9999;
      width: 400px; max-width: calc(100vw - 32px);
      height: 620px; max-height: calc(100vh - 140px);
      background: #0F172A;
      border-radius: 18px;
      box-shadow:
        0 1px 0 rgba(255,255,255,.04) inset,
        0 24px 64px rgba(0,0,0,.65),
        0 4px 12px rgba(0,0,0,.35);
      display: none; flex-direction: column; overflow: hidden;
      font-family: "DM Sans", "Inter", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
      color: #F5F7FB;
      transform: translateY(8px) scale(.98);
      opacity: 0;
      transition:
        transform .28s cubic-bezier(.22,1,.36,1),
        opacity .22s cubic-bezier(.22,1,.36,1);
    }
    .amg-widget-panel.open {
      display: flex;
      transform: translateY(0) scale(1);
      opacity: 1;
    }
    @media (max-width: 560px) {
      .amg-widget-panel { right: 8px; left: 8px; width: auto; bottom: 88px; height: calc(100vh - 104px); }
    }

    .amg-widget-header {
      background:
        radial-gradient(140% 120% at 10% -10%, rgba(0,166,255,.22) 0%, transparent 55%),
        linear-gradient(180deg, #131825 0%, #1A2033 100%);
      color: #fff; padding: 22px 22px 18px;
      border-bottom: 1px solid rgba(255,255,255,.06);
      position: relative;
    }
    .amg-widget-title {
      font-size: 18px; font-weight: 600; line-height: 1.25;
      letter-spacing: -0.01em;
      color: #FFFFFF;
    }
    .amg-widget-subtitle {
      font-size: 13px; color: #9AA4B8;
      margin-top: 4px; font-weight: 500;
      line-height: 1.45;
    }
    .amg-widget-status {
      display: inline-flex; align-items: center; gap: 6px;
      margin-top: 10px;
      font-size: 11px; letter-spacing: .04em;
      color: #10B77F; font-weight: 600; text-transform: uppercase;
    }
    .amg-widget-status-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: #10B77F;
      box-shadow: 0 0 0 3px rgba(16,183,127,.18);
      animation: amg-status-pulse 2.4s cubic-bezier(.22,1,.36,1) infinite;
    }
    @keyframes amg-status-pulse {
      0%,100% { box-shadow: 0 0 0 3px rgba(16,183,127,.18); }
      50%     { box-shadow: 0 0 0 6px rgba(16,183,127,.04); }
    }
    .amg-widget-close {
      position: absolute; top: 14px; right: 14px;
      width: 34px; height: 34px;
      border: 0; background: rgba(255,255,255,.04);
      color: #C5CDD8; cursor: pointer; border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      transition: background .18s cubic-bezier(.22,1,.36,1), color .18s cubic-bezier(.22,1,.36,1);
    }
    .amg-widget-close:hover { background: rgba(255,255,255,.10); color: #FFFFFF; }
    .amg-widget-close:focus-visible { outline: 2px solid #00A6FF; outline-offset: 2px; }

    .amg-widget-messages {
      flex: 1; overflow-y: auto;
      padding: 18px 20px 12px;
      display: flex; flex-direction: column; gap: 12px;
      background: #0F172A;
      scrollbar-width: thin;
      scrollbar-color: rgba(255,255,255,.14) transparent;
    }
    .amg-widget-messages::-webkit-scrollbar { width: 6px; }
    .amg-widget-messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,.14); border-radius: 3px; }
    .amg-widget-messages::-webkit-scrollbar-track { background: transparent; }

    .amg-msg {
      max-width: 86%;
      padding: 11px 15px;
      border-radius: 14px;
      font-size: 14.5px;
      line-height: 1.5;
      word-wrap: break-word;
      animation: amg-msg-enter .26s cubic-bezier(.22,1,.36,1);
    }
    @keyframes amg-msg-enter {
      from { opacity: 0; transform: translateY(4px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .amg-msg.user {
      align-self: flex-end;
      background: linear-gradient(135deg, #00A6FF 0%, #0090E0 100%);
      color: #FFFFFF;
      border-bottom-right-radius: 6px;
      box-shadow: 0 2px 8px rgba(0,144,224,.32);
    }
    .amg-msg.agent {
      align-self: flex-start;
      background: #1A2033;
      color: #F5F7FB;
      border: 1px solid rgba(255,255,255,.06);
      border-bottom-left-radius: 6px;
    }
    .amg-msg.agent.streaming::after {
      content: "▊";
      display: inline-block;
      margin-left: 2px;
      color: #00A6FF;
      animation: amg-cursor-blink 1s steps(2) infinite;
    }
    @keyframes amg-cursor-blink {
      0%,50% { opacity: 1; }
      51%,100% { opacity: 0; }
    }
    .amg-msg.typing {
      color: #8796A8; font-style: italic;
      display: inline-flex; align-items: center; gap: 6px;
    }
    .amg-msg.typing::before {
      content: "";
      display: inline-block; width: 8px; height: 8px; border-radius: 50%;
      background: #00A6FF;
      animation: amg-typing-bounce 1.2s cubic-bezier(.22,1,.36,1) infinite;
    }
    @keyframes amg-typing-bounce {
      0%,100% { transform: translateY(0);   opacity: .6; }
      50%     { transform: translateY(-3px); opacity: 1; }
    }
    .amg-msg a {
      color: #00A6FF; text-decoration: underline;
      text-underline-offset: 2px;
      text-decoration-thickness: 1px;
    }
    .amg-msg a:hover { color: #4DBEFF; }
    .amg-msg strong { font-weight: 700; color: #FFFFFF; }
    .amg-msg code {
      font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
      font-size: 12.5px;
      background: rgba(0,166,255,.08);
      padding: 1px 6px;
      border-radius: 4px;
      color: #4DBEFF;
    }

    /* Rich message components */
    .amg-card {
      align-self: flex-start;
      max-width: 86%;
      background: #1A2033;
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 14px; padding: 14px 16px;
      display: flex; flex-direction: column; gap: 6px;
      animation: amg-msg-enter .26s cubic-bezier(.22,1,.36,1);
    }
    .amg-card-title { font-size: 14px; font-weight: 700; color: #FFFFFF; letter-spacing: -0.005em; }
    .amg-card-body { font-size: 13.5px; color: #C5CDD8; line-height: 1.5; }
    .amg-card-meta { font-size: 11.5px; color: #8796A8; letter-spacing: .04em; text-transform: uppercase; font-weight: 600; margin-bottom: 2px; }

    .amg-buttons {
      align-self: flex-start; max-width: 86%;
      display: flex; flex-wrap: wrap; gap: 8px;
      animation: amg-msg-enter .26s cubic-bezier(.22,1,.36,1);
    }
    .amg-button {
      background: rgba(0,166,255,.10);
      color: #4DBEFF;
      border: 1px solid rgba(0,166,255,.22);
      border-radius: 10px;
      padding: 8px 14px;
      font-size: 13px; font-weight: 600;
      cursor: pointer;
      font-family: inherit;
      transition: all .18s cubic-bezier(.22,1,.36,1);
    }
    .amg-button:hover {
      background: rgba(0,166,255,.18);
      color: #8CD0FF;
      transform: translateY(-1px);
    }
    .amg-button:focus-visible { outline: 2px solid #00A6FF; outline-offset: 2px; }
    .amg-button.primary {
      background: linear-gradient(135deg, #10B77F 0%, #0EA572 100%);
      color: #FFFFFF; border-color: transparent;
      box-shadow: 0 2px 6px rgba(16,183,127,.32);
    }
    .amg-button.primary:hover {
      background: linear-gradient(135deg, #14CC8D 0%, #10B77F 100%);
    }

    .amg-pricing {
      align-self: stretch;
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
      animation: amg-msg-enter .26s cubic-bezier(.22,1,.36,1);
    }
    @media (max-width: 440px) {
      .amg-pricing { grid-template-columns: 1fr 1fr; }
      .amg-pricing-tier:nth-child(3) { grid-column: span 2; }
    }
    .amg-pricing-tier {
      background: #1A2033;
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 12px;
      padding: 12px 10px;
      text-align: center;
      transition: border-color .18s cubic-bezier(.22,1,.36,1), transform .18s cubic-bezier(.22,1,.36,1);
    }
    .amg-pricing-tier:hover {
      border-color: rgba(0,166,255,.32);
      transform: translateY(-2px);
    }
    .amg-pricing-tier.featured { border-color: rgba(16,183,127,.42); }
    .amg-pricing-name { font-size: 11.5px; color: #8796A8; letter-spacing: .06em; text-transform: uppercase; font-weight: 600; }
    .amg-pricing-price { font-size: 19px; font-weight: 700; color: #FFFFFF; margin: 4px 0 2px; letter-spacing: -0.01em; }
    .amg-pricing-unit  { font-size: 11px; color: #8796A8; }

    .amg-widget-form {
      border-top: 1px solid rgba(255,255,255,.06);
      padding: 14px 16px; background: #131825;
      display: flex; gap: 8px;
    }
    .amg-widget-input {
      flex: 1;
      border: 1px solid rgba(255,255,255,.10);
      border-radius: 12px;
      padding: 11px 14px;
      font-size: 14px; font-family: inherit;
      background: #0F172A; color: #FFFFFF;
      transition: border-color .18s cubic-bezier(.22,1,.36,1), box-shadow .18s cubic-bezier(.22,1,.36,1);
    }
    .amg-widget-input::placeholder { color: #8796A8; }
    .amg-widget-input:focus {
      outline: none;
      border-color: #00A6FF;
      box-shadow: 0 0 0 3px rgba(0,166,255,.18);
    }
    .amg-widget-send {
      background: linear-gradient(135deg, #10B77F 0%, #0EA572 100%);
      color: #FFFFFF; border: 0; border-radius: 12px;
      padding: 0 18px;
      font-weight: 600; font-size: 14px; cursor: pointer;
      font-family: inherit;
      box-shadow: 0 2px 6px rgba(16,183,127,.28);
      transition: background .18s cubic-bezier(.22,1,.36,1), box-shadow .18s cubic-bezier(.22,1,.36,1), transform .1s cubic-bezier(.22,1,.36,1);
    }
    .amg-widget-send:hover { background: linear-gradient(135deg, #14CC8D 0%, #10B77F 100%); box-shadow: 0 4px 12px rgba(16,183,127,.45); }
    .amg-widget-send:active { transform: scale(.97); }
    .amg-widget-send:disabled { opacity: .5; cursor: not-allowed; transform: none; }
    .amg-widget-send:focus-visible { outline: 2px solid #FFFFFF; outline-offset: 2px; }

    .amg-widget-footer {
      padding: 10px 16px;
      background: #131825;
      border-top: 1px solid rgba(255,255,255,.04);
      font-size: 11px; color: #6C7589;
      text-align: center;
      letter-spacing: .04em;
    }
    .amg-widget-footer a { color: #8796A8; text-decoration: none; }
    .amg-widget-footer a:hover { color: #C5CDD8; }

    @media (prefers-reduced-motion: reduce) {
      .amg-widget-fab,
      .amg-widget-panel,
      .amg-msg,
      .amg-card,
      .amg-buttons,
      .amg-pricing { transition: none; animation: none; }
      .amg-widget-fab-pulse,
      .amg-widget-status-dot,
      .amg-msg.agent.streaming::after,
      .amg-msg.typing::before { animation: none; }
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
        s.greeted = false;
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(s));
      }
      return s;
    } catch { return { id: 'fallback', count: 0, greeted: false }; }
  }

  function saveSession(s) {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
  }

  const session = getSession();

  function inferIntent(text) {
    for (const h of INTENT_HINTS) {
      if (h.pattern.test(text)) return h.agent;
    }
    return 'alex';
  }

  function pageContextGreeting() {
    const url = window.location.href;
    for (const g of PAGE_CONTEXT_GREETINGS) {
      if (g.test.test(url)) return g.greeting;
    }
    return PAGE_CONTEXT_GREETINGS[PAGE_CONTEXT_GREETINGS.length - 1].greeting;
  }

  // Lightweight markdown pass for agent messages. Safe subset only:
  // **bold**, `code`, [link](url) — no HTML passthrough.
  function renderMarkdownSafe(text) {
    const escaped = String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    return escaped
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  }

  function buildUI() {
    const fab = document.createElement('button');
    fab.className = 'amg-widget-fab';
    fab.setAttribute('aria-label', 'Open AMG chat');
    fab.setAttribute('aria-expanded', 'false');
    fab.innerHTML = `
      <span class="amg-widget-fab-pulse" aria-hidden="true"></span>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C6.48 2 2 5.58 2 10c0 2.64 1.52 4.96 3.86 6.41L4 22l5.74-2.12c.72.08 1.5.12 2.26.12 5.52 0 10-3.58 10-8s-4.48-10-10-10z"/></svg>`;
    document.body.appendChild(fab);

    const panel = document.createElement('div');
    panel.className = 'amg-widget-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Chat with AMG');
    panel.innerHTML = `
      <div class="amg-widget-header">
        <div class="amg-widget-title">Alex · AMG Strategist</div>
        <div class="amg-widget-subtitle">Ask about our platform, pricing, or the Chamber partnership program. I route to the right specialist on our seven-agent team when you need depth.</div>
        <div class="amg-widget-status" aria-live="polite">
          <span class="amg-widget-status-dot" aria-hidden="true"></span>
          <span>Online · avg reply 2s</span>
        </div>
        <button class="amg-widget-close" aria-label="Close chat">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M18.3 5.71L12 12.01l-6.3-6.3-1.4 1.4 6.3 6.3-6.3 6.3 1.4 1.4 6.3-6.3 6.3 6.3 1.4-1.4-6.3-6.3 6.3-6.3z"/></svg>
        </button>
      </div>
      <div class="amg-widget-messages" role="log" aria-live="polite"></div>
      <form class="amg-widget-form" autocomplete="off">
        <input class="amg-widget-input" type="text" placeholder="Ask Alex anything…" aria-label="Your message" autocomplete="off" maxlength="500" />
        <button class="amg-widget-send" type="submit" aria-label="Send">Send</button>
      </form>
      <div class="amg-widget-footer">Powered by AMG · transcripts stored for quality</div>
    `;
    document.body.appendChild(panel);

    const msgs = panel.querySelector('.amg-widget-messages');
    const form = panel.querySelector('.amg-widget-form');
    const input = panel.querySelector('.amg-widget-input');
    const send = panel.querySelector('.amg-widget-send');
    const closeBtn = panel.querySelector('.amg-widget-close');

    function scrollToBottom() {
      msgs.scrollTop = msgs.scrollHeight;
    }

    function addUser(text) {
      const el = document.createElement('div');
      el.className = 'amg-msg user';
      el.textContent = text;
      msgs.appendChild(el);
      scrollToBottom();
      return el;
    }

    function addAgent(text) {
      const el = document.createElement('div');
      el.className = 'amg-msg agent';
      el.innerHTML = renderMarkdownSafe(text);
      msgs.appendChild(el);
      scrollToBottom();
      return el;
    }

    function addAgentStreaming() {
      const el = document.createElement('div');
      el.className = 'amg-msg agent streaming';
      el.textContent = '';
      msgs.appendChild(el);
      scrollToBottom();
      return el;
    }

    function finalizeStreamingAgent(el, fullText) {
      el.classList.remove('streaming');
      el.innerHTML = renderMarkdownSafe(fullText);
      scrollToBottom();
    }

    function addTyping() {
      const el = document.createElement('div');
      el.className = 'amg-msg typing';
      el.textContent = 'Alex is thinking…';
      msgs.appendChild(el);
      scrollToBottom();
      return el;
    }

    function addCard({ meta, title, body }) {
      const el = document.createElement('div');
      el.className = 'amg-card';
      if (meta)  { const m = document.createElement('div'); m.className = 'amg-card-meta';  m.textContent = meta;  el.appendChild(m); }
      if (title) { const t = document.createElement('div'); t.className = 'amg-card-title'; t.textContent = title; el.appendChild(t); }
      if (body)  { const b = document.createElement('div'); b.className = 'amg-card-body';  b.innerHTML = renderMarkdownSafe(body); el.appendChild(b); }
      msgs.appendChild(el);
      scrollToBottom();
      return el;
    }

    function addButtons(buttons) {
      const row = document.createElement('div');
      row.className = 'amg-buttons';
      buttons.forEach(b => {
        const btn = document.createElement('button');
        btn.className = 'amg-button' + (b.primary ? ' primary' : '');
        btn.textContent = b.label;
        btn.type = 'button';
        btn.addEventListener('click', () => {
          if (b.value) {
            input.value = b.value;
            form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
          } else if (b.href) {
            window.open(b.href, '_blank', 'noopener,noreferrer');
          }
        });
        row.appendChild(btn);
      });
      msgs.appendChild(row);
      scrollToBottom();
      return row;
    }

    function addPricing(tiers) {
      const grid = document.createElement('div');
      grid.className = 'amg-pricing';
      tiers.forEach(t => {
        const tier = document.createElement('div');
        tier.className = 'amg-pricing-tier' + (t.featured ? ' featured' : '');
        tier.innerHTML =
          '<div class="amg-pricing-name">' + String(t.name || '').replace(/</g,'&lt;') + '</div>' +
          '<div class="amg-pricing-price">' + String(t.price || '').replace(/</g,'&lt;') + '</div>' +
          '<div class="amg-pricing-unit">' + String(t.unit || '').replace(/</g,'&lt;') + '</div>';
        grid.appendChild(tier);
      });
      msgs.appendChild(grid);
      scrollToBottom();
      return grid;
    }

    function renderRichReply(data) {
      if (data && typeof data.reply === 'string' && data.reply.length) {
        addAgent(data.reply);
      }
      if (Array.isArray(data && data.cards)) {
        data.cards.forEach(c => addCard(c));
      }
      if (Array.isArray(data && data.pricing)) {
        addPricing(data.pricing);
      }
      if (Array.isArray(data && data.buttons) && data.buttons.length) {
        addButtons(data.buttons);
      }
    }

    function openPanel() {
      panel.classList.add('open');
      fab.setAttribute('aria-expanded', 'true');
      setTimeout(() => input.focus(), 120);
      if (!msgs.querySelector('.amg-msg, .amg-card, .amg-buttons, .amg-pricing')) {
        // First open of this session — emit proactive page-context greeting.
        addAgent(pageContextGreeting());
        if (!session.greeted) {
          session.greeted = true;
          saveSession(session);
        }
      }
    }

    function closePanel() {
      panel.classList.remove('open');
      fab.setAttribute('aria-expanded', 'false');
      fab.focus();
    }

    fab.addEventListener('click', () => panel.classList.contains('open') ? closePanel() : openPanel());
    closeBtn.addEventListener('click', closePanel);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && panel.classList.contains('open')) closePanel(); });

    // ────────────────────────────────────────────────────────────────
    // Stream-ready send pipeline. Tries SSE first; falls back to POST
    // JSON if SSE is unavailable or stalls. Progressive text render
    // eliminates the "typing..." dead-air window when the stream is
    // alive. Fair rate-limit + AbortController timeout (Item 4 polish)
    // preserved — counter increments only on successful 2xx round-trip.
    // ────────────────────────────────────────────────────────────────

    async function trySSE(text, intentHint) {
      // SSE path uses fetch + ReadableStream. We don't use EventSource
      // because EventSource can't do POST (we need to send the message
      // body). The server is expected to return `Content-Type: text/event-stream`
      // with `data: <chunk>` lines and a final `event: done` marker.
      const ctrl = new AbortController();
      const firstChunkTimeout = setTimeout(() => ctrl.abort(), STREAM_FIRST_CHUNK_TIMEOUT_MS);
      let res;
      try {
        res = await fetch(STREAM_ENDPOINT, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          },
          body: JSON.stringify({
            text, session_id: session.id, agent: 'alex',
            intent_hint: intentHint, client_id: null, stream: true,
          }),
          signal: ctrl.signal,
        });
      } catch (_) {
        clearTimeout(firstChunkTimeout);
        return null;
      }
      if (!res.ok || !res.body || !(res.headers.get('content-type') || '').includes('event-stream')) {
        clearTimeout(firstChunkTimeout);
        return null;
      }
      clearTimeout(firstChunkTimeout);
      return res;
    }

    async function streamInto(el, res) {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';
      // Overall read timeout — extend the abort window now that stream started.
      const overallCtrl = new AbortController();
      const overallTimeout = setTimeout(() => overallCtrl.abort(), FETCH_TIMEOUT_MS);

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          // Parse complete SSE events (separated by \n\n)
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';
          for (const evt of events) {
            const lines = evt.split('\n');
            let data = '';
            let eventType = 'message';
            for (const line of lines) {
              if (line.startsWith('event:')) eventType = line.slice(6).trim();
              else if (line.startsWith('data:')) data += line.slice(5).trim();
            }
            if (eventType === 'done') {
              finalizeStreamingAgent(el, fullText);
              clearTimeout(overallTimeout);
              return { ok: true, fullText };
            }
            if (data) {
              // Server may send raw text chunks OR JSON-structured
              // {chunk, done, rich?}. Try JSON first, fall back to raw.
              let chunk = data;
              try {
                const parsed = JSON.parse(data);
                if (parsed && typeof parsed.chunk === 'string') chunk = parsed.chunk;
                if (parsed && parsed.rich) {
                  finalizeStreamingAgent(el, fullText);
                  renderRichReply(parsed.rich);
                  clearTimeout(overallTimeout);
                  return { ok: true, fullText };
                }
                if (parsed && parsed.done) {
                  finalizeStreamingAgent(el, fullText);
                  clearTimeout(overallTimeout);
                  return { ok: true, fullText };
                }
              } catch (_) { /* non-JSON chunk, use raw */ }
              fullText += chunk;
              el.textContent = fullText;
              scrollToBottom();
            }
          }
        }
        finalizeStreamingAgent(el, fullText);
        clearTimeout(overallTimeout);
        return { ok: true, fullText };
      } catch (err) {
        clearTimeout(overallTimeout);
        return { ok: false, err };
      }
    }

    async function postJSON(text, intentHint) {
      const ctrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
      const timeoutId = ctrl ? setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS) : null;
      try {
        const res = await fetch(ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text, session_id: session.id, agent: 'alex',
            intent_hint: intentHint, client_id: null,
          }),
          signal: ctrl ? ctrl.signal : undefined,
        });
        if (timeoutId) clearTimeout(timeoutId);
        return { ok: res.ok, res, err: null };
      } catch (err) {
        if (timeoutId) clearTimeout(timeoutId);
        return { ok: false, res: null, err };
      }
    }

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      if (session.count >= RATE_LIMIT_MSGS) {
        addAgent("You've used all " + RATE_LIMIT_MSGS + " messages for this session. Email solon@aimarketinggenius.io to keep the conversation going.");
        return;
      }
      const intentHint = inferIntent(text);
      addUser(text);
      input.value = '';
      send.disabled = true;

      let succeeded = false;
      let errorShown = false;

      // Try SSE first. If it returns a usable stream, render progressively.
      const streamRes = await trySSE(text, intentHint);
      if (streamRes) {
        const streamBubble = addAgentStreaming();
        const streamOutcome = await streamInto(streamBubble, streamRes);
        if (streamOutcome && streamOutcome.ok && streamOutcome.fullText) {
          succeeded = true;
        } else {
          // Stream failed mid-flight; remove the streaming bubble + show error
          streamBubble.remove();
        }
      }

      if (!succeeded && !errorShown) {
        // Fall back to POST JSON (existing path).
        const typing = addTyping();
        const { ok, res, err } = await postJSON(text, intentHint);
        typing.remove();
        if (ok && res) {
          try {
            const data = await res.json();
            renderRichReply(data);
            succeeded = true;
          } catch {
            addAgent("Something hiccuped on our end. Try again, or email solon@aimarketinggenius.io.");
            errorShown = true;
          }
        } else if (err && err.name === 'AbortError') {
          addAgent("That took longer than expected on our side. Try again in a moment, or email solon@aimarketinggenius.io.");
          errorShown = true;
        } else {
          addAgent("Can't reach our server right now. Try again in a moment, or email solon@aimarketinggenius.io.");
          errorShown = true;
        }
      }

      send.disabled = false;
      input.focus();
      if (succeeded) {
        session.count++;
        saveSession(session);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { injectStyles(); buildUI(); });
  } else {
    injectStyles(); buildUI();
  }
})();
