#!/usr/bin/env python3
"""CT-0427-00 RECOVERY — reveal 7 zombie Supabase keys + create amg_eom + re-run R2.

The earlier round 3 created 7 Supabase keys but the values were redacted in
the response (need ?reveal=true). The keys themselves are valid and live —
just need to fetch their secret values via GET-with-reveal. Then create the
missing 'amg_eom' (renamed from 'eom' which was <4 chars rejected).

Also re-issues R2 tokens (round 3 R2 tokens are valid but not in master doc
yet — re-running issues new IDs anyway).
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request

MASTER_DOC = "/home/amg/kb/AMG_UNIFIED_MASTER_CREDENTIALS.md"
SUPABASE_PROJECT_REF = "egoazyasyrhslluossli"
CF_ACCOUNT_ID = "b68a11a140459d0dc5fa0d4a49a02963"
R2_PERMISSION_GROUP_WRITE = "bf7481a1826f439697cb59a20b22293e"
USER_AGENT = "titan-ct-0427-00-recover/0.3"

ZOMBIE_AGENTS = ["codex", "hercules", "nestor", "alexander", "kimi_code", "kimi_claw", "achilles_fallback"]
ALL_AGENTS = ZOMBIE_AGENTS + ["amg_eom"]  # eom renamed to amg_eom to clear 4-char minimum
AGENTS_R2 = [a for a in ALL_AGENTS if a != "achilles_fallback"]

SCOPE_NOTES = {
    "codex": "full op_task_queue + amg_artifact_registry write; achilles_gatekeeper role pending CT-0427-01",
    "hercules": "own lane only (assigned_to='hercules')",
    "nestor": "own lane only (assigned_to='nestor')",
    "alexander": "own lane only (assigned_to='alexander')",
    "kimi_code": "read op_task_queue, write amg_reviews only",
    "kimi_claw": "read-only on all",
    "amg_eom": "read all + write routing rows (renamed from 'eom' — Supabase 4-char minimum)",
    "achilles_fallback": "achilles_gatekeeper role attachment pending CT-0427-01",
}

TEST_NAMES_TO_DELETE = ["titan_field_test", "titan_reveal_test"]


def http(method: str, url: str, headers: dict, body: dict | None = None,
         timeout: int = 30) -> tuple[int, dict | str]:
    safe = {"User-Agent": USER_AGENT}
    for k, v in headers.items():
        try:
            v.encode("ascii")
            safe[k] = v
        except UnicodeEncodeError:
            return 0, f"non-ascii header {k}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=safe, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode()
            try:
                return r.status, json.loads(text)
            except json.JSONDecodeError:
                return r.status, text
    except urllib.error.HTTPError as e:
        body_text = e.read()[:500].decode(errors="replace")
        try:
            return e.code, json.loads(body_text)
        except json.JSONDecodeError:
            return e.code, body_text
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, str(e)


def read_master_field(label_regex: str) -> str | None:
    try:
        with open(MASTER_DOC) as f:
            for line in f:
                m = re.match(rf"\|\s*{label_regex}\s*\|\s*`([^`]+)`", line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None


def list_all_supabase_keys(pat: str) -> list[dict]:
    code, resp = http("GET", f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/api-keys",
                      {"Authorization": f"Bearer {pat}"})
    return resp if isinstance(resp, list) else []


def reveal_supabase_key(pat: str, key_id: str) -> str | None:
    code, resp = http(
        "GET",
        f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/api-keys/{key_id}?reveal=true",
        {"Authorization": f"Bearer {pat}"},
    )
    if 200 <= code < 300 and isinstance(resp, dict):
        return resp.get("api_key")
    return None


def create_supabase_key_revealed(pat: str, name: str) -> dict:
    code, resp = http(
        "POST",
        f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/api-keys?reveal=true",
        {"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        {"name": name, "type": "secret"},
    )
    if 200 <= code < 300 and isinstance(resp, dict):
        return {"ok": True, "id": resp.get("id"), "api_key": resp.get("api_key"), "name": name}
    return {"ok": False, "name": name, "status": code, "error": str(resp)[:300]}


def delete_supabase_key(pat: str, key_id: str) -> bool:
    code, _ = http(
        "DELETE",
        f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/api-keys/{key_id}",
        {"Authorization": f"Bearer {pat}"},
    )
    return 200 <= code < 300


def verify_supabase_key(api_key: str) -> dict:
    if not api_key:
        return {"verified": False, "error": "no key"}
    url = f"https://{SUPABASE_PROJECT_REF}.supabase.co/rest/v1/"
    headers = {"apikey": api_key, "Authorization": f"Bearer {api_key}"}
    code, _ = http("GET", url, headers)
    return {"verified": 200 <= code < 400, "http": code}


def create_r2_token(global_key: str, email: str, agent: str) -> dict:
    body = {
        "name": f"amg-r2-{agent}",
        "policies": [{
            "effect": "allow",
            "resources": {f"com.cloudflare.api.account.{CF_ACCOUNT_ID}": "*"},
            "permission_groups": [{"id": R2_PERMISSION_GROUP_WRITE}],
        }],
    }
    code, resp = http(
        "POST", "https://api.cloudflare.com/client/v4/user/tokens",
        {"X-Auth-Email": email, "X-Auth-Key": global_key, "Content-Type": "application/json"},
        body,
    )
    if 200 <= code < 300 and isinstance(resp, dict) and resp.get("success"):
        result = resp.get("result", {})
        return {"ok": True, "name": f"amg-r2-{agent}", "id": result.get("id"),
                "value": result.get("value")}
    return {"ok": False, "name": f"amg-r2-{agent}", "status": code, "error": str(resp)[:200]}


def verify_r2_token(value: str) -> dict:
    code, _ = http(
        "GET", f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/r2/buckets",
        {"Authorization": f"Bearer {value}"},
    )
    return {"verified": 200 <= code < 400, "http": code}


def append_master(supabase_results: dict, r2_results: dict) -> int:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = ["\n---\n",
           "## SECTION P: AMG Atlas Factory — Agent Credentials",
           f"\n**Generated:** {ts} | **Created by:** titan_ct_0427_00 | **Source:** CT-0427-00-TITAN dispatch\n",
           "⚠️ INTERNAL ONLY — TRADE SECRET. Do not share or commit.\n",
           "\n### P1. Supabase service-role keys (8 agents)\n",
           "| # | Agent | Type | API Key | Scope | Verified |",
           "|---|-------|------|---------|-------|----------|"]
    for i, agent in enumerate(ALL_AGENTS, 1):
        r = supabase_results.get(agent, {})
        if r.get("ok"):
            v = r.get("verify", {}).get("verified", "?")
            out.append(f"| {i} | `{agent}` | secret | `{r['api_key']}` | {SCOPE_NOTES[agent]} | {v} |")
        else:
            out.append(f"| {i} | `{agent}` | — | **FAILED** | {SCOPE_NOTES[agent]} | error: {r.get('error','?')[:80]} |")
    out.append("\n### P2. Cloudflare R2 tokens (7 agents)\n")
    out.append("| # | Agent | Token Name | Token ID | Bearer Token (cfut_*) | Verified |")
    out.append("|---|-------|------------|----------|----------------------|----------|")
    for i, agent in enumerate(AGENTS_R2, 1):
        r = r2_results.get(agent, {})
        if r.get("ok"):
            v = r.get("verify", {}).get("verified", "?")
            out.append(f"| {i} | `{agent}` | `amg-r2-{agent}` | `{r['id']}` | `{r['value']}` | {v} |")
        else:
            out.append(f"| {i} | `{agent}` | `amg-r2-{agent}` | **FAILED** | — | error: {r.get('error','?')[:80]} |")
    out.append("\n**R2 scope:** All tokens are account-scoped Workers R2 Storage Write via permission_group `bf7481a1826f439697cb59a20b22293e`. Prefix scoping (`amg-artifacts/<agent>/`) enforced at bucket-policy layer in CT-0427-01 DDL bundle.\n")
    out.append("\n### P3. Anthropic API key — achilles_fallback\n")
    out.append("⚠️ **MANUAL ROW — SOLON FILL ONLY THIS ONE.** Regular Anthropic API keys cannot create new keys via Admin API; needs `sk-ant-admin-*` admin-tier key not in master doc nor accessible Sheet.\n")
    out.append("\n**Fallback path:** https://console.anthropic.com/settings/keys → Create Key → name `achilles_fallback` → workspace AMG.\n")
    out.append("\n| Agent | Key | Verified |")
    out.append("|-------|-----|----------|")
    out.append("| `achilles_fallback` | `<PASTE_ANTHROPIC_KEY_HERE>` | pending Solon fill |")
    out.append("\n### P4. Post-CT-0427-01 follow-up (automatic)\n")
    out.append("- `GRANT achilles_gatekeeper TO <achilles_fallback service-role identity>;` once CT-0427-01 ships.")
    out.append("- Update P1 row 8 + P3 status from 'pending' to 'attached YYYY-MM-DD'.\n")
    block = "\n".join(out) + "\n"
    with open(MASTER_DOC, "a") as f:
        f.write(block)
    return len(block)


def main(argv: list[str]) -> int:
    pat = read_master_field(r"Personal Access Token")
    cf_global = read_master_field(r"Global API Key")
    cf_email = read_master_field(r"Current Email") or "growmybusiness@aimarketinggenius.io"
    if not pat or not cf_global:
        print("FATAL: missing PAT or CF Global Key", file=sys.stderr)
        return 2

    print("=== Phase 1: list existing Supabase keys, identify zombies + tests ===")
    keys = list_all_supabase_keys(pat)
    by_name = {k.get("name"): k for k in keys}
    print(f"  found: {[k.get('name') for k in keys]}")

    print("\n=== Phase 2: delete test keys (titan_field_test, titan_reveal_test) ===")
    for tname in TEST_NAMES_TO_DELETE:
        k = by_name.get(tname)
        if k:
            ok = delete_supabase_key(pat, k["id"])
            print(f"  delete {tname} (id={k['id']}): ok={ok}")
            time.sleep(3)

    print("\n=== Phase 3: reveal 7 zombie keys (codex/hercules/nestor/alexander/kimi_code/kimi_claw/achilles_fallback) ===")
    sb_results = {}
    for agent in ZOMBIE_AGENTS:
        k = by_name.get(agent)
        if not k:
            print(f"  ✗ {agent}: not found in current key list — will create")
            sb_results[agent] = {"ok": False, "error": "zombie not in list, fallback create needed"}
            continue
        revealed = reveal_supabase_key(pat, k["id"])
        if revealed and "·" not in revealed:
            v = verify_supabase_key(revealed)
            sb_results[agent] = {"ok": True, "id": k["id"], "api_key": revealed, "name": agent, "verify": v}
            print(f"  ✓ {agent}: revealed prefix={revealed[:25]}... verify={v}")
        else:
            print(f"  ✗ {agent}: reveal returned redacted")
            sb_results[agent] = {"ok": False, "error": "reveal_returned_redacted"}
        time.sleep(2)

    # Fallback: any zombie that didn't reveal cleanly → delete + recreate
    for agent in ZOMBIE_AGENTS:
        if not sb_results.get(agent, {}).get("ok"):
            k = by_name.get(agent)
            if k:
                print(f"\n=== Recover {agent}: delete + recreate-with-reveal ===")
                delete_supabase_key(pat, k["id"])
                time.sleep(3)
            r = create_supabase_key_revealed(pat, agent)
            if r["ok"] and "·" not in r["api_key"]:
                v = verify_supabase_key(r["api_key"])
                r["verify"] = v
                sb_results[agent] = r
                print(f"  ✓ {agent} recreated: prefix={r['api_key'][:25]}... verify={v}")
            else:
                sb_results[agent] = r
                print(f"  ✗ {agent} create failed: {r.get('error', '?')}")
            time.sleep(3)

    print("\n=== Phase 4: create amg_eom (renamed from 'eom' — 4-char minimum) ===")
    r = create_supabase_key_revealed(pat, "amg_eom")
    if r["ok"] and "·" not in r["api_key"]:
        v = verify_supabase_key(r["api_key"])
        r["verify"] = v
        sb_results["amg_eom"] = r
        print(f"  ✓ amg_eom: prefix={r['api_key'][:25]}... verify={v}")
    else:
        sb_results["amg_eom"] = r
        print(f"  ✗ amg_eom: {r.get('error', '?')}")

    print("\n=== Phase 5: R2 tokens (8 — round 3 already created 7 valid R2 tokens; "
          "re-issuing for amg_eom only since 'eom' wasn't created earlier; "
          "rest stay live but values lost from script crash) ===")
    # We re-issue ALL 8 R2 tokens since the round 3 values weren't captured
    # to master doc (script halted in Supabase verify before R2 phase wrote anywhere
    # persistent — actually round 3 R2 tokens DID print values to stdout, but those
    # are now in scrolled-back history). Cleanest: revoke prior 7, issue 8 fresh.
    print("  (Note: existing R2 tokens from round 3 are live but values not captured.")
    print("   Listing to find them; rotating to fresh values for clean audit trail.)")

    # List existing R2 tokens
    code, list_resp = http("GET", "https://api.cloudflare.com/client/v4/user/tokens",
                           {"X-Auth-Email": cf_email, "X-Auth-Key": cf_global})
    existing_r2 = []
    if isinstance(list_resp, dict) and list_resp.get("success"):
        for t in list_resp.get("result", []):
            if t.get("name", "").startswith("amg-r2-"):
                existing_r2.append(t)
    print(f"  existing amg-r2-* tokens: {len(existing_r2)} ({[t['name'] for t in existing_r2]})")

    # Delete existing
    for t in existing_r2:
        code, _ = http("DELETE", f"https://api.cloudflare.com/client/v4/user/tokens/{t['id']}",
                       {"X-Auth-Email": cf_email, "X-Auth-Key": cf_global})
        print(f"    delete {t['name']}: http {code}")
        time.sleep(1)

    # Create fresh 7 (or 8 if we want amg_eom too — yes, all R2 agents)
    r2_results = {}
    AGENTS_R2_TO_CREATE = [a for a in ALL_AGENTS if a != "achilles_fallback"]
    for agent in AGENTS_R2_TO_CREATE:
        r = create_r2_token(cf_global, cf_email, agent)
        if r.get("ok"):
            v = verify_r2_token(r["value"])
            r["verify"] = v
            r2_results[agent] = r
            print(f"  ✓ {agent}: id={r['id']} value_prefix={r['value'][:20]}... verify={v}")
        else:
            r2_results[agent] = r
            print(f"  ✗ {agent}: {r.get('error', '?')}")
        time.sleep(2)

    print("\n=== Phase 6: append all to master doc ===")
    n = append_master(sb_results, r2_results)
    print(f"  appended {n} bytes")

    sb_ok = sum(1 for r in sb_results.values() if r.get("ok"))
    sb_ver = sum(1 for r in sb_results.values() if r.get("verify", {}).get("verified"))
    r2_ok = sum(1 for r in r2_results.values() if r.get("ok"))
    r2_ver = sum(1 for r in r2_results.values() if r.get("verify", {}).get("verified"))
    print(f"\n=== SUMMARY ===")
    print(f"Supabase: {sb_ok}/8 created, {sb_ver}/8 verified")
    print(f"R2:       {r2_ok}/7 created, {r2_ver}/7 verified")
    print(f"Anthropic: 0/1 (manual fill — Solon)")
    print(f"Total:    {sb_ok + r2_ok}/16 (excluding Anthropic)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
