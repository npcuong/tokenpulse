/**
 * TokenPulse — Background service worker (Manifest V3)
 *
 * Responsibilities:
 *  - Receive usage messages from content scripts
 *  - Forward data to localhost:7777
 *  - Cache last-known usage in chrome.storage.local
 *  - Open the relevant dashboard when extension icon is clicked and data is stale
 */

const API_BASE  = 'http://localhost:7777';
const STALE_MS  = 30 * 60 * 1000; // 30 minutes

const DASHBOARD_URLS = {
  claude: 'https://console.anthropic.com/settings/usage',
  openai: 'https://platform.openai.com/account/usage',
  gemini: 'https://aistudio.google.com/',
};

// ─── Message listener (from content scripts) ─────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'USAGE_DATA') {
    handleUsageData(message.payload);
    sendResponse({ ok: true });
  }
  // Return true to keep the message channel open for async responses
  return true;
});

// ─── Handle usage payload ────────────────────────────────────────────────────

async function handleUsageData(payload) {
  if (!payload || !payload.provider) return;

  const provider = payload.provider;
  const now      = Date.now();

  // Save to local storage with timestamp
  const entry = { ...payload, updatedAt: now };
  await chrome.storage.local.set({ [`usage_${provider}`]: entry });

  console.log(`[TokenPulse][BG] Cached usage for ${provider}:`, entry);

  // Forward to TokenPulse app
  try {
    const resp = await fetch(`${API_BASE}/api/usage`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    if (resp.ok) {
      console.log(`[TokenPulse][BG] Successfully sent ${provider} data to app.`);
    }
  } catch (_err) {
    // Silently fail — app may not be running
  }
}

// ─── Icon click — open dashboard if data is stale ────────────────────────────

chrome.action.onClicked.addListener(async () => {
  const now    = Date.now();
  const stored = await chrome.storage.local.get([
    'usage_claude',
    'usage_openai',
    'usage_gemini',
  ]);

  // Find the provider whose data is most stale (or missing)
  let stalestProvider = null;
  let stalestAge      = -1;

  for (const provider of ['claude', 'openai', 'gemini']) {
    const entry = stored[`usage_${provider}`];
    const age   = entry ? now - entry.updatedAt : Infinity;
    if (age > stalestAge) {
      stalestAge      = age;
      stalestProvider = provider;
    }
  }

  if (stalestProvider && stalestAge > STALE_MS) {
    chrome.tabs.create({ url: DASHBOARD_URLS[stalestProvider] });
  }
  // If all data is fresh, the popup.html will open automatically (action popup)
});

// ─── Periodic ping to app to check connectivity ──────────────────────────────

async function pingApp() {
  try {
    const resp = await fetch(`${API_BASE}/api/status`, { method: 'GET' });
    const connected = resp.ok;
    await chrome.storage.local.set({ appConnected: connected, appPingedAt: Date.now() });
  } catch (_err) {
    await chrome.storage.local.set({ appConnected: false, appPingedAt: Date.now() });
  }
}

// Ping on startup and every 60 seconds via alarms
chrome.runtime.onInstalled.addListener(() => {
  pingApp();
  chrome.alarms.create('pingApp', { periodInMinutes: 1 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'pingApp') pingApp();
});

// Also ping when service worker wakes
pingApp();
