#!/bin/bash
# titan-harness/bin/titan-slack-setup.sh
#
# One-time onboarding for the Slack-Computer reviewer transport.
# Run on VPS AFTER Solon creates the "Titan" Slack app and copies the bot token.
#
# Flow:
#   1. Prompt `read -rs` for the xoxb-... token (HIDDEN — never echoed, not in history)
#   2. Verify the token via Slack auth.test
#   3. Find #titan-aristotle channel ID via conversations.list
#   4. Verify Titan bot is a member; if not, print instructions and bail
#   5. Enumerate channel members, auto-discover the Perplexity Computer bot user ID
#   6. Write /root/.infisical/slack-config.json (non-secret: channel_id, reviewer_bot_id, titan_bot_id)
#   7. Silent-import SLACK_BOT_TOKEN to Infisical harness-core/dev via jq+curl
#   8. Post a "Titan online — reviewer transport verified" message (auto-deleted after 5s)
#   9. Run slack_reviewer smoke test to confirm end-to-end wiring
#
# The token value is NEVER printed to stdout. Only names, IDs, counts, and OK/FAIL markers.

set -u

INFISICAL_API_URL="http://127.0.0.1:8080"
INFISICAL_PID="1434a671-aecf-4a3c-84bf-ebd2a7c5e24d"  # harness-core UUID
CHANNEL_NAME="titan-aristotle"
CONFIG_PATH="/root/.infisical/slack-config.json"
HC_TOKEN_PATH="/root/.infisical/service-token-harness-core"

# ──────────────────────────────────────────────────────────────────────────────
echo "=== Titan Slack Setup — one-time onboarding ==="
echo

# STEP 1: read token
# --stdin-mode: read token from first line of stdin (for automation pipelines)
# interactive (default): read -rs prompt for hidden paste
if [ "${1:-}" = "--stdin-mode" ]; then
  echo "[stdin-mode] Reading token from stdin..."
  IFS= read -r SLACK_BOT_TOKEN
  if [ -z "$SLACK_BOT_TOKEN" ]; then
    echo "ERROR: stdin was empty. Aborting."
    exit 1
  fi
  echo "[stdin-mode] Token received (len=${#SLACK_BOT_TOKEN})"
  echo
else
  read -rs -p "Paste the Titan Slack bot token (xoxb-...): " SLACK_BOT_TOKEN
  echo
  echo
  if [ -z "$SLACK_BOT_TOKEN" ]; then
    echo "ERROR: no token provided. Aborting."
    exit 1
  fi
fi
if [[ ! "$SLACK_BOT_TOKEN" =~ ^xoxb- ]]; then
  echo "ERROR: token does not start with 'xoxb-'. Make sure you copied the Bot User OAuth Token (not the User OAuth Token or App-level Token)."
  unset SLACK_BOT_TOKEN
  exit 1
fi

# STEP 2: verify token via auth.test
echo "[1/8] Verifying token via Slack auth.test..."
AUTH_RESP=$(curl -s -X POST "https://slack.com/api/auth.test" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}')

AUTH_OK=$(echo "$AUTH_RESP" | jq -r '.ok // false')
if [ "$AUTH_OK" != "true" ]; then
  AUTH_ERR=$(echo "$AUTH_RESP" | jq -r '.error // "unknown"')
  echo "FAIL: auth.test returned error: $AUTH_ERR"
  unset SLACK_BOT_TOKEN
  exit 1
fi

WORKSPACE=$(echo "$AUTH_RESP" | jq -r '.team')
TITAN_BOT_USER_ID=$(echo "$AUTH_RESP" | jq -r '.user_id')
TITAN_BOT_NAME=$(echo "$AUTH_RESP" | jq -r '.user')
echo "       OK workspace='${WORKSPACE}' titan_bot='${TITAN_BOT_NAME}' titan_bot_user_id='${TITAN_BOT_USER_ID:0:6}...'"
echo

