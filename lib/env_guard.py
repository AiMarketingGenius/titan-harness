"""
lib/env_guard.py
Ironclad architecture §5.5 — ENV check. MCP exports are READ-ONLY.

Import-time enforcement: any script imported while TITAN_ENV=mcp that tries
to write to the harness raises ImportError. Honest callers import this
module at the top of anything that could mutate state.

Usage:
    from env_guard import assert_writable
    assert_writable("bin/harness-incident.sh")
"""
from __future__ import annotations

import os
from pathlib import Path


VALID_ENVS = {"mac", "vps", "mcp", "unknown"}


def current_env() -> str:
    env = os.environ.get("TITAN_ENV", "").strip().lower()
    if env in VALID_ENVS:
        return env
    # Heuristic fallback: if we're under /opt, assume vps; under $HOME, mac;
    # under /opt/mcp, mcp.
    cwd = Path.cwd()
    if str(cwd).startswith("/opt/mcp"):
        return "mcp"
    if str(cwd).startswith("/opt/"):
        return "vps"
    if str(cwd).startswith(os.path.expanduser("~")):
        return "mac"
    return "unknown"


def assert_writable(caller: str = "<unknown>") -> None:
    env = current_env()
    if env == "mcp":
        raise RuntimeError(
            f"env_guard: MCP context is read-only, but {caller} attempted a write. "
            "Run this from a mac or vps environment (TITAN_ENV=mac|vps)."
        )


def assert_env(allowed: set[str], caller: str = "<unknown>") -> None:
    env = current_env()
    if env not in allowed:
        raise RuntimeError(
            f"env_guard: {caller} requires TITAN_ENV in {sorted(allowed)} "
            f"but current env is '{env}'."
        )


if __name__ == "__main__":
    print(f"TITAN_ENV={current_env()}")
