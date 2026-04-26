#!/usr/bin/env python3
"""
einstein_call.py — Einstein fact-check call helper.

Wraps the disposable-user JWT signin flow that the Einstein Edge Function
requires (anon key alone returns 401; service_role JWT also rejected).
Reads credentials from /etc/amg/einstein-staging.env (mode 0600 root:root).

Usage:
    einstein_call.py --text "claim to fact-check" \
                     --memories '[{"id":"m1","text":"prior memory","ts":1}]'
    einstein_call.py --text "..." --memories-file mem.json

Output: JSON from Einstein. Non-zero exit if auth or HTTP failure.

Env file must define:
    EINSTEIN_FUNCTION_URL
    EINSTEIN_URL
    EINSTEIN_ANON_KEY
    EINSTEIN_SMOKE_USER_EMAIL
    EINSTEIN_SMOKE_USER_PASSWORD
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.request

ENV_FILE_DEFAULT = pathlib.Path("/etc/amg/einstein-staging.env")


def load_env(path: pathlib.Path) -> dict:
    env = {}
    if not path.exists():
        sys.stderr.write(f"einstein env file not found: {path}\n")
        sys.exit(2)
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    required = (
        "EINSTEIN_FUNCTION_URL", "EINSTEIN_URL",
        "EINSTEIN_ANON_KEY",
        "EINSTEIN_SMOKE_USER_EMAIL", "EINSTEIN_SMOKE_USER_PASSWORD",
    )
    missing = [k for k in required if k not in env]
    if missing:
        sys.stderr.write(f"missing env keys: {missing}\n")
        sys.exit(2)
    return env


def http_post(url: str, headers: dict, body: dict, timeout: int = 15) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except Exception as e:
        return -1, {"error": repr(e)}


def signin(env: dict) -> str:
    url = f"{env['EINSTEIN_URL']}/auth/v1/token?grant_type=password"
    code, body = http_post(
        url,
        {"apikey": env["EINSTEIN_ANON_KEY"], "Content-Type": "application/json"},
        {"email": env["EINSTEIN_SMOKE_USER_EMAIL"],
         "password": env["EINSTEIN_SMOKE_USER_PASSWORD"]},
    )
    if code != 200 or not body.get("access_token"):
        sys.stderr.write(f"signin failed: {code} {body}\n")
        sys.exit(3)
    return body["access_token"]


def call_einstein(env: dict, text: str, memories: list, jwt: str) -> tuple[int, dict]:
    return http_post(
        env["EINSTEIN_FUNCTION_URL"],
        {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
        {"text": text, "memories": memories},
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Einstein fact-check helper")
    p.add_argument("--text", required=True, help="claim to fact-check")
    p.add_argument("--memories", default="[]", help="JSON list of prior memories")
    p.add_argument("--memories-file", default=None, help="path to JSON file with memories list")
    p.add_argument("--env-file", default=str(ENV_FILE_DEFAULT))
    args = p.parse_args()

    env = load_env(pathlib.Path(args.env_file))

    if args.memories_file:
        memories = json.loads(pathlib.Path(args.memories_file).read_text())
    else:
        memories = json.loads(args.memories)

    jwt = signin(env)
    code, body = call_einstein(env, args.text, memories, jwt)
    print(json.dumps({"http_status": code, "body": body, "ts": int(time.time())}))
    return 0 if code == 200 and body.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
