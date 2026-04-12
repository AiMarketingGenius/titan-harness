#!/usr/bin/env bash
# bin/harness-freeze.sh
# Ironclad architecture §5.1 — tag a freeze/<date>-<sha> rollback point.
# Auto-invoked before every STRUCTURAL class write by the post-commit hook
# when the directive metadata says class=STRUCTURAL. Safe to call manually.
set -euo pipefail

HARNESS_DIR="${TITAN_HARNESS_DIR:-$HOME/titan-harness}"
DATE=$(date +%Y-%m-%d)
SHORT=$(git -C "$HARNESS_DIR" rev-parse --short HEAD)
FREEZE_TAG="freeze/${DATE}-${SHORT}"

if git -C "$HARNESS_DIR" rev-parse -q --verify "refs/tags/$FREEZE_TAG" >/dev/null; then
  echo "[FREEZE] Tag $FREEZE_TAG already exists — skipping."
  exit 0
fi

git -C "$HARNESS_DIR" tag "$FREEZE_TAG"
if git -C "$HARNESS_DIR" push origin "$FREEZE_TAG" 2>/dev/null; then
  echo "[FREEZE] Tagged + pushed: $FREEZE_TAG"
else
  echo "[FREEZE] Tagged locally ($FREEZE_TAG) — remote push skipped (origin unreachable)"
fi
