/* ============================================================
   OpsMemory — app.js
   Vanilla JavaScript for the single-page frontend
   ============================================================ */

'use strict';

const DEMO_INCIDENTS = {
  A: {
    title: 'payments-api — HikariPool connection timeout causing 5xx flood',
    service: 'payments-api',
    severity: 'SEV1',
    symptoms: '5xx error rate climbed to 40%. HikariPool-1 timeout errors in logs. Payments failing for all users.',
    error_log: `2025-09-28T08:12:15.342Z ERROR HikariPool-1 — Connection is not available, request timed out after 30000ms
2025-09-28T08:12:15.350Z ERROR com.zaxxer.hikari.pool.HikariPool — HikariPool-1 — Exception during pool initialization.
2025-09-28T08:12:15.400Z WARN payments-api-7b9d4f-xkq2p — Pool size: 20/20 active connections
2025-09-28T08:12:16.001Z ERROR payments-api-7b9d4f-xkq2p — org.postgresql.util.PSQLException: FATAL: sorry, too many clients already
2025-09-28T08:12:16.100Z ERROR payments-api-7b9d4f-xkq2p — Unable to acquire JDBC Connection
2025-09-28T08:12:16.200Z WARN k8s — HPA payments-api: 8/8 replicas at maximum, cannot scale further
2025-09-28T08:12:17.001Z ERROR nginx — upstream timed out (110: Connection timed out) while reading response header from upstream
2025-09-28T08:12:17.100Z ERROR payments-api-7b9d4f-xkq2p — Retrying DB connection... attempt 3 of 3 FAILED`
  },
  B: {
    title: 'auth-service — Redis OOM errors causing login failures',
    service: 'auth-service',
    severity: 'SEV2',
    symptoms: 'Redis OOM command not allowed when used memory > maxmemory errors causing login failures. Session writes failing.',
    error_log: `2025-09-28T10:45:02.100Z ERROR auth-service-6c8b2d-p9mn1 — OOM command not allowed when used memory > 'maxmemory'
2025-09-28T10:45:02.110Z ERROR auth-service-6c8b2d-p9mn1 — redis.clients.jedis.exceptions.JedisDataException: OOM command not allowed
2025-09-28T10:45:02.200Z WARN auth-service-6c8b2d-p9mn1 — Redis used_memory: 3.98GB / maxmemory: 4GB (99.5%)
2025-09-28T10:45:03.001Z ERROR auth-service-6c8b2d-p9mn1 — Session write failed for user_id=usr_8847: Redis out of memory
2025-09-28T10:45:03.100Z WARN auth-service-6c8b2d-p9mn1 — Cache miss rate: 87% — thundering herd on DB
2025-09-28T10:45:04.000Z ERROR auth-service-6c8b2d-p9mn1 — Login rejected: unable to create session token
2025-09-28T10:45:04.200Z WARN redis-cache-01 — eviction_stat: evicted_keys=0 (noeviction policy)`
  },
  C: {
    title: 'order-service — DB connection slots exhausted, orders failing',
    service: 'order-service',
    severity: 'SEV1',
    symptoms: 'Order creation failing with 500 errors. DB connection errors in logs. Similar pattern to previous pool exhaustion incidents.',
    error_log: `2025-09-28T14:33:11.001Z ERROR order-service-4a7c1e-wnbx3 — psycopg2.OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections
2025-09-28T14:33:11.010Z ERROR order-service-4a7c1e-wnbx3 — sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) FATAL: sorry, too many clients already
2025-09-28T14:33:11.100Z WARN order-service-4a7c1e-wnbx3 — Connection pool: 20/20 active, 34 waiting
2025-09-28T14:33:12.000Z ERROR order-service-4a7c1e-wnbx3 — TimeoutError: QueuePool limit of size 20 overflow 10 reached, connection timed out, timeout 30
2025-09-28T14:33:12.100Z ERROR order-service-4a7c1e-wnbx3 — POST /api/orders → 500 Internal Server Error
2025-09-28T14:33:12.200Z WARN k8s — order-service HPA: all 6 replicas running, each holding max connections`
  }
};

let memoryOn = true;
let currentIncidentId = null;
let historyFilter = 'all';
let historyCache = [];

const form = document.getElementById('incident-form');
const demoSelect = document.getElementById('demo-select');
const memoryToggle = document.getElementById('memory-toggle');
const memoryLabel = document.getElementById('memory-label');
const btnAnalyze = document.getElementById('btn-analyze');

