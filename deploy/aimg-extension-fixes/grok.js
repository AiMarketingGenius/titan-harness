/**
 * Grok Content Script
 * Observes conversation, extracts AI responses, builds provenance stamps,
 * sends to service worker for processing
 */

(function() {
  'use strict';

  const PLATFORM = 'grok';
  let exchangeCounter = 0;
  const processedMessages = new Set();

  function waitForPlatform(cb, retries = 20) {
    if (window.__AIMEMORY_PLATFORM) return cb(window.__AIMEMORY_PLATFORM);
    if (retries <= 0) return console.warn('[AI Memory] Platform detector not found');
    setTimeout(() => waitForPlatform(cb, retries - 1), 250);
  }

  waitForPlatform((platformInfo) => {
    console.log(`[AI Memory] Grok content script active. Thread: ${platformInfo.threadId}`);
    observeConversation(platformInfo);
  });

  function observeConversation(platformInfo) {
    const container = document.querySelector('main') || document.body;

    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;

          const assistantMsgs = node.matches?.('.assistant-message')
            ? [node]
            : (node.querySelectorAll?.('.assistant-message, [data-testid="message"]') || []);

          for (const msg of assistantMsgs) {
            scheduleExtraction(msg, platformInfo);
          }
        }
      }
    });

    observer.observe(container, { childList: true, subtree: true });

    document.querySelectorAll('.assistant-message, [data-testid="message"]')
      .forEach(msg => processMessage(msg, platformInfo));
  }

  const extractionTimers = new WeakMap();

  function scheduleExtraction(element, platformInfo) {
    if (extractionTimers.has(element)) clearTimeout(extractionTimers.get(element));
    const timer = setTimeout(() => {
      processMessage(element, platformInfo);
      extractionTimers.delete(element);
    }, 3000);
    extractionTimers.set(element, timer);
  }

  function processMessage(element, platformInfo) {
    const content = element.querySelector('.message-content, .prose')?.innerText?.trim();
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
      timestamp: new Date().toISOString()
    };

    chrome.runtime.sendMessage({
      type: 'NEW_RESPONSE',
      platform: PLATFORM,
      content: content,
      provenance: provenance,
      contentLength: content.length
    });

    // Pill updates moved to ui/exchange-detector.js (v0.1.13 single-source-of-truth).
    console.log(`[AI Memory] Grok response captured. Exchange #${exchangeCounter}, ${content.length} chars`);
  }

  function hashCode(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash |= 0;
    }
    return 'grok_' + Math.abs(hash).toString(36);
  }
})();
