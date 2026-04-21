# Memory Guard Site Audit — 2026-04-20

## Scope

Audit target: `aimemoryguard.com`
Requested deliverable path: `/opt/amg-handoffs/titan-reports/memory-guard-audit-2026-04-20.md`

## Findings

1. Public `https://aimemoryguard.com` is serving the current Cloudflare Pages build, not the stale VPS static root.
   - Evidence: response headers report `server: cloudflare`.
   - Public markers match the current canonical landing page: Free / $9.99 / $19.99 pricing, zero testimonial blocks, and the current "No fake social proof" early-access copy.

2. The VPS fallback root at `/opt/aimemoryguard-site/index.html` was stale.
   - That file was an older 2026-04-16 build with a testimonials section still present and older copy structure.
   - Caddy on the VPS is still configured to serve that folder directly if traffic is routed there.

3. The deploy helper was pointed at a dead source path.
   - `/opt/titan-harness/scripts/deploy_aimemoryguard.sh` expected `$HOME/Sites/aimemoryguard-site`, which does not exist on the VPS.
   - The canonical landing source that actually matches production lives at `/opt/titan-harness/deploy/aimemoryguard-landing/index.html`.

## Action Taken Tonight

1. Updated the deploy helper to use `/opt/titan-harness/deploy/aimemoryguard-landing` as the canonical source.
2. Added a mirror refresh step so each deploy also updates `/opt/aimemoryguard-site/index.html`.
3. Preserved existing VPS-only legal/support artifacts under `/opt/aimemoryguard-site` by syncing the landing page without deleting `/privacy`, `/terms`, or the extension zip.
4. Synced the stale VPS landing page back to the current canonical build.

## Verification

- Public site markers confirmed:
  - Free tier present
  - Pro tier displays `$9.99`
  - Pro+ tier displays `$19.99`
  - no testimonial markers in the public HTML
  - early-access copy explicitly states "No fake social proof"
- VPS origin verified separately through local host-header curl after the mirror refresh.

## Residual Notes

- The public site was already healthy when checked tonight; the real regression surface was the stale VPS fallback plus the broken deploy path.
- This closes the drift so future deploys and VPS-origin traffic do not fall back to the older testimonial-bearing build.
