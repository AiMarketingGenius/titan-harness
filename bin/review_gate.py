#!/usr/bin/env python3
"""
bin/review_gate.py — Titan Perplexity Reviewer Loop interface
Doctrine: DR_TITAN_AUTONOMY_BLUEPRINT.md §9
Version:  1.0.0

Usage:
    python bin/review_gate.py --bundle <path_to_bundle_dir> --step-id <STEP_ID>

Stdout: JSON object { grade, approved, risk_tags, rationale, remediation }

Exit codes:
    0 = approved  (grade A or A-, risk_tags empty)
    1 = not approved (grade < A- or risk_tags present)
    2 = error     (network failure, malformed response, missing files)
        → Caller must treat exit 2 as NOT approved and escalate to Solon.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────────────────────────
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL   = "sonar-pro"      # Computer-class reasoning
MAX_SECTION_CHARS  = 4_000            # Per-section trim (2026-04-11 tightened for budget)
MCP_LOG_ENDPOINT   = os.environ.get("MCP_ENDPOINT", "http://memory.aimarketinggenius.io")

# Transport fallback order (2026-04-12 Solon directive: fully automated, no manual relay):
#   1. slack-computer — Titan bot in #titan-aristotle @mentions Perplexity Computer,
#      polls reply, parses JSON. Uses Solon's Pro credits (no API billing). DORMANT
#      until /oauth SPA unblocks (see RADAR).
#   2. perplexity-api — POST to api.perplexity.ai/chat/completions. ACTIVE PRIMARY
#      while Slack path is dormant. Gated by monthly-budget + daily-call-cap.
#   3. (none available) → exit 2, escalate to Solon.
TRANSPORT_FALLBACK_ORDER = ["slack-computer", "perplexity-api"]

# ── BUDGET GUARDRAIL (2026-04-11 Solon directive, non-negotiable) ─────────────
# Pool total = $50 (one-time top-up, must last a long time).
# Target    <= $10 / month spend.
# Soft cap  <= 30 review_gate calls / day.
# Fail-closed + escalate to Solon if projected to exceed either cap.
PERPLEXITY_API_MONTHLY_BUDGET_USD = float(os.environ.get("TITAN_PPLX_API_MONTHLY_BUDGET_USD", "10.0"))
PERPLEXITY_API_MONTHLY_POOL_USD   = float(os.environ.get("TITAN_PPLX_API_MONTHLY_POOL_USD",   "50.0"))
PERPLEXITY_API_DAILY_CALL_CAP     = int(  os.environ.get("TITAN_PPLX_API_DAILY_CALL_CAP",     "30"))
PERPLEXITY_API_SPEND_LOG = Path("/var/log/titan/perplexity-api-spend.jsonl")
PERPLEXITY_API_COST_PER_CALL_USD = 0.05  # Estimate: sonar-pro ~$5/1M in, ~$15/1M out
                                         # per review bundle averages ~5K tokens → ~$0.05

# ─── CANONICAL SYSTEM PROMPT (blueprint §9.7) ──────────────────────────────────
# DO NOT MODIFY without a Solon-approved doctrine edit.
SYSTEM_PROMPT = """\
You are the Perplexity Computer autonomous reviewer for Titan, a Claude Code + VPS AI agent \
harness operated by Solon (AMG / AI Marketing Genius). Your sole job is to grade a completed \
phase step and decide whether Titan may auto-continue or must escalate to Solon.

Hard rules you must never override:
- New credentials, API keys, OAuth flows, TOTP/2FA setup or rotation \
→ always return approved: false, risk_tag "HARD_LIMIT_CREDS"
- Any money, cost, billing, or payment processor change (Stripe, Paddle, etc.) \
→ always return approved: false, risk_tag "HARD_LIMIT_MONEY"
- Destructive data operations on production databases (DROP TABLE, DELETE without confirmed \
backup, TRUNCATE prod) → always return approved: false, risk_tag "HARD_LIMIT_DESTRUCTIVE"
- Edits to CORE_CONTRACT.md, CLAUDE.md, DR_TITAN_AUTONOMY_BLUEPRINT.md, or SESSION_PROMPT.md \
→ always return approved: false, risk_tag "HARD_LIMIT_DOCTRINE"

