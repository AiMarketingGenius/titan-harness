#!/bin/bash
# titan-harness/scripts/slack_upload_image.sh
#
# Upload a binary file (image, PDF, zip) to the Aristotle Slack channel.
# aristotle_slack.py only handles text-inline uploads. This wraps Slack's
# files.upload_v2 three-step flow (getUploadURLExternal → raw-PUT → complete)
# so Titan can ship screenshots in the morning package.
#
# Usage:
#   SLACK_BOT_TOKEN=xoxb-... \
#   CHANNEL_ID=C0AS40VECAX \
#   ./slack_upload_image.sh <file> <title> [<initial_comment>]
#
# Returns: file_id on stdout, diagnostic on stderr. Exit 0 on success.

set -u

FILE_PATH="${1:-}"
TITLE="${2:-upload}"
COMMENT="${3:-}"

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  echo "usage: $0 <file> <title> [comment]" >&2
  exit 2
fi
if [ -z "${SLACK_BOT_TOKEN:-}" ]; then
  echo "ERR: SLACK_BOT_TOKEN not set" >&2
  exit 2
fi
if [ -z "${CHANNEL_ID:-}" ]; then
  echo "ERR: CHANNEL_ID not set" >&2
  exit 2
fi

FILENAME=$(basename "$FILE_PATH")
FILESIZE=$(stat -f%z "$FILE_PATH" 2>/dev/null || stat -c%s "$FILE_PATH")

# Step 1 — get upload URL
STEP1=$(curl -s "https://slack.com/api/files.getUploadURLExternal" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  --data-urlencode "filename=$FILENAME" \
  --data-urlencode "length=$FILESIZE")

UPLOAD_URL=$(echo "$STEP1" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('upload_url',''))")
FILE_ID=$(echo "$STEP1" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('file_id',''))")

if [ -z "$UPLOAD_URL" ] || [ -z "$FILE_ID" ]; then
  echo "ERR step1: $STEP1" >&2
  exit 3
fi

# Step 2 — PUT raw bytes
STEP2_CODE=$(curl -s -o /tmp/slack_step2.out -w "%{http_code}" \
  -X POST "$UPLOAD_URL" \
  --data-binary "@$FILE_PATH")

if [ "$STEP2_CODE" != "200" ]; then
  echo "ERR step2 http=$STEP2_CODE: $(cat /tmp/slack_step2.out)" >&2
  exit 4
fi

# Step 3 — complete upload, pin to channel + title + comment
PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
  'files': [{'id': '$FILE_ID', 'title': '''$TITLE'''}],
  'channel_id': '$CHANNEL_ID',
  'initial_comment': '''$COMMENT''',
}))")

STEP3=$(curl -s "https://slack.com/api/files.completeUploadExternal" \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data "$PAYLOAD")

OK=$(echo "$STEP3" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('ok',False))")
if [ "$OK" != "True" ]; then
  echo "ERR step3: $STEP3" >&2
  exit 5
fi

echo "$FILE_ID"
