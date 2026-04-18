# Titan response to EOM Task Bundle 2026-04-18

**Bundle:** Phase 0 (Viktor honeypot) / Phase 1 (sprint continue) / Phase 2 (hardening) / Phase 3 (Mac + Drive hygiene)
**Status:** Acknowledged. Phase 1 starts immediately (Step 6.4). Phase 0 slots between 6.4 and 6.5, gated on Solon legal-notice confirmation. Phase 2 + 3 queued per bundle sequencing.

---

## 1. Phase 0 gate status

**Blocked on Task 0.0 completion (Solon + EOM work):**
1. EOM drafts access-revocation notice `.md` deliverable
2. Solon sends via email + certified mail
3. Solon forwards sent-copy to `growmybusiness@aimarketinggenius.io`
4. Solon confirms to Titan: "notice sent, here's the proof"

Only THEN does Phase 0 Titan work proceed:
- Task 0.1 — snapshot Viktor's current Slack access scope to R2 Object Lock (requires Solon Slack admin session cookie + Stagehand)
- Task 0.2 — canary deployment via Stagehand (requires Solon Slack session + canarytokens.org account login)
- Task 0.3 — 24/7 monitoring wiring (Titan can do standalone once Task 0.2 is done)
- Task 0.5 — completion report

**Between Step 6.4 and Step 6.5 Titan will ask:** "Access-revocation notice sent? If yes, let's run Task 0.1–0.3 now. If no, Phase 0 defers to post-Step-9."

---

## 2. Answers — §3.6 Gemini CLI questions

### Q1. Install blockers Titan sees

- **Node version.** Gemini CLI npm path needs Node 18+. VPS is likely on 20.x (atlas-api uvicorn runs Python 3.10, Node version unknown — will verify pre-install).
- **Cloud Billing Budgets API** must be enabled on the AMG Google Cloud project + the API key must have `billing.budgets.*` scope added. Will verify + enable via Cloud SDK.
- **Outbound HTTPS** to `generativelanguage.googleapis.com` — already open on VPS (Cloudflare / no-egress-firewall posture confirmed via earlier testing).
- **Pub/Sub topic** + **Cloud Function** for the $30 hard-stop need setup. If unavailable, fallback = systemd-timer polling Cloud Billing REST API + programmatic `services.disable` call.

### Q2. Role-split conflict

None. Current Titan workflow (build → commit → dual-grade → push → mirror) continues. Gemini CLI becomes a post-commit hook (read-only) in normal mode + a Titan surrogate during outages with direct-to-master authority constrained by the §3.3 boundaries. Zero write-conflict risk because only one writer is ever authorized at a time (Titan when up, Gemini when Anthropic is down).

### Q3. Mac install