const diagEmpty = document.getElementById('diag-empty');
const diagLoading = document.getElementById('diag-loading');
const diagResults = document.getElementById('diag-results');

const memoryBanner = document.getElementById('memory-banner');
const resultIncidentId = document.getElementById('result-incident-id');
const resultLatency = document.getElementById('result-latency');
const resultDiagnosis = document.getElementById('result-diagnosis');
const resultRootCause = document.getElementById('result-root-cause');
const resultSteps = document.getElementById('result-steps');
const resultConfidence = document.getElementById('result-confidence');

const resolveSection = document.getElementById('resolve-section');
const resolveForm = document.getElementById('resolve-form');
const resolveIncidentId = document.getElementById('resolve-incident-id');
const resolveRootCause = document.getElementById('resolve-root-cause');
const resolveSteps = document.getElementById('resolve-steps');
const resolveMinutes = document.getElementById('resolve-minutes');
const memoryLearned = document.getElementById('memory-learned');
const memoryLearnedText = document.getElementById('memory-learned-text');

const recallEmpty = document.getElementById('recall-empty');
const recallList = document.getElementById('recall-list');

const statTotal = document.getElementById('stat-total');
const statResolved = document.getElementById('stat-resolved');
const statAvg = document.getElementById('stat-avg');
const statMemories = document.getElementById('stat-memories');
const btnReset = document.getElementById('btn-reset');
const modeBadge = document.getElementById('mode-badge');

const btnHistory = document.getElementById('btn-history');
const btnCloseHistory = document.getElementById('btn-close-history');
const historyDrawer = document.getElementById('history-drawer');
const historyBackdrop = document.getElementById('history-backdrop');
const historyList = document.getElementById('history-list');

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }
function setText(el, text) { el.textContent = text; }

function showError(msg) {
  alert(`Error: ${msg}`);
}

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const data = await res.json();
    setText(statTotal, data.total_incidents ?? '—');
    setText(statResolved, data.resolved ?? '—');
    setText(statAvg, data.avg_resolution_minutes ? `${data.avg_resolution_minutes} min` : '—');
    setText(statMemories, data.memories_retained ?? '—');
  } catch (_) { /* ignore */ }
}

async function loadHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    const data = await res.json();
    const local =
      data.demo_mode ||
      data.storage === 'local' ||
      data.memory_backend === 'local' ||
      data.llm_backend === 'local';
    if (local) {
      show(modeBadge);
      const parts = [];
      if (data.storage === 'local') parts.push('JSON store');
      if (data.memory_backend === 'local') parts.push('local memory');
      if (data.llm_backend === 'local') parts.push('local LLM');
      modeBadge.title = parts.length ? `Using ${parts.join(', ')}` : 'Local demo mode';
      modeBadge.textContent = 'Local mode';
    } else {
      hide(modeBadge);
    }
  } catch (_) { /* ignore */ }
}

memoryToggle.addEventListener('click', () => {
  memoryOn = !memoryOn;
  memoryToggle.setAttribute('aria-pressed', String(memoryOn));
  if (memoryOn) {
    memoryToggle.classList.add('memory-on');
    setText(memoryLabel, 'Memory ON');
  } else {
    memoryToggle.classList.remove('memory-on');
    setText(memoryLabel, 'Memory OFF');
  }
});

