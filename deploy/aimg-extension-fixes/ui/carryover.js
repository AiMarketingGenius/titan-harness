/**
 * Auto-Carryover System — C3
 * Carryover generation, clipboard copy, modal/card/banner logic
 */

(function() {
  'use strict';

  let suggestionShown = false;
  let modalShown = false;
  let bannerShown = false;
  let snoozedUntil = 0; // exchange number to snooze until

  function logUIEvent(event, data = {}) {
    console.log(`[UI Event] ${event}`, data);
  }

  // C3.2: Non-blocking suggestion card (exchange 35)
  function showSuggestionCard() {
    if (suggestionShown) return;
    suggestionShown = true;
    logUIEvent('carryover_suggestion_shown', { exchange: 35 });

    const card = document.createElement('div');
    card.className = 'mg-carryover-card mg-extension';
    card.innerHTML = `
      <div class="glass-card">
        <div class="mg-card-title">🔄 Time for a Fresh Start?</div>
        <div class="mg-card-body">
          Your thread is getting long. AI tools work best with shorter conversations.
          We'll create a summary of everything discussed so your next thread picks up right where you left off.
        </div>
        <div class="mg-card-actions">
          <button class="btn-primary mg-carryover-accept">🚀 Start Fresh</button>
          <button class="btn-secondary mg-carryover-dismiss">Not Right Now</button>
        </div>
      </div>
    `;

    document.body.appendChild(card);

    card.querySelector('.mg-carryover-accept').addEventListener('click', () => {
      logUIEvent('carryover_accepted', { exchange: 35 });
      generateCarryover();
      card.remove();
    });

    card.querySelector('.mg-carryover-dismiss').addEventListener('click', () => {
      logUIEvent('carryover_dismissed', { exchange: 35 });
      card.remove();
    });

    // Auto-dismiss after 15s
    setTimeout(() => { if (card.parentElement) card.remove(); }, 15000);
  }

  // C3.3: Blocking modal (exchange 46)
  function showCarryoverModal() {
    if (modalShown || snoozedUntil > 0) return;
    modalShown = true;
    logUIEvent('carryover_modal_shown', { exchange: 46 });

    const overlay = document.createElement('div');
    overlay.className = 'mg-carryover-overlay mg-extension';
    overlay.innerHTML = `
      <div class="mg-carryover-modal">
        <div class="glass-card">
          <div class="mg-modal-title">⚠️ Thread Quality Alert</div>
          <div class="mg-modal-body">
            Let's start a fresh new thread to maintain the highest quality output from your AI!
            Don't worry — we'll start off the new thread with a detailed summary of this conversation so everything continues seamlessly.
          </div>
          <div class="mg-modal-summary-box">
            <strong>📋 Your carryover summary includes:</strong><br><br>
            • Key decisions made<br>
            • Facts established<br>
            • Current task status<br>
            • Open questions
          </div>
          <div class="mg-modal-actions">
            <button class="btn-primary mg-modal-generate">🚀 Generate & Copy Carryover Summary</button>
            <button class="btn-secondary mg-modal-snooze">⏭️ Remind Me in 10 More Exchanges</button>
            <button class="btn-tertiary mg-modal-continue">Continue This Thread</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.querySelector('.mg-modal-generate').addEventListener('click', () => {
      logUIEvent('carryover_accepted', { exchange: 46, source: 'modal' });
      showLoadingSkeleton(overlay.querySelector('.mg-modal-actions'));
      generateCarryover().then(() => overlay.remove());
    });

    overlay.querySelector('.mg-modal-snooze').addEventListener('click', () => {
      logUIEvent('carryover_snoozed', { exchange: 46, snooze_until: 56 });
      snoozedUntil = 56;
      modalShown = false;
      overlay.remove();
    });

    overlay.querySelector('.mg-modal-continue').addEventListener('click', () => {
      logUIEvent('carryover_dismissed', { exchange: 46, source: 'modal' });
      overlay.remove();
    });
  }

  // C3.4: Persistent top banner (exchange 55)
  function showPersistentBanner() {
    if (bannerShown) return;
    bannerShown = true;

    const banner = document.createElement('div');
    banner.className = 'mg-carryover-banner mg-extension';
    banner.innerHTML = `
      ⚠️ This thread is very long. AI quality degrades significantly.
      <a class="mg-banner-fresh">Start Fresh →</a>
      <button class="mg-banner-dismiss">Dismiss</button>
    `;

    document.body.appendChild(banner);

    banner.querySelector('.mg-banner-fresh').addEventListener('click', () => {
      generateCarryover();
      banner.remove();
    });

    banner.querySelector('.mg-banner-dismiss').addEventListener('click', () => {
      banner.remove();
    });
  }

  // Skeleton loading state
  function showLoadingSkeleton(container) {
    container.innerHTML = `
      <div class="skeleton skeleton-text" style="width: 100%; height: 20px;"></div>
      <div class="skeleton skeleton-text" style="width: 85%; height: 20px;"></div>
      <div class="skeleton skeleton-text" style="width: 60%; height: 20px;"></div>
      <p style="color: var(--text-muted); font-size: var(--text-sm); text-align: center; margin-top: 12px;">
        Creating your summary...
      </p>
    `;
  }

  // C3.1: Generate carryover (tier-gated per DOCTRINE_CONSUMER_TIERS)
  // Free  → rule-based plain summary
  // Pro   → structured Doc-10 format (goal / decisions / NOT-do / deferred / priority stack / cold-start)
  // Pro+  → Doc-10 format + deduplication signal against recent memories
  async function generateCarryover() {
    const platform = window.__AIMEMORY_PLATFORM;
    if (!platform) return;

    try {
      const [hotCacheRes, userBag] = await Promise.all([
        chrome.runtime.sendMessage({ type: 'GET_HOT_CACHE' }),
        chrome.storage.local.get('user')
      ]);

      const memories = (hotCacheRes?.memories || []).filter(m =>
        m.provenance?.thread_id === platform.threadId
      );

      const tier = (userBag?.user?.tier || 'free').toLowerCase();
      let summary;
      let method;

      if (tier === 'pro_plus' || tier === 'pro+') {
        summary = buildStructuredSummary(memories, platform, { dedup: true });
        method = 'doc10_deduped';
      } else if (tier === 'pro') {
        summary = buildStructuredSummary(memories, platform, { dedup: false });
        method = 'doc10_structured';
      } else {
        summary = buildRuleBasedSummary(memories);
        method = 'rule_based';
      }

      await navigator.clipboard.writeText(summary);

      showToast(
        tier === 'free'
          ? 'Summary copied! Upgrade to Pro for the structured Doc-10 carryover. 📋'
          : 'Structured carryover copied. Paste into your new thread. 📋'
      );

      logUIEvent('carryover_generated', {
        tier,
        method,
        memories_count: memories.length,
        summary_length: summary.length
      });
    } catch (err) {
      console.error('[Carryover] Generation error:', err);
      showToast('Could not generate summary. Please try again.');
    }
  }

  function buildRuleBasedSummary(memories) {
    const decisions = memories.filter(m => m.type === 'decision' || m.memory_type === 'decision');
    const facts = memories.filter(m => m.type === 'fact' || m.memory_type === 'fact');
    const corrections = memories.filter(m => m.type === 'correction' || m.memory_type === 'correction');
    const actions = memories.filter(m => m.type === 'action' || m.memory_type === 'action');

    let summary = '## Continuing from Previous Thread\n\n';
    summary += "Here's a summary of our previous conversation:\n\n";

    if (decisions.length > 0) {
      summary += '**Key Decisions:**\n';
      decisions.forEach(d => { summary += `- ${d.content}\n`; });
      summary += '\n';
    }

    if (facts.length > 0) {
      summary += '**Established Facts:**\n';
      facts.forEach(f => { summary += `- ${f.content}\n`; });
      summary += '\n';
    }

    if (corrections.length > 0) {
      summary += '**Corrections Made:**\n';
      corrections.forEach(c => { summary += `- ${c.content}\n`; });
      summary += '\n';
    }

    if (actions.length > 0) {
      summary += '**Open Items:**\n';
      actions.forEach(a => { summary += `- ${a.content}\n`; });
      summary += '\n';
    }

    summary += 'Please continue from here.\n';
    return summary;
  }

  /**
   * Structured Doc-10 carryover used by Pro + Pro+ tiers.
   * Format matches EOM / AI Memory Guard carryover doctrine:
   *   goal → completed → decisions → NOT-do → deferred → priority stack → cold-start prompt.
   *
   * Pro+ additionally de-duplicates against recent prior carryovers referenced in the hot cache
   * so the pasted summary doesn't repeat facts already present in the new thread's seed.
   */
  function buildStructuredSummary(memories, platform, { dedup } = {}) {
    const decisions = memories.filter(m => m.type === 'decision' || m.memory_type === 'decision');
    const facts = memories.filter(m => m.type === 'fact' || m.memory_type === 'fact');
    const corrections = memories.filter(m => m.type === 'correction' || m.memory_type === 'correction');
    const actions = memories.filter(m => m.type === 'action' || m.memory_type === 'action');

    const seen = new Set();
    const unique = (list) => list.filter(m => {
      if (!dedup) return true;
      const key = (m.content || '').toLowerCase().slice(0, 80);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    const uniqueDecisions = unique(decisions);
    const uniqueFacts = unique(facts);
    const uniqueCorrections = unique(corrections);
    const uniqueActions = unique(actions);

    const platformName = platform?.platform || 'an AI assistant';
    const dateLine = new Date().toISOString().slice(0, 10);
    const hasCorrections = uniqueCorrections.length > 0;

    let out = '## Carryover — Continuing Previous Thread\n';
    out += `_Generated ${dateLine} from ${platformName} · AI Memory Guard${dedup ? ' (deduped)' : ''}_\n\n`;

    out += '### Goal\n';
    out += uniqueDecisions.length > 0
      ? `${uniqueDecisions[0].content}\n\n`
      : 'Continue from the previous thread with full context.\n\n';

    out += '### What was completed\n';
    if (uniqueFacts.length > 0) {
      uniqueFacts.forEach(f => { out += `- ${f.content}\n`; });
    } else {
      out += '- (No concrete completions captured in the hot cache.)\n';
    }
    out += '\n';

    out += '### Key decisions\n';
    if (uniqueDecisions.length > 0) {
      uniqueDecisions.forEach(d => { out += `- ${d.content}\n`; });
    } else {
      out += '- (No decisions locked in this thread yet.)\n';
    }
    out += '\n';

    out += '### Do NOT do\n';
    if (hasCorrections) {
      uniqueCorrections.forEach(c => { out += `- Avoid: ${c.content}\n`; });
    } else {
      out += '- (No explicit corrections were captured. Ask before assuming anything.)\n';
    }
    out += '\n';

    out += '### Deferred / open items\n';
    if (uniqueActions.length > 0) {
      uniqueActions.forEach(a => { out += `- ${a.content}\n`; });
    } else {
      out += '- (Nothing deferred.)\n';
    }
    out += '\n';

    out += '### Priority stack for the next thread\n';
    const priorityItems = [
      uniqueActions[0]?.content,
      uniqueDecisions[0]?.content ? `Revisit: ${uniqueDecisions[0].content}` : null,
      uniqueCorrections[0]?.content ? `Respect correction: ${uniqueCorrections[0].content}` : null
    ].filter(Boolean);
    if (priorityItems.length > 0) {
      priorityItems.slice(0, 3).forEach((item, i) => { out += `${i + 1}. ${item}\n`; });
    } else {
      out += '1. Confirm current goal before proceeding.\n';
    }
    out += '\n';

    out += '### Cold-start prompt\n';
    out += '```\n';
    out += 'Pick up from the carryover above.\n';
    out += 'Confirm the goal, acknowledge the corrections, then ask for the next move.\n';
    out += 'Do NOT repeat work already completed in "What was completed."\n';
    out += '```\n';

    if (dedup) {
      out += '\n_Pro+ dedup: entries already referenced in recent carryovers were trimmed so this paste is novel context only._\n';
    }

    return out;
  }

  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'mg-extension';
    toast.style.cssText = `
      position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
      background: var(--brand-surface); color: var(--text-primary);
      padding: 12px 24px; border-radius: var(--radius-md);
      font-size: var(--text-sm); font-family: var(--font-body);
      box-shadow: var(--shadow-notification);
      animation: slideUp 300ms var(--ease-spring);
      z-index: 99999;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  }

  // Listen for carryover triggers from service worker
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'TRIGGER_CARRYOVER_SUGGESTION') showSuggestionCard();
    if (message.type === 'TRIGGER_CARRYOVER_MODAL') showCarryoverModal();
    if (message.type === 'TRIGGER_CARRYOVER_BANNER') showPersistentBanner();
  });

  window.__AIMEMORY_CARRYOVER = {
    showSuggestion: showSuggestionCard,
    showModal: showCarryoverModal,
    generate: generateCarryover
  };
})();
