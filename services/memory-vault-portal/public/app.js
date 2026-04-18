// Memory Vault Portal — AMG AI Memory Guard
// Supabase-auth-gated SPA. RLS isolates per consumer_uid.

// LOAD HEARTBEAT — visible banner that proves app.js executed.
// If you don't see this banner on page load, app.js never ran in your browser.
(function heartbeat() {
  const b = document.createElement('div');
  b.id = 'aimg-heartbeat';
  b.style.cssText = 'position:fixed;bottom:0;left:0;right:0;padding:6px 14px;background:#26C6A8;color:#032D26;z-index:99999;font:12px -apple-system,sans-serif;text-align:center;';
  b.textContent = 'app.js loaded — build 2026-04-18T21:25Z — if you see this, JavaScript is running';
  (document.body || document.documentElement).appendChild(b);
  setTimeout(() => b.remove(), 6000);
})();

const CFG = window.AIMG_CONFIG || {};

// Defensive: if config is broken, make it VISIBLE instead of silently dead.
function showFatal(msg) {
  const el = document.createElement('div');
  el.style.cssText = 'position:fixed;top:0;left:0;right:0;padding:14px 20px;background:#C62828;color:#fff;z-index:9999;font:14px -apple-system,sans-serif;';
  el.textContent = 'Memory Vault failed to load: ' + msg + '. Hard-refresh (Cmd+Shift+R) or tell Titan.';
  (document.body || document.documentElement).appendChild(el);
}

if (!CFG.supabaseUrl || !CFG.supabaseAnonKey) {
  showFatal('Supabase config missing');
  throw new Error('AIMG_CONFIG missing supabaseUrl/anonKey');
}
if (typeof window.supabase === 'undefined' || !window.supabase.createClient) {
  showFatal('Supabase JS library not loaded (CDN blocked?)');
  throw new Error('supabase-js CDN failed');
}

const sb = window.supabase.createClient(CFG.supabaseUrl, CFG.supabaseAnonKey);

// ─── State ───
let state = {
  user: null,
  memories: [],
  filtered: [],
  tenants: [],
  selectedId: null,
  filters: { search: '', platform: '', verified: '', tenant: '' },
  sort: 'newest',
};

// ─── Elements ───
const $ = (id) => document.getElementById(id);

const els = {
  login: $('login-view'),
  dashboard: $('dashboard-view'),
  loginForm: $('login-form'),
  loginError: $('login-error'),
  loginBtn: $('login-btn'),
  email: $('email'),
  password: $('password'),
  logoutBtn: $('logout-btn'),
  topbarUser: $('topbar-user'),
  statTotal: $('stat-total'),
  statVerified: $('stat-verified'),
  statWeek: $('stat-week'),
  statConfidence: $('stat-confidence'),
  filterSearch: $('filter-search'),
  filterPlatform: $('filter-platform'),
  filterVerified: $('filter-verified'),
  filterTenant: $('filter-tenant'),
  resetFilters: $('reset-filters'),
  feedTitle: $('feed-title'),
  feedLoading: $('feed-loading'),
  feedEmpty: $('feed-empty'),
  feedList: $('feed-list'),
  sortBy: $('sort-by'),
  refreshBtn: $('refresh-btn'),
  detailPane: $('detail-pane'),
  detailBody: $('detail-body'),
  detailClose: $('detail-close'),
};

// ─── Auth ───
async function checkAuth() {
  const { data } = await sb.auth.getSession();
  if (data.session && data.session.user) {
    state.user = data.session.user;
    showDashboard();
  } else {
    showLogin();
  }
}

function showLogin() {
  els.login.hidden = false;
  els.dashboard.hidden = true;
}

async function showDashboard() {
  els.login.hidden = true;
  els.dashboard.hidden = false;
  els.topbarUser.textContent = state.user.email || state.user.id;
  await loadMemories();
}

function setLoginStatus(msg, isError = false) {
  els.loginError.hidden = false;
  els.loginError.textContent = msg;
  els.loginError.style.color = isError ? '#E85960' : '#9AA4BF';
}

els.loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  els.loginBtn.disabled = true;
  setLoginStatus('Connecting to Supabase…');
  try {
    const email = els.email.value.trim();
    const password = els.password.value;
    if (!email || !password) {
      setLoginStatus('Email + password required.', true);
      els.loginBtn.disabled = false;
      return;
    }
    setLoginStatus('Signing in…');
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    if (error) {
      setLoginStatus(`Auth error: ${error.message}`, true);
      els.loginBtn.disabled = false;
      return;
    }
    if (!data || !data.user) {
      setLoginStatus('Auth returned no user.', true);
      els.loginBtn.disabled = false;
      return;
    }
    setLoginStatus('Signed in. Loading memories…');
    state.user = data.user;
    await showDashboard();
  } catch (err) {
    const m = err && err.message ? err.message : String(err);
    setLoginStatus(`Unexpected: ${m}`, true);
    console.error('login error:', err);
    els.loginBtn.disabled = false;
  }
});

