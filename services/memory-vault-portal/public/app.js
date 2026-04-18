// Memory Vault Portal — AMG AI Memory Guard
// Supabase-auth-gated SPA. RLS isolates per consumer_uid.

const CFG = window.AIMG_CONFIG;
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

els.loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  els.loginBtn.disabled = true;
  els.loginError.hidden = true;
  els.loginError.textContent = '';
  try {
    const { data, error } = await sb.auth.signInWithPassword({
      email: els.email.value.trim(),
      password: els.password.value,
    });
    if (error) throw error;
    state.user = data.user;
    showDashboard();
  } catch (err) {
    els.loginError.textContent = err.message || 'Sign-in failed.';
    els.loginError.hidden = false;
  } finally {
    els.loginBtn.disabled = false;
  }
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

// ─── Render ───
function render() {
  els.feedLoading.hidden = true;
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
  const vsLabel = vs === 'verified' ? '✓ verified' : vs === 'contradicted' ? '✗ contradicted' : '⚠ unverified';
  const ts = m.source_timestamp ? new Date(m.source_timestamp).toLocaleString() : '—';
  const platform = (m.platform || '—').toLowerCase();
  const platformLabel = {
    'claude': 'Claude.ai', 'chatgpt': 'ChatGPT', 'perplexity': 'Perplexity',
    'gemini': 'Gemini', 'grok': 'Grok', 'copilot': 'Copilot', 'amg-agents': 'AMG Agents'
  }[platform] || (m.platform || '—');
  const body = (m.content || '').trim();
  const bodyHtml = escapeHtml(body);
  const tenant = m.project_id ? `· ${escapeHtml(m.project_id)}` : '';

  return `
    <div class="memory-card${state.selectedId === m.id ? ' selected' : ''}" data-id="${escapeHtml(m.id)}">
      <div class="memory-head">
        <div class="left">
          <span class="platform-badge">${escapeHtml(platformLabel)}</span>
          <span class="verify-badge ${vs}">${vsLabel}</span>
        </div>
        <div>${escapeHtml(ts)}</div>
      </div>
      <div class="memory-body">${bodyHtml}</div>
      <div class="memory-foot">
        <span>conf ${m.confidence != null ? parseFloat(m.confidence).toFixed(2) : '—'} · exchange #${m.exchange_number ?? '—'} ${tenant}</span>
        <span>→</span>
      </div>
    </div>
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