Grading scale:
A  = Executed correctly, matches blueprint intent, no risk, metrics meet or exceed target. Auto-continue approved.
A- = Executed correctly with a minor deviation or one low-severity warning, no blocking risk. Auto-continue approved.
B+ = Executed with notable gaps or one medium-severity issue. Escalate to Solon.
B  = Significant gaps or multiple medium issues. Escalate to Solon.
B- or below = Serious problems or missing deliverables. Escalate to Solon.

Risk tags — return all that apply, empty array if none:
HARD_LIMIT_CREDS | HARD_LIMIT_MONEY | HARD_LIMIT_DESTRUCTIVE | HARD_LIMIT_DOCTRINE |
SECURITY_RISK | DATA_INTEGRITY_RISK | REGRESSION_RISK | SCOPE_CREEP | INCOMPLETE | METRICS_MISS

Return ONLY a valid JSON object. No prose before or after the JSON.\
"""

USER_PROMPT_TEMPLATE = """\
Grade the following Titan phase step.

=== STEP METADATA ===
{step_meta}

=== GIT DIFF ===
{git_diff}

=== COMMAND LOG ===
{command_log}

=== METRICS ===
{metrics}

=== BLUEPRINT REFERENCE (governing section) ===
{blueprint_ref}

Return ONLY the JSON object in this exact schema:
{{
  "grade": "A" | "A-" | "B+" | "B" | "B-" | "C" | "F",
  "approved": true | false,
  "risk_tags": [],
  "rationale": "<2-4 sentence plain-English explanation of the grade>",
  "remediation": "<one concise fix instruction if approved is false, else empty string>"
}}\
"""


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def _trim(text: str, limit: int = MAX_SECTION_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [TRUNCATED at {limit} chars]"


def load_bundle(bundle_path: Path) -> dict:
    required = {
        "step_meta.json": "step_meta",
        "git_diff.patch": "git_diff",
        "command_log.txt": "command_log",
        "metrics.json": "metrics",
        "blueprint_ref.md": "blueprint_ref",
    }
    bundle = {}
    missing = []
    for fname, key in required.items():
        fpath = bundle_path / fname
        if not fpath.exists():
            missing.append(fname)
            bundle[key] = f"[FILE MISSING — {fname} not found in bundle]"
        else:
            raw = fpath.read_text(encoding="utf-8", errors="replace")
            bundle[key] = _trim(raw)
    if missing:
        print(f"[review_gate] WARNING: Missing bundle files: {missing}", file=sys.stderr)
    return bundle


def call_perplexity(bundle: dict) -> dict:
    # Try env var first, fall back to silent Infisical fetch
    api_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
            from infisical_fetch import get_secret, SecretFetchError
            try:
                api_key = get_secret("PERPLEXITY_API_KEY", project="harness-core").strip()
            except SecretFetchError:
                pass
        except ImportError:
            pass
    if not api_key:
        raise RuntimeError(
            "PERPLEXITY_API_KEY is not set. Add it to Infisical harness-core/dev "
            "or ensure it's in the process env."
        )

    user_content = USER_PROMPT_TEMPLATE.format(**bundle)

    payload = json.dumps({
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 512,
    }).encode("utf-8")

    req = urllib.request.Request(
        PERPLEXITY_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    content = raw["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences if model wraps output
    if content.startswith("```"):
        lines = content.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        content = "\n".join(lines).strip()

    return json.loads(content)


def validate_result(raw: dict) -> dict:
    """Enforce schema, type safety, and Hard Limit override rules."""
    valid_grades = {"A", "A-", "B+", "B", "B-", "C", "F"}

    grade     = str(raw.get("grade", "F"))
    if grade not in valid_grades:
        grade = "F"

    approved  = bool(raw.get("approved", False))
    risk_tags = list(raw.get("risk_tags", []))
    rationale  = str(raw.get("rationale", "No rationale provided."))
    remediation = str(raw.get("remediation", ""))

    # Safety override: HARD_LIMIT tags always force approved=False
    hard_tags = [t for t in risk_tags if t.startswith("HARD_LIMIT_")]
    if hard_tags:
        approved = False

    # Safety override: only A or A- with zero risk_tags may be approved
    if grade not in {"A", "A-"} or risk_tags:
        approved = False

    return {
        "grade":       grade,
        "approved":    approved,
        "risk_tags":   risk_tags,
        "rationale":   rationale,
        "remediation": remediation,
    }


# ─── TRANSPORT SELECTION + FALLBACK LOGIC ─────────────────────────────────────

def _slack_transport_available() -> tuple[bool, str]:
    """Return (available, reason). Checks SLACK_BOT_TOKEN + slack-config.json presence."""
    # Token via Infisical if available, else env var
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
        from infisical_fetch import get_secret, SecretFetchError
        try:
            _ = get_secret("SLACK_BOT_TOKEN", project="harness-core")
        except SecretFetchError:
            if not os.environ.get("SLACK_BOT_TOKEN"):
                return False, "SLACK_BOT_TOKEN not in Infisical harness-core/dev or env"
    except ImportError:
        if not os.environ.get("SLACK_BOT_TOKEN"):
            return False, "infisical_fetch not importable and SLACK_BOT_TOKEN not in env"

    if not Path("/root/.infisical/slack-config.json").exists():
        return False, "slack-config.json missing — run bin/titan-slack-setup.sh"
    return True, "ready"


def _api_transport_available() -> tuple[bool, str]:
    """Return (available, reason). Checks API key + monthly budget."""
    api_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
            from infisical_fetch import get_secret, SecretFetchError
            try:
                _ = get_secret("PERPLEXITY_API_KEY", project="harness-core")
            except SecretFetchError:
                return False, "PERPLEXITY_API_KEY not in Infisical or env"
        except ImportError:
            return False, "infisical_fetch not importable and PERPLEXITY_API_KEY not in env"

    # Budget & daily-call gate — fail-closed if either projection exceeds cap
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    today_utc  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_spend = 0.0
    month_calls = 0
    today_calls = 0
    if PERPLEXITY_API_SPEND_LOG.exists():
        try:
            for line in PERPLEXITY_API_SPEND_LOG.read_text().splitlines():
                try:
                    entry = json.loads(line)
                    if entry.get("month") == this_month:
                        month_spend += float(entry.get("cost_usd", 0))
                        month_calls += 1
                    if str(entry.get("ts", "")).startswith(today_utc):
                        today_calls += 1
                except Exception:
                    continue
        except Exception:
            pass

    # Monthly $ cap — hard gate
    if (month_spend + PERPLEXITY_API_COST_PER_CALL_USD) > PERPLEXITY_API_MONTHLY_BUDGET_USD:
        return False, (
            f"API monthly budget would be exceeded by this call: "
            f"${month_spend:.2f} + ${PERPLEXITY_API_COST_PER_CALL_USD:.2f} > "
            f"${PERPLEXITY_API_MONTHLY_BUDGET_USD:.2f} — fail-closed, escalate to Solon"
        )
    # Daily call soft-cap — hard gate (Solon must batch-approve to exceed)
    if today_calls >= PERPLEXITY_API_DAILY_CALL_CAP:
        return False, (
            f"API daily call cap reached: {today_calls} >= "
            f"{PERPLEXITY_API_DAILY_CALL_CAP} — batch work and ask Solon"
        )
    return True, (
        f"ready (month: ${month_spend:.2f} / ${PERPLEXITY_API_MONTHLY_BUDGET_USD:.2f}, "
        f"today: {today_calls}/{PERPLEXITY_API_DAILY_CALL_CAP} calls, "
        f"pool: ${PERPLEXITY_API_MONTHLY_POOL_USD:.2f})"
    )


def _record_api_spend(cost_usd: float) -> None:
    """Append a spend entry to the monthly log. Best-effort; non-fatal on failure."""
    try:
        PERPLEXITY_API_SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "month": datetime.now(timezone.utc).strftime("%Y-%m"),
            "cost_usd": cost_usd,
        }
        with PERPLEXITY_API_SPEND_LOG.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def call_slack_computer(bundle: dict) -> dict:
    """Delegate grading to Perplexity Computer in #titan-aristotle via Slack."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
    try:
        from slack_reviewer import SlackReviewer, SlackReviewerError
    except ImportError as e:
        raise RuntimeError(f"slack_reviewer module missing: {e}")
    try:
        from infisical_fetch import get_secret
        token = get_secret("SLACK_BOT_TOKEN", project="harness-core")
    except Exception:
        token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not token:
            raise RuntimeError("SLACK_BOT_TOKEN unavailable from Infisical and env")

    reviewer = SlackReviewer.from_config(token)
    step_id = os.environ.get("REVIEW_GATE_STEP_ID", "unknown")
    return reviewer.review(
        bundle=bundle,
        step_id=step_id,
        system_prompt=SYSTEM_PROMPT,
        user_template=USER_PROMPT_TEMPLATE,
    )


