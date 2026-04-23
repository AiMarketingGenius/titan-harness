/**
 * Popup Script — handles UI rendering and user interaction
 *
 * CT-0416-07 (2026-04-16): loadStats() now also renders a truthful sync indicator
 * (last saved at / pending queue size / error) so the popup stops lying when sync fails.
 */

const API_URL = 'https://gaybcxzrzfgvcqpkbeiq.supabase.co';
const API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdheWJjeHpyemZndmNxcGtiZWlxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU0MzA4MDEsImV4cCI6MjA5MTAwNjgwMX0.1sNlNDkvJ3n6Y9ZDkxBa1c8el_2Gre6lCFdN7wMvJdA';

let isSignupMode = false;

document.addEventListener('DOMContentLoaded', async () => {
  const { token, user } = await chrome.storage.local.get(['token', 'user']);

  if (token && user) {
    showApp(user);
    loadStats();
    loadRecentMemories();
    loadSyncStatus();
  } else {
    showAuth();
    loadSyncStatus();
  }

  // Search handler
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    let searchTimeout;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        const query = searchInput.value.trim();
        if (query.length >= 3) {
          searchMemories(query);
        } else if (query.length === 0) {
          loadRecentMemories();
        }
      }, 300);
    });
  }

  // Auth form handler
  document.getElementById('auth-form')?.addEventListener('submit', handleAuthSubmit);

  // Auth toggle (login/signup switch)
  document.getElementById('auth-toggle-link')?.addEventListener('click', (e) => {
    e.preventDefault();
    isSignupMode = !isSignupMode;
    const submitBtn = document.getElementById('auth-submit-btn');
    const toggleText = document.getElementById('auth-toggle-text');
    const toggleLink = document.getElementById('auth-toggle-link');
    if (isSignupMode) {
      submitBtn.textContent = 'Create Account';
      toggleText.textContent = 'Already have an account?';
      toggleLink.textContent = 'Sign in';
    } else {
      submitBtn.textContent = 'Sign In';
      toggleText.textContent = 'No account yet?';
      toggleLink.textContent = 'Sign up free';
    }
    hideAuthError();
  });

  // Logout handler
  document.getElementById('logout-btn')?.addEventListener('click', handleLogout);

  // Settings link handler
  document.getElementById('settings-link')?.addEventListener('click', (e) => {
    e.preventDefault();
    showSettings();
  });

  // Settings back button
  document.getElementById('settings-back')?.addEventListener('click', () => {
    hideSettings();
  });

  // Settings save
  document.getElementById('settings-save')?.addEventListener('click', async (e) => {
    e.preventDefault();
    const settings = {
      showThreadHealth: document.getElementById('setting-thread-health').checked,
      soundAlert: document.getElementById('setting-sound').checked,
      showWarningBar: document.getElementById('setting-warning-bar').checked,
      enableFactChecker: document.getElementById('setting-fact-checker').checked
    };
    await chrome.storage.local.set({ settings });
    hideSettings();
  });

  // Force-drain button — lets Solon trigger a sync on demand if queue has backlog.
  document.getElementById('sync-retry-btn')?.addEventListener('click', async (e) => {
    e.preventDefault();
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = 'Syncing…';
    try {
      await chrome.runtime.sendMessage({ type: 'DRAIN_QUEUE_NOW' });
      await loadSyncStatus();
      await loadStats();
    } finally {
      btn.disabled = false;
      btn.textContent = 'Retry sync';
    }
  });
});

function showApp(user) {
  document.getElementById('auth-section').style.display = 'none';
  document.getElementById('app-section').style.display = 'block';
  document.getElementById('header-actions').style.display = 'flex';
  document.getElementById('settings-panel').style.display = 'none';

  const tierBadge = document.getElementById('tier-badge');
  const tier = user.tier || 'free';
  tierBadge.textContent = tier === 'pro_plus' ? 'PRO+' : tier.toUpperCase();
  tierBadge.className = `tier-badge tier-${tier === 'pro_plus' ? 'proplus' : tier}`;
}

function showAuth() {
  document.getElementById('auth-section').style.display = 'block';
  document.getElementById('app-section').style.display = 'none';
  document.getElementById('header-actions').style.display = 'none';
  document.getElementById('settings-panel').style.display = 'none';
}

function showSettings() {
  document.getElementById('app-section').style.display = 'none';
  document.getElementById('settings-panel').style.display = 'block';

  // Load current settings
  chrome.storage.local.get('settings', ({ settings }) => {
    if (settings) {
      document.getElementById('setting-thread-health').checked = settings.showThreadHealth !== false;
      document.getElementById('setting-sound').checked = settings.soundAlert !== false;
      document.getElementById('setting-warning-bar').checked = settings.showWarningBar !== false;
      document.getElementById('setting-fact-checker').checked = settings.enableFactChecker !== false;
    }
  });
}

function hideSettings() {
  document.getElementById('settings-panel').style.display = 'none';
  document.getElementById('app-section').style.display = 'block';
}

function showAuthError(msg) {
  const el = document.getElementById('auth-error');
  el.textContent = msg;
  el.style.display = 'block';
}

