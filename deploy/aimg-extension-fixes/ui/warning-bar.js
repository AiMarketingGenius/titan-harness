/**
 * C6: Persistent bottom warning bar
 */
(function() {
  'use strict';

  function createWarningBar() {
    // Check if user has disabled it
    chrome.storage.local.get('settings', (result) => {
      if (result?.settings?.showWarningBar === false) return;

      // Check if collapsed this session
      chrome.storage.session.get('warningBarCollapsed', (s) => {
        const bar = document.createElement('div');
        bar.className = 'mg-warning-bar mg-extension' + (s.warningBarCollapsed ? ' collapsed' : '');
        bar.innerHTML = `
          <span>ℹ️ AI can make mistakes. Please double-check all responses.</span>
          <span style="margin-left: auto;">Powered by <a href="#">AI Memory Guard</a></span>
          <button class="mg-warning-bar-collapse" title="Collapse">—</button>
        `;

        bar.querySelector('.mg-warning-bar-collapse').addEventListener('click', () => {
          bar.classList.toggle('collapsed');
          chrome.storage.session.set({ warningBarCollapsed: bar.classList.contains('collapsed') });
        });

        document.body.appendChild(bar);
      });
    });
  }

  // Delay 2 seconds after page load
  setTimeout(createWarningBar, 2000);
})();
