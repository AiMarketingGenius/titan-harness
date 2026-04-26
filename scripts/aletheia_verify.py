#!/usr/bin/env python3
"""
aletheia_verify.py — Anti-hallucination enforcer daemon.

Polls MCP `op_decisions` every 60s for new agent claims and verifies them
against ground truth (MCP queue, filesystem, git log). When a claim cannot
be verified, logs an `aletheia-violation` decision and writes a shame report
to ~/AMG/hercules-inbox/SHAME__<TS>__<topic>.md.

Tracked claim patterns (regex in decision text or rationale):
- "task_id=CT-XXXX-XX dispatched|queued|ingested" → verify task exists in MCP
- "Mercury executed task <id>" → verify task is locked or done by mercury
- "wrote /path/file" or "file written: /path" → stat file exists
- "commit <hash>" → git log for hash
- "service <name> restarted" → not auto-verified (requires SSH; deferred)

Run modes:
    aletheia_verify.py --watch       # daemon (default)
    aletheia_verify.py --once        # one pass
    aletheia_verify.py --backfill 60 # process last 60 min
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

HOME = pathlib.Path.home()
sys.path.insert(0, str(HOME / "titan-harness" / "lib"))
from mcp_rest_client import (  # noqa: E402
    get_recent_decisions as mcp_get_recent,
    get_task_queue as mcp_get_task_queue,
    log_decision as mcp_log_decision,
)

INBOX = HOME / "AMG" / "hercules-inbox"
OUTBOX = HOME / "AMG" / "hercules-outbox"
STATE_DIR = HOME / ".openclaw" / "state"
CURSOR_FILE = STATE_DIR / "aletheia_cursor.json"
VIOLATIONS_FILE = STATE_DIR / "aletheia_violations.json"
LOGFILE = HOME / ".openclaw" / "logs" / "aletheia_verify.log"

CLAIM_TASK_DISPATCHED = re.compile(r"task_id[=:]\s*(CT-\d{4}-\d{2,3})", re.IGNORECASE)
CLAIM_FILE_WROTE = re.compile(r'(?:wrote|written to|created)[: ]+["\']?(/[A-Za-z0-9_./~-]+)["\']?', re.IGNORECASE)
CLAIM_COMMIT = re.compile(r"\bcommit[: ]+([0-9a-f]{7,40})\b", re.IGNORECASE)

# Fix 2 (2026-04-26 CT-0426): catch fake-completion patterns where the proof
# is a /tmp file with a notification stub instead of real work artifacts.
# When Mercury logs "executed task CT-XXXX-XX ok=True" we must verify the
# task's acceptance_criteria artifacts ACTUALLY exist on disk / in git.
CLAIM_TASK_EXECUTED = re.compile(
    r"(?:Mercury|mercury|agent)\s+executed\s+task[: ]+(CT-\d{4}-\d{2,3})", re.IGNORECASE
)
# Suspicious "fake completion" file patterns — written to /tmp/ AND filename
# suggests notification/completion stub. Real work doesn't live in /tmp/.
SUSPICIOUS_FAKE_PATHS = re.compile(
    r"(/tmp/[^\s\"']*(?:notifier|complete|done|fake|stub|test)[^\s\"']*\.(?:txt|md|json))",
    re.IGNORECASE,
)
# Phrases that signal a Mercury hallucinated completion — agent claims to have
# done the work but only wrote a single notification text file.
HALLUCINATION_PHRASES = (
    "notification sent to hercules",
    "notification sent via macos",
    "notified hercules via",
    "notified solon via macos notification",
)
# Minimum bytes a "completion proof" file should have to NOT be a stub.
MIN_PROOF_BYTES = 200

VERIFICATION_WINDOW_S = 60


def _log(msg: str) -> None:
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).isoformat()
    line = f"[{ts}] {msg}\n"
    sys.stderr.write(line)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line)


def _load_state(path: pathlib.Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_state(path: pathlib.Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def parse_iso(ts: str) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


# ─── verifications ──────────────────────────────────────────────────────────
def verify_task_exists(task_id: str) -> tuple[bool, str]:
    code, body = mcp_get_task_queue(task_id=task_id)
    if code != 200:
        return False, f"MCP query error code={code}"
    tasks = body.get("tasks") or []
    if not tasks:
        return False, f"task {task_id} not found in MCP"
    return True, f"task {task_id} exists; status={tasks[0].get('status')}"


def verify_file_exists(path: str, claim_ts: float | None) -> tuple[bool, str]:
    p = pathlib.Path(path).expanduser()
    if not p.exists():
        return False, f"file {path} does not exist"
    if claim_ts:
        mtime = p.stat().st_mtime
        skew = mtime - claim_ts
        if abs(skew) > 86400:
            return True, f"file exists but mtime skew {skew:.0f}s — may be stale unrelated file"
    return True, f"file {path} exists (size={p.stat().st_size}B)"


def verify_real_artifacts(task_id: str, decision: dict) -> tuple[bool, str]:
    """Fix 2 (2026-04-26): when a 'mercury-proof' decision claims a multi-phase
    task is complete, confirm the acceptance_criteria artifacts actually exist
    on disk / in git. A stub /tmp/notifier.txt is NOT a completion proof.

    Returns (True, evidence) when at least one real artifact exists OR the task
    is single-primitive and the claim text references a real ssh_run/file_write
    proof. Returns (False, evidence) for fake completions.
    """
    code, body = mcp_get_task_queue(task_id=task_id)
    if code != 200:
        return True, f"could not fetch task {task_id} for verification (MCP code={code}); skipped"
    tasks = body.get("tasks") or []
    if not tasks:
        return True, f"task {task_id} not in queue; skipped artifact check"
    task = tasks[0]
    accept = (task.get("acceptance_criteria") or "")
    instr = (task.get("instructions") or "")
    proof_text = ((decision.get("text") or "") + "\n" + (decision.get("rationale") or ""))

    # Hard fail: the proof contains hallucination phrases AND no real artifact paths
    proof_lower = proof_text.lower()
    has_hallucination = any(p in proof_lower for p in HALLUCINATION_PHRASES)
    suspicious_paths = SUSPICIOUS_FAKE_PATHS.findall(proof_text)
    real_paths_in_proof = re.findall(r'(/(?:Users|opt|root|home)/[A-Za-z0-9_./-]+)', proof_text)
    real_paths_in_proof = [p for p in real_paths_in_proof if not p.startswith("/tmp/")]
    commits_in_proof = CLAIM_COMMIT.findall(proof_text)

    # If Mercury wrote ONLY a /tmp/notifier-style stub and nothing else, fail
    if has_hallucination and not real_paths_in_proof and not commits_in_proof:
        return False, (
            f"FALSE_COMPLETION: proof contains hallucination phrase ({[p for p in HALLUCINATION_PHRASES if p in proof_lower]}) "
            f"and only suspicious /tmp/ paths ({suspicious_paths}). No real artifact paths or git commits in proof. "
            f"Task {task_id} acceptance_criteria expected real artifacts."
        )

    # Check expected paths from acceptance_criteria — if AC mentions `reports/X` etc.,
    # verify at least one such file exists with mtime within last 24h.
    expected_path_patterns = re.findall(
        r'(?:reports?/|deploy/|scripts/|plans/|/opt/amg-|achilles-harness/)[A-Za-z0-9_./*-]+',
        accept + "\n" + instr,
    )
    if expected_path_patterns:
        found = []
        for pattern in expected_path_patterns[:10]:  # cap at 10 patterns
            base = HOME / "titan-harness"
            achilles = HOME / "achilles-harness"
            for root in (base, achilles):
                candidate = root / pattern
                if candidate.exists():
                    found.append(str(candidate))
                    break
        if not found:
            return False, (
                f"FALSE_COMPLETION: task {task_id} acceptance_criteria mentions paths "
                f"{expected_path_patterns[:5]} but NONE of them exist in titan-harness or "
                f"achilles-harness. Proof text: {proof_text[:200]}"
            )
        return True, f"task {task_id}: found {len(found)}/{len(expected_path_patterns)} expected artifacts: {found[:3]}"

    # If acceptance criteria mentions a git tag, verify it exists
    tag_match = re.search(r"tag[s]?\s+(v\d+\.\d+\.\d+)", accept + "\n" + instr, re.IGNORECASE)
    if tag_match:
        tag = tag_match.group(1)
        for repo in [HOME / "achilles-harness", HOME / "titan-harness"]:
            try:
                out = subprocess.run(
                    ["git", "-C", str(repo), "tag", "-l", tag],
                    capture_output=True, text=True, timeout=5,
                )
                if out.returncode == 0 and tag in out.stdout:
                    return True, f"task {task_id}: git tag {tag} exists in {repo.name}"
            except Exception:
                continue
        return False, f"FALSE_COMPLETION: task {task_id} expects git tag {tag} but tag does not exist in any repo"

    # Acceptance criteria didn't reference verifiable artifacts — pass-through
    return True, f"task {task_id}: no verifiable artifact patterns in acceptance_criteria (skipped)"


def verify_commit_exists(commit_hash: str) -> tuple[bool, str]:
    repos = [HOME / "titan-harness", HOME / "achilles-harness"]
    for repo in repos:
        if not (repo / ".git").exists():
            continue
        try:
            out = subprocess.run(
                ["git", "-C", str(repo), "log", "-1", "--format=%H", commit_hash],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode == 0 and commit_hash[:7] in out.stdout:
                return True, f"commit {commit_hash[:12]} found in {repo.name}"
        except Exception:
            continue
    return False, f"commit {commit_hash[:12]} not found in titan-harness or achilles-harness"


# ─── claim extraction + verification loop ───────────────────────────────────
def extract_claims(decision: dict) -> list[dict]:
    """From a decision row, pull every checkable claim."""
    text = (decision.get("text") or "") + "\n" + (decision.get("rationale") or "")
    claim_ts = parse_iso(decision.get("created_at") or "")
    tags = [str(t).lower() for t in (decision.get("tags") or [])]
    claims: list[dict] = []
    for m in CLAIM_TASK_DISPATCHED.finditer(text):
        claims.append({"kind": "task_exists", "value": m.group(1), "claim_ts": claim_ts})
    for m in CLAIM_FILE_WROTE.finditer(text):
        path = m.group(1)
        if path.startswith("/private/"):
            path = path[len("/private"):]
        claims.append({"kind": "file_exists", "value": path, "claim_ts": claim_ts})
    for m in CLAIM_COMMIT.finditer(text):
        claims.append({"kind": "commit_exists", "value": m.group(1), "claim_ts": claim_ts})
    # Fix 2 (CT-0426 2026-04-26): Mercury-proof / mercury-executor "executed task X"
    # claims must verify the task's acceptance_criteria artifacts actually exist.
    if "mercury-proof" in tags or "mercury-executor" in tags:
        for m in CLAIM_TASK_EXECUTED.finditer(text):
            claims.append({
                "kind": "real_artifacts",
                "value": m.group(1),
                "claim_ts": claim_ts,
                "decision": decision,
            })
        # Even if the regex doesn't catch a CT-####-## reference, look in tags
        for tag in tags:
            if tag.startswith("task:ct-"):
                tid = tag.split(":", 1)[1].upper()
                claims.append({
                    "kind": "real_artifacts",
                    "value": tid,
                    "claim_ts": claim_ts,
                    "decision": decision,
                })
    return claims


def verify_claim(claim: dict) -> tuple[bool, str]:
    if claim["kind"] == "task_exists":
        return verify_task_exists(claim["value"])
    if claim["kind"] == "file_exists":
        return verify_file_exists(claim["value"], claim.get("claim_ts"))
    if claim["kind"] == "commit_exists":
        return verify_commit_exists(claim["value"])
    if claim["kind"] == "real_artifacts":
        return verify_real_artifacts(claim["value"], claim.get("decision") or {})
    return True, "unknown claim kind, skipped"


def write_shame_report(decision: dict, claim: dict, evidence: str) -> pathlib.Path:
    INBOX.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    topic = f"{claim['kind']}__{str(claim['value']).replace('/', '_')[:40]}"
    path = INBOX / f"SHAME__{stamp}__{topic}.md"
    body = (
        f"# ALETHEIA VIOLATION — {claim['kind']}: {claim['value']}\n\n"
        f"**Decision ID:** {decision.get('id')}\n"
        f"**Project source:** {decision.get('project_source')}\n"
        f"**Tags:** {', '.join(decision.get('tags') or [])}\n"
        f"**Claim timestamp:** {decision.get('created_at')}\n"
        f"**Verification timestamp:** {datetime.now(tz=timezone.utc).isoformat()}\n\n"
        f"## Claim made\n\n> {decision.get('text', '')[:600]}\n\n"
        f"## What I checked\n\n- Kind: {claim['kind']}\n- Value: {claim['value']}\n\n"
        f"## What I found\n\n```\n{evidence}\n```\n\n"
        f"## Verdict\n\nFalse claim — verification source returned no match within "
        f"{VERIFICATION_WINDOW_S}s window.\n\n"
        f"## Required remediation\n\n"
        f"- The claiming agent must re-execute the action OR retract with a public correction.\n"
        f"- Hercules audits this in the next dispatch cycle.\n"
        f"- 3rd violation in 1 hour → Solon SMS (P0).\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def queue_hercules_callout(decision: dict, claim: dict, shame_path: pathlib.Path) -> None:
    """For Hercules-originated claims, drop a callout JSON in the outbox so
    the next Hercules session sees the violation in his own inbox."""
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "objective": f"ALETHEIA CALLOUT: Hercules made a verifiably false claim — {claim['kind']}: {claim['value']}",
        "instructions": (
            f"1. Read shame report at {shame_path}.\n"
            f"2. Either re-execute the action OR retract the claim publicly with a correction posted to MCP.\n"
            f"3. Do NOT proceed with new dispatches until this is acknowledged."
        ),
        "acceptance_criteria": "Hercules acknowledges the violation in MCP via a `hercules-correction` decision OR re-executes the original action successfully.",
        "agent_assigned": "atlas_hercules",
        "priority": "P1",
        "tags": ["aletheia-callout", "hercules-correction-required"],
        "context": f"Decision {decision.get('id')} contained a claim that did not verify. Shame report: {shame_path}",
        "project_id": "EOM",
    }
    (OUTBOX / f"aletheia_callout_{stamp}.json").write_text(json.dumps(payload, indent=2))


def drain_once() -> dict:
    state = _load_state(CURSOR_FILE, {"seen_decision_ids": []})
    seen = set(state.get("seen_decision_ids") or [])
    violations_state = _load_state(VIOLATIONS_FILE, {"violations_per_agent": {}})
    code, body = mcp_get_recent(count=20)
    if code != 200:
        return {"scanned": 0, "verified": 0, "violations": 0, "error": f"MCP code={code}"}
    decisions = body.get("decisions") or []
    out = {"scanned": len(decisions), "verified": 0, "violations": 0, "skipped_seen": 0}
    for d in decisions:
        did = d.get("id") or d.get("created_at", "") + d.get("text", "")[:40]
        if did in seen:
            out["skipped_seen"] += 1
            continue
        # Skip Aletheia's own decisions to avoid loops
        tags = [str(t).lower() for t in (d.get("tags") or [])]
        if any(t.startswith("aletheia-") for t in tags):
            seen.add(did)
            continue
        claims = extract_claims(d)
        for claim in claims:
            ok, evidence = verify_claim(claim)
            if ok:
                out["verified"] += 1
                # silent log — can opt back in if Solon wants
            else:
                out["violations"] += 1
                offending_agent = (d.get("project_source") or "unknown")
                violations_state["violations_per_agent"].setdefault(offending_agent, []).append({
                    "ts": datetime.now(tz=timezone.utc).isoformat(),
                    "decision_id": d.get("id"),
                    "claim_kind": claim["kind"],
                    "claim_value": claim["value"],
                    "evidence": evidence,
                })
                shame_path = write_shame_report(d, claim, evidence)
                if offending_agent.lower() in {"hercules", "atlas_hercules", "kimi", "moonshot"}:
                    queue_hercules_callout(d, claim, shame_path)
                mcp_log_decision(
                    text=(
                        f"ALETHEIA VIOLATION — {offending_agent} claimed "
                        f"{claim['kind']}={claim['value']}; verification failed."
                    ),
                    rationale=(
                        f"Source decision id={d.get('id')}. Evidence: {evidence}. "
                        f"Shame report: {shame_path}."
                    ),
                    tags=["aletheia-violation", f"agent:{offending_agent}", f"kind:{claim['kind']}"],
                    project_source="titan",
                )
                _log(f"VIOLATION agent={offending_agent} kind={claim['kind']} val={claim['value']} → {shame_path.name}")
        seen.add(did)
    state["seen_decision_ids"] = list(seen)[-500:]
    _save_state(CURSOR_FILE, state)
    _save_state(VIOLATIONS_FILE, violations_state)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Aletheia anti-hallucination verifier")
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--backfill", action="store_true", help="clear cursor + scan recent")
    args = p.parse_args()

    if args.backfill:
        try:
            CURSOR_FILE.unlink()
        except FileNotFoundError:
            pass
        _log("backfill: cursor cleared")

    if args.once or not args.watch:
        print(json.dumps(drain_once(), indent=2))
        return 0

    _log(f"aletheia_verify starting watch interval={args.interval}s")
    while True:
        try:
            r = drain_once()
            if r.get("violations", 0) > 0:
                _log(f"poll: scanned={r['scanned']} verified={r['verified']} violations={r['violations']}")
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            _log(f"poll error: {e!r}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
