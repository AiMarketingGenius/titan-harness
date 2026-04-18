#!/usr/bin/env python3
"""Titan canary v1 — Slack recon: Viktor lookup + public channel enumeration."""
import json
import os
import sys
import urllib.request

TOKEN = os.environ.get("SLACK_BOT_TOKEN")
if not TOKEN:
    sys.exit("SLACK_BOT_TOKEN missing from env")


def slack_get(method, params=None):
    url = f"https://slack.com/api/{method}"
    if params:
        q = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{q}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def slack_post(method, body):
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def find_viktor():
    out = []
    cursor = ""
    while True:
        params = {"limit": "200"}
        if cursor:
            params["cursor"] = cursor
        r = slack_get("users.list", params)
        if not r.get("ok"):
            return {"error": r.get("error"), "users": []}
        for u in r.get("members", []):
            name = (u.get("name") or "").lower()
            real = (u.get("real_name") or "").lower()
            email = ((u.get("profile") or {}).get("email") or "").lower()
            if "viktor" in name or "viktor" in real or "viktor" in email:
                out.append(u)
        cursor = (r.get("response_metadata") or {}).get("next_cursor") or ""
        if not cursor:
            break
    return {"error": None, "users": out}


def list_public_channels():
    out = []
    cursor = ""
    while True:
        params = {
            "types": "public_channel",
            "limit": "200",
            "exclude_archived": "true",
        }
        if cursor:
            params["cursor"] = cursor
        r = slack_get("conversations.list", params)
        if not r.get("ok"):
            return {"error": r.get("error"), "channels": []}
        out.extend(r.get("channels", []))
        cursor = (r.get("response_metadata") or {}).get("next_cursor") or ""
        if not cursor:
            break
    return {"error": None, "channels": out}


def is_viktor_in_channel(channel_id, viktor_id):
    cursor = ""
    while True:
        params = {"channel": channel_id, "limit": "200"}
        if cursor:
            params["cursor"] = cursor
        r = slack_get("conversations.members", params)
        if not r.get("ok"):
            return {"error": r.get("error"), "member": False, "partial": True}
        if viktor_id in r.get("members", []):
            return {"error": None, "member": True}
        cursor = (r.get("response_metadata") or {}).get("next_cursor") or ""
        if not cursor:
            break
    return {"error": None, "member": False}


def main():
    v = find_viktor()
    print(json.dumps({"stage": "viktor_lookup", "result": v}, default=str))

    if v["users"]:
        vu = v["users"][0]
        vid = vu["id"]
        print(
            json.dumps(
                {
                    "stage": "viktor_profile",
                    "id": vid,
                    "name": vu.get("name"),
                    "real_name": vu.get("real_name"),
                    "email": (vu.get("profile") or {}).get("email"),
                    "is_admin": vu.get("is_admin"),
                    "is_owner": vu.get("is_owner"),
                    "is_bot": vu.get("is_bot"),
                    "deleted": vu.get("deleted"),
                    "tz": vu.get("tz"),
                    "updated": vu.get("updated"),
                    "title": (vu.get("profile") or {}).get("title"),
                },
                default=str,
            )
        )
    else:
        vid = None

    ch = list_public_channels()
    print(
        json.dumps(
            {
                "stage": "public_channels_summary",
                "count": len(ch["channels"]),
                "error": ch["error"],
            }
        )
    )
    for c in ch["channels"]:
        print(
            json.dumps(
                {
                    "stage": "public_channel",
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "members": c.get("num_members"),
                    "is_member": c.get("is_member"),
                    "is_archived": c.get("is_archived"),
                    "topic": (c.get("topic") or {}).get("value", "")[:80],
                }
            )
        )

    if vid:
        viktor_channels = []
        for c in ch["channels"]:
            res = is_viktor_in_channel(c["id"], vid)
            if res.get("member"):
                viktor_channels.append({"id": c["id"], "name": c["name"], "members": c.get("num_members")})
        print(
            json.dumps(
                {
                    "stage": "viktor_public_channel_membership",
                    "count": len(viktor_channels),
                    "channels": viktor_channels,
                }
            )
        )


if __name__ == "__main__":
    main()
