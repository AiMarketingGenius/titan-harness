#!/usr/bin/env python3
"""
seed_revere_chamber.py — Seed the consumer_memories + einstein_fact_checks tables
with a Revere Chamber demo tenant for Monday Don Martelli pitch.

Creates 8-12 memory rows simulating Solon's pre-pitch browsing:
  - Claude.ai thread researching Revere Chamber + Don Martelli
  - ChatGPT thread comparing Chamber partnership models
  - Perplexity queries on Chamber AI Advantage vertical
  - Gemini thread on B2B AI marketing
All tagged project_id='revere-chamber' (or similar) for filter testing.

Run from VPS with env sourced:
  set -a; source /etc/amg/aimg-supabase.env; set +a
  python3 seed_revere_chamber.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone


def env(k):
    v = os.environ.get(k)
    if not v:
        print(f"MISSING ENV: {k}", file=sys.stderr)
        sys.exit(2)
    return v


SB_URL = env("AIMG_SUPABASE_URL").rstrip("/")
SB_KEY = env("AIMG_SUPABASE_SERVICE_KEY")

# Demo consumer user
DEMO_EMAIL = os.environ.get("VAULT_DEMO_EMAIL", "demo@aimarketinggenius.io")
DEMO_PASSWORD = os.environ.get("VAULT_DEMO_PASSWORD", "chamber-demo-2026")


def rest(path, method="GET", body=None, params=None):
    url = f"{SB_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode()
            return resp.status, (json.loads(text) if text else None)
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        print(f"HTTP {e.code}: {text}", file=sys.stderr)
        return e.code, None


def ensure_demo_user():
    """Create the demo consumer user via Supabase auth admin API if not exists."""
    url = f"{SB_URL}/auth/v1/admin/users"
    body = {
        "email": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
        "email_confirm": True,
        "user_metadata": {"seeded_by": "titan-memory-vault-seed", "tenant": "revere-chamber"},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            uid = data.get("id") or data.get("user", {}).get("id")
            print(f"[seed] created demo user {DEMO_EMAIL} uid={uid}")
            return uid
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        if "already" in text.lower() or e.code == 422:
            # Already exists — look up
            status, users = rest(
                "/auth/v1/admin/users",
                params={"email": DEMO_EMAIL},
            )
            if users and users.get("users"):
                uid = users["users"][0]["id"]
                print(f"[seed] demo user exists {DEMO_EMAIL} uid={uid}")
                return uid
            # Last resort: use user list endpoint
            status2, data2 = rest("/auth/v1/admin/users?per_page=1000")
            if data2 and data2.get("users"):
                for u in data2["users"]:
                    if u.get("email") == DEMO_EMAIL:
                        uid = u["id"]
                        print(f"[seed] found demo user in list uid={uid}")
                        return uid
        print(f"[seed] user create failed HTTP {e.code}: {text}", file=sys.stderr)
        sys.exit(1)


def seed_memories(consumer_uid):
    now = datetime.now(timezone.utc)
    memories = [
        # Claude.ai researching Revere Chamber
        {
            "platform": "claude",
            "thread_id": "seed-claude-revere-01",
            "thread_url": "https://claude.ai/chat/seed-claude-revere-01",
            "exchange_number": 3,
            "source_timestamp": (now - timedelta(hours=48)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.92,
            "content": "Revere Chamber of Commerce — Revere, MA. ~280 member businesses. Annual gala at Hilton Boston Dedham. Don Martelli (board chair 2024-2026) leads strategic partnerships.",
            "verification_status": "verified",
        },
        {
            "platform": "claude",
            "thread_id": "seed-claude-revere-01",
            "thread_url": "https://claude.ai/chat/seed-claude-revere-01",
            "exchange_number": 5,
            "source_timestamp": (now - timedelta(hours=47, minutes=30)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.88,
            "content": "Don Martelli also president of Martelli Marketing Group. Known for ROI-driven pitches, values marketing that's measurable. Prefers direct communication, dislikes jargon.",
            "verification_status": "verified",
        },
        # ChatGPT comparing partnership models
        {
            "platform": "chatgpt",
            "thread_id": "seed-chatgpt-partnerships",
            "thread_url": "https://chat.openai.com/c/seed-chatgpt-partnerships",
            "exchange_number": 2,
            "source_timestamp": (now - timedelta(hours=36)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.84,
            "content": "Chamber AI partnership models comparison: revenue share (15-25% to Chamber on member signups) vs. flat licensing ($2k-5k/mo) vs. pilot-then-share hybrid. Hybrid model reduces Chamber risk + aligns incentives.",
            "verification_status": "verified",
        },
        # Perplexity on Chamber AI Advantage vertical
        {
            "platform": "perplexity",
            "thread_id": "seed-perplexity-chamberai",
            "thread_url": "https://perplexity.ai/search/seed-perplexity-chamberai",
            "exchange_number": 1,
            "source_timestamp": (now - timedelta(hours=30)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.81,
            "content": "Local Chambers of Commerce in 2026 face member retention pressure: average 6-8% annual churn, event attendance flat, non-dues revenue stagnant. AI-assisted member services is the top-mentioned differentiation vector.",
            "verification_status": "verified",
        },
        # Gemini on B2B AI marketing
        {
            "platform": "gemini",
            "thread_id": "seed-gemini-b2bai",
            "thread_url": "https://gemini.google.com/app/seed-gemini-b2bai",
            "exchange_number": 4,
            "source_timestamp": (now - timedelta(hours=24)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.76,
            "content": "For small-to-mid B2B associations, the most effective AI marketing stack in 2026: unified voice agent (inbound + outbound), nurture sequencer on member lifecycle, content engine for Chamber newsletter + social. ROI measurable within 60-90 days.",
            "verification_status": "unverified",
        },
        # Claude thread on Hormozi offer mechanics
        {
            "platform": "claude",
            "thread_id": "seed-claude-hormozi",
            "thread_url": "https://claude.ai/chat/seed-claude-hormozi",
            "exchange_number": 7,
            "source_timestamp": (now - timedelta(hours=18)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.90,
            "content": "Hormozi Grand Slam Offer equation: Value = (Dream Outcome × Perceived Likelihood of Achievement) / (Time Delay × Effort/Sacrifice). For Chamber pitch: dream outcome = member retention + non-dues revenue; perceived likelihood boosted via guarantee; time delay reduced via 90-day pilot; effort reduced via 'done-for-you' positioning.",
            "verification_status": "verified",
        },
        # Perplexity on guarantee language
        {
            "platform": "perplexity",
            "thread_id": "seed-perplexity-guarantee",
            "thread_url": "https://perplexity.ai/search/seed-perplexity-guarantee",
            "exchange_number": 1,
            "source_timestamp": (now - timedelta(hours=12)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.85,
            "content": "Most effective B2B service guarantee patterns: performance-based (results not met = partial/full refund), time-based (extra month free), satisfaction-based (full satisfaction or work continues free). Satisfaction + time combo reduces buyer risk to near zero without putting agency cash at risk directly.",
            "verification_status": "verified",
        },
        # AMG Agents internal memory
        {
            "platform": "amg-agents",
            "thread_id": "alex-revere-prep",
            "thread_url": "internal://alex/revere-chamber-prep",
            "exchange_number": 1,
            "source_timestamp": (now - timedelta(hours=6)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.95,
            "content": "Alex prep brief: Don Martelli — direct, ROI-focused, no jargon. Lead with proof, not story. Case studies: Shop UNIS organic traffic +180% 30d, Paradise Park local-pack wins 4 of 6 target keywords, Revel & Roll West booking velocity +35%. Guarantee: 3-month satisfaction-or-extra-month-free.",
            "verification_status": "verified",
        },
        # ChatGPT on 7-agent roster
        {
            "platform": "chatgpt",
            "thread_id": "seed-chatgpt-roster",
            "thread_url": "https://chat.openai.com/c/seed-chatgpt-roster",
            "exchange_number": 6,
            "source_timestamp": (now - timedelta(hours=4)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.87,
            "content": "AMG 7-agent roster mapped to Chamber member needs: Maya (content/newsletter/blog), Nadia (member nurture + renewals), Alex (voice + chatbot for inbound), Jordan (SEO for member websites), Sam (social scheduling), Riley (reputation monitoring), Lumina (visual consistency across member touchpoints).",
            "verification_status": "verified",
        },
        # Unverified / contradicted example for demo realism
        {
            "platform": "gemini",
            "thread_id": "seed-gemini-stat",
            "thread_url": "https://gemini.google.com/app/seed-gemini-stat",
            "exchange_number": 1,
            "source_timestamp": (now - timedelta(hours=2)).isoformat(),
            "project_id": "revere-chamber",
            "confidence": 0.45,
            "content": "Chambers of Commerce nationwide have grown membership 12% since 2022. [Einstein contradicted — Sonar crosscheck found national Chamber membership flat-to-down in same period; likely Gemini hallucination.]",
            "verification_status": "contradicted",
        },
    ]

    inserted = 0
    for m in memories:
        row = {
            "consumer_uid": consumer_uid,
            "platform": m["platform"],
            "thread_id": m["thread_id"],
            "thread_url": m["thread_url"],
            "exchange_number": m["exchange_number"],
            "source_timestamp": m["source_timestamp"],
            "project_id": m["project_id"],
            "confidence": m["confidence"],
            "content": m["content"],
        }
        status, resp = rest("/rest/v1/consumer_memories", method="POST", body=row)
        if status in (200, 201):
            mem_id = resp[0]["id"] if isinstance(resp, list) and resp else None
            inserted += 1
            if mem_id:
                fc = {
                    "memory_id": mem_id,
                    "verification_status": m["verification_status"],
                    "confidence": m["confidence"],
                    "claim": m["content"][:200],
                }
                rest("/rest/v1/einstein_fact_checks", method="POST", body=fc)
            print(f"[seed] + {m['platform']} #{m['exchange_number']} ({m['verification_status']})")
        else:
            print(f"[seed] FAIL {status} on {m['platform']} #{m['exchange_number']}")

    print(f"[seed] inserted {inserted}/{len(memories)} memory rows for consumer_uid={consumer_uid}")
    return inserted


if __name__ == "__main__":
    uid = ensure_demo_user()
    seed_memories(uid)
    print()
    print("DEMO LOGIN for Monday pitch:")
    print(f"  URL:      https://memory.aimarketinggenius.io/memoryvault/")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")
