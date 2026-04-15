-- CT-0414-09 — AIMG tier router usage tracking + platform cost ledger.
-- v1.1 — Perplexity C→A deltas: atomic check-and-increment, platform
-- cost single-row ledger, pause flag cache.
-- Apply via: supabase db push (linked to gaybcxzrzfgvcqpkbeiq).
-- Rollback: see README.md.

create table if not exists public.aimg_usage (
    user_id     uuid not null,
    day_utc     date not null,
    call_count  integer not null default 0,
    cost_usd    numeric(10, 6) not null default 0,
    updated_at  timestamptz not null default now(),
    primary key (user_id, day_utc)
);
create index if not exists aimg_usage_day_utc_idx on public.aimg_usage (day_utc);

-- Platform-wide daily ledger — single-row-per-day, cheap to read every request.
-- Replaces expensive sum(cost_usd) query across N rows.
create table if not exists public.aimg_platform_daily (
    day_utc     date primary key,
    total_calls bigint not null default 0,
    total_cost_usd numeric(12, 6) not null default 0,
    paused      boolean not null default false,
    updated_at  timestamptz not null default now()
);

-- RLS
alter table public.aimg_usage enable row level security;
drop policy if exists "aimg_usage_own_row_read" on public.aimg_usage;
create policy "aimg_usage_own_row_read" on public.aimg_usage
    for select using (auth.uid() = user_id);
drop policy if exists "aimg_usage_service_write" on public.aimg_usage;
create policy "aimg_usage_service_write" on public.aimg_usage
    for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

alter table public.aimg_platform_daily enable row level security;
drop policy if exists "aimg_platform_service_only" on public.aimg_platform_daily;
create policy "aimg_platform_service_only" on public.aimg_platform_daily
    for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');

-- ATOMIC check-and-increment. Single round-trip. Returns structured JSON:
--   {allowed: bool, reason: text|null, call_count: int, daily_cap: int,
--    platform_paused: bool, platform_cost_usd: numeric}
-- Caller passes the user's daily_cap (from the edge function's tier table)
-- and the current platform hard-ceiling. RPC handles all serialization
-- under row-level locks; no read-modify-write race possible.
create or replace function public.aimg_try_increment(
    p_user_id   uuid,
    p_day       date,
    p_daily_cap integer,
    p_platform_hard_usd numeric,
    p_cost_usd  numeric
) returns jsonb
language plpgsql
security definer
as $$
declare
    v_cur integer;
    v_platform_cost numeric;
    v_paused boolean;
begin
    -- Platform pause check (single-row read; O(1))
    select coalesce(total_cost_usd, 0), coalesce(paused, false)
      into v_platform_cost, v_paused
      from public.aimg_platform_daily
     where day_utc = p_day
       for update;

    if v_paused or v_platform_cost >= p_platform_hard_usd then
        return jsonb_build_object(
            'allowed', false,
            'reason', 'platform_cost_ceiling',
            'call_count', coalesce((select call_count from public.aimg_usage
                                     where user_id = p_user_id and day_utc = p_day), 0),
            'daily_cap', p_daily_cap,
            'platform_paused', true,
            'platform_cost_usd', coalesce(v_platform_cost, 0)
        );
    end if;

    -- Per-user row-level lock + atomic check
    insert into public.aimg_usage (user_id, day_utc, call_count, cost_usd, updated_at)
    values (p_user_id, p_day, 0, 0, now())
    on conflict (user_id, day_utc) do nothing;

    select call_count into v_cur
      from public.aimg_usage
     where user_id = p_user_id and day_utc = p_day
       for update;

    if v_cur >= p_daily_cap then
        return jsonb_build_object(
            'allowed', false,
            'reason', 'tier_cap_exceeded',
            'call_count', v_cur,
            'daily_cap', p_daily_cap,
            'platform_paused', false,
            'platform_cost_usd', coalesce(v_platform_cost, 0)
        );
    end if;

    update public.aimg_usage
       set call_count = call_count + 1,
           cost_usd = cost_usd + p_cost_usd,
           updated_at = now()
     where user_id = p_user_id and day_utc = p_day
    returning call_count into v_cur;

    -- Increment platform ledger (single-row upsert)
    insert into public.aimg_platform_daily (day_utc, total_calls, total_cost_usd, paused, updated_at)
    values (p_day, 1, p_cost_usd, false, now())
    on conflict (day_utc) do update
        set total_calls = public.aimg_platform_daily.total_calls + 1,
            total_cost_usd = public.aimg_platform_daily.total_cost_usd + p_cost_usd,
            paused = (public.aimg_platform_daily.total_cost_usd + p_cost_usd) >= p_platform_hard_usd,
            updated_at = now();

    return jsonb_build_object(
        'allowed', true,
        'reason', null,
        'call_count', v_cur,
        'daily_cap', p_daily_cap,
        'platform_paused', false,
        'platform_cost_usd', v_platform_cost + p_cost_usd
    );
end;
$$;

-- Reconciliation RPC — called AFTER OpenAI response with actual token counts.
-- Corrects cost_usd drift (fixed $0.0002 estimate → real token-based cost).
create or replace function public.aimg_reconcile_cost(
    p_user_id uuid,
    p_day     date,
    p_actual_cost_usd numeric,
    p_estimate_cost_usd numeric
) returns void
language plpgsql
security definer
as $$
declare
    v_delta numeric;
begin
    v_delta := p_actual_cost_usd - p_estimate_cost_usd;
    if v_delta = 0 then return; end if;

    update public.aimg_usage
       set cost_usd = cost_usd + v_delta,
           updated_at = now()
     where user_id = p_user_id and day_utc = p_day;

    update public.aimg_platform_daily
       set total_cost_usd = total_cost_usd + v_delta,
           paused = (total_cost_usd + v_delta) >= (
               select coalesce(nullif(current_setting('aimg.hard_cap', true), '')::numeric, 5.0)
           ),
           updated_at = now()
     where day_utc = p_day;
end;
$$;

grant execute on function public.aimg_try_increment  to service_role;
grant execute on function public.aimg_reconcile_cost to service_role;
revoke execute on function public.aimg_try_increment  from anon, authenticated;
revoke execute on function public.aimg_reconcile_cost from anon, authenticated;

-- users.tier column — uncomment if absent on the AIMG users table
-- alter table public.users add column if not exists tier text not null default 'free'
--     check (tier in ('free', 'basic', 'plus', 'pro'));