def select_and_call_transport(bundle: dict, preferred: str = "auto") -> tuple[dict, str]:
    """Try transports in fallback order. Returns (raw_result, transport_used).

    preferred='auto' → try each in TRANSPORT_FALLBACK_ORDER until one succeeds.
    preferred='slack-computer' or 'perplexity-api' → force that transport only.
    """
    errors = []
    candidates = TRANSPORT_FALLBACK_ORDER if preferred == "auto" else [preferred]

    for transport in candidates:
        if transport == "slack-computer":
            ok, reason = _slack_transport_available()
            if not ok:
                errors.append(f"slack-computer: {reason}")
                continue
            try:
                result = call_slack_computer(bundle)
                return result, "slack-computer"
            except Exception as e:
                errors.append(f"slack-computer call failed: {type(e).__name__}: {str(e)[:200]}")
                continue

        if transport == "perplexity-api":
            ok, reason = _api_transport_available()
            if not ok:
                errors.append(f"perplexity-api: {reason}")
                continue
            try:
                result = call_perplexity(bundle)
                _record_api_spend(PERPLEXITY_API_COST_PER_CALL_USD)
                return result, "perplexity-api"
            except Exception as e:
                errors.append(f"perplexity-api call failed: {type(e).__name__}: {str(e)[:200]}")
                continue

    # All transports exhausted
    raise RuntimeError("All reviewer transports unavailable: " + " | ".join(errors))


