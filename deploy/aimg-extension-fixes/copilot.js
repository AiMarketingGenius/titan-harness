/**
 * Copilot (copilot.microsoft.com) Content Script
 *
 * Mirrors the pattern used by chatgpt.js / claude.js / gemini.js: wait for
 * the platform detector to populate, then observe the conversation container
 * for assistant-message additions and forward them to the service worker.
 *
 * Copilot uses a Web Components / shadow-DOM tree under `cib-` prefixes
 * (chat-island, cib-serp, cib-chat-turn). The selectors below target the
 * text-containing elements inside those shadow trees that DO pierce through
 * the light DOM. If Microsoft changes selectors, update the SELECTORS object
 * and re-test via Chrome MCP — same maintenance pattern as claude.js.
 *
 * CT-0416-22 2026-04-17: initial copilot.js scaffold. Live-DOM verification
 * (selector-locking against actual assistant output) is queued as Phase 2 of
 * CT-0417-02; pending Solon logged-in session via Chrome MCP.
 */

(function () {
  'use strict';

  const PLATFORM = 'copilot';
  let exchangeCounter = 0;
  const processedMessages = new Set();

  // Copilot-specific selectors — update when Microsoft ships UI changes.
  // Primary: the assistant message bubbles inside cib-chat-turn elements.
  // Fallbacks walk up the shadow tree for resiliency.
  const SELECTORS = {
    turnContainer: 'cib-chat-turn, [data-testid="chat-turn"], article[role="article"]',
    assistantBubble: '[data-author="bot"], [data-role="assistant"], cib-message-group[source="bot"]',
    assistantTextNode: 'cib-shared, .response-message-group, [data-content="text"]',
    userBubble: '[data-author="user"], [data-role="user"], cib-message-group[source="user"]'
  };

  function waitForPlatform(cb, retries = 20) {
    if (window.__AIMEMORY_PLATFORM) return cb(window.__AIMEMORY_PLATFORM);
    if (retries <= 0) {
      console.warn('[AI Memory] Platform detector not found (copilot)');
      return;
    }
    setTimeout(() => waitForPlatform(cb, retries - 1), 250);
  }

  waitForPlatform((platformInfo) => {
    console.log(`[AI Memory] Copilot content script active. Thread: ${platformInfo.threadId}`);
    observeConversation(platformInfo);
  });

  function extractText(node) {
    // Walk light DOM first
    const textEl = node.querySelector && node.querySelector(SELECTORS.assistantTextNode);
    if (textEl && textEl.textContent) return textEl.textContent.trim();

    // Fall back to full text content of the node
    if (node.textContent) return node.textContent.trim();
    return '';
  }

  function detectModel() {
    // Copilot displays model badge near the input or in header settings
    // Examples: "Copilot", "Copilot (GPT-5)", "Copilot Think Deeper"
    const badge =
      document.querySelector('[data-testid="model-indicator"]') ||
      document.querySelector('[aria-label*="model" i]');
    if (badge && badge.textContent) return badge.textContent.trim();
    return 'Copilot';
  }

  function observeConversation(platformInfo) {
    const container = document.querySelector('main') || document.body;

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;

          // Find assistant bubbles added by this mutation
          const bubbles = [];
          if (node.matches && node.matches(SELECTORS.assistantBubble)) bubbles.push(node);
          if (node.querySelectorAll) {
            node.querySelectorAll(SELECTORS.assistantBubble).forEach((b) => bubbles.push(b));
          }

          for (const bubble of bubbles) {
            // Dedupe by stable-ID: prefer data-msg-id, fallback to hash of first 200 chars
            const text = extractText(bubble);
            if (!text || text.length < 5) continue;

            const msgId =
              bubble.getAttribute('data-msg-id') ||
              bubble.getAttribute('id') ||
              `${PLATFORM}-${exchangeCounter}-${text.slice(0, 40).replace(/\s+/g, '_')}`;

            if (processedMessages.has(msgId)) continue;
            processedMessages.add(msgId);

            exchangeCounter++;

            const payload = {
              platform: PLATFORM,
              platform_name: 'Copilot',
              thread_id: platformInfo.threadId,
              thread_url: window.location.href,
              exchange_number: exchangeCounter,
              role: 'assistant',
              content: text,
              model_used: detectModel(),
              source_timestamp: new Date().toISOString()
            };

            try {
              chrome.runtime.sendMessage(
                { type: 'CAPTURE_MESSAGE', payload },
                (resp) => {
                  if (chrome.runtime.lastError) {
                    console.warn('[AI Memory] Copilot send failed:', chrome.runtime.lastError.message);
                  }
                }
              );
            } catch (e) {
              console.warn('[AI Memory] Copilot dispatch error:', e.message);
            }
          }
        }
      }
    });

    observer.observe(container, { childList: true, subtree: true });
    console.log('[AI Memory] Copilot observer attached.');
  }
})();
