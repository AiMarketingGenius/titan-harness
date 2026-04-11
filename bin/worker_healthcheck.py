#!/usr/bin/env python3
"""titan-harness/bin/worker_healthcheck.py - Phase P9
Docker HEALTHCHECK script. Exit 0 = healthy, non-zero = unhealthy.
Checks:
    1. check_capacity() not in hard_block (exit 2)
    2. SUPABASE_URL reachable (GET /rest/v1/ returns 2xx/401)
    3. LITELLM gateway /health/liveliness reachable
"""
import os
import sys
sys.path.insert(0, "/opt/titan-harness/lib")

try:
    from capacity import capacity_status
    s = capacity_status()
    if s == "hard_block":
        print("unhealthy: capacity hard block", file=sys.stderr)
        sys.exit(2)
except Exception as e:
    # Capacity unavailable is non-fatal (fail-open)
    pass

# Probe LiteLLM gateway
try:
    import httpx
    base = os.environ.get("LITELLM_BASE_URL", "http://host.docker.internal:4000")
    r = httpx.get(base + "/health/liveliness", timeout=3.0)
    if r.status_code != 200:
        print(f"unhealthy: litellm /health/liveliness -> {r.status_code}", file=sys.stderr)
        sys.exit(3)
except Exception as e:
    print(f"unhealthy: litellm probe error: {e}", file=sys.stderr)
    sys.exit(4)

# Probe Supabase reachability (auth required, so we accept 200/401)
try:
    url = os.environ.get("SUPABASE_URL", "")
    if url:
        r = httpx.get(url + "/rest/v1/", timeout=3.0)
        if r.status_code not in (200, 401):
            print(f"unhealthy: supabase -> {r.status_code}", file=sys.stderr)
            sys.exit(5)
except Exception as e:
    print(f"unhealthy: supabase probe error: {e}", file=sys.stderr)
    sys.exit(6)

print("healthy")
sys.exit(0)
