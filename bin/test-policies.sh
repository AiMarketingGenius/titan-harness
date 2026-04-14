#!/usr/bin/env bash
# bin/test-policies.sh
# Gate #4 v1.2 — runs OPA unit tests for rego policies.
# Wired into install-gate4-opa.sh + optionally into pre-commit (Layer 4).

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v opa >/dev/null 2>&1; then
    echo "[test-policies] opa binary not installed — skipping tests (soft-pass)."
    echo "                install via bin/install-gate4-opa.sh --install-opa"
    exit 0
fi

echo "[test-policies] running: opa test $REPO/opa/"
if opa test "$REPO/opa/" -v 2>&1; then
    echo "[test-policies] PASS"
    exit 0
else
    echo "[test-policies] FAIL — rego tests red; refusing downstream deploys" >&2
    exit 1
fi
