// Supabase Edge Function — aimg-qe-call (v1.1)
// CT-0414-09 single-model tier router per AIMG TIER MATRIX FINAL LOCK.
// v1.1 C→A deltas: atomic check-and-increment RPC (race-free), token-based
// cost reconciliation post-OpenAI, pause-flag short-circuit from platform ledger.

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

// ---- tier matrix (FINAL LOCK) ----
const TIERS: Record<string, { price: number; daily_cap: number }> = {
  free:  { price: 0,     daily_cap: 20 },
  basic: { price: 4.99,  daily_cap: 50 },
  plus:  { price: 9.99,  daily_cap: 150 },
  pro:   { price: 19.99, daily_cap: 300 },
};
const NEXT_TIER: Record<string, string> = { free: "basic", basic: "plus", plus: "pro", pro: "pro" };

const PLATFORM_COST_HARD_USD  = Number(Deno.env.get("AIMG_PLATFORM_DAILY_CAP_USD") ?? 5);
const PLATFORM_COST_ALERT_USD = Number(Deno.env.get("AIMG_PLATFORM_DAILY_ALERT_USD") ?? 3);
// Pre-call ESTIMATE (reconciled to real token cost post-response).
const COST_ESTIMATE_USD       = Number(Deno.env.get("AIMG_COST_PER_CALL_USD") ?? 0.0002);

// GPT-4o-mini pricing (USD/1M tokens) — update here if OpenAI changes rates.
const OPENAI_INPUT_PER_MTOK   = Number(Deno.env.get("OPENAI_INPUT_PER_MTOK")  ?? 0.15);
const OPENAI_OUTPUT_PER_MTOK  = Number(Deno.env.get("OPENAI_OUTPUT_PER_MTOK") ?? 0.60);

const supabaseAdmin = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false } },
);
const OPENAI_KEY    = Deno.env.get("OPENAI_API_KEY")!;
const SLACK_WEBHOOK = Deno.env.get("AMG_ADMIN_SLACK_WEBHOOK") ?? "";

// ---- helpers ----
async function getUserTier(user_id: string): Promise<string> {
  const { data } = await supabaseAdmin
    .from("users").select("tier").eq("user_id", user_id).maybeSingle();
  return (data?.tier ?? "free").toLowerCase();
}

async function tryIncrement(user_id: string, day: string, daily_cap: number): Promise<any> {
  const { data, error } = await supabaseAdmin.rpc("aimg_try_increment", {
    p_user_id: user_id,
    p_day: day,
    p_daily_cap: daily_cap,
    p_platform_hard_usd: PLATFORM_COST_HARD_USD,
    p_cost_usd: COST_ESTIMATE_USD,
  });
  if (error) throw new Error(`rpc aimg_try_increment: ${error.message}`);
  return data;
}

async function reconcileCost(user_id: string, day: string, actual_usd: number): Promise<void> {
  await supabaseAdmin.rpc("aimg_reconcile_cost", {
    p_user_id: user_id,
    p_day: day,
    p_actual_cost_usd: actual_usd,
    p_estimate_cost_usd: COST_ESTIMATE_USD,
  });
}