**Defer to post-Monday, possibly skip entirely.** VPS is where commits land + post-commit hooks fire + outage-mode surrogate runs. Mac install adds no verification value (Mac is dev-only — doesn't receive post-commit hook triggers because commits push from Mac, hook runs on VPS via post-receive). Only reason to install on Mac = local debugging of Gemini rubric; low priority.

### Q4. `gemini-verification` MCP tag surfacing to EOM

**YELLOW / RED only.** GREEN = same as dual-grade PASS; flooding EOM's bootstrap context with one entry per commit is noise. YELLOW + RED surface because they indicate drift the grader missed.

### Q5. Budget kill-switch mechanism — most reliable

**Primary: Cloud Billing Budget API + Pub/Sub → Cloud Function.**
- Budget config: threshold notifications at $25 (warn) and $30 (hard-stop)
- $30 threshold publishes to Pub/Sub topic `gemini-budget-exceeded`
- Cloud Function subscribed to the topic calls `serviceusage.services.disable` on `generativelanguage.googleapis.com` for the AMG project's Gemini API key
- Gemini CLI wrapper detects 403 from Gemini API → falls back to Vertex AI Express Mode (free Flash tier)

**Fallback if Cloud Function setup blocked:** systemd timer on VPS polls the Cloud Billing API every 5 min, compares current spend to $30 cap, invokes `gcloud services disable` if exceeded. Less responsive (~5-min lag), same endgame.

**Will implement primary + configure fallback as a hot spare.** Both at install time, not later.

---

## 3. Answers — §4.4 Social Engineering questions

### Q1. Current vendor API access + email-parse-fallback list

**API access Titan already holds:**
- GitHub (org PAT + personal PAT)
- Cloudflare (Workers + DNS API tokens)
- HostHatch (root SSH — implicit "API" via shell)
- Supabase (service role key + PAT)
- AMG Google Cloud / Workspace (OAuth + service account; Gemini API key; Drive API scope pending audit in Task 4)
- OpenAI / Anthropic (LLM provider keys)
- Perplexity (API key via LiteLLM gateway)
- Deepgram (STT), ElevenLabs (TTS), Grok (xAI)

**Needs email-parse fallback (no reliable monitoring API):**
- Domain registrar (Porkbun — no login-event API)
- PaymentCloud (when live — old-school processor, likely no API)
- Any bank/brokerage portal
- Credit bureaus
- Cyber-insurance carrier
- Slack workspace admin actions (has SCIM but per-event-webhook not universal)

### Q2. Cred vault pattern

**Recommend self-hosted Infisical on VPS** — already on the roadmap as `PLAN_2026-04-12_autonomy-phase1-infisical.md` (CT-0412-03, just recovered via WIP cherry-pick commit `a4bf51f`). Fits Task 4's HIGH/CRITICAL separation: Titan gets scoped project-level JWTs per cred category (LOW + MEDIUM); HIGH/CRITICAL creds live in a separate Infisical project Solon unlocks per-session via TOTP. Replaces flat `/root/.titan-env` for secrets above MEDIUM.

### Q3. Canary patterns to add

- **Honeytoken SSH key** at `/root/.ssh/id_ed25519.backup` on VPS — read-only fires canary (uses canarytokens file-open beacon). Anyone who pops root + scans .ssh for stashed keys gets caught.
- **Honeytoken GitHub commit** in a dummy public repo (e.g. `AiMarketingGenius/archive-samples`) with a fake AWS access key in a Python file — fires on any use on the open internet.
- **Canary folder in AMG Google Drive** named `Solon CEO Private` with a PDF tracker inside — anyone who spiders the Drive gets the beacon. (Does NOT touch Dr. SEO Workspace per brand separation.)
- **Canary Supabase RLS policy** — a dummy table `public.financial_reports_confidential` with RLS allowing only `service_role` + an insert trigger that logs any SELECT attempt (fires if attacker reaches in with a stolen service key).

### Q4. Prompt-injection scan on ALL prompts — architectural risk

**Latency acceptable (~30-80ms per scan with Flash-Lite).** The architectural risk: the scanner itself is a prompt target. Mitigations:
- Run scanner with ZERO tool access (pure text-in / verdict-out)
- Hardened system prompt declaring scanner's verdict-only scope
- Second-layer hash check: scanner output must match regex `^(CLEAN|SUSPICIOUS|BLOCK)(:.{0,500})?$` — anything else = treat as SUSPICIOUS (scanner itself compromised)
- Separate Gemini API key for scanner — its own $5/mo budget cap so a runaway scan loop doesn't eat the verification budget

Feasible to ship as part of Task 4 step 5.

---

## 4. Phase 1 sprint sequencing (canonical order Titan will follow)

1. **Step 6.4** — Mobile PWA scaffold (React + Vite + AMG brand + voice orb + 4 lifecycle buttons + push opt-in + PWA manifest + service worker). Builds against STUBBED auth (503s OK — PWA surfaces graceful "Configure credentials" state).
2. **Natural pause → Phase 0 gate check** with Solon (Viktor canary trap).
3. **Step 6.5** — Voice I/O wiring (Deepgram STT + ElevenLabs TTS, integrated with existing `/api/titan/{stt,tts,chat}`).
4. **Step 6.6** — Auth/security Sonar Pro consult (Perplexity credits now funded per MCP decision).
5. **Step 7** — CRM multi-tenant (CT-0417-35: RLS + Email Outbound + Voice AI Outbound).
6. **Step 8** — AIMG extension POST-output fact-checking (inline visual indicators).
7. **Step 9** — Command Center Portal (Atlas admin card pattern × 15 monitoring surfaces per scope-lock).
8. **Ship signal** → MCP `sprint-phase-1-complete` tag + Ntfy push to Solon.

Phase 2 kicks off on that signal; Titan does not fork back to Phase 1 items once Phase 2 starts.

---

## 5. Standing rule compliance notes

- **No Slack refs** — will scan every Phase 1 commit message + doctrine drift check for `#solon-command` or similar; strip before push. Also folded into the Phase 2 Gemini-CLI doctrine-drift rubric so stale refs elsewhere in the repo get caught in Task 3 §3.4-6(c).
- **Rule #10** — this response itself lives in `plans/` as a `.md` file; chat message points at the file. Walk-through responses (Phase 2 Tasks 1 + 2) will stay under 20 lines per step per the protocol.
- **Brevity** — all Phase 1 progress updates to Solon will use the `Now / Next / Blocked on` format from CLAUDE.md §2. No essays.
- **Hard Limits** — no credential writes, no destructive ops, no external communications without Solon green light. Phase 0 canary deploy requires Solon session cookie + explicit "go" per Task 0.0 gating.
