# Memory Vault — Caddy Same-Origin Supabase Proxy

**Why:** direct-to-supabase.co fetches from the browser were blocked on some
Mac environments (Safari ITP + Chrome extensions/firewalls), causing silent
"Load failed" errors on the login button. Same-origin proxy eliminates every
cross-origin call so the browser only ever talks to `memory.aimarketinggenius.io`.

## Caddy block (on VPS `/opt/n8n/Caddyfile`, inside `memory.aimarketinggenius.io`)

```caddyfile
# Same-origin Supabase proxy — eliminates browser cross-origin blocks (Safari ITP etc)
@sbproxy path /supabase/* /auth/v1/* /rest/v1/* /storage/v1/* /realtime/v1/*
handle @sbproxy {
    uri strip_prefix /supabase
    reverse_proxy https://gaybcxzrzfgvcqpkbeiq.supabase.co {
        header_up Host gaybcxzrzfgvcqpkbeiq.supabase.co
        header_up X-Forwarded-Proto https
        transport http {
            tls
            tls_server_name gaybcxzrzfgvcqpkbeiq.supabase.co
        }
    }
}
```

Place this block immediately after the `@memoryvault handle` block and before
the `@ingest` / default `handle` fallback so `/supabase/*` paths match before
falling through to the MCP default handler.

## Client (config.js)

```js
window.AIMG_CONFIG = {
  supabaseUrl: 'https://memory.aimarketinggenius.io/supabase',
  ...
};
```

Supabase-JS transparently uses this URL for all auth + REST calls.

## Verification

```bash
# Health via proxy (expects 401 for unauth, proves path routes)
curl -sSI https://memory.aimarketinggenius.io/supabase/auth/v1/health | head -3

# Auth POST via proxy (expects 200 + access_token)
curl -sS -X POST https://memory.aimarketinggenius.io/supabase/auth/v1/token?grant_type=password \
  -H "apikey: $AIMG_SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@aimarketinggenius.io","password":"chamber-demo-2026"}'
```

## Rollback

If proxy misbehaves, revert config.js to `supabaseUrl: 'https://gaybcxzrzfgvcqpkbeiq.supabase.co'`
and remove the `@sbproxy` Caddy block. Browser falls back to direct cross-origin
calls (subject to the original blocking issue).