async function notifySlack(text: string): Promise<void> {
  if (!SLACK_WEBHOOK) return;
  try {
    await fetch(SLACK_WEBHOOK, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch { /* swallow */ }
}

async function callOpenAI(content: string, operation: string): Promise<{
  parsed: { verified: boolean; confidence: number; result: string };
  usage: { prompt_tokens: number; completion_tokens: number };
}> {
  const sys = operation === "verify"
    ? "You are a fact-checking layer. Given a memory extracted by AI Memory Guard, return JSON { verified: bool, confidence: 0-1, result: <verdict> }. Be strict; low confidence for noise."
    : "You are an extraction layer. Given AI thread text, return JSON { verified: bool, confidence: 0-1, result: <memory or null> }. Strict 0.75 threshold; return confidence<0.75 for low-quality content.";
  const resp = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "Authorization": `Bearer ${OPENAI_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: sys },
        { role: "user",   content: content.slice(0, 6000) },
      ],
      max_tokens: 250,
      temperature: 0.1,
    }),
  });
  if (!resp.ok) throw new Error(`openai ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  const j = await resp.json();
  const usage = {
    prompt_tokens:     j.usage?.prompt_tokens     ?? 0,
    completion_tokens: j.usage?.completion_tokens ?? 0,
  };
  let parsed;
  try { parsed = JSON.parse(j.choices[0].message.content); }
  catch { parsed = { verified: false, confidence: 0.0, result: "parse_error" }; }
  return { parsed, usage };
}

function actualCostUsd(prompt_tokens: number, completion_tokens: number): number {
  return (prompt_tokens / 1_000_000) * OPENAI_INPUT_PER_MTOK +
         (completion_tokens / 1_000_000) * OPENAI_OUTPUT_PER_MTOK;
}

// ---- main handler ----
serve(async (req) => {
  if (req.method !== "POST") return new Response("method not allowed", { status: 405 });

  let body: any;
  try { body = await req.json(); }
  catch { return new Response(JSON.stringify({ error: "invalid_json" }), { status: 400 }); }

  const { user_id, memory_content, operation = "verify" } = body;
  if (!user_id || !memory_content) {
    return new Response(JSON.stringify({ error: "missing_fields" }), { status: 400 });
  }

  const day = new Date().toISOString().slice(0, 10);
  const tier = await getUserTier(user_id);
  const cfg  = TIERS[tier] ?? TIERS.free;

  // 1. Atomic check-and-increment (race-free).
  //    If allowed: count was incremented pessimistically with COST_ESTIMATE.
  //    If provider errors, we reconcile with negative delta to back out the charge.
  const gate = await tryIncrement(user_id, day, cfg.daily_cap);

  if (!gate.allowed && gate.reason === "platform_cost_ceiling") {
    const retry = new Date(); retry.setUTCDate(retry.getUTCDate() + 1); retry.setUTCHours(0, 0, 0, 0);
    return new Response(JSON.stringify({
      error: "platform_cost_ceiling",
      retry_after_utc: retry.toISOString(),
      platform_cost_usd: gate.platform_cost_usd,
    }), { status: 429 });
  }
  if (!gate.allowed && gate.reason === "tier_cap_exceeded") {
    const suggested = NEXT_TIER[tier];
    return new Response(JSON.stringify({
      error: "tier_cap_exceeded",
      upsell: {
        current_tier: tier,
        current_cap: cfg.daily_cap,
        suggested_tier: suggested,
        suggested_cap: TIERS[suggested]?.daily_cap ?? cfg.daily_cap,
        next_tier_price: TIERS[suggested]?.price ?? cfg.price,
      },
    }), { status: 402 });
  }

  // Fire Slack alert if we crossed the $3 threshold this call
  if (gate.platform_cost_usd >= PLATFORM_COST_ALERT_USD &&
      gate.platform_cost_usd - COST_ESTIMATE_USD < PLATFORM_COST_ALERT_USD) {
    notifySlack(`:warning: AIMG daily spend crossed $${PLATFORM_COST_ALERT_USD} (now $${gate.platform_cost_usd.toFixed(4)}).`);
  }

  // 2. Provider call
  let openaiResult;
  try { openaiResult = await callOpenAI(memory_content, operation); }
  catch (e) {
    // Back out the pre-charged estimate on provider failure.
    await reconcileCost(user_id, day, 0).catch(() => {});
    return new Response(JSON.stringify({
      error: "provider_error",
      detail: String(e).slice(0, 200),
    }), { status: 502 });
  }

  // 3. Reconcile cost with actual tokens (close the accounting drift)
  const actual = actualCostUsd(openaiResult.usage.prompt_tokens, openaiResult.usage.completion_tokens);
  reconcileCost(user_id, day, actual).catch(() => {});

  // 4. Response + countdown data
  return new Response(JSON.stringify({
    result: openaiResult.parsed,
    usage: {
      tier,
      used_today: gate.call_count,
      daily_cap: cfg.daily_cap,
      remaining: cfg.daily_cap - gate.call_count,
      actual_cost_usd: actual,
    },
  }), { status: 200, headers: { "Content-Type": "application/json" } });
});
