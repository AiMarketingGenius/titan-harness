"""Shared library for watchdog v0.1 (CT-0427-57). Signal collection + receipt
emission + MCP post helpers. No side effects on import."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request

CONFIG_PATH = os.environ.get("WATCHDOG_CONFIG", "/opt/amg-titan/scripts/watchdog/config.json")
RECEIPT_DIR = os.environ.get("WATCHDOG_RECEIPT_DIR", "/var/lib/amg-watchdog/receipts")
HEARTBEAT_PATH = os.environ.get("WATCHDOG_HEARTBEAT", "/var/lib/amg-watchdog/heartbeat.txt")
LOG_PATH = os.environ.get("WATCHDOG_LOG", "/var/log/amg-watchdog.log")
MCP_BASE = os.environ.get("MCP_BASE", "http://localhost:3000")


def log(msg: str, mode: str = "main") -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"[{ts}] [watchdog/{mode}] {msg}\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line)
    except OSError:
        pass


def load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CONFIG


DEFAULT_CONFIG = {
    "thresholds": {
        "disk_used_pct": {"warn": 80, "action": 85, "critical": 92},
        "free_gib":       {"warn": 25, "action": 15, "critical": 8},
        "inode_used_pct": {"warn": 80, "action": 85, "critical": 92},
        "ram_used_pct":   {"warn": 85, "action": 90, "critical": 95},
        "swap_used_pct":  {"warn": 50, "action": 75, "critical": 90},
    },
    "protected_paths": [
        "/home/amg/kb",
        "/etc",
        "/usr/share/ollama/.ollama/models",
        "/var/lib/postgresql",
        "/var/lib/redis",
    ],
    "safe_remediation": {
        "journal_vacuum_size": "200M",
        "playwright_cache_path": "/root/.cache/ms-playwright",
        "trivy_cache_path": "/root/.cache/trivy",
        "rotated_log_retention_days": 14,
        "docker_dangling_prune_enabled": True,
    },
    "required_services": [
        "wazuh-manager",
        "ollama",
        "docker",
    ],
}


# ---- Signal collection -----------------------------------------------------
def disk_signals() -> dict:
    """root filesystem stats."""
    s = shutil.disk_usage("/")
    used_pct = round((s.used / s.total) * 100, 2)
    free_gib = round(s.free / (1024**3), 2)
    return {"disk_used_pct": used_pct, "free_gib": free_gib, "total_gib": round(s.total / (1024**3), 2)}


def inode_signals() -> dict:
    """root inode usage from `df -i`."""
    try:
        out = subprocess.run(["df", "-i", "/"], capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return {"inode_used_pct": -1}
        line = out.stdout.strip().splitlines()[-1]
        parts = line.split()
        # Filesystem Inodes IUsed IFree IUse% Mounted
        pct = parts[4].rstrip("%")
        return {"inode_used_pct": float(pct)}
    except (subprocess.SubprocessError, ValueError, IndexError):
        return {"inode_used_pct": -1}


def memory_signals() -> dict:
    """RAM + swap stats from /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            mi = {}
            for line in f:
                k, v = line.split(":", 1)
                mi[k.strip()] = int(v.strip().split()[0])  # kB
        total = mi.get("MemTotal", 0)
        avail = mi.get("MemAvailable", mi.get("MemFree", 0))
        used = total - avail
        ram_pct = round((used / total) * 100, 2) if total else 0.0
        swap_total = mi.get("SwapTotal", 0)
        swap_free = mi.get("SwapFree", 0)
        swap_used = swap_total - swap_free
        swap_pct = round((swap_used / swap_total) * 100, 2) if swap_total else 0.0
        return {"ram_used_pct": ram_pct, "swap_used_pct": swap_pct}
    except OSError:
        return {"ram_used_pct": -1, "swap_used_pct": -1}


def heartbeat_signal() -> dict:
    """Read last-heartbeat ts; -1 if missing or stale."""
    if not os.path.exists(HEARTBEAT_PATH):
        return {"heartbeat_age_sec": -1}
    try:
        mt = os.path.getmtime(HEARTBEAT_PATH)
        age = int(time.time() - mt)
        return {"heartbeat_age_sec": age}
    except OSError:
        return {"heartbeat_age_sec": -1}