// Surface any uncaught error as an on-page banner so button-does-nothing is impossible.
window.addEventListener('error', (ev) => {
  const msg = ev && ev.message ? ev.message : 'unknown runtime error';
  try { showFatal('JS error: ' + msg); } catch (_) {}
});
window.addEventListener('unhandledrejection', (ev) => {
  const r = ev && ev.reason;
  const msg = r && r.message ? r.message : String(r);
  try { showFatal('Promise rejection: ' + msg); } catch (_) {}
});

els.logoutBtn.addEventListener('click', async () => {
  await sb.auth.signOut();
  state = { ...state, user: null, memories: [], filtered: [], selectedId: null };
  showLogin();
});

// ─── Data fetch ───
async function loadMemories() {
  els.feedLoading.hidden = false;
  els.feedEmpty.hidden = true;
  els.feedList.innerHTML = '';
  try {
    // Fetch memories (RLS gates to current user_id)
    const { data: memories, error } = await sb
      .from(CFG.memoriesTable)
      .select('*')
      .order('source_timestamp', { ascending: false })
      .limit(200);
    if (error) throw error;
    state.memories = (memories || []).map(m => ({
      ...m,
      // qe_status is the canonical Einstein verification field on consumer_memories
      verification_status: (m.qe_status || 'unverified').toLowerCase(),
      verification_confidence: m.confidence,
    }));

    // Build tenant filter from distinct project_id values
    const tenantSet = new Set(state.memories.map(m => m.project_id).filter(Boolean));
    state.tenants = Array.from(tenantSet).sort();
    rebuildTenantSelect();

    applyFilters();
  } catch (err) {
    els.feedLoading.textContent = `Error loading memories: ${err.message}`;
  }
}

function rebuildTenantSelect() {
  const current = els.filterTenant.value;
  const frag = document.createDocumentFragment();
  const all = document.createElement('option');
  all.value = '';
  all.textContent = 'All tenants';
  frag.appendChild(all);
  for (const t of state.tenants) {
    const o = document.createElement('option');
    o.value = t;
    o.textContent = t;
    frag.appendChild(o);
  }
  els.filterTenant.innerHTML = '';
  els.filterTenant.appendChild(frag);
  els.filterTenant.value = state.tenants.includes(current) ? current : '';
}

// ─── Filter + sort ───
function applyFilters() {
  const f = state.filters;
  let list = state.memories.slice();

  if (f.search) {
    const q = f.search.toLowerCase();
    list = list.filter(m => (m.content || '').toLowerCase().includes(q) || (m.thread_url || '').toLowerCase().includes(q));
  }
  if (f.platform) list = list.filter(m => (m.platform || '').toLowerCase() === f.platform);
  if (f.verified) list = list.filter(m => (m.verification_status || 'unverified').toLowerCase() === f.verified);
  if (f.tenant) list = list.filter(m => m.project_id === f.tenant);

  switch (state.sort) {
    case 'oldest': list.sort((a, b) => new Date(a.source_timestamp) - new Date(b.source_timestamp)); break;
    case 'confidence': list.sort((a, b) => (b.confidence || 0) - (a.confidence || 0)); break;
    default: list.sort((a, b) => new Date(b.source_timestamp) - new Date(a.source_timestamp));
  }

  state.filtered = list;
  render();
}

