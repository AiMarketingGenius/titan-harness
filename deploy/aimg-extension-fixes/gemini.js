/**
 * Gemini (gemini.google.com) Content Script — v0.1.2 selectors
 * CT-0417-02 Phase 2: hardened selectors per 2026 DOM patterns
 *
 * Live-DOM verification pending per CT-0417-02 Phase 2 gap map — needs Solon's
 * logged-in Gemini session via Chrome MCP to confirm selectors lock.
 */

(function () {
  'use strict';

  const PLATFORM = 'gemini';
  let exchangeCounter = 0;
  const processedMessages = new Set();

  // Gemini uses Angular; selectors typically stable around these attributes
  const SELECTORS = {
    conversationContainer: 'main, [role="main"], bard-main, chat-window',
    // Gemini wraps responses in <model-response> custom elements
    assistantTurn: 'model-response, [data-message-type="model_response"], .model-response-text',
    userTurn: 'user-query, [data-message-type="user_query"]',
    // Text content inside the model response
    textContentEl: 'message-content, .markdown, [class*="response-container"]',
    // Model switcher typically in top nav or side menu
    modelIndicator: '[data-test-id="bard-mode-menu-button"], [aria-label*="Gemini" i], [aria-label*="model" i]',
  };

  function waitForPlatform(cb, retries = 20) {
    if (window.__AIMEMORY_PLATFORM) return cb(window.__AIMEMORY_PLATFORM);
    if (retries <= 0) { console.warn('[AI Memory] Platform detector not found (gemini)'); return; }
    setTimeout(() => waitForPlatform(cb, retries - 1), 250);
  }

  waitForPlatform((platformInfo) => {
    console.log(`[AI Memory] Gemini content script v0.1.2 active. Thread: ${platformInfo.threadId}`);
    observeConversation(platformInfo);
  });

  function detectModel() {
    const el = document.querySelector(SELECTORS.modelIndicator);
    if (el && el.textContent) return el.textContent.trim();
    return 'Gemini';
  }

  function extractThreadId() {
    // URL pattern: gemini.google.com/app/<id> or gemini.google.com/chat/<id>
    const m = window.location.pathname.match(/\/(app|chat)\/([a-z0-9_-]+)/i);
    return m ? m[2] : null;
  }

  function extractAssistantText(turn) {
    const textEl = turn.querySelector(SELECTORS.textContentEl) || turn;
    const clone = textEl.cloneNode(true);
    clone.querySelectorAll('button, [role="button"], .thumb-button, .copy-button').forEach(b => b.remove());
    return (clone.textContent || '').trim();
  }

  function extractMessageId(turn) {
    return turn.getAttribute('data-message-id')
        || turn.getAttribute('response-id')
        || turn.id
        || null;
  }

  function dispatchCapture(payload) {
    try {
      chrome.runtime.sendMessage({ type: 'CAPTURE_MESSAGE', payload }, (resp) => {
        if (chrome.runtime.lastError) {
          console.warn('[AI Memory] Gemini send failed:', chrome.runtime.lastError.message);
        }
      });
    } catch (e) {
      console.warn('[AI Memory] Gemini dispatch error:', e.message);
    }
  }

  function processAssistantTurn(turn, platformInfo) {
    const text = extractAssistantText(turn);
    if (!text || text.length < 5) return;

    const msgId = extractMessageId(turn) || `${PLATFORM}-${exchangeCounter}-${text.slice(0, 40).replace(/\s+/g, '_')}`;
    if (processedMessages.has(msgId)) return;
    processedMessages.add(msgId);

    exchangeCounter++;

    dispatchCapture({
      platform: PLATFORM,
      platform_name: 'Gemini',
      thread_id: extractThreadId() || platformInfo.threadId,
      thread_url: window.location.href,
      exchange_number: exchangeCounter,
      role: 'assistant',
      content: text,
      model_used: detectModel(),
      source_timestamp: new Date().toISOString(),
      message_id: msgId,
    });
  }

  function observeConversation(platformInfo) {
    const container = document.querySelector(SELECTORS.conversationContainer) || document.body;

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;

          const turns = [];
          if (node.matches && node.matches(SELECTORS.assistantTurn)) turns.push(node);
          if (node.querySelectorAll) {
            node.querySelectorAll(SELECTORS.assistantTurn).forEach(t => turns.push(t));
          }
          for (const turn of turns) {
            processAssistantTurn(turn, platformInfo);
          }
        }
      }
    });

    observer.observe(container, { childList: true, subtree: true });
    console.log('[AI Memory] Gemini observer attached (v0.1.2 hardened selectors).');

    document.querySelectorAll(SELECTORS.assistantTurn).forEach(t => processAssistantTurn(t, platformInfo));
  }
})();
