"""5-lane LiteLLM direct concurrency test (bypasses llm_client capacity gate)."""
import asyncio, os, time, json, httpx

BASE = os.environ["LITELLM_BASE_URL"].rstrip("/")
KEY = os.environ["LITELLM_MASTER_KEY"]

async def one_lane(lane_id: int, client: httpx.AsyncClient) -> dict:
    t0 = time.time()
    try:
        r = await client.post(
            f"{BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
            json={
                "model": "claude-haiku-4-5",
                "messages": [{"role": "user", "content": f"Reply with exactly: lane_{lane_id}_ok (no other text)"}],
                "max_tokens": 15,
                "temperature": 0.0,
            },
            timeout=60.0,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()
        t1 = time.time()
        return {"lane": lane_id, "ok": True, "latency_ms": (t1-t0)*1000, "content": content[:60]}
    except Exception as e:
        t1 = time.time()
        return {"lane": lane_id, "ok": False, "latency_ms": (t1-t0)*1000, "err": str(e)[:100]}

async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        t0 = time.time()
        results = await asyncio.gather(*[one_lane(i, client) for i in range(5)])
        wall = (time.time() - t0) * 1000

    ok = sum(1 for r in results if r["ok"])
    seq = sum(r["latency_ms"] for r in results)
    speedup = seq / wall if wall else 0

    print("=== 5-lane LIVE LiteLLM test ===")
    print(f"Pass: {ok}/5  Wall-clock: {wall:.1f}ms  Sum-of-latencies: {seq:.1f}ms  Speedup: {speedup:.2f}x")
    for r in results:
        status = "OK " if r["ok"] else "ERR"
        lat = r["latency_ms"]; lid = r["lane"]
        preview = r.get("content", r.get("err", ""))[:60]
        print(f"  lane {lid}: {status} lat={lat:>7.1f}ms | {preview}")

asyncio.run(main())
