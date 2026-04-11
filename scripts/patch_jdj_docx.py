#!/usr/bin/env python3
"""
Hot-fix for /tmp/jdj_proposal_v3.docx (Option A):
Insert the two PayPal subscribe URLs into Section 3 (Your Investment) and
update Clause 4 (Payment Terms) to reference them with real links instead
of a dead "see Section 3" pointer.

Writes the patched file to /tmp/jdj_proposal_v4.docx and leaves the
original v3 untouched for audit.
"""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

SRC = Path("/tmp/jdj_proposal_v3.docx")
DST = Path("/tmp/jdj_proposal_v4.docx")

SETUP_URL = "https://www.paypal.com/webapps/billing/plans/subscribe?plan_id=P-40456056SB832583SNHL7VCI"
GROWTH_URL = "https://www.paypal.com/webapps/billing/plans/subscribe?plan_id=P-9RY420484S5847021NHLQTKQ"


def patch_document_xml(xml: str):
    def make_paragraph(text_content: str) -> str:
        return (
            '<w:p><w:pPr><w:spacing w:before="120" w:after="120"/></w:pPr>'
            f'<w:r><w:rPr><w:b/><w:color w:val="0066CC"/><w:sz w:val="22"/></w:rPr>'
            f'<w:t xml:space="preserve">{text_content}</w:t></w:r></w:p>'
        )

    setup_insert = make_paragraph(f"→ Subscribe — Infrastructure Setup Fee ($500/mo × 3): {SETUP_URL}")
    growth_insert = make_paragraph(f"→ Subscribe — Monthly Marketing Service ($797/mo): {GROWTH_URL}")

    setup_anchor = "Total: $1,500, split into 3 easy payments."
    n_setup = 0
    if setup_anchor in xml:
        idx = xml.find(setup_anchor)
        p_end = xml.find('</w:p>', idx)
        if p_end != -1:
            xml = xml[:p_end + 6] + setup_insert + xml[p_end + 6:]
            n_setup = 1

    growth_anchor = "rate is guaranteed and will not increase."
    n_growth = 0
    if growth_anchor in xml:
        idx = xml.find(growth_anchor)
        p_end = xml.find('</w:p>', idx)
        if p_end != -1:
            xml = xml[:p_end + 6] + growth_insert + xml[p_end + 6:]
            n_growth = 1

    old_clause_4 = "Processed via the secure payment links provided in Section 3 of this proposal."
    new_clause_4 = (
        "Processed via the PayPal subscribe links in Section 3 above. "
        "Both subscriptions start Day 1: Setup Fee ($500/mo × 3) auto-expires after 3 payments, "
        "Monthly Marketing Service ($797/mo) continues until cancelled per Clause 6."
    )
    n_clause = 0
    if old_clause_4 in xml:
        xml = xml.replace(old_clause_4, new_clause_4)
        n_clause = 1

    return xml, {
        "setup_inserts": n_setup,
        "growth_inserts": n_growth,
        "clause_4_updates": n_clause,
    }


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: source not found: {SRC}", file=sys.stderr)
        return 2

    shutil.copy(SRC, DST)

    with zipfile.ZipFile(DST, "r") as zf:
        xml = zf.read("word/document.xml").decode("utf-8")

    new_xml, stats = patch_document_xml(xml)

    tmp = DST.with_suffix(".docx.tmp")
    with zipfile.ZipFile(DST, "r") as src_zip, zipfile.ZipFile(
        tmp, "w", zipfile.ZIP_DEFLATED
    ) as dst_zip:
        for item in src_zip.infolist():
            if item.filename == "word/document.xml":
                dst_zip.writestr(item, new_xml)
            else:
                dst_zip.writestr(item, src_zip.read(item.filename))
    tmp.replace(DST)

    print(f"patched: {DST}")
    print(f"  setup_inserts: {stats['setup_inserts']}")
    print(f"  growth_inserts: {stats['growth_inserts']}")
    print(f"  clause_4_updates: {stats['clause_4_updates']}")

    with zipfile.ZipFile(DST, "r") as zf:
        verify_xml = zf.read("word/document.xml").decode("utf-8")
    plain = re.sub(r'<[^>]+>', ' ', verify_xml)
    plain = re.sub(r'\s+', ' ', plain)

    setup_present = SETUP_URL in plain
    growth_present = GROWTH_URL in plain
    clause_fixed = "PayPal subscribe links in Section 3 above" in plain

    print()
    print("--- verification ---")
    print(f"  setup URL present:   {setup_present}")
    print(f"  growth URL present:  {growth_present}")
    print(f"  clause 4 fixed:      {clause_fixed}")

    ok = (stats["setup_inserts"] >= 1 and stats["growth_inserts"] >= 1
          and stats["clause_4_updates"] >= 1
          and setup_present and growth_present and clause_fixed)
    if not ok:
        print()
        print("VERIFICATION FAILED — at least one edit did not apply cleanly.")
        return 1

    print()
    print(f"v4 template verified. File: {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