// ─── Filter chips rendering ───
function renderFilterChips() {
  const chipsEl = document.getElementById('filter-chips-row');
  if (!chipsEl) return;

  const total = state.memories.length;
  const verified = state.memories.filter(m => (m.verification_status || '').toLowerCase() === 'verified').length;
  const contradicted = state.memories.filter(m => (m.verification_status || '').toLowerCase() === 'contradicted').length;

  const activeVerify = state.filters.verified;
  const activePlatform = state.filters.platform;
  const activeTenant = state.filters.tenant;

  const platforms = [
    { k: '', label: 'All LLMs', n: total },
    ...Array.from(new Set(state.memories.map(m => (m.platform || '').toLowerCase()).filter(Boolean)))
      .map(p => ({ k: p, label: { claude: 'Claude', chatgpt: 'ChatGPT', perplexity: 'Perplexity', gemini: 'Gemini', grok: 'Grok', copilot: 'Copilot', 'amg-agents': 'AMG Agents' }[p] || p, n: state.memories.filter(m => (m.platform || '').toLowerCase() === p).length })),
  ];

  const tenants = Array.from(new Set(state.memories.map(m => m.project_id).filter(Boolean))).sort();

  const html = [
    `<button class="filter-chip ${!activeVerify && !activePlatform && !activeTenant ? 'active' : ''}" data-action="reset-all">All <span class="chip-count">${total}</span></button>`,
    `<button class="filter-chip verify-chip ${activeVerify === 'verified' ? 'active' : ''}" data-action="verify" data-value="verified">✓ Verified <span class="chip-count">${verified}</span></button>`,
    `<button class="filter-chip contradict-chip ${activeVerify === 'contradicted' ? 'active' : ''}" data-action="verify" data-value="contradicted">✗ Contradicted <span class="chip-count">${contradicted}</span></button>`,
    '<span class="filter-chip-sep" style="color:var(--text-faint);padding:0 4px;align-self:center;">·</span>',
    ...platforms.slice(1).map(p => `<button class="filter-chip llm-filter-chip ${activePlatform === p.k ? 'active' : ''}" data-action="platform" data-value="${escapeHtml(p.k)}">${escapeHtml(p.label)} <span class="chip-count">${p.n}</span></button>`),
  ];
  if (tenants.length > 0) {
    html.push('<span class="filter-chip-sep" style="color:var(--text-faint);padding:0 4px;align-self:center;">·</span>');
    html.push(...tenants.map(t => `<button class="filter-chip ${activeTenant === t ? 'active' : ''}" data-action="tenant" data-value="${escapeHtml(t)}">${escapeHtml(t)}</button>`));
  }

  chipsEl.innerHTML = html.join('');
  chipsEl.querySelectorAll('.filter-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const action = btn.dataset.action;
      const value = btn.dataset.value || '';
      if (action === 'reset-all') {
        state.filters = { search: state.filters.search, platform: '', verified: '', tenant: '' };
        els.filterPlatform.value = '';
        els.filterVerified.value = '';
        els.filterTenant.value = '';
      } else if (action === 'verify') {
        state.filters.verified = state.filters.verified === value ? '' : value;
        els.filterVerified.value = state.filters.verified;
      } else if (action === 'platform') {
        state.filters.platform = state.filters.platform === value ? '' : value;
        els.filterPlatform.value = state.filters.platform;
      } else if (action === 'tenant') {
        state.filters.tenant = state.filters.tenant === value ? '' : value;
        els.filterTenant.value = state.filters.tenant;
      }
      applyFilters();
    });
  });
}

// ─── Render ───
function render() {
  els.feedLoading.hidden = true;
  renderFilterChips();
  if (state.filtered.length === 0) {
    els.feedEmpty.hidden = false;
    els.feedList.innerHTML = '';
  } else {
    els.feedEmpty.hidden = true;
    els.feedList.innerHTML = state.filtered.map(renderCard).join('');
    els.feedList.querySelectorAll('.memory-card').forEach(el => {
      el.addEventListener('click', () => {
        const id = el.dataset.id;
        selectMemory(id);
      });
    });
  }
  // Stats
  els.statTotal.textContent = `${state.memories.length} memor${state.memories.length === 1 ? 'y' : 'ies'}`;
  const verified = state.memories.filter(m => (m.verification_status || '').toLowerCase() === 'verified').length;
  els.statVerified.textContent = `${verified} verified`;
  els.feedTitle.textContent = state.filtered.length === state.memories.length
    ? 'Memory feed'
    : `Memory feed — ${state.filtered.length} of ${state.memories.length}`;

  const weekAgo = Date.now() - 7 * 86400 * 1000;
  const week = state.memories.filter(m => new Date(m.source_timestamp).getTime() > weekAgo).length;
  els.statWeek.textContent = week;

  const confs = state.memories.map(m => parseFloat(m.confidence)).filter(x => !isNaN(x));
  const avg = confs.length ? (confs.reduce((a, b) => a + b, 0) / confs.length) : null;
  els.statConfidence.textContent = avg !== null ? avg.toFixed(2) : '—';
}

