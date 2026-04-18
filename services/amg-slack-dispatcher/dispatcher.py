#!/usr/bin/env python3
"""
AMG Slack Dispatcher — P0-P3 severity router with dedup, rate-limit, maintenance-gate, cost kill-switch.

Listens on 127.0.0.1:9876/dispatch. Sources call this instead of posting to Slack directly.

CONTRACT (POST /dispatch):
  {
    "severity": "P0|P1|P2|P3",
    "source":   "<name>",
    "message":  "<text>",
    "fingerprint": "<optional; defaults to sha256(source:message)[:16]>",
    "extra":    {...}  // optional
  }

Behavior matrix (per CLAUDE.md §standing-rule SLACK COST CONTROL DOCTRINE 2026-04-18T19:23Z):
  P3                        -> SQLite log only (no push)
  P2                        -> Ntfy only
  P1 (dup in 10-min window) -> dedup counter bump, no emit
  P1 (rate-limited)         -> Ntfy fallback
  P1 (ok)                   -> Slack
  P0 (dup in 10-min window) -> dedup counter bump, no emit
  P0 (ok)                   -> Slack + Ntfy urgent
  maintenance-mode-active   -> P1/P2 suppressed, P0 still fires
  kill-switch-active        -> ALL downgraded to Ntfy

Admin endpoints (GET):
  /health
  /admin/stats
  /admin/set-kill-switch
  /admin/reset-kill-switch
  /admin/set-maintenance
  /admin/reset-maintenance
"""

