/**
 * C8: First-run onboarding wizard
 * 3-screen wizard on first install
 */
(function() {
  'use strict';

  function logUIEvent(event, data = {}) {
    console.log(`[UI Event] ${event}`, data);
  }

  const SCREENS = [
    {
      icon: '🧠',
      title: 'Your AI Never Forgets Again',
      body: 'We remember what you tell AI tools — across Claude, ChatGPT, Gemini, Grok, and Perplexity — so you never have to repeat yourself.\n\nNothing changes about how your AI works. We just add a memory layer on top.',
      button: 'Next →'
    },
    {
      icon: '🔍',
      title: 'Catch AI Mistakes Before You Act',
      body: 'We quietly check AI answers against your own history and known facts. When something looks off, we let you know.\n\nExample: You told Claude your budget is $3,500/mo. Two weeks later, Gemini says it\'s $5,000. We catch that.',
      button: 'Next →',
      socialProof: 'Join early adopters who catch AI mistakes before they matter.'
    },
    {
      icon: '⚙️',
      title: 'How Should We Help?',
      body: null,
      options: [
        { id: 'memory_only', icon: '🧠', title: 'Memory Only', desc: 'Just remember everything. No alerts, no checking.' },
        { id: 'memory_plus_qe', icon: '🔍', title: 'Memory + Fact Checking', desc: 'Remember everything AND catch mistakes automatically.', recommended: true }
      ],
      button: 'Get Started 🚀'
    }
  ];

  let currentScreen = 0;
  let selectedMode = 'memory_plus_qe';

  function showOnboarding(container) {
    logUIEvent('onboarding_screen_viewed', { screen: currentScreen + 1 });

    const screen = SCREENS[currentScreen];
    let html = `
      <div style="text-align: center; padding: 24px;">
        <div style="font-size: 48px; margin-bottom: 16px;">${screen.icon}</div>
        <h2 style="font-size: var(--text-2xl); font-weight: var(--weight-bold); color: var(--text-primary); margin-bottom: 16px; line-height: var(--leading-title);">
          ${screen.title}
        </h2>
    `;

    if (screen.body) {
      html += `<p style="font-size: var(--text-base); color: var(--text-secondary); line-height: var(--leading-body); margin-bottom: 24px; white-space: pre-line;">${screen.body}</p>`;
    }

    if (screen.options) {
      html += '<div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px;">';
      for (const opt of screen.options) {
        const isSelected = opt.id === selectedMode;
        const borderStyle = isSelected ? '2px solid var(--brand-primary)' : '1px solid var(--border-subtle)';
        html += `
          <div class="mg-onboarding-option" data-mode="${opt.id}" style="
            background: var(--brand-surface); border: ${borderStyle}; border-radius: var(--radius-md);
            padding: 16px; cursor: pointer; text-align: left;
          ">
            <div style="font-size: var(--text-lg); font-weight: var(--weight-semibold); color: var(--text-primary);">
              ${opt.icon} ${opt.title} ${opt.recommended ? '★' : ''}
            </div>
            <div style="font-size: var(--text-sm); color: var(--text-secondary); margin-top: 4px;">
              ${opt.desc}
            </div>
            ${opt.recommended ? '<div style="font-size: var(--text-xs); color: var(--brand-primary); margin-top: 4px;">(Recommended)</div>' : ''}
          </div>
        `;
      }
      html += '<p style="font-size: var(--text-sm); color: var(--text-muted); margin-top: 8px;">You can change this anytime in Settings.</p>';
      html += '</div>';
    }

    if (screen.socialProof) {
      html += `<p style="font-size: var(--text-sm); color: var(--text-muted); font-style: italic; margin-bottom: 16px;">${screen.socialProof}</p>`;
    }

    // Progress dots
    html += '<div style="margin-bottom: 16px;">';
    for (let i = 0; i < SCREENS.length; i++) {
      html += `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin: 0 4px; background: ${i === currentScreen ? 'var(--brand-primary)' : 'var(--border-subtle)'}"></span>`;
    }
    html += '</div>';

    html += `<button class="btn-primary" style="width: 100%;" id="mg-onboarding-next">${screen.button}</button>`;
    html += '</div>';

    container.innerHTML = html;

    // Wire option selection
    container.querySelectorAll('.mg-onboarding-option').forEach(opt => {
      opt.addEventListener('click', () => {
        selectedMode = opt.dataset.mode;
        container.querySelectorAll('.mg-onboarding-option').forEach(o => {
          o.style.border = o.dataset.mode === selectedMode ? '2px solid var(--brand-primary)' : '1px solid var(--border-subtle)';
        });
        logUIEvent('onboarding_mode_selected', { mode: selectedMode });
      });
    });

    // Wire next button
    container.querySelector('#mg-onboarding-next').addEventListener('click', () => {
      if (currentScreen < SCREENS.length - 1) {
        currentScreen++;
        showOnboarding(container);
      } else {
        completeOnboarding();
      }
    });
  }

  function completeOnboarding() {
    logUIEvent('onboarding_completed', { mode: selectedMode });
    chrome.storage.local.set({
      onboardingComplete: true,
      settings: {
        mode: selectedMode,
        showThreadHealth: true,
        soundAlert: true,
        showWarningBar: true,
        enableFactChecker: selectedMode === 'memory_plus_qe',
        enableEinstein: selectedMode === 'memory_plus_qe'
      }
    });
  }

  window.__AIMEMORY_ONBOARDING = {
    show: showOnboarding,
    isComplete: async () => {
      const { onboardingComplete } = await chrome.storage.local.get('onboardingComplete');
      return !!onboardingComplete;
    }
  };
})();
