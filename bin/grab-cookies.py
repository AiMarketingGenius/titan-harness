#!/usr/bin/env python3
"""
titan-harness/bin/grab-cookies.py

One-shot credential harvester for the 2FA batch unlock (`plans/BATCH_2FA_UNLOCK_2026-04-12.md`).

Reads cookies from Solon's active Chrome/Brave/Firefox profile for claude.ai,
perplexity.ai, and loom.com, writes them to local temp env files, then scp's
them to the VPS secrets directory (`/opt/titan-harness-secrets/`) with 600 perms.

The script NEVER prints cookie values — only counts and file paths. The values
flow local temp → scp → VPS, never through stdout or any LLM context.

Usage:
    python3 bin/grab-cookies.py

Prerequisites:
    pip3 install --user browser_cookie3
    You must be logged into claude.ai / perplexity.ai / loom.com in at least
    one browser (Chrome / Brave / Firefox / Edge).
    macOS may prompt for your login password once (Keychain unlock for
    Chrome's cookie encryption key).

Gmail OAuth is separate (step 4 of the 2FA checklist) — OAuth is its own
flow and requires Google consent UI, not a cookie grab.
"""
import os
import sys
import tempfile
import subprocess
from pathlib import Path

try:
    import browser_cookie3
except ImportError:
    print("ERROR: browser_cookie3 not installed.")
    print()
    print("Install with:")
    print("    pip3 install --user --break-system-packages browser_cookie3")
    print()
    print("Then re-run: python3 bin/grab-cookies.py")
    sys.exit(1)

VPS_HOST = os.environ.get("TITAN_VPS_HOST", "170.205.37.148")
SECRETS_DIR = "/opt/titan-harness-secrets"

TARGETS = {
    "claude.ai": {
        "file": "claude_ai.env",
        "cookies": ["sessionKey"],
        "var_prefix": "CLAUDE_AI",
    },
    "perplexity.ai": {
        "file": "perplexity.env",
        "cookies": [
            "__Secure-next-auth.session-token",
            "__cf_bm",
            "pplx.visitor-id",
        ],
        "var_prefix": "PERPLEXITY",
    },
    "loom.com": {
        "file": "loom.env",
        "cookies": ["connect.sid", "__Secure-next-auth.session-token"],
        "var_prefix": "LOOM",
    },
}

BROWSER_ORDER = [
    ("Chrome", "chrome"),
    ("Brave", "brave"),
    ("Firefox", "firefox"),
    ("Edge", "edge"),
    ("Safari", "safari"),
]


def try_browser(domain):
    """Try each browser in priority order until we find cookies for this domain."""
    for label, fn_name in BROWSER_ORDER:
        func = getattr(browser_cookie3, fn_name, None)
        if func is None:
            continue
        try:
            cj = func(domain_name=domain)
            # Materialize to list so we can check length without exhausting the iterator
            cookies = list(cj)
            if cookies:
                return label, cookies
        except Exception as e:
            # Most common: Chrome App Bound Encryption error on macOS, profile not found, etc.
            # Silently try the next browser. We'll report at the end.
            continue
    return None, []


def slugify_var(name):
    return name.upper().replace("-", "_").replace(".", "_")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="titan-creds-"))
    found = {}
    missing = []

    print("=" * 60)
    print(" TITAN-HARNESS: one-shot cookie grabber")
    print("=" * 60)
    print()
    print("Reading cookies from your logged-in browser session.")
    print("macOS may prompt for your login password (Keychain unlock).")
    print()

    for domain, cfg in TARGETS.items():
        browser, cookies = try_browser(domain)
        if not cookies:
            print(f"  [MISS] {domain}: no cookies found in any browser")
            missing.append(domain)
            continue

        got = {}
        for cookie in cookies:
            if cookie.name in cfg["cookies"]:
                got[cookie.name] = cookie.value

        if not got:
            print(f"  [WARN] {domain}: {browser} has a session but no matching cookies — are you logged in?")
            missing.append(domain)
            continue

        lines = []
        for cname, cval in got.items():
            var = f"{cfg['var_prefix']}_{slugify_var(cname)}"
            lines.append(f"{var}={cval}")

        env_file = tmp / cfg["file"]
        env_file.write_text("\n".join(lines) + "\n")
        env_file.chmod(0o600)
        found[domain] = (env_file, browser, len(got))
        print(f"  [ OK ] {domain}: {len(got)} cookie(s) from {browser}")

    if not found:
        print()
        print("ERROR: no cookies found in any browser for any target domain.")
        print("Log into claude.ai / perplexity.ai / loom.com in Chrome, Brave,")
        print("or Firefox, then re-run this script.")
        sys.exit(2)

    print()
    print(f"Uploading {len(found)} env file(s) to {VPS_HOST}:{SECRETS_DIR}/ ...")

    # Ensure secrets dir exists on VPS with correct perms
    try:
        subprocess.run(
            [
                "ssh",
                VPS_HOST,
                f"sudo mkdir -p {SECRETS_DIR} && sudo chmod 700 {SECRETS_DIR}",
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(f"ERROR: could not ssh to {VPS_HOST} or create {SECRETS_DIR}.")
        print("Check your SSH config and that you can run 'ssh 170.205.37.148' manually.")
        sys.exit(3)

    for domain, (env_file, browser, count) in found.items():
        remote_final = f"{SECRETS_DIR}/{TARGETS[domain]['file']}"
        remote_tmp = f"/tmp/titan-creds-{os.getpid()}-{TARGETS[domain]['file']}"

        # scp to temp (no sudo needed, user-writable), then sudo-mv to final location
        subprocess.run(
            ["scp", "-q", str(env_file), f"{VPS_HOST}:{remote_tmp}"],
            check=True,
        )
        subprocess.run(
            [
                "ssh",
                VPS_HOST,
                f"sudo mv {remote_tmp} {remote_final} && "
                f"sudo chmod 600 {remote_final} && "
                f"sudo chown root:root {remote_final}",
            ],
            check=True,
        )
        print(f"  [ OK ] {remote_final} (mode 600, root-owned)")

    # Clean up local tmp (overwrite-then-unlink for defense-in-depth)
    for env_file, _, _ in found.values():
        try:
            size = env_file.stat().st_size
            env_file.write_bytes(b"\x00" * size)
            env_file.unlink()
        except Exception:
            pass
    try:
        tmp.rmdir()
    except Exception:
        pass

    print()
    print("=" * 60)
    print(f" DONE: {len(found)}/{len(TARGETS)} cookie-based creds landed on VPS.")
    if missing:
        print(f" Missing: {', '.join(missing)}")
        print(" Log into the missing site(s) in a supported browser and re-run.")
    print("=" * 60)
    print()
    print("Remaining step: Gmail OAuth (step 4 of BATCH_2FA_UNLOCK).")
    print("That's a separate Google consent flow — not a cookie grab.")
    print("Tell Titan 'cookies done' and he'll run verify-secrets + kick off")
    print("MP-1 harvest, then walk you through the Gmail OAuth flow.")


if __name__ == "__main__":
    main()
