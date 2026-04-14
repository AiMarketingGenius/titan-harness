"""
lib/hmac_state.py — HMAC-signed state file + HMAC-chained audit log helpers.

Gate #2 v1.1 dependency. Keeps .harness-state/active-hypothesis.json and
.harness-state/hypothesis-audit.jsonl tamper-evident.

Key material: /etc/amg/gate2.secret on VPS, ~/.amg/gate2.secret on Mac.
32 bytes random, 0400 root:root / 0400 user. Rotate via bin/install-gate2.sh
--rotate-secret.

Audit log chaining: each line includes prev_hmac; any single-line tamper or
removal breaks the chain and is detected by verify_audit_chain().
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import tempfile
from typing import Any

GATE2_SECRET_CANDIDATES = [
    "/etc/amg/gate2.secret",
    os.path.expanduser("~/.amg/gate2.secret"),
]


def _read_secret() -> bytes:
    for p in GATE2_SECRET_CANDIDATES:
        if os.path.isfile(p):
            with open(p, "rb") as f:
                return f.read().strip()
    raise RuntimeError(
        "gate2.secret not found in any of: "
        + ", ".join(GATE2_SECRET_CANDIDATES)
        + " — run bin/install-gate2.sh --rotate-secret"
    )


def canonical_json(payload: dict[str, Any]) -> bytes:
    """Deterministic JSON encoding for HMAC. Sorted keys, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return state dict with hmac field set. Pass through; mutates copy."""
    secret = _read_secret()
    body = {k: v for k, v in state.items() if k != "hmac"}
    mac = hmac.new(secret, canonical_json(body), hashlib.sha256).hexdigest()
    out = dict(body)
    out["hmac"] = mac
    return out


def verify_state(state: dict[str, Any]) -> bool:
    secret = _read_secret()
    claim = state.get("hmac")
    if not claim:
        return False
    body = {k: v for k, v in state.items() if k != "hmac"}
    expected = hmac.new(secret, canonical_json(body), hashlib.sha256).hexdigest()
    return hmac.compare_digest(claim, expected)


def load_state(path: str | pathlib.Path) -> tuple[dict[str, Any] | None, str]:
    """
    Returns (state_dict or None, status) where status ∈ {ok, missing, tampered, parse_error}.
    """
    p = pathlib.Path(path)
    if not p.exists():
        return None, "missing"
    try:
        with open(p) as f:
            s = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None, "parse_error"
    if not verify_state(s):
        return s, "tampered"
    return s, "ok"


def write_state(path: str | pathlib.Path, state: dict[str, Any]) -> None:
    """Atomic write: tmp + rename. Caller is responsible for flock."""
    signed = sign_state(state)
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".tmp-state.", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(signed, f, sort_keys=True, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
    except Exception:
        try:
            os.unlink(tmp)
        finally:
            raise


# ----- Audit log with HMAC chain -----

def audit_append(log_path: str | pathlib.Path, entry: dict[str, Any]) -> str:
    """
    Append to HMAC-chained JSONL audit log. Returns the new line's hmac.
    Each entry carries prev_hmac; the HMAC is computed over the entry body
    INCLUDING prev_hmac, so tampering with any line breaks the chain from
    that point forward.
    """
    secret = _read_secret()
    p = pathlib.Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    prev = "GENESIS"
    if p.exists() and p.stat().st_size > 0:
        with open(p, "rb") as f:
            # Read last non-empty line efficiently
            f.seek(0, os.SEEK_END)
            size = f.tell()
            buf = b""
            pos = size
            while pos > 0 and b"\n" not in buf.strip(b"\n")[:-1]:
                step = min(4096, pos)
                pos -= step
                f.seek(pos)
                buf = f.read(step) + buf
                if pos == 0:
                    break
            lines = [l for l in buf.splitlines() if l.strip()]
            if lines:
                try:
                    prev = json.loads(lines[-1]).get("hmac", "GENESIS")
                except (json.JSONDecodeError, AttributeError):
                    prev = "CORRUPTED"

    body = dict(entry)
    body["prev_hmac"] = prev
    mac = hmac.new(secret, canonical_json(body), hashlib.sha256).hexdigest()
    line = dict(body)
    line["hmac"] = mac

    # O_APPEND for atomic append on POSIX
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (json.dumps(line, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return mac


def verify_audit_chain(log_path: str | pathlib.Path) -> tuple[bool, str]:
    """
    Walk the audit log from the beginning. Each line's hmac must match a
    recomputation over its body, AND its prev_hmac must equal the previous
    line's hmac. Returns (ok, message).
    """
    secret = _read_secret()
    p = pathlib.Path(log_path)
    if not p.exists():
        return True, "no audit log yet"
    prev = "GENESIS"
    n = 0
    with open(p) as f:
        for i, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError as e:
                return False, f"line {i}: json parse error ({e})"
            claim = d.get("hmac")
            body = {k: v for k, v in d.items() if k != "hmac"}
            if body.get("prev_hmac") != prev:
                return False, f"line {i}: chain break (prev_hmac mismatch)"
            expected = hmac.new(secret, canonical_json(body), hashlib.sha256).hexdigest()
            if not claim or not hmac.compare_digest(claim, expected):
                return False, f"line {i}: hmac mismatch"
            prev = claim
            n += 1
    return True, f"chain verified ({n} entries)"
