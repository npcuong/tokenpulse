/**
 * TokenPulse — OpenAI content script
 * Injected on:
 *   https://platform.openai.com/account/usage*
 *   https://platform.openai.com/settings/organization/billing/overview*
 *
 * Parses USD spending / credit balance and sends it to the TokenPulse app.
 */

const TP_PREFIX = '[TokenPulse][OpenAI]';
const API_URL   = 'http://localhost:7777/api/usage';

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Parse a dollar amount string like "$12.50" or "12.50" into a float */
function parseDollarAmount(str) {
  if (!str) return null;
  const cleaned = str.replace(/[$,\s]/g, '');
  const n = parseFloat(cleaned);
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
 * Strategy 1: Scan visible dollar amounts on the page.
 * The usage page usually shows a prominent monthly total.
 */
function parseFromDollarAmounts() {
  const text = document.body.innerText || '';

  // Look for "Total: $12.34" or "Monthly usage: $12.34"
  const labeledPattern = /(?:total|monthly|spend|cost|usage)[^\n$]*\$([\d,]+\.?\d*)/gi;
  let m;
  while ((m = labeledPattern.exec(text)) !== null) {
    const cost = parseDollarAmount(m[1]);
    if (cost !== null) {
      console.log(`${TP_PREFIX} Strategy 1 (labeled dollar) — cost_used: ${cost}`);
      return { cost_used: cost };
    }
  }

  // Collect all dollar amounts and pick the largest as the total
  const allDollarPattern = /\$([\d,]+\.?\d*)/g;
  const amounts = [];
  while ((m = allDollarPattern.exec(text)) !== null) {
    const v = parseDollarAmount(m[1]);
    if (v !== null && v > 0) amounts.push(v);
  }
  if (amounts.length > 0) {
    // On the usage page the largest visible amount is typically the monthly total
    const cost_used = Math.max(...amounts);
    console.log(`${TP_PREFIX} Strategy 1 (max dollar) — cost_used: ${cost_used}`);
    return { cost_used };
  }

  return null;
}

/**
 * Strategy 2: Look for credit balance on the billing overview page.
 */
function parseFromBillingOverview() {
  // Look for elements that typically contain balance info
  const candidates = [
    ...document.querySelectorAll('[class*="balance"], [class*="credit"], [class*="spend"], [class*="usage"]'),
  ];

  for (const el of candidates) {
    const text = el.innerText || el.textContent || '';
    const m = /\$([\d,]+\.?\d*)/.exec(text);
    if (m) {
      const cost = parseDollarAmount(m[1]);
      if (cost !== null) {
        console.log(`${TP_PREFIX} Strategy 2 (billing element) — cost: ${cost}`);
        // On billing page, this is likely remaining credit not usage — treat as cost_limit
        return { cost_limit: cost };
      }
    }
  }

  return null;
}

/**
 * Strategy 3: Check for JSON data embedded in page / script tags.
 */
function parseFromEmbeddedJSON() {
  const scripts = document.querySelectorAll('script[type="application/json"], script:not([src])');
  for (const script of scripts) {
    const content = script.textContent || '';
    // Look for cost/spend fields
    const costPattern = /"(?:cost|spend|total_cost|amount_spent|total_usage)"\s*:\s*([\d.]+)/i;
    const m = costPattern.exec(content);
    if (m) {
      const cost = parseFloat(m[1]);
      if (!isNaN(cost)) {
        console.log(`${TP_PREFIX} Strategy 3 (embedded JSON) — cost_used: ${cost}`);
        return { cost_used: cost };
      }
    }
  }
  return null;
}

// ─── Main extraction ─────────────────────────────────────────────────────────

function extractAndSend() {
  const isBillingPage = window.location.href.includes('billing');

  let result;
  if (isBillingPage) {
    result = parseFromBillingOverview() || parseFromDollarAmounts() || parseFromEmbeddedJSON();
  } else {
    result = parseFromDollarAmounts() || parseFromEmbeddedJSON() || parseFromBillingOverview();
  }

  if (!result) {
    console.log(`${TP_PREFIX} No usage data found on this page.`);
    return;
  }

  const payload = {
    provider:   'openai',
    cost_used:  result.cost_used  ?? 0,
    cost_limit: result.cost_limit ?? 0,
    source:     'extension',
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
  if (text.includes('$')) {
    extractionDone = false;
    tryExtract();
    observer.disconnect();
  }
});

observer.observe(document.body, { childList: true, subtree: true });

setTimeout(() => { extractionDone = false; tryExtract(); }, 3000);
setTimeout(() => { extractionDone = false; tryExtract(); observer.disconnect(); }, 8000);
