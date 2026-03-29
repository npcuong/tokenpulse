/**
 * TokenPulse — Gemini / AI Studio content script
 * Injected on: https://aistudio.google.com/*
 *
 * Parses token counts / quota info and sends it to the TokenPulse app.
 */

const TP_PREFIX = '[TokenPulse][Gemini]';
const API_URL   = 'http://localhost:7777/api/usage';

// ─── Helpers ────────────────────────────────────────────────────────────────

function parseTokenNumber(str) {
  if (!str) return null;
  const cleaned = str.replace(/[,\s]/g, '');
  const n = parseInt(cleaned, 10);
  return isNaN(n) ? null : n;
}

function sendToTokenPulse(payload) {
  console.log(`${TP_PREFIX} Sending usage:`, payload);
  fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => {});
}

// ─── Parsing strategies ─────────────────────────────────────────────────────

/**
 * Strategy 1: Look for token count displays in the UI.
 * AI Studio shows token counts in the prompt composer and response area.
 */
function parseFromTokenDisplays() {
  const text = document.body.innerText || '';

  // Pattern: "X / Y tokens" or "X tokens used"
  const ratioPattern = /([\d,]+)\s*\/\s*([\d,]+)\s*(?:token|tok)/gi;
  let m;
  while ((m = ratioPattern.exec(text)) !== null) {
    const used  = parseTokenNumber(m[1]);
    const limit = parseTokenNumber(m[2]);
    if (used !== null) {
      console.log(`${TP_PREFIX} Strategy 1 (ratio) — used: ${used}, limit: ${limit}`);
      return { used, limit: limit ?? 0 };
    }
  }

  // "X tokens" standalone — collect candidates
  const singlePattern = /([\d,]+)\s*(?:token|tok)/gi;
  const candidates = [];
  while ((m = singlePattern.exec(text)) !== null) {
    const n = parseTokenNumber(m[1]);
    if (n !== null && n > 0) candidates.push(n);
  }
  if (candidates.length > 0) {
    const used = Math.max(...candidates);
    console.log(`${TP_PREFIX} Strategy 1 (max token) — used: ${used}`);
    return { used, limit: 0 };
  }

  return null;
}

/**
 * Strategy 2: Look for quota / rate-limit indicators in the UI.
 * AI Studio sometimes shows "X requests per minute" or quota bars.
 */
function parseFromQuotaIndicators() {
  // Progress bars or meter elements
  const progressEl = document.querySelector('progress, meter, [role="progressbar"]');
  if (progressEl) {
    const value = parseFloat(progressEl.value || progressEl.getAttribute('aria-valuenow'));
    const max   = parseFloat(progressEl.max   || progressEl.getAttribute('aria-valuemax') || '0');
    if (!isNaN(value)) {
      console.log(`${TP_PREFIX} Strategy 2 (progress) — value: ${value}, max: ${max}`);
      return { used: Math.round(value), limit: Math.round(max) };
    }
  }

  // aria-valuenow on any element
  const ariaEls = document.querySelectorAll('[aria-valuenow]');
  for (const el of ariaEls) {
    const used  = parseInt(el.getAttribute('aria-valuenow'), 10);
    const limit = parseInt(el.getAttribute('aria-valuemax') || '0', 10);
    if (!isNaN(used) && used > 0) {
      console.log(`${TP_PREFIX} Strategy 2 (aria) — used: ${used}, limit: ${limit}`);
      return { used, limit: isNaN(limit) ? 0 : limit };
    }
  }

  return null;
}

/**
 * Strategy 3: Check embedded JSON / script data for usage metrics.
 */
function parseFromEmbeddedData() {
  const scripts = document.querySelectorAll('script:not([src])');
  for (const script of scripts) {
    const content = script.textContent || '';
    const tokenPattern = /"(?:tokenCount|token_count|totalTokens|total_tokens|inputTokens|outputTokens)"\s*:\s*(\d+)/gi;
    const matches = [];
    let m;
    while ((m = tokenPattern.exec(content)) !== null) {
      const n = parseInt(m[1], 10);
      if (n > 0) matches.push(n);
    }
    if (matches.length > 0) {
      const used = Math.max(...matches);
      console.log(`${TP_PREFIX} Strategy 3 (embedded JSON) — used: ${used}`);
      return { used, limit: 0 };
    }
  }
  return null;
}

/**
 * Strategy 4: Look for "context window" or "max tokens" references.
 */
function parseFromContextWindow() {
  const text = document.body.innerText || '';

  // Pattern: "1,048,576 token context window"
  const ctxPattern = /([\d,]+)\s*(?:token|tok)\s*context/gi;
  let m;
  while ((m = ctxPattern.exec(text)) !== null) {
    const limit = parseTokenNumber(m[1]);
    if (limit !== null) {
      console.log(`${TP_PREFIX} Strategy 4 (context window) — limit: ${limit}`);
      // This is a limit indicator, not current usage
      return { used: 0, limit };
    }
  }

  return null;
}

// ─── Main extraction ─────────────────────────────────────────────────────────

function extractAndSend() {
  const result =
    parseFromQuotaIndicators() ||
    parseFromTokenDisplays()   ||
    parseFromEmbeddedData()    ||
    parseFromContextWindow();

  if (!result) {
    console.log(`${TP_PREFIX} No usage data found on this page.`);
    return;
  }

  const payload = {
    provider: 'gemini',
    used:     result.used  ?? 0,
    limit:    result.limit ?? 0,
    source:   'extension',
  };

  sendToTokenPulse(payload);
}

// ─── Boot ────────────────────────────────────────────────────────────────────

let extractionDone = false;

function tryExtract() {
  if (extractionDone) return;
  extractAndSend();
  extractionDone = true;
}

tryExtract();

const observer = new MutationObserver(() => {
  const text = document.body.innerText || '';
  if (text.toLowerCase().includes('token') || text.includes('quota')) {
    extractionDone = false;
    tryExtract();
    observer.disconnect();
  }
});

observer.observe(document.body, { childList: true, subtree: true });

setTimeout(() => { extractionDone = false; tryExtract(); }, 3000);
setTimeout(() => { extractionDone = false; tryExtract(); observer.disconnect(); }, 8000);