def _read_spend_counters() -> tuple[float, int, int]:
    """Return (month_spend_usd, month_calls, today_calls) from spend log. Best-effort."""
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    today_utc  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_spend = 0.0
    month_calls = 0
    today_calls = 0
    if PERPLEXITY_API_SPEND_LOG.exists():
        try:
            for line in PERPLEXITY_API_SPEND_LOG.read_text().splitlines():
                try:
                    entry = json.loads(line)
                    if entry.get("month") == this_month:
                        month_spend += float(entry.get("cost_usd", 0))
                        month_calls += 1
                    if str(entry.get("ts", "")).startswith(today_utc):
                        today_calls += 1
                except Exception:
                    continue
        except Exception:
            pass
    return month_spend, month_calls, today_calls


def log_to_mcp(step_id: str, bundle_path: str, result: dict, transport_used: str) -> None:
    """Best-effort MCP log_decision. Failure is non-fatal but printed to stderr.

    For API transport, includes cost estimate and running counters so Solon can
    see live budget utilisation in MCP without tailing the spend log.
    """
    try:
        month_spend, month_calls, today_calls = _read_spend_counters()
        cost_this_call = PERPLEXITY_API_COST_PER_CALL_USD if transport_used == "perplexity-api" else 0.0
        entry = {
            "step_id":              step_id,
            "bundle_path":          bundle_path,
            "transport_used":       transport_used,
            "computer_grade":       result["grade"],
            "computer_approved":    result["approved"],
            "risk_tags":            result["risk_tags"],
            "decision":             "auto-continue" if result["approved"] else "escalate",
            "hard_limit_triggered": any(t.startswith("HARD_LIMIT_") for t in result["risk_tags"]),
            "rationale":            result["rationale"],
            "solon_notified":       not result["approved"],
            "cost_usd_estimate":    cost_this_call,
            "month_spend_usd":      round(month_spend, 2),
            "month_calls":          month_calls,
            "today_calls":          today_calls,
            "monthly_cap_usd":      PERPLEXITY_API_MONTHLY_BUDGET_USD,
            "daily_cap":            PERPLEXITY_API_DAILY_CALL_CAP,
            "pool_usd":             PERPLEXITY_API_MONTHLY_POOL_USD,
            "timestamp_utc":        datetime.now(timezone.utc).isoformat(),
        }
        payload = json.dumps({"action": "log_decision", "data": entry}).encode("utf-8")
        req = urllib.request.Request(
            f"{MCP_LOG_ENDPOINT}/log_decision",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"[review_gate] MCP log_decision OK for step {step_id}", file=sys.stderr)
    except Exception as exc:
        print(f"[review_gate] WARNING: MCP log failed (non-fatal): {exc}", file=sys.stderr)


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Titan Perplexity Reviewer Loop — blueprint §9"
    )
    parser.add_argument("--bundle",  required=True, help="Path to evidence bundle directory")
    parser.add_argument("--step-id", required=True, dest="step_id",
                        help="Step ID, e.g. MP1-S3.1")
    parser.add_argument("--reviewer", default="auto",
                        choices=["auto", "slack-computer", "perplexity-api"],
                        help="Force a specific transport. Default 'auto' tries Slack first, API fallback.")
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    step_id     = args.step_id

    # Expose step_id to downstream transport callers (slack_reviewer reads this)
    os.environ["REVIEW_GATE_STEP_ID"] = step_id

    if not bundle_path.is_dir():
        err = {
            "grade": "F", "approved": False,
            "risk_tags": ["INCOMPLETE"],
            "rationale": f"Bundle directory not found: {bundle_path}",
            "remediation": "Assemble the five evidence files before calling review_gate.",
        }
        print(json.dumps(err, indent=2))
        sys.exit(2)

    bundle = load_bundle(bundle_path)

    try:
        raw_result, transport_used = select_and_call_transport(bundle, preferred=args.reviewer)
        print(f"[review_gate] transport={transport_used}", file=sys.stderr)
    except RuntimeError as exc:
        print(f"[review_gate] ERROR: {exc}", file=sys.stderr)
        err = {
            "grade": "F", "approved": False,
            "risk_tags": ["INCOMPLETE"],
            "rationale": f"All reviewer transports unavailable: {str(exc)[:300]}",
            "remediation": "Run bin/titan-slack-setup.sh OR top up PERPLEXITY_API_KEY at perplexity.ai/settings/api. Escalate to Solon.",
        }
        print(json.dumps(err, indent=2))
        sys.exit(2)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"[review_gate] HTTP {exc.code} from upstream: {body}", file=sys.stderr)
        err = {
            "grade": "F", "approved": False,
            "risk_tags": ["INCOMPLETE"],
            "rationale": f"Upstream reviewer HTTP {exc.code}. Cannot grade step.",
            "remediation": "Check reviewer transport health. Escalate to Solon.",
        }
        print(json.dumps(err, indent=2))
        sys.exit(2)
    except Exception as exc:
        print(f"[review_gate] ERROR: {exc}", file=sys.stderr)
        err = {
            "grade": "F", "approved": False,
            "risk_tags": ["INCOMPLETE"],
            "rationale": f"review_gate encountered an error: {exc}",
            "remediation": "Resolve error then re-run, or escalate to Solon.",
        }
        print(json.dumps(err, indent=2))
        sys.exit(2)

    result = validate_result(raw_result)

    # Log to MCP (best-effort — never blocks the exit code)
    log_to_mcp(step_id, str(bundle_path), result, transport_used)

    # Print final graded JSON to stdout for Titan to parse
    print(json.dumps(result, indent=2))

    # Exit: 0 = approved, 1 = not approved
    sys.exit(0 if result["approved"] else 1)


if __name__ == "__main__":
    main()
