/**
 * Claude.ai Content Script
 * Observes conversation, extracts AI responses, builds provenance stamps,
 * sends to service worker for processing
 */

(function() {
  'use strict';

  const PLATFORM = 'claude';
  let exchangeCounter = 0;
  const processedMessages = new Set();

  // Wait for platform detector
  function waitForPlatform(cb, retries = 20) {
    if (window.__AIMEMORY_PLATFORM) return cb(window.__AIMEMORY_PLATFORM);
    if (retries <= 0) return console.warn('[AI Memory] Platform detector not found');
    setTimeout(() => waitForPlatform(cb, retries - 1), 250);
  }

  waitForPlatform((platformInfo) => {
    console.log(`[AI Memory] Claude content script active. Thread: ${platformInfo.threadId}`);
    observeConversation(platformInfo);
  });

  function observeConversation(platformInfo) {
    const container = document.querySelector('[data-testid="conversation-turn"]')?.parentElement
      || document.querySelector('.font-claude-message')?.parentElement?.parentElement
      || document.body;

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;
          
          const assistantMsgs = node.matches?.('[data-testid="assistant-message"]')
            ? [node]
            : (node.querySelectorAll?.('[data-testid="assistant-message"], .font-claude-message') || []);

          for (const msg of assistantMsgs) {
            scheduleExtraction(msg, platformInfo);
          }
        }
      }
    });

    observer.observe(container, { childList: true, subtree: true });

    const existingMsgs = document.querySelectorAll('[data-testid="assistant-message"], .font-claude-message');
    existingMsgs.forEach(msg => processMessage(msg, platformInfo));
  }

  const extractionTimers = new WeakMap();

  function scheduleExtraction(element, platformInfo) {
    if (extractionTimers.has(element)) {
      clearTimeout(extractionTimers.get(element));
    }

    const timer = setTimeout(() => {
      processMessage(element, platformInfo);
      extractionTimers.delete(element);
    }, 3000);

    extractionTimers.set(element, timer);
  }

  function processMessage(element, platformInfo) {
    const content = element.querySelector('.whitespace-pre-wrap, .prose')?.innerText?.trim();
    if (!content || content.length < 20) return;

    const msgId = hashCode(content.substring(0, 200));
    if (processedMessages.has(msgId)) return;
    processedMessages.add(msgId);

    exchangeCounter++;

    const provenance = {
      platform: PLATFORM,
      thread_id: platformInfo.threadId,
      thread_url: platformInfo.threadUrl,
      exchange_number: exchangeCounter,
      timestamp: new Date().toISOString(),
      project_id: extractProjectId()
    };

    chrome.runtime.sendMessage({
      type: 'NEW_RESPONSE',
      platform: PLATFORM,
      content: content,
      provenance: provenance,
      contentLength: content.length
    });

    // NOTE: pill updates live in ui/exchange-detector.js now (v0.1.13) — the
    // detector is the single source of truth for the Hallucinometer count
    // and Einstein check results. Calling them here too caused double-count.
    console.log(`[AI Memory] Claude response captured. Exchange #${exchangeCounter}, ${content.length} chars`);
  }

  function extractProjectId() {
    const match = window.location.href.match(/\/project\/([a-f0-9-]+)/);
    return match ? match[1] : null;
  }

  function hashCode(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash |= 0;
    }
    return 'claude_' + Math.abs(hash).toString(36);
  }
})();
