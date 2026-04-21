#!/usr/bin/env python3
# AMG MCP-over-stdio bridge for Achilles
# Read: op_decisions, op_task_queue, op_sprint_state, op_blockers
# Write: op_decisions (log_decision), op_blockers (flag_blocker),
#        op_sprint_state (update_sprint_state), op_task_queue (queue_operator_task)
# v1.3.0: add flag_blocker, update_sprint_state, queue_operator_task
#         alongside existing watchdog and credential stubs
# MCP stdio transport, JSON-RPC 2.0
import sys, json, os, urllib.request, urllib.parse, datetime, time

SUPABASE_URL = "https://egoazyasyrhslluossli.supabase.co"

def load_key():
    with open("/etc/amg/mcp-server.env") as f:
        for line in f:
            if line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("No SUPABASE_SERVICE_ROLE_KEY in /etc/amg/mcp-server.env")

SERVICE_KEY = load_key()

TOOLS = [
    {
        "name": "get_recent_decisions",
        "description": "Get recent decisions from op_decisions. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "default": 10}
            }
        }
    },
    {
        "name": "get_sprint_state",
        "description": "Get current sprint state. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "default": "EOM"}
            }
        }
    },
    {
        "name": "get_task_queue",
        "description": "Get tasks from op_task_queue. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "default": "approved"},
                "limit": {"type": "integer", "default": 10}
            }
        }
    },
    {
        "name": "get_blockers",
        "description": "Get open blockers from op_blockers. Read-only.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "log_decision",
        "description": "Write a decision to op_decisions. Achilles executor write access.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_source": {"type": "string"},
                "decision_text": {"type": "string"},
                "rationale": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["project_source", "decision_text"],
        },
    },
    {
        "name": "flag_blocker",
        "description": "Flag a new blocker that is preventing progress on a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                },
                "project_source": {"type": "string"},
            },
            "required": ["text", "severity", "project_source"],
        },
    },
    {
        "name": "update_sprint_state",
        "description": "Update sprint state for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "sprint_name": {"type": "string"},
                "kill_chain": {"type": "array"},
                "blockers": {"type": "array"},
                "completion_pct": {"type": "number"},
                "infrastructure_status": {"type": "object"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "queue_operator_task",
        "description": "Create a structured task in the operator task queue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "objective": {"type": "string"},
                "instructions": {"type": "string"},
                "acceptance_criteria": {"type": "string"},
                "priority": {
                    "type": "string",
                    "enum": ["urgent", "normal", "low"],
                    "default": "normal",
                },
                "agent": {
                    "type": "string",
                    "enum": ["alex", "maya", "jordan", "sam", "riley", "nadia", "lumina", "ops"],
                },
                "assigned_to": {
                    "type": "string",
                    "enum": ["titan", "manual", "n8n"],
                    "default": "titan",
                },
                "project_id": {"type": "string"},
                "campaign_id": {"type": "string"},
                "context": {"type": "string"},
                "output_target": {"type": "string"},
                "approval": {
                    "type": "string",
                    "enum": ["pre_approved", "pending"],
                    "default": "pending",
                },
                "tags": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "parent_task_id": {"type": "string"},
            },
            "required": ["objective", "instructions", "acceptance_criteria"],
        },
    },
    {
        "name": "read_credential_registry",
        "description": "Read /etc/amg/credential-registry.yaml. Returns full YAML content.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "watchdog_status",
        "description": "Read watchdog config and last Achilles heartbeat timestamp.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "watchdog_heartbeat",
        "description": "Write current UTC timestamp to /etc/amg/achilles-heartbeat.ts to signal liveness.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "gmail_stub",
        "description": "Gmail integration stub. Returns CREDENTIALS_NEEDED until Solon provisions OAuth tokens.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "gcalendar_stub",
        "description": "Google Calendar integration stub. Returns CREDENTIALS_NEEDED until Solon provisions OAuth tokens.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "gdrive_stub",
        "description": "Google Drive integration stub. Returns CREDENTIALS_NEEDED until Solon provisions OAuth tokens.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "canva_stub",
        "description": "Canva Connect integration stub. Returns CREDENTIALS_NEEDED until backend client credentials are provisioned.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "stripe_stub",
        "description": "Stripe integration stub. Returns CREDENTIALS_NEEDED until Solon provisions secret key.",
        "inputSchema": {"type": "object", "properties": {}}
    },
]