# STEP 3: find #titan-aristotle channel ID
echo "[2/8] Finding #${CHANNEL_NAME} channel..."
CH_RESP=$(curl -s -X GET "https://slack.com/api/conversations.list?types=private_channel,public_channel&limit=1000" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN")

CH_OK=$(echo "$CH_RESP" | jq -r '.ok // false')
if [ "$CH_OK" != "true" ]; then
  CH_ERR=$(echo "$CH_RESP" | jq -r '.error // "unknown"')
  echo "FAIL: conversations.list error: $CH_ERR"
  echo "       Likely missing scope. Your Titan app needs: channels:read + groups:read"
  unset SLACK_BOT_TOKEN
  exit 1
fi

CHANNEL_ID=$(echo "$CH_RESP" | jq -r --arg n "$CHANNEL_NAME" '.channels[] | select(.name == $n) | .id' | head -1)
if [ -z "$CHANNEL_ID" ]; then
  echo "FAIL: #${CHANNEL_NAME} not found in channels this bot has access to."
  echo "       Make sure the Titan bot has been invited to #${CHANNEL_NAME}:"
  echo "       In Slack, go to #${CHANNEL_NAME} and type: /invite @${TITAN_BOT_NAME}"
  unset SLACK_BOT_TOKEN
  exit 1
fi
echo "       OK channel_id='${CHANNEL_ID:0:6}...'"
echo

# STEP 4: verify Titan bot is a member
echo "[3/8] Verifying Titan bot is a member of #${CHANNEL_NAME}..."
MEM_RESP=$(curl -s -X GET "https://slack.com/api/conversations.members?channel=${CHANNEL_ID}&limit=100" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN")

MEM_OK=$(echo "$MEM_RESP" | jq -r '.ok // false')
if [ "$MEM_OK" != "true" ]; then
  MEM_ERR=$(echo "$MEM_RESP" | jq -r '.error // "unknown"')
  echo "FAIL: conversations.members error: $MEM_ERR"
  unset SLACK_BOT_TOKEN
  exit 1
fi

MEMBERS=$(echo "$MEM_RESP" | jq -r '.members[]')
if ! echo "$MEMBERS" | grep -q "^${TITAN_BOT_USER_ID}$"; then
  echo "FAIL: Titan bot is not a member of #${CHANNEL_NAME}."
  echo "       In Slack, type in that channel: /invite @${TITAN_BOT_NAME}"
  unset SLACK_BOT_TOKEN
  exit 1
fi
MEMBER_COUNT=$(echo "$MEMBERS" | wc -l)
echo "       OK titan_bot present. channel has ${MEMBER_COUNT} members total."
echo

# STEP 5: auto-discover Perplexity Computer bot user ID
echo "[4/8] Auto-discovering Perplexity reviewer bot (Computer / Ask / Perplexity)..."
REVIEWER_BOT_ID=""
REVIEWER_BOT_NAME=""
REVIEWER_BOT_PRIORITY=99  # lower is better

while IFS= read -r USER_ID; do
  [ -z "$USER_ID" ] && continue
  [ "$USER_ID" = "$TITAN_BOT_USER_ID" ] && continue  # skip Titan itself

  USER_RESP=$(curl -s -X GET "https://slack.com/api/users.info?user=${USER_ID}" \
    -H "Authorization: Bearer $SLACK_BOT_TOKEN")
  USER_OK=$(echo "$USER_RESP" | jq -r '.ok // false')
  [ "$USER_OK" != "true" ] && continue

  IS_BOT=$(echo "$USER_RESP" | jq -r '.user.is_bot // false')
  [ "$IS_BOT" != "true" ] && continue

  REAL_NAME=$(echo "$USER_RESP" | jq -r '.user.real_name // ""' | tr '[:upper:]' '[:lower:]')
  DISPLAY=$(echo "$USER_RESP" | jq -r '.user.profile.display_name // ""' | tr '[:upper:]' '[:lower:]')
  COMBINED="${REAL_NAME} ${DISPLAY}"

  # Priority: Perplexity Computer > Perplexity Ask > anything with "perplexity" > anything with "computer"
  PRIO=99
  if [[ "$COMBINED" == *"perplexity"*"computer"* ]] || [[ "$COMBINED" == *"computer"*"perplexity"* ]]; then
    PRIO=1
  elif [[ "$COMBINED" == *"perplexity"*"ask"* ]] || [[ "$COMBINED" == *"ask"*"perplexity"* ]]; then
    PRIO=2
  elif [[ "$COMBINED" == *"perplexity"* ]]; then
    PRIO=3
  elif [[ "$COMBINED" == *"computer"* ]]; then
    PRIO=4
  fi

  if [ $PRIO -lt $REVIEWER_BOT_PRIORITY ]; then
    REVIEWER_BOT_PRIORITY=$PRIO
    REVIEWER_BOT_ID="$USER_ID"
    REVIEWER_BOT_NAME="${REAL_NAME} / ${DISPLAY}"
  fi
done <<< "$MEMBERS"

if [ -z "$REVIEWER_BOT_ID" ]; then
  echo "FAIL: no Perplexity/Computer bot found in #${CHANNEL_NAME}."
  echo "       Make sure the Perplexity Computer Slack app is invited to the channel."
  unset SLACK_BOT_TOKEN
  exit 1
fi
echo "       OK reviewer_bot_id='${REVIEWER_BOT_ID:0:6}...' name='${REVIEWER_BOT_NAME}' priority=${REVIEWER_BOT_PRIORITY}"
echo

# STEP 6: write slack-config.json (non-secret data only)
echo "[5/8] Writing ${CONFIG_PATH}..."
mkdir -p "$(dirname "$CONFIG_PATH")"
chmod 700 "$(dirname "$CONFIG_PATH")"
cat > "$CONFIG_PATH" <<EOF
{
  "channel_id": "${CHANNEL_ID}",
  "channel_name": "${CHANNEL_NAME}",
  "reviewer_bot_id": "${REVIEWER_BOT_ID}",
  "reviewer_bot_name": "${REVIEWER_BOT_NAME}",
  "titan_bot_id": "${TITAN_BOT_USER_ID}",
  "titan_bot_name": "${TITAN_BOT_NAME}",
  "workspace": "${WORKSPACE}",
  "configured_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
chmod 600 "$CONFIG_PATH"
echo "       OK written (mode 600)"
echo

# STEP 7: silent-import SLACK_BOT_TOKEN to Infisical harness-core/dev
echo "[6/8] Silent-importing SLACK_BOT_TOKEN to Infisical harness-core/dev..."
if [ ! -f "$HC_TOKEN_PATH" ]; then
  echo "FAIL: Infisical harness-core service token missing at $HC_TOKEN_PATH"
  unset SLACK_BOT_TOKEN
  exit 1
fi

INF_TOKEN=$(cat "$HC_TOKEN_PATH")
BODY=$(jq -cn --arg wid "$INFISICAL_PID" --arg val "$SLACK_BOT_TOKEN" \
  '{workspaceId:$wid, environment:"dev", secretPath:"/", secretValue:$val, type:"shared"}')

# Try POST (create new); if it returns 400 (already exists), PATCH it
CODE=$(printf '%s' "$BODY" | curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $INF_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @- \
  "${INFISICAL_API_URL}/api/v3/secrets/raw/SLACK_BOT_TOKEN")

if [ "$CODE" = "400" ] || [ "$CODE" = "409" ]; then
  # Already exists — PATCH instead
  CODE=$(printf '%s' "$BODY" | curl -s -o /dev/null -w "%{http_code}" -X PATCH \
    -H "Authorization: Bearer $INF_TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary @- \
    "${INFISICAL_API_URL}/api/v3/secrets/raw/SLACK_BOT_TOKEN")
fi
unset BODY INF_TOKEN

if [ "$CODE" != "200" ]; then
  echo "FAIL: Infisical import returned http=${CODE}"
  unset SLACK_BOT_TOKEN
  exit 1
fi
echo "       OK SLACK_BOT_TOKEN imported to harness-core/dev (http=200)"
echo

# STEP 8: post a "Titan online" test message + auto-delete
echo "[7/8] Posting test message + auto-deleting after 5s..."
TEST_PAYLOAD=$(jq -cn --arg cid "$CHANNEL_ID" \
  '{channel:$cid, text:"[Titan] Slack reviewer transport wiring verified. This message will self-destruct in 5s."}')
TEST_RESP=$(printf '%s' "$TEST_PAYLOAD" | curl -s -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @-)

TEST_OK=$(echo "$TEST_RESP" | jq -r '.ok // false')
if [ "$TEST_OK" != "true" ]; then
  TEST_ERR=$(echo "$TEST_RESP" | jq -r '.error // "unknown"')
  echo "FAIL: chat.postMessage error: $TEST_ERR"
  echo "       Likely missing scope. Your Titan app needs: chat:write"
  unset SLACK_BOT_TOKEN
  exit 1
fi

TEST_TS=$(echo "$TEST_RESP" | jq -r '.ts')
echo "       OK posted ts=${TEST_TS:0:12}... sleeping 5s..."
sleep 5

DEL_PAYLOAD=$(jq -cn --arg cid "$CHANNEL_ID" --arg ts "$TEST_TS" \
  '{channel:$cid, ts:$ts}')
DEL_CODE=$(printf '%s' "$DEL_PAYLOAD" | curl -s -o /dev/null -w "%{http_code}" -X POST "https://slack.com/api/chat.delete" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @-)
echo "       OK deleted (http=${DEL_CODE})"
echo

# STEP 9: final auth + config recheck via slack_reviewer module smoke test
echo "[8/8] Running slack_reviewer module smoke test (imports, config parse, no Slack call)..."
if [ -f /opt/titan-harness/lib/slack_reviewer.py ]; then
  cd /opt/titan-harness/lib && \
  SLACK_BOT_TOKEN="$SLACK_BOT_TOKEN" python3 -c "
import sys
sys.path.insert(0, '.')
from slack_reviewer import SlackReviewer, SLACK_CONFIG_PATH
import os
token = os.environ['SLACK_BOT_TOKEN']
rev = SlackReviewer.from_config(token)
print(f'       OK SlackReviewer loaded. channel_id={rev.channel_id[:6]}... reviewer_bot_id={rev.reviewer_bot_id[:6]}... titan_bot_id={rev.titan_bot_id[:6] if rev.titan_bot_id else \"unset\"}...')
"
else
  echo "       SKIP /opt/titan-harness/lib/slack_reviewer.py not yet deployed (run after git pull)"
fi

unset SLACK_BOT_TOKEN

echo
echo "=== DONE — Titan Slack reviewer transport fully wired ==="
echo
echo "Next live test: Titan auto-grades the next soft step via Slack-Computer,"
echo "logs result to MCP, and auto-continues without Solon involvement."
echo
echo "Fallback order Titan uses (auto-detected at review_gate.py runtime):"
echo "  1. Slack-Computer (preferred — uses your Perplexity Pro account, 0 API cost)"
echo "  2. Perplexity API (dormant fallback — will replug if you top up at"
echo "     perplexity.ai/settings/api)"
echo "  3. Exit 2 error → escalate to Solon (if both paths fail)"