import hashlib
import http.server
import json
import logging
import os
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DB_PATH = os.environ.get("SLACK_DISPATCHER_DB", "/var/lib/amg-slack-dispatcher/state.sqlite")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "amg-ops")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
SLACK_DAILY_CAP = int(os.environ.get("SLACK_DAILY_CAP", "50"))
SLACK_PER_SOURCE_CAP = int(os.environ.get("SLACK_PER_SOURCE_CAP", "10"))
SLACK_MONTHLY_CAP = int(os.environ.get("SLACK_MONTHLY_CAP", "500"))
DEDUP_WINDOW_SEC = int(os.environ.get("DEDUP_WINDOW_SEC", "600"))
MCP_TAG_CHECK_INTERVAL = int(os.environ.get("MCP_TAG_CHECK_INTERVAL", "60"))
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
PORT = int(os.environ.get("SLACK_DISPATCHER_PORT", "9876"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS dispatch_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  severity TEXT NOT NULL,
  source TEXT NOT NULL,
  fingerprint TEXT,
  message TEXT NOT NULL,
  decision TEXT NOT NULL,
  extra_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_dispatch_log_ts ON dispatch_log(ts);
CREATE INDEX IF NOT EXISTS idx_dispatch_log_fp ON dispatch_log(fingerprint);

CREATE TABLE IF NOT EXISTS dedup (
  fingerprint TEXT PRIMARY KEY,
  first_seen REAL NOT NULL,
  last_seen REAL NOT NULL,
  count INTEGER NOT NULL DEFAULT 1,
  suppressed INTEGER NOT NULL DEFAULT 0,
  last_decision TEXT
);

CREATE TABLE IF NOT EXISTS counters (
  key TEXT PRIMARY KEY,
  value INTEGER NOT NULL DEFAULT 0,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS kill_switch (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  active INTEGER NOT NULL DEFAULT 0,
  reason TEXT,
  activated_at REAL
);
INSERT OR IGNORE INTO kill_switch (id, active) VALUES (1, 0);

CREATE TABLE IF NOT EXISTS maintenance (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  active INTEGER NOT NULL DEFAULT 0,
  reason TEXT,
  activated_at REAL
);
INSERT OR IGNORE INTO maintenance (id, active) VALUES (1, 0);
"""

_maintenance_mcp = False
_maintenance_lock = threading.Lock()


def db_conn():
    conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_dirs_and_schema():
    d = os.path.dirname(DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    with db_conn() as c:
        c.executescript(SCHEMA)


def today_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def month_key():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def increment_counter(key):
    with db_conn() as c:
        c.execute(
            """INSERT INTO counters (key, value, updated_at) VALUES (?, 1, ?)
               ON CONFLICT(key) DO UPDATE SET value = value + 1, updated_at = excluded.updated_at""",
            (key, time.time()),
        )


def get_counter(key):
    with db_conn() as c:
        row = c.execute("SELECT value FROM counters WHERE key=?", (key,)).fetchone()
        return row["value"] if row else 0


def set_counter(key, value):
    with db_conn() as c:
        c.execute(
            """INSERT INTO counters (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, value, time.time()),
        )


def kill_switch_active():
    with db_conn() as c:
        row = c.execute("SELECT active FROM kill_switch WHERE id=1").fetchone()
        return bool(row["active"]) if row else False


def set_kill_switch(active, reason=None):
    with db_conn() as c:
        c.execute(
            "UPDATE kill_switch SET active=?, reason=?, activated_at=? WHERE id=1",
            (1 if active else 0, reason, time.time() if active else None),
        )


def local_maintenance_active():
    with db_conn() as c:
        row = c.execute("SELECT active FROM maintenance WHERE id=1").fetchone()
        return bool(row["active"]) if row else False


def set_local_maintenance(active, reason=None):
    with db_conn() as c:
        c.execute(
            "UPDATE maintenance SET active=?, reason=?, activated_at=? WHERE id=1",
            (1 if active else 0, reason, time.time() if active else None),
        )


def is_maintenance_active():
    with _maintenance_lock:
        if _maintenance_mcp:
            return True
    return local_maintenance_active()


def dedup_check_and_bump(fingerprint):
    """Returns (is_dup_within_window, total_count, suppressed_count)."""
    if not fingerprint:
        return (False, 1, 0)
    now = time.time()
    with db_conn() as c:
        row = c.execute("SELECT * FROM dedup WHERE fingerprint=?", (fingerprint,)).fetchone()
        if row:
            last_seen = row["last_seen"]
            if now - last_seen < DEDUP_WINDOW_SEC:
                c.execute(
                    "UPDATE dedup SET last_seen=?, count=count+1, suppressed=suppressed+1 WHERE fingerprint=?",
                    (now, fingerprint),
                )
                return (True, row["count"] + 1, row["suppressed"] + 1)
            c.execute(
                "UPDATE dedup SET last_seen=?, count=count+1, suppressed=0 WHERE fingerprint=?",
                (now, fingerprint),
            )
            return (False, row["count"] + 1, 0)
        c.execute(
            "INSERT INTO dedup (fingerprint, first_seen, last_seen, count, suppressed) VALUES (?, ?, ?, 1, 0)",
            (fingerprint, now, now),
        )
        return (False, 1, 0)


def log_dispatch(severity, source, fingerprint, message, decision, extra=None):
    with db_conn() as c:
        c.execute(
            """INSERT INTO dispatch_log (ts, severity, source, fingerprint, message, decision, extra_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), severity, source, fingerprint, message, decision, json.dumps(extra or {})),
        )


def check_mcp_maintenance_tag():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    since_iso = datetime.fromtimestamp(time.time() - 86400, tz=timezone.utc).isoformat()
    url = (
        f"{SUPABASE_URL}/rest/v1/op_decisions"
        f"?select=created_at,tags,text"
        f"&or=(tags.cs.{{maintenance-mode-active}},tags.cs.{{maintenance-mode-clear}})"
        f"&order=created_at.desc&limit=5"
        f"&created_at=gte.{urllib.parse.quote(since_iso)}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            rows = json.load(resp)
        for row in rows:
            tags = row.get("tags") or []
            if "maintenance-mode-clear" in tags:
                return False
            if "maintenance-mode-active" in tags:
                return True
    except Exception as e:
        logging.error(f"mcp tag check failed: {e}")
    return False


def maintenance_mode_checker():
    global _maintenance_mcp
    while True:
        try:
            active = check_mcp_maintenance_tag()
            with _maintenance_lock:
                _maintenance_mcp = active
        except Exception as e:
            logging.error(f"maintenance-check thread error: {e}")
        time.sleep(MCP_TAG_CHECK_INTERVAL)


def send_slack(text):
    if not SLACK_WEBHOOK:
        return (False, "no-webhook-configured")
    try:
        payload = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            SLACK_WEBHOOK, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return (resp.status < 300, f"http-{resp.status}")
    except Exception as e:
        return (False, str(e))


def send_ntfy(text, title=None, priority="default"):
    try:
        headers = {"Priority": priority}
        if title:
            headers["Title"] = title
        req = urllib.request.Request(NTFY_URL, data=text.encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return (resp.status < 300, f"http-{resp.status}")
    except Exception as e:
        return (False, str(e))


def check_cost_caps_and_maybe_activate_kill_switch():
    daily = get_counter(f"slack_global_{today_key()}")
    monthly = get_counter(f"slack_global_month_{month_key()}")
    if daily >= SLACK_DAILY_CAP or monthly >= SLACK_MONTHLY_CAP:
        reason = f"cap-breach daily={daily}/{SLACK_DAILY_CAP} monthly={monthly}/{SLACK_MONTHLY_CAP}"
        set_kill_switch(True, reason)
        send_ntfy(
            f"SLACK KILL-SWITCH ACTIVATED: {reason}",
            title="slack-kill-switch",
            priority="urgent",
        )
        return True
    return False


def dispatch(payload):
    severity = str(payload.get("severity", "P2")).upper()
    if severity not in ("P0", "P1", "P2", "P3"):
        severity = "P2"
    source = str(payload.get("source", "unknown"))[:128]
    message = str(payload.get("message", ""))[:2000]
    fingerprint = payload.get("fingerprint") or hashlib.sha256(
        f"{source}:{message}".encode()
    ).hexdigest()[:16]
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}

    if severity == "P3":
        log_dispatch(severity, source, fingerprint, message, "mcp-only", extra)
        return {"ok": True, "decision": "mcp-only", "fingerprint": fingerprint}

    if kill_switch_active():
        ok, detail = send_ntfy(
            f"[{severity} kill-switched] {source}: {message}",
            title=f"{severity} {source}",
            priority="default",
        )
        log_dispatch(
            severity,
            source,
            fingerprint,
            message,
            f"kill-switch-ntfy-{'ok' if ok else 'fail'}",
            {"detail": detail},
        )
        return {"ok": ok, "decision": "kill-switch-ntfy", "fingerprint": fingerprint}

    if check_cost_caps_and_maybe_activate_kill_switch():
        ok, detail = send_ntfy(
            f"[{severity} cap-breached] {source}: {message}",
            title=f"{severity} {source}",
            priority="default",
        )
        log_dispatch(
            severity,
            source,
            fingerprint,
            message,
            "kill-switch-activated",
            {"detail": detail},
        )
        return {"ok": ok, "decision": "kill-switch-activated-ntfy", "fingerprint": fingerprint}

    if severity in ("P1", "P2") and is_maintenance_active():
        log_dispatch(severity, source, fingerprint, message, "maintenance-suppressed", extra)
        return {"ok": True, "decision": "maintenance-suppressed", "fingerprint": fingerprint}

    if severity == "P2":
        ok, detail = send_ntfy(
            f"[{source}] {message}", title=f"P2 {source}", priority="default"
        )
        log_dispatch(
            severity, source, fingerprint, message, f"ntfy-{'ok' if ok else 'fail'}", {"detail": detail}
        )
        return {"ok": ok, "decision": "ntfy", "fingerprint": fingerprint}

    # P0/P1: dedup first
    is_dup, total, suppressed = dedup_check_and_bump(fingerprint)
    if is_dup:
        log_dispatch(
            severity,
            source,
            fingerprint,
            message,
            "deduped",
            {"total": total, "suppressed": suppressed},
        )
        return {
            "ok": True,
            "decision": "deduped",
            "suppressed": suppressed,
            "fingerprint": fingerprint,
        }

    # P1 rate-limit check
    if severity == "P1":
        per_source = get_counter(f"slack_{source}_{today_key()}")
        daily = get_counter(f"slack_global_{today_key()}")
        if per_source >= SLACK_PER_SOURCE_CAP:
            ok, detail = send_ntfy(
                f"[P1 source-capped {source}] {message}",
                title=f"P1 {source} source-capped",
                priority="default",
            )
            log_dispatch(
                severity,
                source,
                fingerprint,
                message,
                "rate-limit-per-source",
                {"count": per_source, "detail": detail},
            )
            return {"ok": ok, "decision": "rate-limited-per-source", "fingerprint": fingerprint}
        if daily >= SLACK_DAILY_CAP:
            ok, detail = send_ntfy(
                f"[P1 global-cap {source}] {message}",
                title=f"P1 {source} global-cap",
                priority="default",
            )
            log_dispatch(
                severity,
                source,
                fingerprint,
                message,
                "rate-limit-global",
                {"count": daily, "detail": detail},
            )
            return {"ok": ok, "decision": "rate-limited-global", "fingerprint": fingerprint}

    slack_text = f"[{severity} {source}] {message}"
    ok, detail = send_slack(slack_text)
    if ok:
        increment_counter(f"slack_global_{today_key()}")
        increment_counter(f"slack_global_month_{month_key()}")
        increment_counter(f"slack_{source}_{today_key()}")

    if severity == "P0":
        send_ntfy(
            f"[{severity} {source}] {message}",
            title=f"P0 {source}",
            priority="urgent",
        )

    log_dispatch(
        severity,
        source,
        fingerprint,
        message,
        f"slack-{'ok' if ok else 'fail'}",
        {"detail": detail},
    )
    return {"ok": ok, "decision": "slack", "fingerprint": fingerprint}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send_json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            return self._send_json(
                200,
                {
                    "ok": True,
                    "service": "amg-slack-dispatcher",
                    "maintenance_mcp": _maintenance_mcp,
                    "maintenance_local": local_maintenance_active(),
                    "kill_switch": kill_switch_active(),
                    "daily_slack": get_counter(f"slack_global_{today_key()}"),
                    "monthly_slack": get_counter(f"slack_global_month_{month_key()}"),
                },
            )
        if self.path == "/admin/reset-kill-switch":
            set_kill_switch(False)
            return self._send_json(200, {"ok": True, "decision": "kill-switch-reset"})
        if self.path == "/admin/set-kill-switch":
            set_kill_switch(True, "manual")
            return self._send_json(200, {"ok": True, "decision": "kill-switch-activated"})
        if self.path == "/admin/set-maintenance":
            set_local_maintenance(True, "manual")
            return self._send_json(200, {"ok": True, "decision": "maintenance-on-local"})
        if self.path == "/admin/reset-maintenance":
            set_local_maintenance(False)
            return self._send_json(200, {"ok": True, "decision": "maintenance-off-local"})
        if self.path.startswith("/admin/set-daily-count"):
            q = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(q)
            v = int(params.get("value", ["0"])[0])
            set_counter(f"slack_global_{today_key()}", v)
            return self._send_json(200, {"ok": True, "daily": v})
        if self.path == "/admin/stats":
            with db_conn() as c:
                recent = c.execute(
                    """SELECT decision, COUNT(*) AS n FROM dispatch_log
                       WHERE ts > ? GROUP BY decision ORDER BY n DESC""",
                    (time.time() - 86400,),
                ).fetchall()
            return self._send_json(
                200,
                {
                    "ok": True,
                    "decisions_24h": [dict(r) for r in recent],
                    "daily_slack": get_counter(f"slack_global_{today_key()}"),
                    "monthly_slack": get_counter(f"slack_global_month_{month_key()}"),
                    "kill_switch": kill_switch_active(),
                    "maintenance": is_maintenance_active(),
                },
            )
        return self._send_json(404, {"error": "not-found"})

    def do_POST(self):
        if self.path != "/dispatch":
            return self._send_json(404, {"error": "not-found"})
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length > 0 else b""
        try:
            payload = json.loads(body.decode()) if body else {}
        except json.JSONDecodeError:
            return self._send_json(400, {"error": "invalid-json"})
        try:
            result = dispatch(payload)
        except Exception as e:
            logging.exception("dispatch-error")
            return self._send_json(500, {"error": str(e)})
        return self._send_json(200, result)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ensure_dirs_and_schema()
    threading.Thread(target=maintenance_mode_checker, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    logging.info(f"amg-slack-dispatcher listening on 127.0.0.1:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
