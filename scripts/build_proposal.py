#!/usr/bin/env python3
"""
titan-harness/scripts/build_proposal.py

Reusable client proposal generator for AMG (and any future Titan-as-COO
tenant). Builds a client-ready DOCX from a Jinja template + a pricing
manifest + the live PayPal plan catalog, with a **build-time payment-link
verification gate** that refuses to ship a contract missing any referenced
subscribe URL.

Born from the JDJ Lavar incident (2026-04-09) where a contract shipped to
a signed client with zero payment links because the template said "see
Section 3" and Section 3 was empty. This script makes that class of
failure structurally impossible.

Architecture:
  1. Load proposal spec (YAML or JSON) describing the client, the
     price plans referenced, the sections, the terms, and any
     client-specific overrides.
  2. Load `payment_links_paypal.json` (or equivalent for other processors)
     and build a plan_id → subscribe_url lookup.
  3. GATE 1: For every price plan the spec references, assert a matching
     subscribe URL exists in the catalog. If ANY plan is missing its URL,
     FAIL the build and exit non-zero — no DOCX is written.
  4. GATE 3: For every resolved subscribe URL, query Supabase
     public.payment_link_tests and assert a row with status='pass' and
     tested_at within the last 24 hours exists. This forces every URL
     shipped to a client to have been end-to-end browser-tested by
     scripts/test_payment_url.py against sql/006_payment_link_tests.sql.
     Born from JDJ Lavar 2026-04-10 — wrong brand name on the rendered
     checkout page that API-level checks could not catch.
  5. Render the DOCX via python-docx or a Jinja template applied to
     document.xml of a base template file.
  6. GATE 2: Run a post-build scan: extract plain text from the rendered
     DOCX and verify every referenced plan URL is actually present.
     Belt-and-suspenders verification.
  7. Emit a summary JSON to stdout for mp-runner consumption.

Usage:
  build_proposal.py --spec spec.yaml --template base.docx --out out.docx
  build_proposal.py --spec specs/jdj.yaml --catalog payment_links_paypal.json

Exit codes:
  0  — proposal built + verified successfully
  1  — generic failure (I/O, template error)
  2  — build-time gate 1 failure: referenced plan missing subscribe URL
  3  — post-build gate 2 failure: plan URL not found in rendered DOCX
  4  — bad arguments
  5  — gate 3 failure: subscribe URL lacks a payment_link_tests pass row
       within 24 hours (run scripts/test_payment_url.py first)

This script is the canonical proposal builder. It replaces manual DOCX
editing for any future client engagement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


DEFAULT_CATALOG = "/home/titan/amg/payment_links_paypal.json"
SUPABASE_URL_DEFAULT = "https://egoazyasyrhslluossli.supabase.co"
GATE3_WINDOW_HOURS = 24
DEFAULT_TEMPLATE = str(
    Path(__file__).resolve().parent.parent / "templates" / "proposals" / "jdj_proposal_v4_linksfix.docx"
)


# -----------------------------------------------------------------------------
# Spec schema
# -----------------------------------------------------------------------------
# A proposal spec describes the client, the plans referenced, and the
# placeholder values that get substituted into the template. Specs are JSON
# or YAML; YAML is preferred for readability but JSON is supported for
# simpler downstream parsing.
#
# Required fields:
#   client:
#     business_name: str
#     display_name: str           # person to address the proposal to
#     city_state: str
#     email: str                  # recipient
#   pricing:
#     plans:
#       - name: str               # e.g. "Infrastructure Setup Fee"
#         plan_id: str            # PayPal plan ID, e.g. "P-40456056SB832583SNHL7VCI"
#         price_label: str        # e.g. "$500/mo × 3"
#         description: str        # one-line description
#   terms:
#     cancellation: str           # or default template
#     performance_guarantee: str  # or default template
#     ownership: str
#   metadata:
#     proposal_version: str       # e.g. "v4"
#     generated_at: iso string    # auto-filled
#     project_id: str             # tenant tag for multi-tenant use
#
# The template DOCX must contain placeholder tokens like {{plan.name}},
# {{plan.subscribe_url}}, {{client.display_name}} etc. The renderer walks
# the template's document.xml and performs literal token replacement.


@dataclass
class ProposalPlan:
    name: str
    plan_id: str
    price_label: str
    description: str
    subscribe_url: str = ""  # filled in from catalog


@dataclass
class ProposalSpec:
    client: dict
    plans: list[ProposalPlan]
    terms: dict
    metadata: dict

    @classmethod
    def load(cls, path: Path) -> "ProposalSpec":
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError:
                # Minimal fallback — specs will typically be simple
                # enough to hand-parse if yaml isn't available, but
                # the canonical path is pyyaml.
                sys.stderr.write(
                    "ERROR: PyYAML not installed. Install with: pip install pyyaml\n"
                )
                sys.exit(1)
            data = yaml.safe_load(raw)
        else:
            data = json.loads(raw)

        plans = []
        for p in data.get("pricing", {}).get("plans", []):
            plans.append(ProposalPlan(
                name=p["name"],
                plan_id=p["plan_id"],
                price_label=p.get("price_label", ""),
                description=p.get("description", ""),
            ))

        return cls(
            client=data.get("client", {}),
            plans=plans,
            terms=data.get("terms", {}),
            metadata=data.get("metadata", {}),
        )


# -----------------------------------------------------------------------------
# Catalog loader
# -----------------------------------------------------------------------------

def load_catalog(catalog_path: Path) -> dict[str, dict]:
    """Load the PayPal plan catalog and return a plan_id → plan dict lookup.

    Tolerates the catalog being either a flat list of plans or an object
    with a 'products' / 'plans' / 'items' wrapper key.
    """
    data = json.loads(catalog_path.read_text(encoding="utf-8"))

    plans_list: list[dict] = []
    if isinstance(data, list):
        plans_list = data
    elif isinstance(data, dict):
        for key in ("plans", "products", "items"):
            if key in data and isinstance(data[key], list):
                plans_list = data[key]
                break
        if not plans_list:
            # Maybe the dict itself is a plan_id → plan map
            if all(isinstance(v, dict) for v in data.values()):
                plans_list = list(data.values())

    lookup: dict[str, dict] = {}
    for p in plans_list:
        if not isinstance(p, dict):
            continue
        pid = p.get("plan_id")
        if pid:
            lookup[pid] = p
    return lookup


# -----------------------------------------------------------------------------
# Build-time gate 1: every referenced plan must have a subscribe URL
# -----------------------------------------------------------------------------

def resolve_subscribe_urls(spec: ProposalSpec, catalog: dict[str, dict]) -> list[str]:
    """Attach catalog subscribe URLs to spec plans. Returns a list of
    missing plan IDs (empty list = gate passes)."""
    missing: list[str] = []
    for plan in spec.plans:
        entry = catalog.get(plan.plan_id)
        if not entry:
            missing.append(f"{plan.plan_id} (not in catalog)")
            continue
        url = entry.get("subscribe_link") or entry.get("subscribe_url") or entry.get("approve_link")
        if not url:
            missing.append(f"{plan.plan_id} (catalog entry has no subscribe URL)")
            continue
        plan.subscribe_url = url
    return missing


# -----------------------------------------------------------------------------
# Gate 3: every resolved subscribe URL must have a payment_link_tests
# row with status='pass' and tested_at within the last 24 hours.
# -----------------------------------------------------------------------------

def _resolve_supabase_key() -> Optional[str]:
    """Find a Supabase service role key from env or known dotenv files."""
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY"))
    if key:
        return key
    for envf in ("/opt/titan-processor/.env",
                 "/opt/amg-titan/.env",
                 "/opt/amg-mcp-server/.env.local",
                 str(Path.home() / ".amg_supabase_env")):
        if not os.path.isfile(envf):
            continue
        try:
            for line in open(envf, errors="replace"):
                line = line.strip()
                for prefix in ("SUPABASE_SERVICE_ROLE_KEY=",
                               "SUPABASE_SERVICE_KEY="):
                    if line.startswith(prefix):
                        return line.split("=", 1)[1].strip().strip("'\"")
        except Exception:
            continue
    return None


def _query_latest_pass(sup_url: str, sup_key: str, url: str,
                       since_iso: str) -> Optional[dict]:
    """Return the most-recent passing payment_link_tests row for `url`
    with tested_at >= since_iso, or None if no such row exists."""
    params = {
        "url": f"eq.{url}",
        "status": "eq.pass",
        "tested_at": f"gte.{since_iso}",
        "order": "tested_at.desc",
        "limit": "1",
        "select": "id,url,status,tested_at,brand_match,observed_brand_name",
    }
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    full = f"{sup_url}/rest/v1/payment_link_tests?{query}"
    req = urllib.request.Request(
        full,
        headers={
            "apikey": sup_key,
            "Authorization": f"Bearer {sup_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except Exception as e:
        sys.stderr.write(
            f"build_proposal: gate 3 supabase query error for "
            f"{url[:80]}: {type(e).__name__}: {e}\n"
        )
        return None
    if isinstance(data, list) and data:
        return data[0]
    return None


def verify_gate3_payment_link_tests(spec: ProposalSpec,
                                    window_hours: int = GATE3_WINDOW_HOURS
                                    ) -> list[str]:
    """For every plan with a resolved subscribe_url, require a passing
    payment_link_tests row tested within the last `window_hours` hours.
    Returns a list of human-readable failures (empty list = gate passes)."""
    failures: list[str] = []

    # Collect URLs to check (only those actually resolved by gate 1)
    to_check: list[tuple[str, str]] = []  # (plan_label, url)
    for plan in spec.plans:
        if not plan.subscribe_url:
            # Gate 1 already missed this; gate 3 has nothing to verify
            continue
        label = f"{plan.name} [{plan.plan_id}]"
        to_check.append((label, plan.subscribe_url))

    if not to_check:
        sys.stderr.write(
            "build_proposal: gate 3 has no URLs to verify "
            "(empty spec or gate 1 failed)\n"
        )
        return failures

    sup_url = os.environ.get("SUPABASE_URL") or SUPABASE_URL_DEFAULT
    sup_key = _resolve_supabase_key()
    if not sup_key:
        failures.append(
            "Supabase service role key not found in env or known dotenv files. "
            "Gate 3 requires SUPABASE_SERVICE_ROLE_KEY to query "
            "public.payment_link_tests. Set the env var or place it in "
            "/opt/titan-processor/.env or ~/.amg_supabase_env."
        )
        return failures

    since_dt = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    for label, url in to_check:
        row = _query_latest_pass(sup_url, sup_key, url, since_iso)
        if not row:
            failures.append(
                f"{label}: no 'pass' row in payment_link_tests within the "
                f"last {window_hours}h for URL {url[:100]}. Run: "
                f"scripts/test_payment_url.py --url '{url}' "
                f"--expected-brand 'AI Marketing Genius' "
                f"--plan-id {_plan_id_from_label(label)}"
            )
            continue
        # Row exists — sanity check brand_match if present
        if row.get("brand_match") is False:
            failures.append(
                f"{label}: latest payment_link_tests row passed status "
                f"but brand_match=false (observed '{row.get('observed_brand_name')}') "
                f"— re-run test_payment_url.py against a ba_token URL."
            )
    return failures


def _plan_id_from_label(label: str) -> str:
    # "Plan Name [P-XYZ]" → "P-XYZ"
    m = re.search(r"\[([^\]]+)\]", label)
    return m.group(1) if m else ""


# -----------------------------------------------------------------------------
# DOCX renderer (token substitution against a base template)
# -----------------------------------------------------------------------------

def render_docx(template_path: Path, output_path: Path, spec: ProposalSpec) -> None:
    """Render the proposal DOCX by substituting tokens in the template's
    document.xml. Uses the simplest possible approach — literal string
    replacement on the XML — because the template is controlled and the
    tokens are unique. For richer templating, swap in python-docx-template
    (docxtpl) at this layer without changing the rest of the pipeline.
    """
    if not template_path.is_file():
        raise FileNotFoundError(f"template not found: {template_path}")

    shutil.copy(template_path, output_path)

    # Read document.xml from the copy
    with zipfile.ZipFile(output_path, "r") as zf:
        xml = zf.read("word/document.xml").decode("utf-8")

    # Build token → value dict
    tokens: dict[str, str] = {
        "{{client.business_name}}": spec.client.get("business_name", ""),
        "{{client.display_name}}": spec.client.get("display_name", ""),
        "{{client.city_state}}": spec.client.get("city_state", ""),
        "{{client.email}}": spec.client.get("email", ""),
        "{{metadata.proposal_version}}": spec.metadata.get("proposal_version", ""),
        "{{metadata.generated_at}}": spec.metadata.get("generated_at", ""),
        "{{metadata.project_id}}": spec.metadata.get("project_id", "EOM"),
    }

    # Plan-specific tokens: {{plan.0.name}}, {{plan.0.subscribe_url}}, etc.
    for i, plan in enumerate(spec.plans):
        tokens[f"{{{{plan.{i}.name}}}}"] = plan.name
        tokens[f"{{{{plan.{i}.plan_id}}}}"] = plan.plan_id
        tokens[f"{{{{plan.{i}.price_label}}}}"] = plan.price_label
        tokens[f"{{{{plan.{i}.description}}}}"] = plan.description
        tokens[f"{{{{plan.{i}.subscribe_url}}}}"] = plan.subscribe_url

    # Apply substitutions
    replaced_count = 0
    for token, value in tokens.items():
        if token in xml:
            xml = xml.replace(token, value)
            replaced_count += 1

    # Rebuild the zip with the updated document.xml
    tmp = output_path.with_suffix(".docx.tmp")
    with zipfile.ZipFile(output_path, "r") as src, zipfile.ZipFile(
        tmp, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for item in src.infolist():
            if item.filename == "word/document.xml":
                dst.writestr(item, xml)
            else:
                dst.writestr(item, src.read(item.filename))
    tmp.replace(output_path)


# -----------------------------------------------------------------------------
# Post-build gate 2: verify every plan URL is actually present in the DOCX
# -----------------------------------------------------------------------------

def verify_docx_has_all_urls(output_path: Path, spec: ProposalSpec) -> list[str]:
    """Extract plain text from the rendered DOCX and confirm every plan's
    subscribe URL appears. Returns a list of missing URLs (empty = pass)."""
    with zipfile.ZipFile(output_path, "r") as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    plain = re.sub(r"<[^>]+>", " ", xml)
    plain = re.sub(r"\s+", " ", plain)

    missing: list[str] = []
    for plan in spec.plans:
        if not plan.subscribe_url:
            missing.append(f"{plan.name} (subscribe_url empty in spec)")
            continue
        if plan.subscribe_url not in plain:
            missing.append(f"{plan.name}: {plan.subscribe_url}")
    return missing


# -----------------------------------------------------------------------------
# Summary emission
# -----------------------------------------------------------------------------

def emit_summary(output_path: Path, spec: ProposalSpec, bytes_written: int) -> None:
    summary = {
        "phase": "build_proposal",
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "output_path": str(output_path),
        "bytes": bytes_written,
        "client": spec.client.get("business_name", ""),
        "client_contact": spec.client.get("display_name", ""),
        "project_id": spec.metadata.get("project_id", "EOM"),
        "plans_included": len(spec.plans),
        "plan_details": [
            {
                "name": p.name,
                "plan_id": p.plan_id,
                "price_label": p.price_label,
                "subscribe_url_present": bool(p.subscribe_url),
            }
            for p in spec.plans
        ],
        "status": "ok",
    }
    print(json.dumps(summary, indent=2))


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="build_proposal",
        description="Build a client proposal DOCX with build-time payment-link verification",
    )
    parser.add_argument("--spec", required=True,
                        help="Path to proposal spec file (YAML or JSON)")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE,
                        help="Path to base DOCX template (default: %(default)s)")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG,
                        help="Path to payment plan catalog JSON (default: %(default)s)")
    parser.add_argument("--out", required=True,
                        help="Output DOCX path")
    parser.add_argument("--allow-missing-urls", action="store_true",
                        help="(DANGEROUS) Skip the build-time payment-link gate. "
                             "Use only for dry-run testing. Never ship a contract "
                             "built with this flag.")
    parser.add_argument("--skip-gate3", action="store_true",
                        help="(DANGEROUS) Skip Gate 3 — the payment_link_tests "
                             "24h-pass requirement. Use only when running from "
                             "an environment without Supabase access (local "
                             "dry-run). Never ship a contract built with this flag.")
    parser.add_argument("--gate3-window-hours", type=int, default=GATE3_WINDOW_HOURS,
                        help="Gate 3 freshness window in hours (default: %(default)s). "
                             "A URL must have a passing payment_link_tests row "
                             "tested within this window.")
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    template_path = Path(args.template).resolve()
    catalog_path = Path(args.catalog).resolve()
    output_path = Path(args.out).resolve()

    if not spec_path.is_file():
        sys.stderr.write(f"ERROR: spec not found: {spec_path}\n")
        return 4
    if not template_path.is_file():
        sys.stderr.write(f"ERROR: template not found: {template_path}\n")
        return 4
    if not catalog_path.is_file():
        sys.stderr.write(f"ERROR: catalog not found: {catalog_path}\n")
        return 4

    # Load
    spec = ProposalSpec.load(spec_path)
    spec.metadata["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if "project_id" not in spec.metadata:
        spec.metadata["project_id"] = os.environ.get("MP_PROJECT_ID", "EOM")

    catalog = load_catalog(catalog_path)
    sys.stderr.write(f"build_proposal: loaded {len(catalog)} plans from catalog\n")

    # Gate 1: resolve subscribe URLs
    missing = resolve_subscribe_urls(spec, catalog)
    if missing and not args.allow_missing_urls:
        sys.stderr.write("\n" + "=" * 64 + "\n")
        sys.stderr.write("BUILD-TIME GATE FAILED: referenced plans missing subscribe URLs\n")
        sys.stderr.write("=" * 64 + "\n")
        for m in missing:
            sys.stderr.write(f"  - {m}\n")
        sys.stderr.write("\nRefusing to build a contract that will ship without payment links.\n")
        sys.stderr.write("Fix: add the missing plan(s) to the payment catalog,\n")
        sys.stderr.write("or correct the plan_id in the spec file.\n")
        return 2
    if missing and args.allow_missing_urls:
        sys.stderr.write("WARNING: --allow-missing-urls set, proceeding despite gaps:\n")
        for m in missing:
            sys.stderr.write(f"  - {m}\n")

    sys.stderr.write(f"build_proposal: gate 1 passed ({len(spec.plans)} plans resolved)\n")

    # Gate 3: every resolved URL must have a payment_link_tests pass row
    # within the last N hours. This is the Lavar 2026-04-10 fix — an API
    # status check isn't enough; the URL must have been end-to-end
    # browser-tested against the wrong-brand class of failure.
    if not args.allow_missing_urls and not args.skip_gate3:
        gate3_failures = verify_gate3_payment_link_tests(
            spec, window_hours=args.gate3_window_hours
        )
        if gate3_failures:
            sys.stderr.write("\n" + "=" * 64 + "\n")
            sys.stderr.write(
                "BUILD-TIME GATE 3 FAILED: payment link tests missing/stale\n"
            )
            sys.stderr.write("=" * 64 + "\n")
            for f in gate3_failures:
                sys.stderr.write(f"  - {f}\n")
            sys.stderr.write(
                f"\nRefusing to build a contract whose payment URLs have not "
                f"been end-to-end browser-tested within the last "
                f"{args.gate3_window_hours}h.\n"
            )
            sys.stderr.write(
                "Fix: run scripts/test_payment_url.py for each failing URL "
                "(see commands in the failure list above), then re-run "
                "build_proposal.py.\n"
            )
            return 5
        sys.stderr.write(
            f"build_proposal: gate 3 passed "
            f"(all {len(spec.plans)} plan URLs have a passing "
            f"payment_link_tests row within {args.gate3_window_hours}h)\n"
        )
    elif args.skip_gate3:
        sys.stderr.write(
            "WARNING: --skip-gate3 set, gate 3 (payment_link_tests 24h-pass "
            "requirement) SKIPPED. Never ship a contract built with this flag.\n"
        )

    # Render
    try:
        render_docx(template_path, output_path, spec)
    except Exception as e:
        sys.stderr.write(f"ERROR: render failed: {type(e).__name__}: {e}\n")
        return 1

    bytes_written = output_path.stat().st_size
    sys.stderr.write(f"build_proposal: wrote {output_path} ({bytes_written} bytes)\n")

    # Gate 2: post-build verification
    if not args.allow_missing_urls:
        missing_in_doc = verify_docx_has_all_urls(output_path, spec)
        if missing_in_doc:
            sys.stderr.write("\n" + "=" * 64 + "\n")
            sys.stderr.write("POST-BUILD GATE FAILED: rendered DOCX missing URLs\n")
            sys.stderr.write("=" * 64 + "\n")
            for m in missing_in_doc:
                sys.stderr.write(f"  - {m}\n")
            sys.stderr.write("\nThe spec declared these URLs but they did NOT make it into\n")
            sys.stderr.write("the rendered document. Check the template for matching\n")
            sys.stderr.write("placeholder tokens ({{plan.N.subscribe_url}}).\n")
            output_path.unlink(missing_ok=True)
            return 3
        sys.stderr.write(f"build_proposal: gate 2 passed (all plan URLs present in DOCX)\n")

    # Summary
    emit_summary(output_path, spec, bytes_written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
