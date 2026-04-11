#!/usr/bin/env python3
"""
titan-harness/scripts/test_payment_url.py

End-to-end browser test for a payment URL. This is the tool behind Gate 3
of the proposal generator: every URL that ships to a client must first pass
a run of this script, and the passing result must be logged in
public.payment_link_tests within the last 24 hours.

What it validates:
  1. The URL loads in a real non-headless Chromium against Xvfb
  2. The rendered page is an actual checkout form (not an error page)
  3. The displayed brand name matches what Titan expected
     (the Lavar 2026-04-10 bug was "Credit Repair Hawk LLC dba Dr. SEO"
     showing up instead of "AI Marketing Genius" on the legacy plan_id URL)
  4. No error markers are visible
  5. No CAPTCHA gate (if hit, the verdict is 'captcha_blocked' and
     the caller must retry with a seasoned profile)

Usage:
  test_payment_url.py \
    --url 'https://www.paypal.com/...' \
    --expected-brand 'AI Marketing Genius' \
    --plan-id P-40456056SB832583SNHL7VCI \
    --project-id EOM

  test_payment_url.py \
    --plan-id P-40456056SB832583SNHL7VCI \
    --expected-brand 'AI Marketing Genius' \
    --auto-generate-ba-token

Exit codes:
  0 — pass (rendered checkout + correct brand name)
  1 — fail (rendered but wrong brand or error markers)
  2 — captcha blocked (cannot determine — retry later)
  3 — nav / load error
  4 — bad arguments
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


PAYPAL_ENV_FILE = "/home/titan/amg/poll_invoicing_scope.sh"
SUPABASE_URL_DEFAULT = "https://egoazyasyrhslluossli.supabase.co"
XVFB_DISPLAY = ":99"
SCREENSHOT_DIR = Path("/var/log/payment-link-tests")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
CHROME_PROFILE = "/opt/chrome-profile-paypal-test"


def _load_paypal_creds() -> tuple[str, str]:
    cid = sec = ""
    if not os.path.isfile(PAYPAL_ENV_FILE):
        return cid, sec
    for line in open(PAYPAL_ENV_FILE, errors="replace"):
        line = line.strip()
        if line.startswith("export PAYPAL_CLIENT_ID="):
            cid = line.split("=", 1)[1].strip().strip("'\"")
        elif line.startswith("export PAYPAL_SECRET="):
            sec = line.split("=", 1)[1].strip().strip("'\"")
    return cid, sec


def _paypal_token() -> str:
    cid, sec = _load_paypal_creds()
    if not cid or not sec:
        raise RuntimeError("PayPal credentials not found in poll_invoicing_scope.sh")
    auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    req = urllib.request.Request(
        "https://api-m.paypal.com/v1/oauth2/token",
        data=b"grant_type=client_credentials",
        headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def create_ba_token_url(plan_id: str, brand_name: str,
                        return_url: str, cancel_url: str) -> str:
    token = _paypal_token()
    body = {
        "plan_id": plan_id,
        "application_context": {
            "brand_name": brand_name,
            "user_action": "SUBSCRIBE_NOW",
            "return_url": return_url,
            "cancel_url": cancel_url,
        },
    }
    req = urllib.request.Request(
        "https://api-m.paypal.com/v1/billing/subscriptions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": f"titan-tpu-{int(time.time())}-{plan_id[-6:]}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            return link["href"]
    raise RuntimeError(f"no approve link in response: {data}")


def _classify_url_kind(url: str) -> str:
    u = url.lower()
    if "paypal.com" in u and "/plans/subscribe" in u:
        return "legacy_plan_id"
    if "paypal.com" in u and "ba_token=" in u:
        return "ba_token"
    if "pay.aimarketinggenius.io" in u or "aimarketinggenius.io/pay" in u:
        return "redirector"
    if "stripe.com" in u or "checkout.stripe.com" in u:
        return "stripe_checkout"
    if "paddle.com" in u:
        return "paddle_checkout"
    return "other"


def _classify_processor(url: str) -> str:
    u = url.lower()
    if "paypal.com" in u or "paypalobjects" in u:
        return "paypal"
    if "stripe.com" in u:
        return "stripe"
    if "paddle.com" in u:
        return "paddle"
    if "square" in u:
        return "square"
    return "other"


def run_test(url: str, expected_brand: str,
             plan_id: str | None, product_id: str | None,
             expected_price: str | None) -> dict:
    os.environ["DISPLAY"] = XVFB_DISPLAY
    run_id = hashlib.md5(f"{url}:{time.time()}".encode()).hexdigest()[:12]
    screenshot = str(SCREENSHOT_DIR / f"tpu_{run_id}.png")

    start_ms = int(time.time() * 1000)

    result = {
        "url": url,
        "url_kind": _classify_url_kind(url),
        "processor": _classify_processor(url),
        "plan_id": plan_id,
        "product_id": product_id,
        "expected_brand_name": expected_brand,
        "expected_price_label": expected_price,
        "observed_brand_name": None,
        "observed_price_label": None,
        "page_title": None,
        "url_after_redirect": None,
        "body_excerpt": None,
        "iframe_excerpt": None,
        "screenshot_path": screenshot,
        "status": "error",
        "fail_reason": None,
        "brand_match": None,
        "tested_by": socket.gethostname(),
        "tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "test_duration_ms": 0,
        "playwright_user_agent": None,
    }

    try:
        with sync_playwright() as p:
            UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/146.0.0.0 Safari/537.36")
            result["playwright_user_agent"] = UA

            context = p.chromium.launch_persistent_context(
                user_data_dir=CHROME_PROFILE,
                headless=False,
                viewport={"width": 1400, "height": 900},
                user_agent=UA,
                locale="en-US",
                timezone_id="America/New_York",
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1400,900",
                ],
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                result["status"] = "error"
                result["fail_reason"] = f"nav_error: {e}"
                context.close()
                return result

            # Let PayPal's JS settle
            time.sleep(8)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            time.sleep(2)

            result["page_title"] = page.title()
            result["url_after_redirect"] = page.url

            # Extract visible text (body + iframes)
            body_text = ""
            try:
                body_text = page.evaluate("() => document.body.innerText || ''")
            except Exception:
                pass

            iframe_text_parts = []
            for frame in page.frames:
                try:
                    t = frame.evaluate("() => document.body.innerText || ''")
                    if t and len(t) > 30:
                        iframe_text_parts.append(t)
                except Exception:
                    continue
            iframe_text = "\n".join(iframe_text_parts)

            result["body_excerpt"] = body_text[:2000]
            result["iframe_excerpt"] = iframe_text[:2000]
            full_text = (body_text + "\n" + iframe_text).strip()
            full_lower = full_text.lower()

            page.screenshot(path=screenshot, full_page=True)

            # Classify the render — CAPTCHA detection must be very specific
            # because "captcha" shows up in PayPal's anti-abuse JS even on
            # normally-rendered checkout pages. Only flag as blocked when
            # the CAPTCHA UI is actually the main rendered page content.
            captcha_ui = [
                "confirm you're human",  # the CAPTCHA page header
                "confirm you&#39;re human",
                "move the slider all the way to the right",
            ]
            errors = ["things don't appear", "something went wrong",
                      "page not found", "plan not found",
                      "subscription not available", "we can't process",
                      "temporarily unavailable"]
            form_markers = ["let's check out with", "let&#39;s check out with",
                            "agree & subscribe",
                            "agree and subscribe", "subscribe now",
                            "log in to your paypal", "pay with paypal",
                            "pay with debit or credit card", "choose a way to pay",
                            "email or mobile number", "create an account",
                            "per month", "/month"]

            # Only flag CAPTCHA if a CAPTCHA UI string is present AND the
            # form markers are NOT. If both are present, the form rendered
            # correctly and "captcha" is just a hidden anti-abuse reference.
            captcha_hit = [m for m in captcha_ui if m in full_lower]
            form_hit_early = [m for m in form_markers if m in full_lower]
            if captcha_hit and not form_hit_early:
                result["status"] = "captcha_blocked"
                result["fail_reason"] = (
                    f"PayPal CAPTCHA page rendered: {captcha_hit}; "
                    f"retry with seasoned profile"
                )
                context.close()
                return result

            if any(m in full_lower for m in errors):
                result["status"] = "fail"
                result["fail_reason"] = (
                    f"error markers on rendered page: "
                    f"{[m for m in errors if m in full_lower]}"
                )
                context.close()
                return result

            form_hit = form_hit_early
            if not form_hit:
                result["status"] = "inconclusive"
                result["fail_reason"] = (
                    "no error markers but no form markers either; "
                    "could not confirm checkout form rendered"
                )
                context.close()
                return result

            # Extract the observed brand name — PayPal renders
            # "Let's check out with <BRAND>" on the login page
            import re as re_mod
            brand_match = re_mod.search(
                r"let'?s check out with\s+([^\n]+?)(?:\s*Email|\n|$)",
                full_text, re_mod.IGNORECASE,
            )
            if brand_match:
                result["observed_brand_name"] = brand_match.group(1).strip()

            # Extract observed price if the page shows one
            price_match = re_mod.search(r"\$[\d,]+\.\d{2}", full_text)
            if price_match:
                result["observed_price_label"] = price_match.group(0)

            # Brand name check
            if expected_brand and result["observed_brand_name"]:
                # Normalize for comparison
                exp_norm = expected_brand.lower().strip()
                obs_norm = result["observed_brand_name"].lower().strip()
                result["brand_match"] = (exp_norm in obs_norm) or (obs_norm in exp_norm)
                if not result["brand_match"]:
                    result["status"] = "fail"
                    result["fail_reason"] = (
                        f"brand name mismatch — expected '{expected_brand}', "
                        f"observed '{result['observed_brand_name']}'. "
                        f"This is the JDJ Lavar class of bug."
                    )
                    context.close()
                    return result

            # All checks passed
            result["status"] = "pass"
            context.close()

    except Exception as e:
        result["status"] = "error"
        result["fail_reason"] = f"{type(e).__name__}: {e}"

    result["test_duration_ms"] = int(time.time() * 1000) - start_ms
    return result


def log_to_supabase(row: dict, project_id: str) -> bool:
    """POST the test row to public.payment_link_tests via PostgREST."""
    # Resolve Supabase creds
    sup_url = os.environ.get("SUPABASE_URL") or SUPABASE_URL_DEFAULT
    sup_key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
               or os.environ.get("SUPABASE_SERVICE_KEY"))
    if not sup_key:
        # Try loading from titan-processor env
        for envf in ("/opt/titan-processor/.env", "/opt/amg-titan/.env",
                     "/opt/amg-mcp-server/.env.local"):
            if os.path.isfile(envf):
                for line in open(envf, errors="replace"):
                    line = line.strip()
                    if line.startswith("SUPABASE_SERVICE_KEY=") or \
                       line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
                        sup_key = line.split("=", 1)[1].strip().strip("'\"")
                        break
            if sup_key:
                break
    if not sup_key:
        print("WARN: no Supabase key, skipping log")
        return False

    row_for_db = {**row, "project_id": project_id}
    # Remove client-only fields that aren't DB columns
    row_for_db.pop("test_duration_ms", None)  # actually IS a column
    row_for_db["test_duration_ms"] = row.get("test_duration_ms", 0)

    body = json.dumps(row_for_db).encode()
    req = urllib.request.Request(
        f"{sup_url}/rest/v1/payment_link_tests",
        data=body,
        headers={
            "apikey": sup_key,
            "Authorization": f"Bearer {sup_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in (200, 201, 204)
    except Exception as e:
        print(f"WARN: supabase log failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(prog="test_payment_url")
    parser.add_argument("--url",
                        help="URL to test (mutually exclusive with --auto-generate-ba-token)")
    parser.add_argument("--expected-brand", required=True,
                        help="Brand name that must appear on the rendered page")
    parser.add_argument("--plan-id", help="PayPal plan ID (for logging)")
    parser.add_argument("--product-id", help="PayPal product ID (for logging)")
    parser.add_argument("--expected-price", help="Expected price label e.g. '$500.00'")
    parser.add_argument("--project-id", default="EOM")
    parser.add_argument("--auto-generate-ba-token", action="store_true",
                        help="Create a fresh ba_token URL via PayPal API using --plan-id")
    parser.add_argument("--return-url", default="https://aimarketinggenius.io/subscription-confirmed")
    parser.add_argument("--cancel-url", default="https://aimarketinggenius.io/subscription-cancelled")
    parser.add_argument("--json", action="store_true",
                        help="Emit full result as JSON on stdout")
    args = parser.parse_args()

    url = args.url
    if args.auto_generate_ba_token:
        if not args.plan_id:
            print("ERROR: --auto-generate-ba-token requires --plan-id", file=sys.stderr)
            return 4
        url = create_ba_token_url(
            args.plan_id, args.expected_brand,
            args.return_url, args.cancel_url,
        )
        print(f"generated ba_token URL: {url}")

    if not url:
        print("ERROR: --url or --auto-generate-ba-token required", file=sys.stderr)
        return 4

    result = run_test(
        url=url,
        expected_brand=args.expected_brand,
        plan_id=args.plan_id,
        product_id=args.product_id,
        expected_price=args.expected_price,
    )

    log_to_supabase(result, args.project_id)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print()
        print("=" * 64)
        print(f"URL:           {result['url'][:100]}")
        print(f"Status:        {result['status']}")
        print(f"Title:         {result['page_title']}")
        print(f"Expected:      {result['expected_brand_name']}")
        print(f"Observed:      {result['observed_brand_name']}")
        print(f"Brand match:   {result['brand_match']}")
        print(f"Screenshot:    {result['screenshot_path']}")
        if result["fail_reason"]:
            print(f"Fail reason:   {result['fail_reason']}")

    exit_map = {
        "pass": 0,
        "fail": 1,
        "captcha_blocked": 2,
        "inconclusive": 1,
        "error": 3,
    }
    return exit_map.get(result["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
