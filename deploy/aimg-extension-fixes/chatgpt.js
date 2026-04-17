/**
 * ChatGPT (chatgpt.com / chat.openai.com) Content Script — v0.1.2 selectors
 * CT-0417-02 Phase 2: hardened selectors per 2026 DOM patterns
 *
 * What changed from v0.1.1:
 *   - Added platform-specific locks instead of generic `main` MutationObserver
 *   - Dedupe via data-message-id (stable across streaming updates)
 *   - Model detection via new model-indicator in compose panel
 *   - Thread ID extraction from URL path
 *
 * Live-DOM verification pending per CT-0417-02 Phase 2 gap map — needs Solon's
 * logged-in ChatGPT session via Chrome MCP to confirm selectors lock.
 */

(function () {
  'use strict';

  const PLATFORM = 'chatgpt';
  let exchangeCounter = 0;
  const processedMessages = new Set();

  // Primary selectors (2026-04 DOM snapshot target)
  const SELECTORS = {
    conversationContainer: 'main, [role="main"]',
    assistantTurn: '[data-message-author-role="assistant"], [data-testid^="conversation-turn-"]',
    userTurn: '[data-message-author-role="user"]',
    messageIdAttr: 'data-message-id',
    // Model indicator appears near compose input or in header
    modelIndicator: '[data-testid="model-switcher-dropdown-button"], [aria-label*="model" i]',
    // Text content nodes inside assistant bubbles
    textContentEl: '[data-message-author-role="assistant"] .markdown, [data-message-author-role="assistant"] [class*="prose"]',
  };

  // Fallback legacy selectors (pre-2026 DOM)
  const LEGACY_SELECTORS = {
    assistantTurn: '.group.w-full[class*="bg-"]',
    messageIdAttr: 'data-id',
  };

  function waitForPlatform(cb, retries = 20) {
    if (window.__AIMEMORY_PLATFORM) return cb(window.__AIMEMORY_PLATFORM);
    if (retries <= 0) { console.warn('[AI Memory] Platform detector not found (chatgpt)'); return; }
    setTimeout(() => waitForPlatform(cb, retries - 1), 250);
  }

  waitForPlatform((platformInfo) => {
    console.log(`[AI Memory] ChatGPT content script v0.1.2 active. Thread: ${platformInfo.threadId}`);
    observeConversation(platformInfo);
  });

  function detectModel() {
    const el = document.querySelector(SELECTORS.modelIndicator);
    if (el && el.textContent) return el.textContent.trim();
    return 'ChatGPT';
  }

  function extractThreadId() {
    // URL pattern: chatgpt.com/c/<uuid> or chat.openai.com/chat/<uuid>
    const m = window.location.pathname.match(/\/(c|chat)\/([0-9a-f-]{36})/);
    return m ? m[2] : null;
  }

  function extractAssistantText(turn) {
    const textEl = turn.querySelector(SELECTORS.textContentEl) || turn;
    // Prefer .textContent; skip code blocks' <code> since those have newline issues
    const clone = textEl.cloneNode(true);
    // Remove UI chrome (copy buttons, thumbs-up/down, regenerate)
    clone.querySelectorAll('button, [role="button"]').forEach(b => b.remove());
    return (clone.textContent || '').trim();
  }

  function extractMessageId(turn) {
    return turn.getAttribute(SELECTORS.messageIdAttr)
        || turn.getAttribute(LEGACY_SELECTORS.messageIdAttr)
        || turn.id
        || null;
  }

  function dispatchCapture(payload) {
    try {
      chrome.runtime.sendMessage({ type: 'CAPTURE_MESSAGE', payload }, (resp) => {
        if (chrome.runtime.lastError) {
          console.warn('[AI Memory] ChatGPT send failed:', chrome.runtime.lastError.message);
        }
      });
    } catch (e) {
      console.warn('[AI Memory] ChatGPT dispatch error:', e.message);
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
      platform_name: 'ChatGPT',
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
          // Legacy fallback
          if (turns.length === 0 && node.querySelectorAll) {
            node.querySelectorAll(LEGACY_SELECTORS.assistantTurn).forEach(t => turns.push(t));
          }

          for (const turn of turns) {
            processAssistantTurn(turn, platformInfo);
          }
        }
      }
    });

    observer.observe(container, { childList: true, subtree: true });
    console.log('[AI Memory] ChatGPT observer attached (v0.1.2 hardened selectors).');

    // Initial scan for already-present assistant turns
    document.querySelectorAll(SELECTORS.assistantTurn).forEach(t => processAssistantTurn(t, platformInfo));
  }
})();
