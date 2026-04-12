"""
lib/batch_guard.py
Ironclad architecture §4.3 — safe batching rules for a solo operator.

Called by lib/llm_batch.py before every batch dispatch. Escalates via
bin/harness-incident.sh if a batch exceeds the safety rails.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


BATCH_GUARD_RULES = {
    "max_spend_per_batch_run_usd": 5.0,
    "require_dry_run_above_n_items": 30,
    "escalate_on_dlq_rate": 0.20,
}


def _estimate_cost(items: list, task_type: str) -> float:
    """
    Cheap heuristic: assume ~1.5k input tokens + 500 output per item at
    Haiku-class pricing ($0.25/1M in, $1.25/1M out). Real numbers come from
    model_router.price_per_call in production.
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import model_router  # type: ignore
        if hasattr(model_router, "estimate_batch_cost"):
            return model_router.estimate_batch_cost(items, task_type)
    except Exception:
        pass
    n = len(items)
    in_tok = n * 1500
    out_tok = n * 500
    return in_tok / 1_000_000 * 0.25 + out_tok / 1_000_000 * 1.25


def pre_batch_check(items: list, task_type: str, *, dry_run: bool = False) -> tuple[bool, str]:
    n = len(items)
    if n == 0:
        return True, "empty batch"
    if n > BATCH_GUARD_RULES["require_dry_run_above_n_items"] and not dry_run:
        return False, (
            f"batch of {n} items exceeds dry_run threshold "
            f"({BATCH_GUARD_RULES['require_dry_run_above_n_items']}); "
            "re-run with dry_run=True for an estimate"
        )
    cost = _estimate_cost(items, task_type)
    if cost > BATCH_GUARD_RULES["max_spend_per_batch_run_usd"]:
        _incident(
            "BATCH_COST_CEILING",
            f"Estimated batch cost ${cost:.2f} exceeds ${BATCH_GUARD_RULES['max_spend_per_batch_run_usd']:.2f}",
            "HIGH",
        )
        return False, f"estimated cost ${cost:.2f} exceeds ceiling"
    return True, f"ok (n={n}, est_cost=${cost:.2f})"


def post_batch_check(dlq_count: int, total: int) -> tuple[bool, str]:
    if total == 0:
        return True, "empty batch"
    rate = dlq_count / total
    if rate > BATCH_GUARD_RULES["escalate_on_dlq_rate"]:
        _incident(
            "BATCH_DLQ_HIGH",
            f"DLQ rate {rate:.1%} ({dlq_count}/{total}) exceeds "
            f"{BATCH_GUARD_RULES['escalate_on_dlq_rate']:.0%} threshold",
            "HIGH",
        )
        return False, f"dlq rate {rate:.1%}"
    return True, f"dlq rate {rate:.1%}"


def _incident(type_: str, msg: str, sev: str = "HIGH") -> None:
    harness = os.environ.get("TITAN_HARNESS_DIR", os.path.expanduser("~/titan-harness"))
    script = Path(harness) / "bin" / "harness-incident.sh"
    if script.exists():
        subprocess.run(["bash", str(script), type_, msg, sev], check=False)
