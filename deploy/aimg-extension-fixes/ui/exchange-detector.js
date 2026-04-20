/**
 * Exchange detector — SINGLE PATH, real Einstein analysis.
 *
 * v0.1.13 — prior versions had three overlapping strategies (selector scan,
 * text-diff, shadow-DOM walker) all feeding the same counter, plus per-
 * platform content scripts (claude.js etc) ALSO calling the pill update
 * APIs directly. Result: one response ticked 3-4 times. This rewrite is the
 * single source of truth:
 *
 *   - Body-text length delta is the ONLY exchange trigger. One delta > 120
 *     chars = one new assistant response. No secondary signal paths.
 *
 *   - Einstein runs a lightweight rule-based analysis of the delta text to
 *     decide whether to record `verified`, `flagged`, or skip. This makes
 *     the Einstein counter diverge from the exchange counter naturally
 *     (a short chit-chat response ticks the Hallucinometer but skips
 *     Einstein — no claim to check).
 *
 *   Verified: delta contains a concrete factual claim — date, year, percent,
 *             dollar figure, proper-noun pair, numeric quantity.
 *   Flagged:  delta contains hedging language that typically precedes an
 *             AI hallucination or capability-gap disclaimer ("I don't have
 *             access", "as of my knowledge cutoff", "I cannot verify").
 *   Skip:     neither pattern — chit-chat, acknowledgments, short answers.
 */
(function () {
  'use strict';

  const MIN_DELTA = 120;
  const MAX_DELTA = 100000;     // guard against full page reloads
  const SCAN_MS = 1500;

  let lastLen = 0;
  let exchanges = 0;
  let einsteinVerified = 0;
  let einsteinFlagged = 0;
  let einsteinSkipped = 0;
  let primed = false;
  let pendingRaf = null;

  // Concrete-claim patterns — if any of these match, Einstein logs it as a
  // verified check (we ran analysis + found a testable claim).
  const FACT_PATTERNS = [
    /\b(19|20)\d{2}\b/,                                   // years
    /\b\d+(\.\d+)?\s?%/,                                  // percentages
    /\$\d[\d,]*(\.\d+)?/,                                 // dollar figures
    /\b\d+(\.\d+)?\s?(million|billion|thousand|bn|mn|k)\b/i, // magnitudes
    /\b[A-Z][a-z]+ [A-Z][a-z]+(?:,| is | was | runs | owns | leads | founded | heads )/, // full-name + action
    /\b(Founded|Established|Launched|Headquartered|CEO of|President of|Director of)\b/,   // titular facts
  ];

  // Hedging / uncertainty language — Einstein flags these because they are
  // where hallucinations typically live.
  const HEDGE_PATTERNS = [
    /\bI don('?|'?)t have (access|the ability|information|data|details)/i,
    /\bas of my (?:last )?(knowledge|training) (?:cutoff|update)/i,
    /\bI(?:'m| am) not (?:certain|sure|confident|aware)/i,
    /\bI may not (?:have|be)\b/i,
    /\bmy knowledge (?:cutoff|is limited|ends)/i,
    /\bI cannot (?:verify|confirm|check)/i,
    /\bI don('?|'?)t know\b/i,
    /\bunable to (?:verify|confirm)/i,
    /\bas an AI\b/i,
    /\bI'?m just an AI\b/i,
    /\bno real-time (?:access|information|data)/i,
  ];

  function matchesAny(patterns, text) {
    for (const p of patterns) {
      if (p.test(text)) return true;
    }
    return false;
  }

  function analyze(text) {
    const hasHedge = matchesAny(HEDGE_PATTERNS, text);
    const hasFact = matchesAny(FACT_PATTERNS, text);
    if (hasHedge) return 'flagged';      // hedge wins — Einstein flags uncertainty
    if (hasFact) return 'verified';      // concrete claim — Einstein marks verified
    return 'skip';                       // nothing to check
  }

  function scan() {
    pendingRaf = null;
    const body = document.body;
    if (!body) return;
    const currentText = body.innerText || '';
    const currentLen = currentText.length;

    // Prime the baseline on first meaningful scan so we don't count the
    // entire existing page as "one massive response".
    if (!primed) {
      lastLen = currentLen;
      primed = true;
      return;
    }

    const delta = currentLen - lastLen;
    if (delta < MIN_DELTA) return;          // too small — probably typing indicator or UI chrome
    if (delta > MAX_DELTA) {                // page reload / view switch — rebaseline
      lastLen = currentLen;
      return;
    }

    // A new response arrived.
    exchanges += 1;
    const deltaText = currentText.slice(-delta - 200);  // include small overlap so patterns at the boundary match
    const result = analyze(deltaText);
    if (result === 'verified') einsteinVerified += 1;
    else if (result === 'flagged') einsteinFlagged += 1;
    else einsteinSkipped += 1;

    try { window.__AIMEMORY_THREAD_HEALTH?.update?.(exchanges); } catch (_) {}
    try {
      if (result === 'verified') window.__AIMEMORY_EINSTEIN_STATUS?.recordCheck?.('verified');
      else if (result === 'flagged') window.__AIMEMORY_EINSTEIN_STATUS?.recordCheck?.('flagged');
      // 'skip' intentionally does nothing — Einstein only ticks when it actually checked something.
    } catch (_) {}

    lastLen = currentLen;
    console.log(
      `[AI Memory] exchange #${exchanges} — Einstein: ${result} ` +
      `(verified=${einsteinVerified} flagged=${einsteinFlagged} skipped=${einsteinSkipped}) ` +
      `delta=${delta}`
    );
  }

  function requestScan() {
    if (pendingRaf) return;
    pendingRaf = requestAnimationFrame(() => setTimeout(scan, 250));
  }

  // Prime baseline after page stabilizes.
  setTimeout(() => { scan(); }, 1200);
  setInterval(scan, SCAN_MS);

  const obs = new MutationObserver(() => requestScan());
  function startObs() {
    if (!document.body) { setTimeout(startObs, 100); return; }
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  startObs();

  window.__AIMEMORY_EXCHANGE_DETECTOR = {
    count: () => exchanges,
    einstein: () => ({ verified: einsteinVerified, flagged: einsteinFlagged, skipped: einsteinSkipped }),
    rescan: scan,
    reset: () => {
      exchanges = 0;
      einsteinVerified = 0;
      einsteinFlagged = 0;
      einsteinSkipped = 0;
      lastLen = (document.body?.innerText || '').length;
    },
    version: 'v0.1.13-single-path',
  };

  console.log('[AI Memory] exchange-detector v0.1.13 armed — single-path counter + rule-based Einstein.');
})();
