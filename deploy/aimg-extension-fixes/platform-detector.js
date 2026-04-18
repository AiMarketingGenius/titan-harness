/**
 * Platform Detector — identifies which AI platform the user is on
 * Injected as first content script on all supported platforms
 * Sets window.__AIMEMORY_PLATFORM for other scripts to read
 */

(function() {
  'use strict';

  const PLATFORM_RULES = [
    { id: 'claude',     host: 'claude.ai' },
    { id: 'chatgpt',    host: 'chatgpt.com' },
    { id: 'chatgpt',    host: 'chat.openai.com' },
    { id: 'gemini',     host: 'gemini.google.com' },
    { id: 'grok',       host: 'grok.x.ai' },
    { id: 'perplexity', host: 'www.perplexity.ai' }
  ];

  function detectPlatform() {
    const hostname = window.location.hostname;
    for (const rule of PLATFORM_RULES) {
      if (hostname === rule.host || hostname.endsWith('.' + rule.host)) {
        return rule.id;
      }
    }
    return null;
  }

  function extractThreadId(platformId) {
    const url = window.location.href;
    const patterns = {
      claude:     /claude\.ai\/chat\/([a-f0-9-]+)/,
      chatgpt:    /chatgpt\.com\/c\/([a-f0-9-]+)/,
      gemini:     /gemini\.google\.com\/app\/([a-f0-9]+)/,
      grok:       /grok\.x\.ai\/chat\/([a-zA-Z0-9]+)/,
      perplexity: /perplexity\.ai\/search\/([a-zA-Z0-9._-]+)/
    };

    const match = url.match(patterns[platformId]);
    return match ? match[1] : null;
  }

  function buildThreadUrl(platformId, threadId) {
    const templates = {
      claude:     `https://claude.ai/chat/${threadId}`,
      chatgpt:    `https://chatgpt.com/c/${threadId}`,
      gemini:     `https://gemini.google.com/app/${threadId}`,
      grok:       `https://grok.x.ai/chat/${threadId}`,
      perplexity: `https://www.perplexity.ai/search/${threadId}`
    };
    return templates[platformId] || null;
  }

  const platform = detectPlatform();
  if (!platform) return;

  const threadId = extractThreadId(platform);
  const threadUrl = threadId ? buildThreadUrl(platform, threadId) : window.location.href;

  // Expose to other content scripts
  window.__AIMEMORY_PLATFORM = {
    id: platform,
    threadId: threadId,
    threadUrl: threadUrl,
    detectedAt: new Date().toISOString()
  };

  // Notify service worker
  chrome.runtime.sendMessage({
    type: 'PLATFORM_DETECTED',
    platform: platform,
    threadId: threadId,
    threadUrl: threadUrl
  });

  // Re-detect on URL change (SPA navigation)
  let lastUrl = window.location.href;
  const urlObserver = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      const newThreadId = extractThreadId(platform);
      const newThreadUrl = newThreadId ? buildThreadUrl(platform, newThreadId) : window.location.href;
      
      window.__AIMEMORY_PLATFORM.threadId = newThreadId;
      window.__AIMEMORY_PLATFORM.threadUrl = newThreadUrl;
      
      chrome.runtime.sendMessage({
        type: 'THREAD_CHANGED',
        platform: platform,
        threadId: newThreadId,
        threadUrl: newThreadUrl
      });
    }
  });
  urlObserver.observe(document.body, { childList: true, subtree: true });

  console.log(`[AI Memory] Platform detected: ${platform}, Thread: ${threadId || 'none'}`);
})();