def supabase_get(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def supabase_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def supabase_patch(table, data, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="PATCH", headers={
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def load_env_file(path):
    result = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return result

def check_credential(env_var, env_file):
    val = os.environ.get(env_var, "")
    if not val:
        env_vals = load_env_file(env_file)
        val = env_vals.get(env_var, "")
    return bool(val) and val != "CREDENTIALS_NEEDED"

def missing_credentials(env_vars, env_file):
    env_vals = load_env_file(env_file)
    missing = []
    for env_var in env_vars:
        val = os.environ.get(env_var, "")
        if not val:
            val = env_vals.get(env_var, "")
        if not val or val == "CREDENTIALS_NEEDED":
            missing.append(env_var)
    return missing

def handle_tool(name, args):
    if name == "get_recent_decisions":
        count = int(args.get("count", 10))
        rows = supabase_get("op_decisions", {"order": "created_at.desc", "limit": count})
        return json.dumps(rows, default=str)

    elif name == "get_sprint_state":
        pid = args.get("project_id", "EOM")
        rows = supabase_get("op_sprint_state", {"project_id": f"eq.{pid}", "limit": 1})
        return json.dumps(rows[0] if rows else {}, default=str)

    elif name == "get_task_queue":
        status = args.get("status", "approved")
        limit = int(args.get("limit", 10))
        rows = supabase_get("op_task_queue", {
            "status": f"eq.{status}", "limit": limit, "order": "created_at.desc"
        })
        return json.dumps(rows, default=str)

    elif name == "get_blockers":
        rows = supabase_get("op_blockers", {"order": "created_at.desc", "limit": 20})
        return json.dumps(rows, default=str)

    elif name == "log_decision":
        row = supabase_post("op_decisions", {
            "project_source": args.get("project_source", "achilles"),
            "decision_text": args["decision_text"],
            "rationale": args.get("rationale", ""),
            "tags": args.get("tags", []),
            "operator_id": "OPERATOR_AMG",
        })
        return json.dumps(row[0] if isinstance(row, list) else row, default=str)

    elif name == "flag_blocker":
        row = supabase_post("op_blockers", {
            "project_source": args["project_source"],
            "blocker_text": args["text"],
            "severity": args["severity"],
            "status": "open",
            "operator_id": "OPERATOR_AMG",
        })
        return json.dumps(row[0] if isinstance(row, list) else row, default=str)

    elif name == "update_sprint_state":
        updates = {"last_updated": datetime.datetime.utcnow().isoformat() + "Z"}
        for key in (
            "sprint_name",
            "kill_chain",
            "blockers",
            "completion_pct",
            "infrastructure_status",
        ):
            if key in args:
                updates[key] = args[key]

        row = supabase_patch(
            "op_sprint_state",
            updates,
            {"project_id": f"eq.{args['project_id']}"},
        )
        if isinstance(row, list) and row:
            return json.dumps(row[0], default=str)
        return json.dumps({"updated": True, "project_id": args["project_id"]}, default=str)

    elif name == "queue_operator_task":
        priority = args.get("priority", "normal")
        if priority not in ("urgent", "normal", "low"):
            raise ValueError(f"Invalid priority: {priority}")

        agent = args.get("agent")
        if agent not in (None, "alex", "maya", "jordan", "sam", "riley", "nadia", "lumina", "ops"):
            raise ValueError(f"Invalid agent: {agent}")

        assigned_to = args.get("assigned_to", "titan")
        if assigned_to not in ("titan", "manual", "n8n"):
            raise ValueError(f"Invalid assigned_to: {assigned_to}")

        approval = args.get("approval", "pending")
        if approval not in ("pre_approved", "pending"):
            raise ValueError(f"Invalid approval: {approval}")

        status = "queued"
        if priority == "low" and assigned_to == "titan" and (not agent or agent == "ops"):
            approval = "auto_delegated"
            status = "approved"
        elif approval == "pre_approved":
            status = "approved"

        row = supabase_post("op_task_queue", {
            "priority": priority,
            "agent": agent,
            "objective": args["objective"],
            "context": args.get("context"),
            "instructions": args["instructions"],
            "acceptance_criteria": args["acceptance_criteria"],
            "assigned_to": assigned_to,
            "project_id": args.get("project_id"),
            "campaign_id": args.get("campaign_id"),
            "output_target": args.get("output_target"),
            "status": status,
            "approval": approval,
            "queued_by": "achilles",
            "tags": args.get("tags", []),
            "notes": args.get("notes"),
            "parent_task_id": args.get("parent_task_id"),
            "task_risk_tier": "exempt" if agent == "ops" else "standard",
        })
        return json.dumps(row[0] if isinstance(row, list) else row, default=str)

    elif name == "read_credential_registry":
        try:
            with open("/etc/amg/credential-registry.yaml") as f:
                return f.read()
        except FileNotFoundError:
            return "# /etc/amg/credential-registry.yaml not found"

    elif name == "watchdog_status":
        conf_contents = ""
        try:
            with open("/etc/amg/watchdog.conf") as f:
                conf_contents = f.read()
        except FileNotFoundError:
            conf_contents = "# /etc/amg/watchdog.conf not found"

        hb_path = "/etc/amg/achilles-heartbeat.ts"
        last_heartbeat_ts = "never"
        heartbeat_age_seconds = None
        if os.path.exists(hb_path):
            try:
                with open(hb_path) as f:
                    last_heartbeat_ts = f.read().strip()
                mtime = os.path.getmtime(hb_path)
                heartbeat_age_seconds = int(time.time() - mtime)
            except Exception:
                last_heartbeat_ts = "error_reading"

        return json.dumps({
            "conf_contents": conf_contents,
            "last_heartbeat_ts": last_heartbeat_ts,
            "heartbeat_age_seconds": heartbeat_age_seconds,
        })

    elif name == "watchdog_heartbeat":
        ts = datetime.datetime.utcnow().isoformat() + "Z"
        hb_path = "/etc/amg/achilles-heartbeat.ts"
        with open(hb_path, "w") as f:
            f.write(ts + "\n")
        os.chmod(hb_path, 0o644)
        return json.dumps({"written": True, "ts": ts})

    elif name == "gmail_stub":
        if check_credential("GOOGLE_OAUTH_ACCESS_TOKEN", "/etc/amg/google-gmail.env"):
            return json.dumps({
                "status": "CONFIGURED",
                "note": "Full Gmail tools not yet implemented — contact Titan to extend bridge"
            })
        return json.dumps({
            "status": "CREDENTIALS_NEEDED",
            "instructions": "Set GOOGLE_OAUTH_ACCESS_TOKEN, GOOGLE_OAUTH_REFRESH_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_GMAIL_USER in /etc/amg/google-gmail.env (chmod 600, root:root). Titan will provision these via OAuth flow."
        })

    elif name == "gcalendar_stub":
        if check_credential("GOOGLE_CALENDAR_TOKEN", "/etc/amg/google-calendar.env"):
            return json.dumps({
                "status": "CONFIGURED",
                "note": "Full Google Calendar tools not yet implemented — contact Titan to extend bridge"
            })
        return json.dumps({
            "status": "CREDENTIALS_NEEDED",
            "instructions": "Set GOOGLE_CALENDAR_TOKEN in /etc/amg/google-calendar.env (chmod 600, root:root). Titan will provision these via OAuth flow."
        })

    elif name == "gdrive_stub":
        if check_credential("GOOGLE_DRIVE_TOKEN", "/etc/amg/google-drive.env"):
            return json.dumps({
                "status": "CONFIGURED",
                "note": "Full Google Drive tools not yet implemented — contact Titan to extend bridge"
            })
        return json.dumps({
            "status": "CREDENTIALS_NEEDED",
            "instructions": "Set GOOGLE_DRIVE_TOKEN in /etc/amg/google-drive.env (chmod 600, root:root). Titan will provision these via OAuth flow."
        })

    elif name == "canva_stub":
        required = ["CANVA_CLIENT_ID", "CANVA_CLIENT_SECRET"]
        missing = missing_credentials(required, "/etc/amg/canva.env")
        if not missing:
            return json.dumps({
                "status": "CONFIGURED",
                "note": "Canva Connect client credentials are present. Full Canva tools not yet implemented — contact Titan to extend bridge",
                "credential_source": "/etc/amg/canva.env",
                "required_env_vars": required
            })
        return json.dumps({
            "status": "CREDENTIALS_NEEDED",
            "instructions": "Set CANVA_CLIENT_ID and CANVA_CLIENT_SECRET in /etc/amg/canva.env (chmod 600, root:root).",
            "missing": missing
        })

    elif name == "stripe_stub":
        if check_credential("STRIPE_SECRET_KEY", "/etc/amg/stripe.env"):
            return json.dumps({
                "status": "CONFIGURED",
                "note": "Full Stripe tools not yet implemented — contact Titan to extend bridge"
            })
        return json.dumps({
            "status": "CREDENTIALS_NEEDED",
            "instructions": "Set STRIPE_SECRET_KEY in /etc/amg/stripe.env (chmod 600, root:root). Titan will provision these."
        })

    else:
        raise ValueError(f"Unknown tool: {name}")

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method", "")
        rid = msg.get("id")

        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "amg-achilles-bridge", "version": "1.3.0"}
            }})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = msg.get("params", {})
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                result = handle_tool(tool_name, tool_args)
                send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": result}]
                }})
            except Exception as e:
                send({"jsonrpc": "2.0", "id": rid, "error": {
                    "code": -32000, "message": str(e)
                }})
        elif method == "notifications/initialized":
            pass
        else:
            if rid is not None:
                send({"jsonrpc": "2.0", "id": rid, "error": {
                    "code": -32601, "message": f"Method not found: {method}"
                }})

if __name__ == "__main__":
    main()
