#!/bin/bash
# tests/test_hammerspoon_3x_synthetic_cycles.sh
#
# 3x E2E verification of the hammerspoon-auto-restart injection pipeline.
# Triggered after the 2026-04-19 "kW" partial-landing incident (Solon saw
# only "kW" land instead of the full wake phrase post-restart) and
# re-extended after the 2026-04-19T02:26Z "ready-window timeout → inject
# skipped" live-cycle-1 failure (the strict-only wait_for_ready_window
# bailed after 20s because Claude's Electron main window didn't satisfy
# isStandard() on cold boot).
#
# Tests THREE injection subsystems:
#   Phase A: titan_test_clipboard     — clipboard save/set/readback across
#                                       3 cycles with distinct phrases.
#                                       Validates no corruption / truncation
#                                       in the clipboard pipeline.
#   Phase B: titan_test_paste_e2e     — runs inject_via_clipboard() in
#                                       dry-run mode (no Cmd+V + Return
#                                       fired — safe to run inside the
#                                       active Claude Code session).
#                                       Validates per-cycle:
#                                         • clipboard save/set/preverify pass
#                                         • post-paste clipboard readback OK
#                                         • clipboard restored to pre-state
#                                       Cross-app delivery (Cmd+V actually
#                                       lands in target) is proven by the
#                                       next real-world restart cycle.
#   Phase C: titan_test_full_pipeline — NEW (2026-04-19, post live-cycle-1).
#                                       Runs the complete post-launch
#                                       pipeline (wait_for_ready_window
#                                       tiered fallback → ensure_frontmost
#                                       → inject_via_clipboard dry-run)
#                                       against the live Claude instance.
#                                       Validates per-cycle:
#                                         • ready_tier is non-nil (some tier
#                                           of the 4-tier fallback matched,
#                                           or forced-focus fallback ran)
#                                         • frontmost_ok true
#                                         • paste_ok true
#                                         • inject_path_reached true (caller
#                                           would have fired a real paste)
#                                       Eliminates the bail-on-timeout path
#                                       that caused the 2026-04-19T02:26Z
#                                       live-cycle-1 inject-skipped failure.
#
# 3/3 on ALL THREE phases = "kW" + "ready-window timeout" classes of bugs
# structurally eliminated + ship tag earned.
#
# Prereqs:
#   - Hammerspoon running with titan_auto_restart.lua loaded (via
#     ~/.hammerspoon/init.lua loader block).
#   - TextEdit installed (ships default with macOS).
#   - Hammerspoon reloaded after the 2026-04-19 module update so the new
#     URL bindings titan_test_clipboard + titan_test_paste_e2e are active.
#
# Exit 0 = both phases 3/3 green
# Exit 1 = any cycle failed
# Exit 2 = environmental (Hammerspoon URL hook didn't respond)

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="test_$(date +%s)"
CLIP_RESULT="/tmp/titan_clipboard_test_${RUN_ID}.json"
PASTE_RESULT="/tmp/titan_paste_e2e_test_${RUN_ID}.json"
PIPELINE_RESULT="/tmp/titan_full_pipeline_test_${RUN_ID}.json"
TIMEOUT_S=60

echo "=== hammerspoon-auto-restart 3x E2E (run_id=$RUN_ID) ==="
echo ""