demoSelect.addEventListener('change', () => {
  const key = demoSelect.value;
  if (!key || !DEMO_INCIDENTS[key]) return;
  const demo = DEMO_INCIDENTS[key];
  document.getElementById('input-title').value = demo.title;
  document.getElementById('input-service').value = demo.service;
  document.getElementById('input-severity').value = demo.severity;
  document.getElementById('input-symptoms').value = demo.symptoms;
  document.getElementById('input-errorlog').value = demo.error_log;
  demoSelect.value = '';
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const title = document.getElementById('input-title').value.trim();
  const service = document.getElementById('input-service').value;
  const severity = document.getElementById('input-severity').value;
  const symptoms = document.getElementById('input-symptoms').value.trim();
  const error_log = document.getElementById('input-errorlog').value.trim();

  if (!title) { showError('Please enter a title.'); return; }
  if (!service) { showError('Please select a service.'); return; }
  if (!severity) { showError('Please select a severity.'); return; }

  hide(diagEmpty);
  hide(diagResults);
  show(diagLoading);
  hide(recallEmpty);
  hide(recallList);
  recallList.innerHTML = '';
  hide(memoryLearned);
  memoryLearned.classList.remove('warn');
  btnAnalyze.disabled = true;
  currentIncidentId = null;

  try {
    const res = await fetch('/api/incidents/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, service, severity, symptoms, error_log, use_memory: memoryOn })
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || data.detail || 'Analysis failed');
      hide(diagLoading);
      show(diagEmpty);
      return;
    }

    renderDiagnosis(data);
    renderRecalled(data.recalled_incidents || [], data.matched_incident_id, data.match_reason);
    currentIncidentId = data.incident_id;

    resolveIncidentId.value = data.incident_id;
    resolveRootCause.value = data.likely_root_cause || '';
    resolveSteps.value = (data.recommended_steps || []).join('\n');
    resolveMinutes.value = '';

    await loadStats();
  } catch (err) {
    showError('Network error: ' + err.message);
    hide(diagLoading);
    show(diagEmpty);
  } finally {
    btnAnalyze.disabled = false;
  }
});

function renderDiagnosis(data) {
  hide(diagLoading);
  show(diagResults);

  const used = data.memory_used;
  const recalledCount = (data.recalled_incidents || []).length;
  memoryBanner.className = 'memory-banner ' + (used ? 'on' : 'off');
  if (used) {
    memoryBanner.textContent = `Memory ON — used ${recalledCount} past incident${recalledCount !== 1 ? 's' : ''} from memory`;
  } else {
    memoryBanner.textContent = 'Memory OFF — no history used (generic diagnosis only)';
  }

  setText(resultIncidentId, data.incident_id || '—');
  setText(resultLatency, data.latency_ms ? `${data.latency_ms} ms` : '');
  setText(resultDiagnosis, data.diagnosis || '—');
  setText(resultRootCause, data.likely_root_cause || '—');

  resultSteps.innerHTML = '';
  (data.recommended_steps || []).forEach(step => {
    const li = document.createElement('li');
    li.textContent = step;
    resultSteps.appendChild(li);
  });

  const conf = (data.confidence || 'low').toLowerCase();
  resultConfidence.className = `confidence-badge confidence-${conf}`;
  setText(resultConfidence, conf.toUpperCase());

  show(resolveSection);
}

function renderRecalled(recalled, matchedId, matchReason) {
  if (!recalled || recalled.length === 0) {
    show(recallEmpty);
    hide(recallList);
    return;
  }

  hide(recallEmpty);
  recallList.innerHTML = '';
  show(recallList);

  recalled.forEach(item => {
    const isMatched = item.incident_id && item.incident_id === matchedId;
    const card = document.createElement('div');
    card.className = 'recall-card' + (isMatched ? ' matched' : '');

    const header = document.createElement('div');
    header.className = 'recall-card-header';

    const idBadge = document.createElement('span');
    idBadge.className = 'recall-id';
    idBadge.textContent = item.incident_id || 'N/A';

    const rightGroup = document.createElement('div');
    rightGroup.style.display = 'flex';
    rightGroup.style.gap = '6px';
    rightGroup.style.alignItems = 'center';

    if (isMatched) {
      const matchBadge = document.createElement('span');
      matchBadge.className = 'recall-matched-badge';
      matchBadge.textContent = '★ Best Match';
      rightGroup.appendChild(matchBadge);
    }

    if (item.score && item.score > 0) {
      const scoreBadge = document.createElement('span');
      scoreBadge.className = 'recall-score';
      scoreBadge.textContent = `score: ${Number(item.score).toFixed(2)}`;
      rightGroup.appendChild(scoreBadge);
    }

    header.appendChild(idBadge);
    header.appendChild(rightGroup);

    const textEl = document.createElement('div');
    textEl.className = 'recall-text';
    textEl.textContent = (item.text || '').substring(0, 500);

    card.appendChild(header);
    card.appendChild(textEl);

    if (isMatched && matchReason) {
      const reason = document.createElement('div');
      reason.className = 'recall-match-reason';
      reason.textContent = matchReason;
      card.appendChild(reason);
    }

    recallList.appendChild(card);
  });
}

resolveForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const incId = resolveIncidentId.value;
  const root_cause = resolveRootCause.value.trim();
  const fix_steps = resolveSteps.value.trim().split('\n').map(s => s.trim()).filter(Boolean);
  const resolution_minutes = parseInt(resolveMinutes.value, 10);

  if (!root_cause) { showError('Root cause is required.'); return; }
  if (fix_steps.length === 0) { showError('Please enter at least one fix step.'); return; }
  if (!resolution_minutes || resolution_minutes <= 0) { showError('Please enter a valid resolution time.'); return; }

  try {
    const res = await fetch(`/api/incidents/${incId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ root_cause, fix_steps, resolution_minutes })
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || data.detail || 'Resolve failed');
      return;
    }

    show(memoryLearned);
    if (data.memory_retained) {
      memoryLearned.classList.remove('warn');
      setText(
        memoryLearnedText,
        'Learned: this incident is now in memory and will help future diagnoses.'
      );
    } else {
      memoryLearned.classList.add('warn');
      setText(
        memoryLearnedText,
        'Resolved in the store, but memory retain failed — future recalls may miss this incident.'
      );
    }
    await loadStats();
  } catch (err) {
    showError('Network error: ' + err.message);
  }
});

btnReset.addEventListener('click', async () => {
  if (!confirm('Reset all incidents and re-seed demo memory? This cannot be undone.')) return;

  try {
    const res = await fetch('/api/reset?reseed=true', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) { showError('Reset failed'); return; }

    form.reset();
    memoryOn = true;
    memoryToggle.classList.add('memory-on');
    setText(memoryLabel, 'Memory ON');
    hide(diagResults);
    hide(diagLoading);
    show(diagEmpty);
    hide(recallList);
    show(recallEmpty);
    hide(memoryLearned);
    currentIncidentId = null;

    await loadStats();
    const seeded = data.reseeded && data.reseeded.seeded;
    if (seeded) {
      alert(`Demo reset complete. Re-seeded ${seeded} incidents.`);
    }
  } catch (err) {
    showError('Network error: ' + err.message);
  }
});

function openHistory() {
  show(historyDrawer);
  show(historyBackdrop);
  loadHistory();
}

function closeHistory() {
  hide(historyDrawer);
  hide(historyBackdrop);
}

async function loadHistory() {
  historyList.innerHTML = '<p class="history-empty">Loading…</p>';
  try {
    const res = await fetch('/api/incidents');
    if (!res.ok) throw new Error('Failed to load');
    const data = await res.json();
    historyCache = data.incidents || [];
    renderHistory();
  } catch (err) {
    historyList.innerHTML = `<p class="history-empty">Could not load history: ${err.message}</p>`;
  }
}

function renderHistory() {
  const filtered = historyCache.filter(inc => {
    if (historyFilter === 'all') return true;
    return (inc.status || '') === historyFilter;
  });

  if (filtered.length === 0) {
    historyList.innerHTML = '<p class="history-empty">No incidents match this filter.</p>';
    return;
  }

  historyList.innerHTML = '';
  filtered.forEach(inc => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'history-item';
    btn.innerHTML = `
      <div class="history-item-top">
        <span class="history-item-id">${inc.incident_id || '—'}</span>
        <span class="history-status ${(inc.status || 'open').toLowerCase()}">${inc.status || 'open'}</span>
      </div>
      <div class="history-item-title">${escapeHtml(inc.title || 'Untitled')}</div>
      <div class="history-item-meta">${escapeHtml(inc.service || '')} · ${escapeHtml(inc.severity || '')}</div>
    `;
    btn.addEventListener('click', () => loadIncidentIntoForm(inc));
    historyList.appendChild(btn);
  });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function loadIncidentIntoForm(inc) {
  document.getElementById('input-title').value = inc.title || '';
  document.getElementById('input-service').value = inc.service || '';
  document.getElementById('input-severity').value = inc.severity || '';
  document.getElementById('input-symptoms').value = inc.symptoms || '';
  document.getElementById('input-errorlog').value = inc.error_log || '';
  closeHistory();
}

btnHistory.addEventListener('click', openHistory);
btnCloseHistory.addEventListener('click', closeHistory);
historyBackdrop.addEventListener('click', closeHistory);

document.querySelectorAll('.filter-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    historyFilter = chip.dataset.filter || 'all';
    renderHistory();
  });
});

loadStats();
loadHealth();
