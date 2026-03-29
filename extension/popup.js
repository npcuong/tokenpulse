/**
 * TokenPulse — Popup script
 *
 * Reads cached usage from chrome.storage.local and renders the UI.
 * Also pings localhost:7777/api/status to show connectivity.
 */

const API_BASE = 'http://localhost:7777';

const PROVIDERS = [
  { key: 'claude', label: 'Claude',   dashUrl: 'https://console.anthropic.com/settings/usage' },
  { key: 'openai', label: 'ChatGPT',  dashUrl: 'https://platform.openai.com/account/usage'    },
  { key: 'gemini', label: 'Gemini',   dashUrl: 'https://aistudio.google.com/'                  },
];

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Format a token count as a compact string: 1234567 → "1.2M" */
function fmtTokens(n) {
  if (!n && n !== 0) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

/** Format a dollar amount */
function fmtDollars(n) {
  if (!n && n !== 0) return '—';
  return `$${n.toFixed(2)}`;
}

/** Format elapsed time: "2 min ago", "just now", etc. */
function fmtAge(ts) {
  if (!ts) return 'never';
  const secs = Math.floor((Date.now() - ts) / 1000);
  if (secs < 10)  return 'just now';
  if (secs < 60)  return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}

/** Set progress bar value and apply color class */
function setBar(barEl, pct) {
  barEl.value = Math.min(100, Math.max(0, pct));
  barEl.classList.remove('warn', 'danger');
  if (pct >= 90)      barEl.classList.add('danger');
  else if (pct >= 75) barEl.classList.add('warn');
}

// ─── Render a single provider card ──────────────────────────────────────────

function renderProvider(data, key) {
  const barEl     = document.getElementById(`bar-${key}`);
  const pctEl     = document.getElementById(`pct-${key}`);
  const numsEl    = document.getElementById(`nums-${key}`);
  const updatedEl = document.getElementById(`updated-${key}`);

  if (!data) {
    setBar(barEl, 0);
    pctEl.textContent  = '—';
    numsEl.textContent = 'No data yet — visit the dashboard';
    updatedEl.textContent = 'never';
    return;
  }

  updatedEl.textContent = fmtAge(data.updatedAt);

  const isOpenAI = key === 'openai';

  if (isOpenAI) {
    // Cost-based display
    const used  = data.cost_used  ?? 0;
    const limit = data.cost_limit ?? 0;
    const pct   = limit > 0 ? (used / limit) * 100 : 0;

    setBar(barEl, pct);
    pctEl.textContent = limit > 0 ? `${pct.toFixed(0)}%` : '—';
    numsEl.textContent = limit > 0
      ? `${fmtDollars(used)} / ${fmtDollars(limit)}`
      : `${fmtDollars(used)} used`;
  } else {
    // Token-based display
    const used  = data.used  ?? 0;
    const limit = data.limit ?? 0;
    const pct   = limit > 0 ? (used / limit) * 100 : 0;

    setBar(barEl, pct);
    pctEl.textContent = limit > 0 ? `${pct.toFixed(0)}%` : '—';
    numsEl.textContent = limit > 0
      ? `${fmtTokens(used)} / ${fmtTokens(limit)} tokens`
      : `${fmtTokens(used)} tokens used`;
  }
}

// ─── App status ──────────────────────────────────────────────────────────────

async function checkAppStatus() {
  const statusEl   = document.getElementById('app-status');
  const labelEl    = statusEl.querySelector('.status-label');

  try {
    const resp = await fetch(`${API_BASE}/api/status`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000),
    });

    if (resp.ok) {
      statusEl.className  = 'app-status status-connected';
      labelEl.textContent = 'Connected';
    } else {
      throw new Error('non-ok');
    }
  } catch (_) {
    statusEl.className  = 'app-status status-disconnected';
    labelEl.textContent = 'Disconnected';
  }
}

// ─── Refresh button — open all dashboards ────────────────────────────────────

document.getElementById('btn-refresh').addEventListener('click', () => {
  for (const p of PROVIDERS) {
    chrome.tabs.create({ url: p.dashUrl, active: false });
  }
  window.close();
});

// ─── Boot ────────────────────────────────────────────────────────────────────

async function init() {
  // Load cached storage
  const keys   = PROVIDERS.map(p => `usage_${p.key}`);
  const stored = await chrome.storage.local.get(keys);

  for (const p of PROVIDERS) {
    renderProvider(stored[`usage_${p.key}`] || null, p.key);
  }

  // Ping app asynchronously
  checkAppStatus();
}

init();
