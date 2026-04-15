/**
 * Public AIMG client — composes the tier-router fetch wrapper, the Thread
 * Health widget, the red-zone chime, and the carryover modal.
 *
 * Consumers should construct one `AimgClient` per browser tab / thread and
 * call `await client.verify({...})` each time they want to hit the tier
 * router. The client increments the exchange counter and drives the widget
 * automatically — caller only needs to render the returned `data.result`.
 *
 * Contract matches config/aimg/tier-router/README.md and
 * plans/DOCTRINE_AIMG_TIER_MATRIX.md (FINAL LOCK 2026-04-14).
 */

import { makeTierRouterClient } from "./tier-router-client.js";
import { mountThreadHealthWidget } from "./thread-health-widget.js";
import { makeRedZoneChime } from "./chime.js";
import { showCarryoverModal } from "./carryover-modal.js";

export class AimgClient {
  /**
   * @param {object} opts
   * @param {string} opts.supabaseUrl
   * @param {string} opts.jwt
   * @param {HTMLElement=} opts.widgetContainer  defaults to document.body
   * @param {function=} opts.onStartFreshThread  called when user clicks the
   *                                             carryover modal primary button
   */
  constructor({ supabaseUrl, jwt, widgetContainer, onStartFreshThread }) {
    this._call = makeTierRouterClient({ supabaseUrl, jwt });
    this._exchangeCount = 0;
    this._lastUsage = null;
    this._redChime = makeRedZoneChime();
    this._onStartFresh = onStartFreshThread || (() => {});

    this._widget = mountThreadHealthWidget({
      container: widgetContainer || document.body,
      initialCount: 0,
      onZoneChange: (zone, prev) => {
        this._redChime(zone, prev);
        if (zone.key === "red" && (!prev || prev.key !== "red")) {
          showCarryoverModal({
            onStartFresh: () => this._onStartFresh({ reason: "red_zone" }),
          });
        }
      },
      onCountdownNeeded: () =>
        this._lastUsage
          ? { remaining: this._lastUsage.remaining, cap: this._lastUsage.cap }
          : null,
    });
  }

  /**
   * @param {object} payload  body forwarded to /functions/v1/aimg-qe-call
   * @returns {Promise<{status:string, data:object}>}
   */
  async verify(payload) {
    const resp = await this._call(payload);

    this._exchangeCount += 1;
    if (resp.status === "ok" && resp.data?.usage) {
      this._lastUsage = resp.data.usage;
    }
    this._widget.setCount(this._exchangeCount);

    if (resp.status === "cap_exceeded") {
      showCarryoverModal({
        upsell: resp.data?.upsell || null,
        onStartFresh: () => this._onStartFresh({ reason: "cap_exceeded", upsell: resp.data?.upsell }),
      });
    } else if (resp.status === "platform_paused") {
      showCarryoverModal({
        platformPause: { retry_after_utc: resp.data?.retry_after_utc },
      });
    }

    return resp;
  }

  resetThread() {
    this._exchangeCount = 0;
    this._lastUsage = null;
    this._widget.setCount(0);
  }

  destroy() { this._widget.destroy(); }
}
