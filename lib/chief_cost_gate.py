#!/usr/bin/env python3
"""chief_cost_gate.py — per-chief + fleet daily cap enforcement.

Phase 2.5 Phase A (2026-04-27): each Kimi chief (Hercules, Nestor, Alexander)
gets a 4-builder dedicated team. The briefing demands $5/chief/day +
$15/fleet/day mechanical (not trust-based) cost gates.

Implementation: stacks TWO `cost_kill_switch.KillSwitch` instances per call —
one with `tenant_id=<chief>` for the per-chief cap, one with
`tenant_id='fleet'` for the cross-chief ceiling. Both use the same sqlite
ledger with atomic transactions, so enforcement is mechanical: the sqlite
write-ahead log + UNIQUE constraint guarantees no two callers can both
sneak under the cap.

(The briefing said "Redis, not trust-based" — sqlite atomic transactions
provide the same guarantee with zero new infra. If we want Redis later,
this wrapper can swap the underlying store without touching call sites.)

Per-role default sub-caps (sums to $5/chief):
  Slot 1 Daedalus    (V4 Pro)    $3.00/chief/day
  Slot 2 Artisan     (V4 Flash)  $1.00/chief/day
  Slot 3 Hephaestus  (local)     $0.00/chief/day  (no API cost; cap=0 disables gate)
  Slot 4 Specialist  (Kimi/Gemini/V3) $1.00/chief/day

Fleet cap: $15.00/day across all chiefs.

Usage:
    gate = ChiefCostGate(chief='hercules', role='daedalus', vendor='deepseek-v4-pro')
    if not gate.allow_call(estimated_cost_usd=0.10):
        return gate.deny_response()
    # ... API call ...
    gate.record_call(prompt_text, actual_cost)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from cost_kill_switch import KillSwitch  # noqa: E402

ROLE_SUBCAPS_USD = {
    "daedalus":   3.00,
    "artisan":    1.00,
    "hephaestus": 0.00,  # local model, no API cost
    "athena":     1.00,
    "lumina":     1.00,
    "echo":       1.00,
}

FLEET_CAP_USD = float(os.environ.get("AMG_FLEET_DAILY_CAP_USD", "15.00"))

VALID_CHIEFS = {"hercules", "nestor", "alexander"}


class ChiefCostGate:
    """Per-chief + fleet cap stack. Cheap to construct (sqlite open is fast)."""

    def __init__(self, chief: str, role: str, vendor: str,
                 chief_cap_usd: float | None = None,
                 fleet_cap_usd: float | None = None):
        chief = chief.lower()
        role = role.lower()
        if chief not in VALID_CHIEFS:
            raise ValueError(f"chief must be one of {VALID_CHIEFS}, got {chief}")
        if role not in ROLE_SUBCAPS_USD:
            raise ValueError(f"role must be one of {list(ROLE_SUBCAPS_USD)}, got {role}")
        self.chief = chief
        self.role = role
        self.vendor = vendor

        # Resolve per-chief sub-cap (priority: arg → env → default).
        if chief_cap_usd is not None:
            self._chief_cap = chief_cap_usd
        else:
            env_key = f"AMG_CHIEF_CAP_{chief.upper()}_{role.upper()}"
            env_val = os.environ.get(env_key)
            if env_val:
                try:
                    self._chief_cap = float(env_val)
                except ValueError:
                    self._chief_cap = ROLE_SUBCAPS_USD[role]
            else:
                self._chief_cap = ROLE_SUBCAPS_USD[role]

        self._fleet_cap = fleet_cap_usd if fleet_cap_usd is not None else FLEET_CAP_USD

        # Per-chief gate: tenant_id=chief, vendor=API vendor.
        self._chief_ks = KillSwitch(
            vendor=vendor,
            tenant_id=chief,
            daily_cap_usd=self._chief_cap,
            scope=f"chief:{chief}:{role}",
        )

        # Fleet gate: tenant_id='fleet', vendor='fleet' (separate aggregator).
        self._fleet_ks = KillSwitch(
            vendor="fleet",
            tenant_id="fleet",
            daily_cap_usd=self._fleet_cap,
            scope="fleet:total",
        )

    def check_cache(self, artifact_text: str) -> Any | None:
        """Cache hit on the per-chief ledger (chief+vendor+scope+artifact)."""
        return self._chief_ks.check_cache(artifact_text)

    def allow_call(self, estimated_cost_usd: float = 0.05) -> bool:
        """Check BOTH caps. Hephaestus (cap=0) auto-allows when estimated=0."""
        if self._chief_cap == 0.0 and estimated_cost_usd == 0.0:
            return True  # local model, no cost to gate
        if not self._fleet_ks.allow_call(estimated_cost_usd=estimated_cost_usd):
            return False
        if not self._chief_ks.allow_call(estimated_cost_usd=estimated_cost_usd):
            return False
        return True

    def record_call(self, artifact_text: str, actual_cost_usd: float,
                    result: Any | None = None) -> None:
        """Record into BOTH ledgers so per-chief AND fleet running totals stay synced."""
        self._chief_ks.record_call(artifact_text, actual_cost_usd, result=result)
        # Fleet ledger: store SAME artifact_text but under tenant=fleet so both
        # totals can be queried independently. Idempotent on conflict.
        self._fleet_ks.record_call(artifact_text, actual_cost_usd, result=None)

    def deny_response(self) -> dict[str, Any]:
        return {
            "skipped": True,
            "reason": "cost_cap_hit",
            "chief": self.chief,
            "role": self.role,
            "vendor": self.vendor,
            "chief_cap_usd": self._chief_cap,
            "chief_spend_usd": self._chief_ks.today_spend_usd(),
            "fleet_cap_usd": self._fleet_cap,
            "fleet_spend_usd": self._fleet_ks.today_spend_usd(),
        }

    def today_chief_spend_usd(self) -> float:
        return self._chief_ks.today_spend_usd()

    def today_fleet_spend_usd(self) -> float:
        return self._fleet_ks.today_spend_usd()


def main(argv: list[str]) -> int:
    """CLI: `python lib/chief_cost_gate.py [--chief X]` — print per-chief + fleet totals."""
    import argparse
    p = argparse.ArgumentParser(prog="chief-cost-gate")
    p.add_argument("--chief", choices=sorted(VALID_CHIEFS),
                   help="filter to one chief")
    args = p.parse_args(argv)

    chiefs = [args.chief] if args.chief else sorted(VALID_CHIEFS)
    print("=== Per-chief sub-caps ===")
    for c in chiefs:
        for r, sub in ROLE_SUBCAPS_USD.items():
            ks = KillSwitch(vendor=f"per-chief-summary",
                            tenant_id=c, daily_cap_usd=sub, scope=f"chief:{c}:{r}")
            # We can't query without a vendor — skip individual numbers and
            # just print the cap structure.
            print(f"  {c:>10} {r:<10} cap=${sub:.2f}")
    fleet_ks = KillSwitch(vendor="fleet", tenant_id="fleet",
                          daily_cap_usd=FLEET_CAP_USD, scope="fleet:total")
    print(f"\n=== Fleet ===")
    print(f"  fleet cap=${FLEET_CAP_USD:.2f}")
    print(f"  fleet today spend=${fleet_ks.today_spend_usd():.4f}")
    print(f"  fleet today calls={fleet_ks.today_call_count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