def write_heartbeat() -> None:
    os.makedirs(os.path.dirname(HEARTBEAT_PATH), exist_ok=True)
    with open(HEARTBEAT_PATH, "w") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ\n", time.gmtime()))


def collect_fast_signals() -> dict:
    sig = {}
    sig.update(disk_signals())
    sig.update(memory_signals())
    sig.update(heartbeat_signal())
    return sig


def collect_slow_signals() -> dict:
    sig = collect_fast_signals()
    sig.update(inode_signals())
    return sig


# ---- Threshold evaluation --------------------------------------------------
def evaluate_threshold(metric: str, value: float, cfg: dict) -> str:
    """Returns 'ok' | 'warn' | 'action' | 'critical'."""
    th = cfg.get("thresholds", {}).get(metric)
    if th is None or value < 0:
        return "ok"
    # free_gib is reverse: lower is worse
    if metric == "free_gib":
        if value <= th["critical"]:
            return "critical"
        if value <= th["action"]:
            return "action"
        if value <= th["warn"]:
            return "warn"
        return "ok"
    # standard: higher is worse
    if value >= th["critical"]:
        return "critical"
    if value >= th["action"]:
        return "action"
    if value >= th["warn"]:
        return "warn"
    return "ok"


def overall_status(signals: dict, cfg: dict) -> tuple[str, list[str]]:
    """Worst threshold across all signals."""
    rank = {"ok": 0, "warn": 1, "action": 2, "critical": 3}
    worst = "ok"
    breached = []
    for metric, value in signals.items():
        if metric not in cfg.get("thresholds", {}):
            continue
        s = evaluate_threshold(metric, value, cfg)
        if s != "ok":
            breached.append(f"{metric}={value}:{s}")
            if rank[s] > rank[worst]:
                worst = s
    return worst, breached


# ---- Safe remediation ------------------------------------------------------
def safe_journal_vacuum(size: str) -> dict:
    try:
        before = subprocess.run(["journalctl", "--disk-usage"], capture_output=True, text=True, timeout=10)
        before_bytes = parse_size_str(before.stdout)
        r = subprocess.run(["journalctl", f"--vacuum-size={size}"], capture_output=True, text=True, timeout=60)
        after = subprocess.run(["journalctl", "--disk-usage"], capture_output=True, text=True, timeout=10)
        after_bytes = parse_size_str(after.stdout)
        return {
            "name": "journal_vacuum",
            "bytes_reclaimed": max(0, before_bytes - after_bytes),
            "status": "applied" if r.returncode == 0 else "failed",
            "rc": r.returncode,
        }
    except (subprocess.SubprocessError, OSError) as e:
        return {"name": "journal_vacuum", "bytes_reclaimed": 0, "status": "failed", "error": str(e)}


def parse_size_str(s: str) -> int:
    """Best-effort parse of strings like 'Archived and active journals take up 472.0M' → bytes."""
    import re
    m = re.search(r"(\d+(?:\.\d+)?)\s*([KMGT])", s)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2).upper()
    mult = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}.get(unit, 1)
    return int(val * mult)


def safe_cache_wipe(path: str, max_age_days: int = 0) -> dict:
    """Wipe a tool cache. v0.1 always wipes (not age-based) since these are
    repopulating tool caches, not user data. Path must be in safe list."""
    if not path.startswith("/root/.cache/"):
        return {"name": f"cache_wipe:{path}", "bytes_reclaimed": 0, "status": "rejected", "reason": "not /root/.cache"}
    if not os.path.exists(path):
        return {"name": f"cache_wipe:{os.path.basename(path)}", "bytes_reclaimed": 0, "status": "skipped"}
    try:
        before = dir_size_bytes(path)
        shutil.rmtree(path, ignore_errors=True)
        after = dir_size_bytes(path) if os.path.exists(path) else 0
        return {
            "name": f"cache_wipe:{os.path.basename(path)}",
            "bytes_reclaimed": max(0, before - after),
            "status": "applied",
        }
    except OSError as e:
        return {"name": f"cache_wipe:{path}", "bytes_reclaimed": 0, "status": "failed", "error": str(e)}


