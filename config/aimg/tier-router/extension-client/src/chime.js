/**
 * 2-tone "ding-DING" chime — plays ONCE on entering the red zone.
 *
 * Spec: CT-0405-06 thread eaa777fa / plans/DOCTRINE_AIMG_TIER_MATRIX.md.
 *   - 2 tones, second tone slightly higher/louder
 *   - 40% volume (0.4 gain)
 *   - Plays ONCE per zone entry (not a siren)
 *   - Must be dismissable (caller owns the "armed" state)
 *
 * WebAudio generation — no external audio file, no network. Works in
 * Chrome MV3 content scripts and regular web pages.
 */

const DEFAULTS = {
  volume: 0.4,
  tone1Hz: 880,   // A5
  tone2Hz: 1175,  // D6 (perfect fourth above)
  tone1Ms: 140,
  gapMs: 60,
  tone2Ms: 200,
};

/**
 * @param {object} [opts] Override defaults.
 * @returns {Promise<void>} resolves when chime finished playing
 */
export async function playDingDing(opts = {}) {
  const cfg = { ...DEFAULTS, ...opts };
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return;
  const ctx = new AC();

  // Autoplay policy: if user has not interacted, resume may be needed.
  if (ctx.state === "suspended") {
    try { await ctx.resume(); } catch (_) { return; }
  }

  function tone(freq, startSec, durSec, peakGain) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    osc.connect(gain).connect(ctx.destination);
    const t0 = ctx.currentTime + startSec;
    gain.gain.setValueAtTime(0, t0);
    gain.gain.linearRampToValueAtTime(peakGain, t0 + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + durSec);
    osc.start(t0);
    osc.stop(t0 + durSec + 0.02);
  }

  const v = cfg.volume;
  tone(cfg.tone1Hz, 0, cfg.tone1Ms / 1000, v * 0.85);
  tone(cfg.tone2Hz, (cfg.tone1Ms + cfg.gapMs) / 1000, cfg.tone2Ms / 1000, v);

  const totalMs = cfg.tone1Ms + cfg.gapMs + cfg.tone2Ms + 100;
  await new Promise((r) => setTimeout(r, totalMs));
  try { await ctx.close(); } catch (_) { /* noop */ }
}

/**
 * Factory that returns a "play once" chime tied to a zone-entry event.
 * Caller calls `onZoneChange(zone)` — chime fires once per red entry.
 */
export function makeRedZoneChime() {
  let armed = true;
  return function onZoneChange(zone, prevZone) {
    const enteringRed =
      zone?.key === "red" && (!prevZone || prevZone.key !== "red");
    if (enteringRed && armed) {
      armed = false;
      playDingDing().catch(() => { /* swallow — UX not blocking */ });
    }
    // Re-arm when leaving red so a *new* red-entry later fires once more.
    if (zone?.key !== "red") armed = true;
  };
}