function renderCard(m) {
  const vs = (m.verification_status || 'unverified').toLowerCase();
  const platform = (m.platform || '').toLowerCase();
  const platformLabel = {
    'claude': 'Claude', 'chatgpt': 'ChatGPT', 'perplexity': 'Perplexity',
    'gemini': 'Gemini', 'grok': 'Grok', 'copilot': 'Copilot', 'amg-agents': 'AMG Agents'
  }[platform] || (m.platform || 'Source');

  const ts = m.source_timestamp ? new Date(m.source_timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—';
  const body = (m.content || '').trim();
  const bodyHtml = escapeHtml(body);

  const conf = m.confidence != null ? parseFloat(m.confidence) : null;
  const confPct = conf != null ? Math.max(0, Math.min(1, conf)) * 100 : 0;
  const confBand = conf == null ? 'none' : conf >= 0.85 ? 'high' : conf >= 0.60 ? 'mid' : 'low';
  const confLabel = conf != null ? `${Math.round(confPct)}% confidence` : 'No confidence score';

  const pillMap = {
    verified: { cls: 'verified', glyph: '✓', text: 'VERIFIED' },
    contradicted: { cls: 'contradicted', glyph: '✗', text: 'CONTRADICTED' },
    unverified: { cls: 'unverified', glyph: '⚠', text: 'UNVERIFIED' },
  };
  const pill = pillMap[vs] || pillMap.unverified;

  const tenant = m.project_id ? `<span class="card-tenant">${escapeHtml(m.project_id)}</span>` : '';

  return `
    <article class="memory-card${state.selectedId === m.id ? ' selected' : ''}" data-id="${escapeHtml(m.id)}">
      <header class="card-head">
        <span class="llm-chip llm-${platform}">${escapeHtml(platformLabel)}</span>
        <span class="verify-pill verify-${pill.cls}"><span class="glyph">${pill.glyph}</span>${pill.text}</span>
      </header>
      <div class="card-body">${bodyHtml}</div>
      <div class="card-meta-row">
        <span class="card-time">${escapeHtml(ts)}</span>
        ${tenant}
      </div>
      <div class="conf-bar conf-${confBand}" title="${escapeHtml(confLabel)}">
        <div class="conf-fill" style="width:${confPct}%"></div>
        <span class="conf-label">${escapeHtml(confLabel)}</span>
      </div>
    </article>
  `;
}

function selectMemory(id) {
  state.selectedId = id;
  const m = state.memories.find(x => x.id === id);
  if (!m) return;
  els.detailPane.hidden = false;
  els.detailBody.innerHTML = `
    <div class="detail-section">
      <h4>Platform · exchange #${m.exchange_number ?? '—'}</h4>
      <div class="content">${escapeHtml(m.platform || '—')}</div>
    </div>
    <div class="detail-section">
      <h4>Captured at</h4>
      <div class="content">${escapeHtml(m.source_timestamp ? new Date(m.source_timestamp).toLocaleString() : '—')}</div>
    </div>
    <div class="detail-section">
      <h4>Content</h4>
      <div class="content">${escapeHtml(m.content || '')}</div>
    </div>
    <div class="detail-section">
      <h4>Source thread</h4>
      <div class="content"><a href="${escapeHtml(m.thread_url || '#')}" target="_blank" rel="noopener">${escapeHtml(m.thread_url || '—')}</a></div>
    </div>
    <div class="detail-section">
      <h4>Einstein verification</h4>
      <div class="content">
        Status: <strong>${escapeHtml((m.verification_status || 'unverified').toLowerCase())}</strong><br>
        ${m.verification_confidence != null ? `Confidence: ${parseFloat(m.verification_confidence).toFixed(2)}` : 'No deep-check recorded.'}
      </div>
    </div>
    <div class="detail-section">
      <h4>Provenance metadata</h4>
      <div class="detail-meta">
        <div>memory_id: <code>${escapeHtml(m.id || '')}</code></div>
        <div>thread_id: <code>${escapeHtml(m.thread_id || '—')}</code></div>
        <div>project_id: <code>${escapeHtml(m.project_id || '—')}</code></div>
        <div>confidence: <code>${m.confidence != null ? parseFloat(m.confidence).toFixed(3) : '—'}</code></div>
      </div>
    </div>
  `;
  render();
}

els.detailClose.addEventListener('click', () => {
  state.selectedId = null;
  els.detailPane.hidden = true;
  render();
});

// ─── Filter wiring ───
let searchTimeout = null;
els.filterSearch.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    state.filters.search = els.filterSearch.value;
    applyFilters();
  }, 180);
});
els.filterPlatform.addEventListener('change', () => { state.filters.platform = els.filterPlatform.value; applyFilters(); });
els.filterVerified.addEventListener('change', () => { state.filters.verified = els.filterVerified.value; applyFilters(); });
els.filterTenant.addEventListener('change', () => { state.filters.tenant = els.filterTenant.value; applyFilters(); });
els.resetFilters.addEventListener('click', () => {
  state.filters = { search: '', platform: '', verified: '', tenant: '' };
  els.filterSearch.value = '';
  els.filterPlatform.value = '';
  els.filterVerified.value = '';
  els.filterTenant.value = '';
  applyFilters();
});
els.sortBy.addEventListener('change', () => { state.sort = els.sortBy.value; applyFilters(); });
els.refreshBtn.addEventListener('click', () => loadMemories());

// ─── Util ───
function escapeHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ─── Auth state listener ───
sb.auth.onAuthStateChange((event, session) => {
  if (event === 'SIGNED_OUT' || !session) showLogin();
});

// ─── Boot ───
checkAuth();