def dir_size_bytes(path: str) -> int:
    total = 0
    try:
        for root, _, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    except OSError:
        return 0
    return total


def safe_docker_dangling_prune() -> dict:
    try:
        r = subprocess.run(
            ["docker", "image", "prune", "--force"],
            capture_output=True, text=True, timeout=120,
        )
        # Parse "Total reclaimed space: 6.63GB" from output
        bytes_reclaimed = 0
        for line in (r.stdout + r.stderr).splitlines():
            if "Total reclaimed space" in line:
                bytes_reclaimed = parse_size_str(line)
        return {
            "name": "docker_dangling_prune",
            "bytes_reclaimed": bytes_reclaimed,
            "status": "applied" if r.returncode == 0 else "failed",
        }
    except (subprocess.SubprocessError, OSError) as e:
        return {"name": "docker_dangling_prune", "bytes_reclaimed": 0, "status": "failed", "error": str(e)}


# ---- Owner-risk surface ----------------------------------------------------
def top_disk_consumers(n: int = 20) -> list[dict]:
    """Top-N largest dirs from common roots, returning ones >= 100MB."""
    candidates = []
    for root in ["/var/lib/docker", "/usr/share/ollama/.ollama/models", "/home/amg/kb",
                 "/var/log", "/var/ossec", "/root/.cache", "/root/.local", "/opt",
                 "/var/lib/snapd"]:
        if not os.path.exists(root):
            continue
        try:
            sz = dir_size_bytes(root)
            if sz >= 100 * 1024 * 1024:
                candidates.append({"path": root, "bytes_est": sz})
        except OSError:
            continue
    candidates.sort(key=lambda x: -x["bytes_est"])
    return candidates[:n]


def owner_risk_classify(consumers: list[dict]) -> list[dict]:
    """Annotate each candidate with owner_risk reason."""
    risk_map = {
        "/usr/share/ollama/.ollama/models": "model deletion requires owner approval per spec §7",
        "/home/amg/kb": "KB binary deletion requires owner approval per spec §7",
        "/var/lib/docker": "non-dangling Docker prune requires owner approval per spec §6",
        "/var/lib/postgresql": "live database storage protected per spec §7",
        "/var/lib/redis": "live database storage protected per spec §7",
    }
    out = []
    for c in consumers:
        reason = risk_map.get(c["path"], "manual review recommended (>100MB target)")
        out.append({**c, "reason": reason})
    return out


# ---- Receipt + MCP post ----------------------------------------------------
def write_receipt(receipt: dict) -> str:
    os.makedirs(RECEIPT_DIR, exist_ok=True)
    fname = f"{receipt['mode']}_{int(time.time())}.json"
    path = os.path.join(RECEIPT_DIR, fname)
    with open(path, "w") as f:
        json.dump(receipt, f, indent=2)
    # Keep a "latest" symlink for verify
    latest = os.path.join(RECEIPT_DIR, f"latest_{receipt['mode']}.json")
    try:
        if os.path.exists(latest) or os.path.islink(latest):
            os.unlink(latest)
        os.symlink(path, latest)
    except OSError:
        pass
    return path


def mcp_post(path: str, payload: dict) -> tuple[bool, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{MCP_BASE}{path}", data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode()
            return True, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return False, {"error": f"HTTP {e.code}", "body": e.read()[:200].decode(errors='replace')}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return False, {"error": str(e)}


def log_decision(text: str, tags: list, rationale: str = "") -> None:
    mcp_post("/api/decisions", {
        "text": text,
        "project_source": "achilles",
        "rationale": rationale,
        "tags": tags,
    })


def flag_blocker(text: str, severity: str = "high") -> None:
    """No /api/flag-blocker REST shortcut exists; tag a high-priority decision."""
    log_decision(
        text=f"BLOCKER ({severity}): {text}",
        tags=["watchdog-blocker", severity, "ct-0427-57"],
        rationale="Watchdog escalated to blocker via decision log (no flag-blocker REST shortcut).",
    )
