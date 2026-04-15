/**
 * Thread Health meter (marketing brand: "Hallucinometer").
 *
 * Left-edge vertical widget — 8px collapsed → 52px on hover.
 * Four zones driven by exchange count:
 *   🟢 green    1-15   ("Fresh")
 *   🟡 yellow   16-30  ("Warm")
 *   🟠 orange   31-45  ("Hot")
 *   🔴 red      46+    ("Danger — start a fresh thread")
 *
 * Source: CT-0405-06 UI/UX spec (claude.ai thread eaa777fa, 2026-04-06).
 * Locked in plans/DOCTRINE_AIMG_TIER_MATRIX.md.
 *
 * This module is framework-free ES — safe to import into a Chrome
 * MV3 content script or a web-app bundle.
 */

export const ZONES = [
  { key: "green",  label: "Fresh",  color: "#2ecc71", min: 1,  max: 15 },
  { key: "yellow", label: "Warm",   color: "#f1c40f", min: 16, max: 30 },
  { key: "orange", label: "Hot",    color: "#e67e22", min: 31, max: 45 },
  { key: "red",    label: "Danger", color: "#e74c3c", min: 46, max: Infinity },
];

export function zoneForExchangeCount(count) {
  for (const z of ZONES) if (count >= z.min && count <= z.max) return z;
  return ZONES[0];
}

export function mountThreadHealthWidget({
  container = document.body,
  initialCount = 0,
  onZoneChange = () => {},
  onCountdownNeeded = () => null, // return `{remaining, cap}` or null
} = {}) {
  const host = document.createElement("div");
  host.id = "aimg-thread-health";
  host.setAttribute("role", "status");
  host.setAttribute("aria-label", "Thread Health");
  Object.assign(host.style, {
    position: "fixed",
    left: "0",
    top: "50%",
    transform: "translateY(-50%)",
    width: "8px",
    height: "160px",
    zIndex: "2147483646",
    transition: "width 120ms ease-out",
    cursor: "default",
    overflow: "hidden",
    borderRadius: "0 6px 6px 0",
    boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
    background: "#2ecc71",
    color: "#fff",
    fontFamily: "-apple-system, system-ui, sans-serif",
    fontSize: "12px",
    lineHeight: "1.3",
  });

  const label = document.createElement("div");
  Object.assign(label.style, {
    padding: "10px 10px 0 10px",
    opacity: "0",
    transition: "opacity 120ms ease-out",
    whiteSpace: "nowrap",
  });
  const countdown = document.createElement("div");
  Object.assign(countdown.style, {
    padding: "4px 10px 10px 10px",
    opacity: "0",
    fontWeight: "600",
    transition: "opacity 120ms ease-out",
  });
  host.append(label, countdown);

  host.addEventListener("mouseenter", () => {
    host.style.width = "52px";
    label.style.opacity = "1";
    countdown.style.opacity = "1";
  });
  host.addEventListener("mouseleave", () => {
    host.style.width = "8px";
    label.style.opacity = "0";
    countdown.style.opacity = "0";
  });

  let currentZone = null;
  function render(count) {
    const zone = zoneForExchangeCount(Math.max(0, count));
    host.style.background = zone.color;
    label.textContent = `${zone.label} · ${count}`;
    const cd = onCountdownNeeded();
    countdown.textContent = cd ? `${cd.remaining}/${cd.cap} verifies` : "";
    if (!currentZone || currentZone.key !== zone.key) {
      const prev = currentZone;
      currentZone = zone;
      onZoneChange(zone, prev);
    }
  }

  container.appendChild(host);
  render(initialCount);

  return {
    element: host,
    setCount: render,
    getZone: () => currentZone,
    destroy: () => host.remove(),
  };
}
