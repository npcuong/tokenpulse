/**
 * TokenPulse — Claude content script
 * Injected on: https://console.anthropic.com/settings/usage*
 *
 * Parses monthly token usage and sends it to the TokenPulse menu bar app.
 */

const TP_PREFIX = '[TokenPulse][Claude]';
const API_URL   = 'http://localhost:7777/api/usage';

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Strip commas and parse an integer from a string like "1,234,567" */
function parseTokenNumber(str) {
  if (!str) return null;
  const cleaned = str.replace(/,/g, '').trim();
  const n = parseInt(cleaned, 10);
  return isNaN(n) ? null : n;
}

/**
 * POST usage payload to localhost. Fail silently if app is not running.
 */
function sendToTokenPulse(payload) {
  console.log(`${TP_PREFIX} Sending usage:`, payload);
  fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {
    // Silently fail if the menu bar app is not running
  });
}

// ─── Parsing strategies ─────────────────────────────────────────────────────

/**
 * Strategy 1: Scan all text nodes on the page for patterns like
 *   "1,234,567 tokens" or "1234567 / 10,000,000 tokens"
 */
function parseFromTextNodes() {
  const bodyText = document.body.innerText || '';

  // Look for "X / Y tokens" (used / limit)
  const ratioPattern = /([\d,]+)\s*\/\s*([\d,]+)\s*tokens/gi;
  let match = ratioPattern.exec(bodyText);
  if (match) {
    const used  = parseTokenNumber(match[1]);
    const limit = parseTokenNumber(match[2]);
    if (used !== null) {
      console.log(`${TP_PREFIX} Strategy 1 (ratio pattern) — used: ${used}, limit: ${limit}`);
      return { used, limit: limit ?? 0 };
    }
  }

  // Look for standalone token counts
  const singlePattern = /([\d,]+)\s*tokens/gi;
  const matches = [];
  let m;
  while ((m = singlePattern.exec(bodyText)) !== null) {
    const n = parseTokenNumber(m[1]);
    if (n !== null && n > 1000) matches.push(n);  // Filter out tiny numbers
  }
  if (matches.length > 0) {
    // Largest number is likely the usage total
    const used = Math.max(...matches);
    console.log(`${TP_PREFIX} Strategy 1 (single pattern) — used: ${used}`);
    return { used, limit: 0 };
  }

  return null;
}

/**
 * Strategy 2: Look for known Anthropic dashboard element patterns —
 * progress bars, stat cards, aria labels.
 */
function parseFromElements() {
  // <progress> or meter elements
  const progressEl = document.querySelector('progress, meter');
  if (progressEl) {
    const value = parseFloat(progressEl.value);
    const max   = parseFloat(progressEl.max) || 0;
    if (!isNaN(value)) {
      const used  = Math.round(value);
      const limit = Math.round(max);
      console.log(`${TP_PREFIX} Strategy 2 (progress element) — used: ${used}, limit: ${limit}`);
      return { used, limit };
    }
  }

  // Elements with aria-valuenow / aria-valuemax (custom progress bars)
  const ariaEl = document.querySelector('[aria-valuenow]');
  if (ariaEl) {
    const used  = parseInt(ariaEl.getAttribute('aria-valuenow'), 10);
    const limit = parseInt(ariaEl.getAttribute('aria-valuemax') || '0', 10);
    if (!isNaN(used)) {
      console.log(`${TP_PREFIX} Strategy 2 (aria attributes) — used: ${used}, limit: ${limit}`);
      return { used, limit: isNaN(limit) ? 0 : limit };
    }
  }

  // Data attributes
  const dataEl = document.querySelector('[data-tokens-used], [data-usage]');
  if (dataEl) {
    const used  = parseTokenNumber(dataEl.dataset.tokensUsed || dataEl.dataset.usage || '');
    const limit = parseTokenNumber(dataEl.dataset.tokensLimit || dataEl.dataset.limit || '');
    if (used !== null) {
      console.log(`${TP_PREFIX} Strategy 2 (data attributes) — used: ${used}, limit: ${limit}`);
      return { used, limit: limit ?? 0 };
    }
  }

  return null;
}

/**
 * Strategy 3: Regex sweep on the full page HTML / text for numeric patterns.
 */
function parseFromRegex() {
  const text = document.body.innerHTML;

  // Pattern: "used":12345 or "tokens":12345
  const jsonPattern = /"(?:used|tokens|token_count|inputTokens|outputTokens)"\s*:\s*(\d+)/gi;
  const found = [];
  let m;
  while ((m = jsonPattern.exec(text)) !== null) {
    const n = parseInt(m[1], 10);
    if (n > 1000) found.push(n);
  }
  if (found.length > 0) {
    const used = Math.max(...found);
    console.log(`${TP_PREFIX} Strategy 3 (JSON pattern) — used: ${used}`);
    return { used, limit: 0 };
  }

  return null;
}

/**
 * Try to extract current month label from the page.
 */
function extractMonthLabel() {
  const text = document.body.innerText || '';
  const monthPattern = /\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b/i;
  const m = monthPattern.exec(text);
  return m ? m[0] : null;
}

// ─── Main extraction ─────────────────────────────────────────────────────────

function extractAndSend() {
  const result =
    parseFromElements() ||
    parseFromTextNodes() ||
    parseFromRegex();

  if (!result) {
    console.log(`${TP_PREFIX} No usage data found on this page.`);
    return;
  }

  const month = extractMonthLabel();
  const payload = {
    provider: 'claude',
    used:     result.used,
    limit:    result.limit ?? 0,
    source:   'extension',
    ...(month ? { month } : {}),
  };

  sendToTokenPulse(payload);
}

// ─── Boot: immediate + MutationObserver + timeout fallback ───────────────────

let extractionDone = false;

function tryExtract() {
  if (extractionDone) return;
  extractAndSend();
  extractionDone = true;
}

// Attempt immediately (content may already be in DOM)
tryExtract();

// MutationObserver: wait for dynamic content
const observer = new MutationObserver(() => {
  // Re-run only if the page has grown substantially
  const text = document.body.innerText || '';
  if (text.toLowerCase().includes('token')) {
    extractionDone = false; // allow re-run
    tryExtract();
    observer.disconnect();
  }
});

observer.observe(document.body, { childList: true, subtree: true });

// Timeout fallback — try after 3 s and again after 8 s
setTimeout(() => {
  extractionDone = false;
  tryExtract();
}, 3000);

setTimeout(() => {
  extractionDone = false;
  tryExtract();
  observer.disconnect();
}, 8000);
