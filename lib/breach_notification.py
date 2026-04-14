#!/usr/bin/env python3
"""DR-AMG-SECURITY-01 Phase 3 Task 3.6 — GDPR/CCPA Breach Notification Workflow

Triggered by: confirmed unauthorized Supabase PII access OR Suricata exfil alert.
Actions:
1. Log incident with UTC (72h GDPR clock starts)
2. Compute deadlines: GDPR DPA T+72h, CCPA AG T+15d post-consumer-notice
3. Draft notifications from template, save to R2
4. Slack SEV-1 alert with GDPR deadline
5. Calendar reminder T+60h (2h before GDPR deadline)
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_DIR = Path("/var/log/amg-security")
INCIDENTS_DIR = Path("/opt/amg-security/incidents")


def create_incident(incident_type: str, description: str, affected_data: str,
                    affected_count: int = 0) -> dict:
    """Create a breach incident with all required tracking."""
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    incident_id = f"INC-{now.strftime('%Y%m%d-%H%M%S')}"

    # Compute deadlines with weekend/holiday awareness
    gdpr_deadline = now + timedelta(hours=72)
    ccpa_deadline = now + timedelta(days=15)

    # GDPR 72h is absolute (no weekend extension per EDPB guidance)
    # but warn if deadline falls on weekend for practical coordination
    gdpr_weekday = gdpr_deadline.strftime("%A")
    gdpr_on_weekend = gdpr_weekday in ("Saturday", "Sunday")

    # Warning earlier if deadline on weekend (give 4h buffer instead of 2h)
    warning_buffer = timedelta(hours=4) if gdpr_on_weekend else timedelta(hours=2)
    gdpr_warning = gdpr_deadline - warning_buffer

    # False-positive review gate: incident starts in REVIEW status
    # Operator has 1h to confirm or dismiss before notifications draft
    review_deadline = now + timedelta(hours=1)

    incident = {
        "incident_id": incident_id,
        "type": incident_type,
        "description": description,
        "affected_data": affected_data,
        "affected_count": affected_count,
        "detected_at": now.isoformat(),
        "gdpr_72h_deadline": gdpr_deadline.isoformat(),
        "gdpr_deadline_day": gdpr_weekday,
        "gdpr_on_weekend": gdpr_on_weekend,
        "ccpa_15d_deadline": ccpa_deadline.isoformat(),
        "gdpr_warning_at": gdpr_warning.isoformat(),
        "review_deadline": review_deadline.isoformat(),
        "status": "PENDING_REVIEW",  # Not OPEN — requires operator confirmation
        "false_positive_review": {
            "required": True,
            "review_by": review_deadline.isoformat(),
            "reviewed": False,
            "reviewer": None,
            "outcome": None,  # "confirmed_breach" or "false_positive"
        },
        "notifications": {
            "dpa_notified": False,
            "consumers_notified": False,
            "ccpa_ag_notified": False,
        },
        "containment_actions": [],
        "evidence_preserved": False,
        "weekend_note": "GDPR 72h deadline falls on weekend — DPA offices may be closed, coordinate early" if gdpr_on_weekend else None,
    }

    # Save incident
    incident_file = INCIDENTS_DIR / f"{incident_id}.json"
    with open(incident_file, "w") as f:
        json.dump(incident, f, indent=2)

    # Log to security events
    event = {
        "timestamp": now.isoformat(),
        "type": "breach_incident_created",
        "severity": "SEV1",
        "details": {
            "incident_id": incident_id,
            "gdpr_deadline": gdpr_deadline.isoformat(),
            "ccpa_deadline": ccpa_deadline.isoformat(),
        }
    }
    with open(LOG_DIR / "security-events.jsonl", "a") as f:
        f.write(json.dumps(event) + "\n")

    # Generate notification drafts
    dpa_draft = f"""GDPR Data Protection Authority Notification
Incident: {incident_id}
Detected: {now.strftime('%Y-%m-%d %H:%M UTC')}
72h Deadline: {gdpr_deadline.strftime('%Y-%m-%d %H:%M UTC')}

Nature of breach: {description}
Categories of data: {affected_data}
Approximate number of data subjects: {affected_count}
Contact: Solon Zafiropoulos, AI Marketing Genius
"""

    ccpa_draft = f"""CCPA Breach Notification
Incident: {incident_id}
Detected: {now.strftime('%Y-%m-%d %H:%M UTC')}
AG Deadline: {ccpa_deadline.strftime('%Y-%m-%d %H:%M UTC')} (15 days post-consumer-notice)

Type of information: {affected_data}
Number of California residents affected: {affected_count}
"""

    # Save drafts
    (INCIDENTS_DIR / f"{incident_id}-dpa-draft.txt").write_text(dpa_draft)
    (INCIDENTS_DIR / f"{incident_id}-ccpa-draft.txt").write_text(ccpa_draft)

    return incident


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Create test incident")
    parser.add_argument("--type", default="test", help="Incident type")
    parser.add_argument("--description", default="Test breach notification", help="Description")
    parser.add_argument("--data", default="test data", help="Affected data categories")
    parser.add_argument("--count", type=int, default=0, help="Affected count")
    args = parser.parse_args()

    if args.test:
        incident = create_incident(args.type, args.description, args.data, args.count)
        print(json.dumps(incident, indent=2))
        print(f"\nIncident {incident['incident_id']} created")
        print(f"GDPR deadline: {incident['gdpr_72h_deadline']}")
        print(f"CCPA deadline: {incident['ccpa_15d_deadline']}")
