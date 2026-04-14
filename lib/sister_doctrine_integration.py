#!/usr/bin/env python3
"""DR-AMG-GOVERNANCE-01 Phase 3 Task 3.7 — Sister Doctrine Integration Boundaries

Responsibility Matrix:
| Domain           | Resilience    | Security           | Governance           |
|-----------------|---------------|--------------------|-----------------------|
| Agent halts      | Auto-restart  | Threat-detected    | Behavioral/rule halt  |
| Audit stream     | Consumer      | Consumer           | **Owner**             |
| Precedence       | Lowest        | **Highest**        | Middle                |

Conflict resolution: Security > Governance > Resilience
Every override crosses all three doctrines; logged with operator identity.
"""

import json
import os
import sys
from datetime import datetime, timezone

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    sys.exit("psycopg2 required")

DB_URL = os.environ.get("SUPABASE_DB_URL", "")

# Precedence: higher number = higher priority
DOCTRINE_PRECEDENCE = {
    "resilience": 1,
    "governance": 2,
    "security": 3,
}

RESPONSIBILITY_MATRIX = {
    "agent_halt": {
        "resilience": "auto_restart",
        "security": "threat_detected_halt",
        "governance": "behavioral_rule_halt",
    },
    "audit_stream": {
        "resilience": "consumer",
        "security": "consumer",
        "governance": "owner",
    },
    "credential_rotation": {
        "resilience": "n/a",
        "security": "owner",
        "governance": "auditor",
    },
    "mirror_sync": {
        "resilience": "consumer",
        "security": "consumer",
        "governance": "owner",
    },
}


def get_db():
    if not DB_URL:
        raise RuntimeError("SUPABASE_DB_URL not set")
    return psycopg2.connect(DB_URL)


def resolve_conflict(doctrine_a: str, doctrine_b: str, domain: str) -> dict:
    """Resolve a conflict between two doctrines for a given domain."""
    prec_a = DOCTRINE_PRECEDENCE.get(doctrine_a, 0)
    prec_b = DOCTRINE_PRECEDENCE.get(doctrine_b, 0)

    winner = doctrine_a if prec_a >= prec_b else doctrine_b
    rationale = f"Security > Governance > Resilience: {winner} has precedence"

    return {
        "domain": domain,
        "doctrines": [doctrine_a, doctrine_b],
        "winner": winner,
        "rationale": rationale,
        "logged_at": datetime.now(timezone.utc).isoformat()
    }


def log_cross_doctrine_override(domain: str, overriding_doctrine: str,
                                 overridden_doctrine: str, operator: str,
                                 reason: str):
    """Log a cross-doctrine override event to the governance audit stream."""
    conn = get_db()
    cur = conn.cursor()

    payload = {
        "domain": domain,
        "overriding": overriding_doctrine,
        "overridden": overridden_doctrine,
        "operator": operator,
        "reason": reason,
        "precedence_rule": "Security > Governance > Resilience"
    }

    cur.execute("""
        INSERT INTO public.governance_audit (event_type, payload)
        VALUES ('cross_doctrine_override', %s)
    """, (json.dumps(payload),))
    conn.commit()
    cur.close()
    conn.close()
    return payload


def get_responsibility(domain: str) -> dict:
    """Get responsibility assignment for a domain across all doctrines."""
    return RESPONSIBILITY_MATRIX.get(domain, {
        "resilience": "undefined",
        "security": "undefined",
        "governance": "undefined"
    })


if __name__ == "__main__":
    print("=== Sister Doctrine Integration Boundaries ===")
    print("\nPrecedence: Security > Governance > Resilience")
    print("\nResponsibility Matrix:")
    print(json.dumps(RESPONSIBILITY_MATRIX, indent=2))
    print("\nConflict test: governance vs security on agent_halt:")
    print(json.dumps(resolve_conflict("governance", "security", "agent_halt"), indent=2))
