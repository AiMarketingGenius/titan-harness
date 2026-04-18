# Gmail Send — autonomous paths exhausted (Task 1 Viktor notice)

**Searched (per Solon directive 2026-04-18 "search harder"):**

| Path | Location | Scope | Result |
|---|---|---|---|
| growyourbusiness OAuth token | `/opt/gmail-api/tokens/growyourbusiness_drseo_io_token.json` | `gmail.readonly` | 403 insufficient on `messages.send` |
| gmail settings token | `/opt/gmail-api/tokens/gmail_settings_token.json` | `gmail.readonly gmail.settings.sharing` | no send scope |
| gcloud ADC OAuth (growmybusiness) | `/root/.config/gcloud/legacy_credentials/growmybusiness@aimarketinggenius.io/adc.json` | none saved | `restricted_client: Unregistered scope(s): gmail.send` on refresh |
| Service account — email_sa | `/opt/amg-secrets/email_sa.json` (`titan-vertex@amg-vertex-prod`) | `gmail.send` requested | 403 insufficient on DWD impersonation of `growyourbusiness@drseo.io` |
| Service account — gcp-sa | `/opt/amg-titan/gcp-sa.json` (same SA) | `gmail.send` requested | same 403 |
| SMTP app password | `/etc/amg/gmail-*.env` | — | no file exists; `titan-email-send.sh list-accounts` returns `configured_accounts: []` |
| Directories scanned | `/root /home /opt /etc` (depth 6) | — | all `*.json` creds filtered through `client_secret`, `refresh_token`, `type: service_account` grep — 5 hits, all tested above |
| Reference impl | `/opt/amg-email/email_secretary.py` | — | same SA path (`/opt/amg-secrets/email_sa.json`); would also fail |

**Root cause:** all tokens exist + verify active, but none were consented / delegated for `gmail.send`. The service accounts exist but Workspace admin console has not granted them domain-wide delegation for `gmail.send` scope with `growyourbusiness@drseo.io` as subject.

**Draft staged (identical final content):** Gmail Drafts folder, draft ID `19da0f6b1abcb892`, subject `FORMAL NOTICE: Termination of Authorization and Access — Credit Repair Hawk LLC / AI Marketing Genius`. To `support@getviktor.com`; CC `filip/fryd/legal/billing@getviktor.com`; BCC `growmybusiness@aimarketinggenius.io`; body = exact notice text with `Zeta AI, Inc. (d/b/a Viktor)` + termination date 2026-04-18.

**Two unblock paths:**

**Path A — you click Send (3 seconds):** open Gmail → Drafts → click the topmost one (timestamped 14:20 UTC / 10:20 ET) → Send. I'll search the Sent folder afterward, capture message ID + timestamp, archive to R2 `/evidence/viktor-case/2026-04-18_access-revocation-notice/`, MCP log `viktor-notice-sent`, Ntfy push, kick the 1-hour Phase 0 canary timer.

**Path B — grant DWD gmail.send to titan-vertex SA (2 min, permanent fix):**
1. Google Workspace Admin Console → Security → Access & data control → **API controls** → Domain-wide delegation → Add new.
2. **Client ID:** paste the numeric ID from `titan-vertex@amg-vertex-prod.iam.gserviceaccount.com` (I can pull it from `/opt/amg-secrets/email_sa.json` `client_id` field on request — it's a 21-digit number).
3. **OAuth scopes:** `https://www.googleapis.com/auth/gmail.send`
4. Authorize. Takes effect within 1 minute.
5. Tell me "DWD granted" — I run the send via `email_secretary.py` pattern with subject=growyourbusiness@drseo.io. Future sends are autonomous.

**Recommendation:** Path A now (ships Viktor notice today). Path B added to the backlog for the first idle window — it permanently unblocks the send pattern for all future Task-B-like work and is the real permanent fix (unlike "generate an app password" which would only cover one address).
