"""
titan-harness/lib/infisical_fetch.py — silent Infisical secret fetcher

Phase 1 Step 3 helper for Infisical migration per CORE_CONTRACT §8/§9 +
plans/DR_TITAN_AUTONOMY_BLUEPRINT.md §1 two-tier secrets model.

Callers replace `os.environ["SOME_SECRET"]` with:
    from infisical_fetch import get_secret
    value = get_secret("SOME_SECRET", project="harness-core")

Silent transport properties (P0 incident prevention from 2026-04-12):
  - No value ever writes to stdout or stderr
  - Uses curl -o /dev/null for write ops, httpx with raise-on-error for reads
  - Error responses are printed WITHOUT response body (names-only in logs)
  - On fetch failure, raises SecretFetchError — caller decides fallback

Shadow mode pattern (used during Phase 1 Step 3 conversion):
    value_from_infisical = None
    value_from_env = os.environ.get("SOME_SECRET")
    try:
        value_from_infisical = get_secret("SOME_SECRET", project="harness-core")
    except SecretFetchError as e:
        log_shadow_delta(key="SOME_SECRET", infisical_ok=False, env_ok=bool(value_from_env), error=str(e))
    else:
        log_shadow_delta(key="SOME_SECRET", infisical_ok=True, env_ok=bool(value_from_env),
                         match=(value_from_infisical == value_from_env))
    # During soak: return env value (source of truth)
    # After flip: return Infisical value
    return value_from_env if SHADOW_MODE else value_from_infisical

Authentication:
  Reads a service token from /root/.infisical/service-token-<project> by default.
  Falls back to INFISICAL_TOKEN env var if the file isn't readable.

API target:
  http://127.0.0.1:8080 (self-hosted Infisical, internal only, set via INFISICAL_API_URL).

Project → workspace ID mapping:
  Stored in /root/.infisical/project-ids.json (JSON: {"harvesters": "uuid-...", ...}).
  Titan writes this file once per project after Infisical UI creation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import httpx

_DEFAULT_API_URL = "http://127.0.0.1:8080"
_PROJECT_ID_MAP_PATH = Path("/root/.infisical/project-ids.json")
_TOKEN_FILE_TEMPLATE = "/root/.infisical/service-token-{project}"
_HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


class SecretFetchError(Exception):
    """Raised when Infisical fetch fails. Message contains HTTP code but NEVER the secret value."""
    pass


def _get_api_url() -> str:
    return os.environ.get("INFISICAL_API_URL", _DEFAULT_API_URL).rstrip("/")


def _load_project_id(project: str) -> str:
    """Load workspace UUID for a project name from the on-disk map."""
    if not _PROJECT_ID_MAP_PATH.exists():
        raise SecretFetchError(
            f"project-id map missing at {_PROJECT_ID_MAP_PATH}; "
            f"write it as JSON like {{\"{project}\": \"<workspace-uuid>\"}}"
        )
    try:
        data = json.loads(_PROJECT_ID_MAP_PATH.read_text())
    except json.JSONDecodeError:
        raise SecretFetchError(f"project-id map at {_PROJECT_ID_MAP_PATH} is not valid JSON")
    pid = data.get(project)
    if not pid:
        raise SecretFetchError(f"project '{project}' not found in {_PROJECT_ID_MAP_PATH}")
    return pid


def _load_service_token(project: str) -> str:
    """Load service token from /root/.infisical/service-token-<project>.
    Falls back to INFISICAL_TOKEN env var if the file isn't readable.
    """
    token_path = Path(_TOKEN_FILE_TEMPLATE.format(project=project))
    if token_path.exists():
        try:
            return token_path.read_text().strip()
        except PermissionError:
            pass
    env_token = os.environ.get("INFISICAL_TOKEN")
    if env_token:
        return env_token
    raise SecretFetchError(
        f"no service token for project '{project}' — checked {token_path} and INFISICAL_TOKEN env"
    )


def get_secret(
    key: str,
    project: str = "harness-core",
    env: str = "dev",
    path: str = "/",
    api_url: Optional[str] = None,
) -> str:
    """Fetch a single secret value from Infisical. Silent on success.

    On failure, raises SecretFetchError with a safe message (never the value).
    The value is returned to the caller. The caller is responsible for:
      - Not echoing the value to logs
      - Not writing the value to disk
      - Not passing the value to subprocesses without care (subprocess env leaks)
    """
    api = (api_url or _get_api_url()).rstrip("/")
    token = _load_service_token(project)
    workspace_id = _load_project_id(project)

    url = f"{api}/api/v3/secrets/raw/{key}"
    params = {
        "workspaceId": workspace_id,
        "environment": env,
        "secretPath": path,
    }
    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            r = client.get(url, params=params, headers=headers)
    except httpx.HTTPError as e:
        # httpx error message NEVER contains the response body (which might include the value)
        raise SecretFetchError(f"infisical fetch transport error for key '{key}': {type(e).__name__}")

    if r.status_code == 404:
        raise SecretFetchError(f"infisical secret not found: key='{key}' project='{project}' env='{env}'")
    if r.status_code == 401 or r.status_code == 403:
        raise SecretFetchError(f"infisical auth failure for key '{key}': http={r.status_code}")
    if not (200 <= r.status_code < 300):
        raise SecretFetchError(f"infisical fetch failed for key '{key}': http={r.status_code}")

    try:
        body = r.json()
    except ValueError:
        raise SecretFetchError(f"infisical response not JSON for key '{key}'")

    # v3 raw endpoint returns {"secret": {"secretKey": "...", "secretValue": "..."}}
    secret = body.get("secret") or {}
    value = secret.get("secretValue")
    if value is None:
        raise SecretFetchError(f"infisical response missing secretValue for key '{key}'")

    # CRITICAL: the caller owns this value from here. This function does not log,
    # does not write to disk, does not pass to subprocesses. Its sole job is to
    # return the string to the caller.
    return value


def log_shadow_delta(
    key: str,
    infisical_ok: bool,
    env_ok: bool,
    match: Optional[bool] = None,
    error: Optional[str] = None,
) -> None:
    """Append a shadow-mode delta line to /var/log/titan/infisical-shadow.jsonl.

    Records which source served the value (Infisical vs legacy env) + whether
    they matched. Values are NEVER logged — only booleans + error strings
    (which are safe per the SecretFetchError contract).
    """
    import datetime
    log_path = Path("/var/log/titan/infisical-shadow.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "key": key,
        "infisical_ok": infisical_ok,
        "env_ok": env_ok,
        "match": match,
        "error": error,
    }
    try:
        with log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except PermissionError:
        # Logging best-effort; don't crash the caller if the log dir isn't writable
        pass


# ---------------------------------------------------------------------------
# Public shared helper — Phase 1 Step 3 caller conversions use this
# ---------------------------------------------------------------------------
def fetch_with_shadow(key: str, default: str = "", project: str = "harness-core") -> str:
    """Shadow-mode Infisical fetch — shared helper for Phase 1 Step 3 caller conversions.

    Reads TITAN_INFISICAL_MODE env var to decide behavior:
      "shadow" (default)  — try Infisical, return env value (source of truth), log delta
      "infisical-only"    — try Infisical, return Infisical value (post-soak flip)
      "env-only"          — skip Infisical entirely (emergency rollback)

    Used by lib/llm_client.py (Step 3.1) and lib/war_room.py (Step 3.2) and any
    subsequent caller conversions in Phase 1 Step 3. Centralized here so each
    caller doesn't duplicate the shadow-mode logic.

    Silent contract: never writes the value to stdout/stderr/log. On failure,
    returns the env fallback and logs `infisical_ok=false` + error name only.

    Note: lib/llm_client.py currently keeps a local _fetch_with_shadow with
    identical behavior; it will migrate to this public helper after the
    Step 3.1 shadow→infisical-only flip completes.
    """
    mode = os.environ.get("TITAN_INFISICAL_MODE", "shadow")
    env_val = os.environ.get(key, default)
    if mode == "env-only":
        return env_val
    try:
        inf_val = get_secret(key, project=project)
    except Exception as _e:
        try:
            log_shadow_delta(
                key=key, infisical_ok=False, env_ok=bool(env_val),
                error=f"{type(_e).__name__}: {str(_e)[:200]}",
            )
        except Exception:
            pass
        return env_val
    try:
        log_shadow_delta(
            key=key, infisical_ok=True, env_ok=bool(env_val),
            match=(inf_val == env_val),
        )
    except Exception:
        pass
    if mode == "infisical-only":
        return inf_val
    return env_val  # shadow mode default


# ---------------------------------------------------------------------------
# CLI entry for smoke-testing (prints NAME + value_length only, never the value)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python3 -m lib.infisical_fetch <SECRET_KEY> [project] [env] [path]", file=sys.stderr)
        sys.exit(2)
    try:
        v = get_secret(
            sys.argv[1],
            project=sys.argv[2] if len(sys.argv) > 2 else "harness-core",
            env=sys.argv[3] if len(sys.argv) > 3 else "dev",
            path=sys.argv[4] if len(sys.argv) > 4 else "/",
        )
        # SAFETY: print length, never value
        print(f"OK key={sys.argv[1]} len={len(v)} chars")
    except SecretFetchError as e:
        print(f"FAIL key={sys.argv[1]} err={e}", file=sys.stderr)
        sys.exit(1)