function hideAuthError() {
  document.getElementById('auth-error').style.display = 'none';
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const submitBtn = document.getElementById('auth-submit-btn');

  if (!email || !password) return;

  hideAuthError();
  submitBtn.disabled = true;
  submitBtn.textContent = isSignupMode ? 'Creating...' : 'Signing in...';

  try {
    if (isSignupMode) {
      await doSignup(email, password);
    } else {
      await doLogin(email, password);
    }
  } catch (err) {
    showAuthError('Connection error. Please try again.');
    console.error('[Popup] Auth error:', err);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = isSignupMode ? 'Create Account' : 'Sign In';
  }
}

async function doLogin(email, password) {
  const res = await fetch(`${API_URL}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': API_KEY
    },
    body: JSON.stringify({ email, password })
  });

  if (!res.ok) {
    const err = await res.json();
    showAuthError(err.error_description || err.msg || 'Login failed');
    return;
  }

  const data = await res.json();
  await chrome.storage.local.set({
    token: data.access_token,
    refresh_token: data.refresh_token,
    user: data.user
  });

  // Fetch user tier info
  const userRes = await fetch(
    `${API_URL}/rest/v1/users?id=eq.${data.user.id}&select=*`,
    {
      headers: {
        'apikey': API_KEY,
        'Authorization': `Bearer ${data.access_token}`
      }
    }
  );

  if (userRes.ok) {
    const users = await userRes.json();
    if (users.length > 0) {
      await chrome.storage.local.set({ user: { ...data.user, ...users[0] } });
    }
  }

  // Let the service worker drain any memories that piled up while we were signed out.
  chrome.runtime.sendMessage({ type: 'AUTH_RESTORED' }).catch(() => {});

  location.reload();
}

async function doSignup(email, password) {
  if (password.length < 6) {
    showAuthError('Password must be at least 6 characters');
    return;
  }

  const res = await fetch(`${API_URL}/auth/v1/signup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': API_KEY
    },
    body: JSON.stringify({ email, password })
  });

  if (!res.ok) {
    const err = await res.json();
    showAuthError(err.error_description || err.msg || 'Signup failed');
    return;
  }

  // Switch to login mode and show success
  isSignupMode = false;
  document.getElementById('auth-submit-btn').textContent = 'Sign In';
  document.getElementById('auth-toggle-text').textContent = 'No account yet?';
  document.getElementById('auth-toggle-link').textContent = 'Sign up free';
  showAuthError('');
  const errorEl = document.getElementById('auth-error');
  errorEl.style.display = 'block';
  errorEl.style.color = '#4ade80';
  errorEl.textContent = 'Account created! Check your email to confirm, then sign in.';
}

async function handleLogout() {
  await chrome.storage.local.remove(['token', 'refresh_token', 'user']);
  showAuth();
}

async function loadStats() {
  try {
    const swStats = await chrome.runtime.sendMessage({ type: 'GET_STATS' });
    const { token } = await chrome.storage.local.get('token');
    if (!token) return;

    const countRes = await fetch(
      `${API_URL}/rest/v1/consumer_memories?select=id&limit=1`,
      {
        headers: {
          'apikey': API_KEY,
          'Authorization': `Bearer ${token}`,
          'Prefer': 'count=exact'
        }
      }
    );

    const memoryCount = countRes.headers.get('content-range')?.split('/')[1] || swStats.hotCacheSize || 0;
    document.getElementById('stat-memories').textContent = memoryCount;

    const sessionRes = await fetch(
      `${API_URL}/rest/v1/sessions?select=id&limit=1`,
      {
        headers: {
          'apikey': API_KEY,
          'Authorization': `Bearer ${token}`,
          'Prefer': 'count=exact'
        }
      }
    );

    const sessionCount = sessionRes.headers.get('content-range')?.split('/')[1] || '0';
    document.getElementById('stat-sessions').textContent = sessionCount;

    const { user } = await chrome.storage.local.get('user');
    if (user) {
      const limit = user.weekly_limit || 50;
      // Live query — user.memories_this_week is set at login and never updated.
      const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
      const weeklyRes = await fetch(
        `${API_URL}/rest/v1/consumer_memories?select=id&limit=1&created_at=gte.${sevenDaysAgo}`,
        {
          headers: {
            'apikey': API_KEY,
            'Authorization': `Bearer ${token}`,
            'Prefer': 'count=exact'
          }
        }
      );
      const used = parseInt(weeklyRes.headers.get('content-range')?.split('/')[1] || '0', 10);
      document.getElementById('stat-weekly').textContent = `${used}/${limit}`;
    }

    // Integration feedback toast (post-CT-0417-10b brand polish):
    // captured = total captured this session ; available = memories
    // queryable by Atlas agents. Both pull from the same count endpoints
    // used above + the service-worker hot cache.
    const intCapturedEl = document.getElementById('int-captured');
    const intAvailableEl = document.getElementById('int-available');
    if (intCapturedEl) {
      const captured = swStats?.sessionCapturedCount ?? memoryCount;
      intCapturedEl.textContent = `${captured} captured`;
    }
    if (intAvailableEl) {
      intAvailableEl.textContent = `${memoryCount} available`;
    }
  } catch (err) {
    console.error('[Popup] Stats error:', err);
  }
}

