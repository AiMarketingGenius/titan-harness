"""
titan-harness/lib/capacity.py - Phase P1

Tiny Python shim around bin/check-capacity.sh so every Python caller
can gate itself on the CORE CONTRACT capacity policy without duplicating
the shell logic.
"""
import os
import subprocess
from typing import Literal

_SCRIPT = os.environ.get(
    "TITAN_CHECK_CAPACITY_PATH",
    "/opt/titan-harness/bin/check-capacity.sh",
)

CapacityStatus = Literal["ok", "soft_block", "hard_block"]


def check_capacity(timeout: float = 5.0) -> int:
    """Run check-capacity.sh and return the raw exit code.

    Returns:
        0  ok
        1  soft block
        2  hard block
    """
    try:
        r = subprocess.run([_SCRIPT], capture_output=True, timeout=timeout)
        return r.returncode
    except FileNotFoundError:
        return 0  # fail-open: never wedge on guard unavailability
    except subprocess.TimeoutExpired:
        return 0
    except Exception:
        return 0


def capacity_status(timeout: float = 5.0) -> CapacityStatus:
    rc = check_capacity(timeout=timeout)
    if rc == 2:
        return "hard_block"
    if rc == 1:
        return "soft_block"
    return "ok"


def require_capacity(max_severity: CapacityStatus = "soft_block") -> None:
    """Raise if capacity is worse than max_severity.

    max_severity='soft_block' means raise on hard_block only.
    max_severity='ok' means raise on any block (soft or hard).
    """
    s = capacity_status()
    if s == "hard_block":
        raise RuntimeError(f"capacity HARD block - {_SCRIPT} exit 2")
    if s == "soft_block" and max_severity == "ok":
        raise RuntimeError(f"capacity SOFT block - {_SCRIPT} exit 1")