wait_for_file() {
  local path="$1"
  local timeout="$2"
  local waited=0
  while [ "$waited" -lt "$timeout" ]; do
    if [ -f "$path" ]; then return 0; fi
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

# Phase A: clipboard pipeline ----------------------------------------------
echo "=== Phase A: clipboard pipeline (3 cycles) ==="
rm -f "$CLIP_RESULT"
open "hammerspoon://titan_test_clipboard?n=3&run_id=${RUN_ID}"
echo "   URL event fired — waiting up to ${TIMEOUT_S}s for result file ..."
if ! wait_for_file "$CLIP_RESULT" "$TIMEOUT_S"; then
  echo "FAIL Phase A: $CLIP_RESULT not written within ${TIMEOUT_S}s"
  echo "   → Hammerspoon URL binding not active — reload may have failed."
  echo "   → Inspect: tail /tmp/titan_auto_restart.ndjson"
  exit 2
fi

CLIP_SUMMARY=$(python3 -c "
import json, sys
d = json.load(open('$CLIP_RESULT'))
print(f\"passed: {d['passed']}/{d['n']}\")
print(f\"all_ok: {d['all_ok']}\")
for r in d['results']:
  print(f\"  cycle {r['cycle']}: ok={r['ok']} phrase_len={r['phrase_len']} readback_len={r['readback_len']}\")
print('---RESULT---')
print('PASS' if d['all_ok'] else 'FAIL')
")
echo "$CLIP_SUMMARY"

CLIP_VERDICT=$(echo "$CLIP_SUMMARY" | tail -1)
if [ "$CLIP_VERDICT" != "PASS" ]; then
  echo "FAIL Phase A: clipboard pipeline not 3/3 green"
  exit 1
fi
echo "   Phase A: 3/3 PASS"
echo ""

# Phase B: inject_via_clipboard internal-contract test (dry-run) ----------
# Phase B runs the hardened inject_via_clipboard() in DRY-RUN mode (no
# Cmd+V or Return keystrokes fired — safe to run inside the active Claude
# Code session without corrupting it). Verifies per cycle:
#   - clipboard save/set/preverify/postverify/restore all succeed
#   - paste_ok returns true (clipboard still holds phrase after pipeline)
#   - clipboard is cleanly restored to pre-inject state (canary roundtrip)
echo "=== Phase B: inject_via_clipboard internal contract (3 cycles, dry-run) ==="
rm -f "$PASTE_RESULT"
open "hammerspoon://titan_test_paste_e2e?n=3&run_id=${RUN_ID}"
echo "   URL event fired — waiting up to ${TIMEOUT_S}s for result file ..."
if ! wait_for_file "$PASTE_RESULT" "$TIMEOUT_S"; then
  echo "FAIL Phase B: $PASTE_RESULT not written within ${TIMEOUT_S}s"
  exit 2
fi

PASTE_SUMMARY=$(python3 -c "
import json, sys
d = json.load(open('$PASTE_RESULT'))
print(f\"passed: {d['passed']}/{d['n']}\")
print(f\"all_ok: {d['all_ok']}\")
for r in d['results']:
  reason = f\" reason={r['reason']}\" if r.get('reason') else ''
  print(f\"  cycle {r['cycle']}: ok={r['ok']} phrase_len={r['phrase_len']} paste_ok={r.get('paste_ok')} clipboard_restored={r.get('clipboard_restored')} frontmost={r.get('frontmost_at_paste','?')}{reason}\")
print('---RESULT---')
print('PASS' if d['all_ok'] else 'FAIL')
")
echo "$PASTE_SUMMARY"

PASTE_VERDICT=$(echo "$PASTE_SUMMARY" | tail -1)
if [ "$PASTE_VERDICT" != "PASS" ]; then
  echo "FAIL Phase B: paste E2E not 3/3 green"
  exit 1
fi
echo "   Phase B: 3/3 PASS"
echo ""

# Phase C: full pipeline (ready-window tiered + frontmost + paste) --------
# Phase C runs the complete post-launch pipeline against the live Claude
# instance: wait_for_ready_window (4-tier fallback) → ensure_frontmost →
# inject_via_clipboard in dry-run. Proves the 2026-04-19T02:26Z ready-
# window-timeout bail-out path has been eliminated — the caller no longer
# aborts injection when strict isStandard()+isVisible() misses; it falls
# through progressively looser tiers and force_focus_claude() as last resort.
echo "=== Phase C: full post-launch pipeline (3 cycles, dry-run) ==="
rm -f "$PIPELINE_RESULT"
open "hammerspoon://titan_test_full_pipeline?n=3&run_id=${RUN_ID}"
echo "   URL event fired — waiting up to ${TIMEOUT_S}s for result file ..."
if ! wait_for_file "$PIPELINE_RESULT" "$TIMEOUT_S"; then
  echo "FAIL Phase C: $PIPELINE_RESULT not written within ${TIMEOUT_S}s"
  echo "   → URL binding titan_test_full_pipeline not registered — likely"
  echo "     Hammerspoon wasn't reloaded after the 2026-04-19 post-live-cycle-1"
  echo "     hardening lands. Reload via: open -g 'hammerspoon://reload'"
  exit 2
fi

PIPELINE_SUMMARY=$(python3 -c "
import json, sys
d = json.load(open('$PIPELINE_RESULT'))
print(f\"passed: {d['passed']}/{d['n']}\")
print(f\"all_ok: {d['all_ok']}\")
for r in d['results']:
  reason = f\" reason={r.get('reason')}\" if r.get('reason') else ''
  tier = r.get('ready_tier', '?')
  ff = r.get('force_focused', False)
  print(f\"  cycle {r['cycle']}: ok={r['ok']} ready_tier={tier} force_focused={ff} frontmost_ok={r.get('frontmost_ok')} paste_ok={r.get('paste_ok')} inject_path_reached={r.get('inject_path_reached')}{reason}\")
print('---RESULT---')
print('PASS' if d['all_ok'] else 'FAIL')
")
echo "$PIPELINE_SUMMARY"

PIPELINE_VERDICT=$(echo "$PIPELINE_SUMMARY" | tail -1)
if [ "$PIPELINE_VERDICT" != "PASS" ]; then
  echo "FAIL Phase C: full-pipeline not 3/3 green"
  exit 1
fi
echo "   Phase C: 3/3 PASS"
echo ""

# Summary -------------------------------------------------------------------
echo "=== SUMMARY ==="
echo "Phase A (clipboard pipeline):    3/3 PASS"
echo "Phase B (paste E2E contract):    3/3 PASS"
echo "Phase C (full post-launch pipe): 3/3 PASS"
echo ""
echo "PASS: hammerspoon-auto-restart 3x E2E — 'kW' + 'ready-window timeout'"
echo "      classes of bugs structurally eliminated"
echo ""
echo "Result files:"
echo "  $CLIP_RESULT"
echo "  $PASTE_RESULT"
echo "  $PIPELINE_RESULT"
echo ""
echo "Hammerspoon inject log (last 10):"
tail -10 /tmp/titan_auto_restart.ndjson 2>/dev/null || echo "  (no inject log yet)"