/**
 * Render the honest sync indicator — asks the SW for last_sync_at / status / pending size.
 * This is what the product should always have shown: a zero counter + silent "Connected"
 * badge was the lie that CT-0416-07 is here to remove.
 */
async function loadSyncStatus() {
  try {
    const status = await chrome.runtime.sendMessage({ type: 'GET_SYNC_STATUS' });
    if (!status) return;

    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const lastSavedEl = document.getElementById('last-saved');
    const pendingBadge = document.getElementById('pending-badge');
    const retryBtn = document.getElementById('sync-retry-btn');

    if (statusDot && statusText) {
      if (status.last_sync_status === 'success') {
        statusDot.style.background = '#22c55e';
        statusText.textContent = 'Syncing live';
      } else if (status.last_sync_status === 'queued') {
        statusDot.style.background = '#f59e0b';
        statusText.textContent = 'Queued for sync';
      } else if (status.last_sync_status === 'no_auth') {
        statusDot.style.background = '#f59e0b';
        statusText.textContent = 'Sign in to sync';
      } else if (status.last_sync_status === 'error') {
        statusDot.style.background = '#ef4444';
        statusText.textContent = 'Sync paused';
      } else {
        statusDot.style.background = '#64748b';
        statusText.textContent = 'Idle';
      }
    }

    if (lastSavedEl) {
      if (status.last_sync_at) {
        const ago = formatTimeAgo(status.last_sync_at);
        lastSavedEl.textContent = `Last saved ${ago}`;
        lastSavedEl.style.color = '#94a3b8';
      } else if (status.last_sync_status === 'no_auth') {
        lastSavedEl.textContent = 'Not signed in — memories held locally';
        lastSavedEl.style.color = '#f59e0b';
      } else {
        lastSavedEl.textContent = 'No memories saved yet';
        lastSavedEl.style.color = '#64748b';
      }
    }

    if (pendingBadge) {
      if (status.pending_queue_size > 0) {
        pendingBadge.textContent = `${status.pending_queue_size} pending`;
        pendingBadge.style.display = 'inline-flex';
        if (retryBtn) retryBtn.style.display = 'inline-flex';
      } else {
        pendingBadge.style.display = 'none';
        if (retryBtn) retryBtn.style.display = 'none';
      }
    }

    // Surface the underlying error so the user knows what actually went wrong.
    const errorEl = document.getElementById('sync-error-detail');
    if (errorEl) {
      if (status.last_sync_error && status.last_sync_status === 'error') {
        errorEl.textContent = `Reason: ${truncate(status.last_sync_error, 140)}`;
        errorEl.style.display = 'block';
      } else {
        errorEl.style.display = 'none';
      }
    }
  } catch (err) {
    console.error('[Popup] Sync status error:', err);
  }
}

async function loadRecentMemories() {
  try {
    const { token } = await chrome.storage.local.get('token');
    if (!token) {
      const { memories } = await chrome.runtime.sendMessage({ type: 'GET_HOT_CACHE' });
      renderMemories(memories || []);
      return;
    }

    const res = await fetch(
      `${API_URL}/rest/v1/consumer_memories?order=created_at.desc&limit=20`,
      {
        headers: {
          'apikey': API_KEY,
          'Authorization': `Bearer ${token}`
        }
      }
    );

    if (res.ok) {
      const memories = await res.json();
      renderMemories(memories);
    }
  } catch (err) {
    console.error('[Popup] Load memories error:', err);
  }
}

async function searchMemories(query) {
  try {
    const results = await chrome.runtime.sendMessage({
      type: 'SEARCH_MEMORIES',
      query: query,
      limit: 20
    });

    renderMemories(results.results || []);
  } catch (err) {
    console.error('[Popup] Search error:', err);
  }
}

function renderMemories(memories) {
  const list = document.getElementById('memory-list');

  if (!memories || memories.length === 0) {
    list.innerHTML = '<div class="empty-state"><div class="icon">&#x1f9e0;</div><p>No memories yet. Start a conversation on any AI platform.</p></div>';
    return;
  }

  list.innerHTML = memories.map(m => {
    const type = m.memory_type || m.type || 'fact';
    const platform = m.platform || m.provenance?.platform || 'unknown';
    const timestamp = m.source_timestamp || m.provenance?.timestamp || m.created_at;
    const timeAgo = formatTimeAgo(timestamp);

    return `
      <div class="memory-item">
        <span class="type-badge type-${type}">${type}</span>
        <div style="margin-top: 6px;">${escapeHtml(m.content)}</div>
        <div class="meta">
          <span>${platform} ${m.thread_id ? '&#183; Thread ' + m.thread_id.substring(0, 8) : ''}</span>
          <span>${timeAgo}</span>
        </div>
      </div>
    `;
  }).join('');
}

function formatTimeAgo(timestamp) {
  if (!timestamp) return '';
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function truncate(text, max) {
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
