/**
 * Auto-carryover modal.
 *
 * Shown when the thread health meter enters the red zone. Copy is locked
 * per plans/DOCTRINE_AIMG_TIER_MATRIX.md:
 *   "Let's start a fresh thread to maintain quality..."
 *
 * Also renders:
 *   - the upsell payload from a 402 response (optional)
 *   - a platform-pause banner from a 429 response (optional)
 *
 * Footer (all states): "AI can make mistakes please double-check all responses"
 */

const FOOTER = "AI can make mistakes please double-check all responses";

function makeOverlay() {
  const overlay = document.createElement("div");
  overlay.id = "aimg-carryover-overlay";
  Object.assign(overlay.style, {
    position: "fixed",
    inset: "0",
    background: "rgba(10,10,20,0.55)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: "2147483647",
    fontFamily: "-apple-system, system-ui, sans-serif",
  });
  return overlay;
}

function makeCard() {
  const card = document.createElement("div");
  Object.assign(card.style, {
    background: "#fff",
    color: "#111",
    width: "min(440px, 92vw)",
    padding: "24px 24px 20px",
    borderRadius: "12px",
    boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
    lineHeight: "1.5",
  });
  return card;
}

function button(label, { primary = false } = {}) {
  const b = document.createElement("button");
  b.textContent = label;
  Object.assign(b.style, {
    border: "0",
    borderRadius: "8px",
    padding: "10px 16px",
    fontSize: "14px",
    fontWeight: "600",
    cursor: "pointer",
    marginLeft: "8px",
    background: primary ? "#111" : "#f0f0f3",
    color: primary ? "#fff" : "#111",
  });
  return b;
}

export function showCarryoverModal({
  onStartFresh,
  onDismiss,
  upsell = null,       // { next_tier, price, daily_cap } | null
  platformPause = null // { retry_after_utc } | null
} = {}) {
  const overlay = makeOverlay();
  const card = makeCard();

  const title = document.createElement("div");
  title.style.fontSize = "18px";
  title.style.fontWeight = "700";
  title.style.marginBottom = "8px";

  const body = document.createElement("div");
  body.style.fontSize = "14px";
  body.style.color = "#333";
  body.style.marginBottom = "16px";

  if (platformPause) {
    title.textContent = "Service paused until UTC midnight";
    body.textContent =
      `Daily platform cost ceiling reached. Retrying at ${platformPause.retry_after_utc}.`;
  } else if (upsell) {
    title.textContent = "Daily cap reached";
    body.innerHTML =
      `Upgrade to <b>${upsell.next_tier}</b> for ${upsell.daily_cap} verifies/day ` +
      `at $${upsell.price}/mo — or wait until UTC midnight for your cap to reset.`;
  } else {
    title.textContent = "Let's start a fresh thread to maintain quality";
    body.textContent =
      "Long threads reduce model accuracy. Carrying your context into a new thread keeps responses sharp.";
  }

  const btnRow = document.createElement("div");
  btnRow.style.textAlign = "right";
  btnRow.style.marginTop = "8px";

  const dismissBtn = button("Not now");
  const primaryBtn = button(
    platformPause ? "Got it" : upsell ? "Upgrade" : "Start fresh thread",
    { primary: true },
  );
  dismissBtn.addEventListener("click", () => { cleanup(); onDismiss?.(); });
  primaryBtn.addEventListener("click", () => { cleanup(); onStartFresh?.({ upsell, platformPause }); });
  btnRow.append(dismissBtn, primaryBtn);

  const footer = document.createElement("div");
  footer.textContent = FOOTER;
  Object.assign(footer.style, {
    marginTop: "16px",
    fontSize: "11px",
    color: "#888",
    textAlign: "center",
  });

  card.append(title, body, btnRow, footer);
  overlay.appendChild(card);
  document.body.appendChild(overlay);

  function cleanup() { overlay.remove(); }
  return { dismiss: cleanup };
}
