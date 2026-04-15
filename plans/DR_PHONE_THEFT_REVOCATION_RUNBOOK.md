# Phone-Theft Revocation Runbook (CT-0415-05 Phase 3)

If Solon's iPhone is lost or stolen, this runbook revokes every credential the phone could access. Order matters — fastest blast-radius reduction first.

| # | Credential | Storage | Revocation step | Time |
|---|---|---|---|---|
| 1 | Tailscale auth token (iPhone) | iOS Tailscale app | https://login.tailscale.com/admin/machines → find device → ⋯ → **Remove**. All connections from phone instantly terminate. | <30s |
| 2 | Termius SSH key passphrase (if used) | Termius keychain | (a) On VPS: `ssh-keygen -R <stolen device IP>` to remove host. (b) Rotate the SSH keypair on VPS that the phone had: `ssh-keygen -t ed25519 -C "titan-vps-replaced" -f /root/.ssh/titan_mac_v2 -N ""` then update Mac ~/.ssh/authorized_keys to remove the old pubkey. | 2-3min |
| 3 | Slack bot token (if held in iOS Notes/iCloud) | iOS Notes/iCloud | Slack → https://api.slack.com/apps → app → OAuth & Permissions → **Reinstall** (regenerates token). Then update /etc/amg/*.env on VPS + restart consumers. | 1min |
| 4 | RustDesk permanent password (if Phase 3 P1 done) | RustDesk iOS | Open RustDesk on Mac → Settings → Security → change permanent password. Phone loses unattended access. | 1min |
| 5 | iCloud (Find My iPhone) | Apple ID | https://icloud.com/find → Mark as Lost (locks device) → Erase iPhone (factory wipe). | 2-5min |
| 6 | Apple ID password | Apple ID | https://appleid.apple.com → change password. Forces re-auth on all devices, kicks the phone session. | 1min |

**Critical sequencing rules:**

- Always do **#1 (Tailscale) FIRST**. It's the broadest blast (phone → VPS → Mac chain via Tailscale ACL).
- Use **device-specific ephemeral auth keys** when initially enrolling iPhone in Tailscale (Tailscale admin → Settings → Keys → "Single use" + tag:phone). With ephemeral keys, removing the device from Tailscale admin invalidates the key entirely — no separate revoke step needed.
- Do **#5 (Find My)** in parallel with #1 — it doesn't depend on Tailscale being up.
- Do NOT wait for Apple's "lost mode" confirmation before doing the others. Lost Mode is asynchronous; Tailscale + key rotation are synchronous.
- All steps assume Solon still has access to a trusted browser. If both phone AND laptop stolen, fall back to a separate trusted machine (parents, friend) and do steps #1, #5, #6 from there.

**After revocation:**

1. Re-enroll a replacement iPhone with a NEW ephemeral auth key in Tailscale.
2. Re-key the VPS → Mac SSH (the rotated key from step #2).
3. Update /etc/amg/*.env files on VPS with the new Slack token + restart any consumers (`pm2 restart all` for n8n; systemctl restart for harness services).
4. Verify end-to-end demo from new device: iPhone → SSH VPS → `ssh titan-mac` → command runs.
5. Document the incident in MCP via `flag_blocker` with severity=high, then `resolve_blocker` once #1-#4 confirmed.

**Drill cadence:** quarterly. Schedule the next drill 90 days from the last successful run. Keep this runbook open in 1Password Notes section labeled "EMERGENCY — phone theft."
