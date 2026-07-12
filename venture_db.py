#!/usr/bin/env python3
"""SQLite persistence and guarded state transitions for the venture engine."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("VENTURE_DB", DATA_DIR / "venture.sqlite3"))

def offer_config() -> dict:
    try: return json.loads((ROOT / "config" / "venture.json").read_text())
    except (OSError, json.JSONDecodeError): return {}

def acquisition_config() -> dict:
    try: return json.loads((ROOT / "config" / "acquisition.json").read_text())
    except (OSError, json.JSONDecodeError): return {}

MILESTONES = [
    "INSPECTION", "ARCHITECTURE", "QUEUE", "AGENTS", "DASHBOARD", "SECURITY",
    "RESEARCH", "PRODUCT", "QA", "PUBLICATION", "DISTRIBUTION", "SALES",
    "DELIVERY", "PERFORMANCE", "SANDBOX", "LIVE_READINESS", "LIVE_EXPERIMENT",
]
MILESTONE_STATES = {"NOT_STARTED", "INSPECTING", "IMPLEMENTING", "TESTING", "FAILED", "REPAIRING", "BLOCKED", "PASSED", "REGRESSION_FAILED", "REOPENED"}
TASK_STATES = {"BACKLOG", "RESEARCHING", "VALIDATING", "APPROVED_BY_SYSTEM", "BUILDING", "TESTING", "READY_TO_PUBLISH", "PUBLISHED", "MONITORING", "AWAITING_PAYMENT", "PAID", "DELIVERING", "COMPLETED", "FAILED", "PAUSED", "TERMINATED"}
ORDER_STATES = {"AWAITING_PAYMENT", "PAID", "NOT_PAID", "PARTIAL_PAYMENT", "DELIVERING", "COMPLETED", "CANCELLED"}
PAYMENT_STATES = {"UNVERIFIED", "PAID", "NOT_PAID", "PARTIAL_PAYMENT"}

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db() -> None:
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS venture_state (
          id INTEGER PRIMARY KEY CHECK (id = 1), venture_name TEXT NOT NULL,
          objective TEXT NOT NULL, current_milestone TEXT NOT NULL,
          milestone_state TEXT NOT NULL, experiment_status TEXT NOT NULL,
          paused INTEGER NOT NULL DEFAULT 0, publishing_enabled INTEGER NOT NULL DEFAULT 0,
          outreach_enabled INTEGER NOT NULL DEFAULT 0, emergency_stop INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS milestones (
          id INTEGER PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE, name TEXT NOT NULL UNIQUE,
          state TEXT NOT NULL, acceptance_json TEXT NOT NULL DEFAULT '[]', evidence_json TEXT NOT NULL DEFAULT '[]',
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agents (
          id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, role TEXT NOT NULL,
          status TEXT NOT NULL, current_task TEXT NOT NULL DEFAULT '', last_activity TEXT NOT NULL,
          next_action TEXT NOT NULL DEFAULT '', blocking_reason TEXT NOT NULL DEFAULT '',
          retry_count INTEGER NOT NULL DEFAULT 0, last_result TEXT NOT NULL DEFAULT '', cost_usd REAL NOT NULL DEFAULT 0,
          permissions_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, assigned_agent TEXT NOT NULL, objective TEXT NOT NULL,
          input_json TEXT NOT NULL DEFAULT '{}', expected_output TEXT NOT NULL, priority INTEGER NOT NULL,
          status TEXT NOT NULL, deadline TEXT, dependencies_json TEXT NOT NULL DEFAULT '[]',
          retry_count INTEGER NOT NULL DEFAULT 0, cost_usd REAL NOT NULL DEFAULT 0,
          result_json TEXT NOT NULL DEFAULT '{}', verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
          idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS opportunities (
          id TEXT PRIMARY KEY, product_or_service TEXT NOT NULL, target_buyer TEXT NOT NULL,
          problem TEXT NOT NULL, evidence_json TEXT NOT NULL, competition TEXT NOT NULL,
          creation_hours REAL NOT NULL, channel TEXT NOT NULL, price_usd REAL NOT NULL,
          operating_cost_usd REAL NOT NULL, risk TEXT NOT NULL, probability REAL NOT NULL,
          rejection_reason TEXT NOT NULL DEFAULT '', selected INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS products (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, target_buyer TEXT NOT NULL,
          price_usd REAL NOT NULL, version TEXT NOT NULL, files_json TEXT NOT NULL,
          preview_url TEXT NOT NULL DEFAULT '', public_url TEXT NOT NULL DEFAULT '',
          build_status TEXT NOT NULL, qa_status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS leads (
          id TEXT PRIMARY KEY, anonymous_identifier TEXT NOT NULL, source TEXT NOT NULL,
          profile_url TEXT NOT NULL DEFAULT '', inquiry_status TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
          id TEXT PRIMARY KEY, anonymous_customer_id TEXT NOT NULL, product_id TEXT NOT NULL,
          quoted_amount_usd REAL NOT NULL, payment_status TEXT NOT NULL, order_status TEXT NOT NULL,
          profile_url TEXT NOT NULL DEFAULT '', buyer_contact TEXT NOT NULL DEFAULT '',
          delivery_status TEXT NOT NULL DEFAULT 'NOT_STARTED', is_sandbox INTEGER NOT NULL DEFAULT 0,
          customer_email TEXT NOT NULL DEFAULT '', target_audience TEXT NOT NULL DEFAULT '',
          preferred_tone TEXT NOT NULL DEFAULT '', additional_context TEXT NOT NULL DEFAULT '',
          consent_scope TEXT NOT NULL DEFAULT '', payment_reference TEXT NOT NULL DEFAULT '',
          delivery_path TEXT NOT NULL DEFAULT '', purchased_version TEXT NOT NULL DEFAULT '',
          qa_evidence_json TEXT NOT NULL DEFAULT '[]', referral_source TEXT NOT NULL DEFAULT 'direct', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS publications (
          id TEXT PRIMARY KEY, channel TEXT NOT NULL, url TEXT NOT NULL, content TEXT NOT NULL,
          approval_status TEXT NOT NULL, risk_level TEXT NOT NULL, published_at TEXT,
          rollback_ref TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS publication_checks (
          id INTEGER PRIMARY KEY AUTOINCREMENT, publication_id TEXT NOT NULL, checked_at TEXT NOT NULL,
          url TEXT NOT NULL, http_status INTEGER NOT NULL, content_hash TEXT NOT NULL DEFAULT '',
          result TEXT NOT NULL, details_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS distribution_metrics (
          id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL, source TEXT NOT NULL,
          recorded_at TEXT NOT NULL, impressions INTEGER, visits INTEGER, clicks INTEGER,
          inquiries INTEGER, notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, event_type TEXT NOT NULL,
          actor TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
          result TEXT NOT NULL, risk_level TEXT NOT NULL, details_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS costs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, category TEXT NOT NULL,
          amount_usd REAL NOT NULL, task_id TEXT NOT NULL DEFAULT '', note TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS controls_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, control TEXT NOT NULL,
          value INTEGER NOT NULL, actor TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS feedback (
          id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL,
          feedback_text TEXT NOT NULL, permission_status TEXT NOT NULL DEFAULT 'REQUESTED',
          public_text TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, approved_at TEXT
        );
        """)
        order_columns = {row[1] for row in c.execute("PRAGMA table_info(orders)")}
        for column, definition in {
            "is_sandbox": "INTEGER NOT NULL DEFAULT 0",
            "customer_email": "TEXT NOT NULL DEFAULT ''",
            "target_audience": "TEXT NOT NULL DEFAULT ''",
            "preferred_tone": "TEXT NOT NULL DEFAULT ''",
            "additional_context": "TEXT NOT NULL DEFAULT ''",
            "consent_scope": "TEXT NOT NULL DEFAULT ''",
            "payment_reference": "TEXT NOT NULL DEFAULT ''",
            "delivery_path": "TEXT NOT NULL DEFAULT ''",
            "delivery_token": "TEXT NOT NULL DEFAULT ''",
            "purchased_version": "TEXT NOT NULL DEFAULT ''",
            "qa_evidence_json": "TEXT NOT NULL DEFAULT '[]'",
            "referral_source": "TEXT NOT NULL DEFAULT 'direct'",
        }.items():
            if column not in order_columns:
                c.execute(f"ALTER TABLE orders ADD COLUMN {column} {definition}")
        agent_columns = {row[1] for row in c.execute("PRAGMA table_info(agents)")}
        for column, definition in {
            "blocking_reason": "TEXT NOT NULL DEFAULT ''",
            "retry_count": "INTEGER NOT NULL DEFAULT 0",
            "last_result": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if column not in agent_columns:
                c.execute(f"ALTER TABLE agents ADD COLUMN {column} {definition}")
        c.execute("UPDATE agents SET role='Publish only to approved free channels with an allowlisted target' WHERE id='publishing'")
        if c.execute("SELECT 1 FROM venture_state WHERE id=1").fetchone() is None:
            c.execute("INSERT INTO venture_state VALUES (1,?,?,?,?,?,?,?,?,?,?)", (
                "SOL Autonomous Venture Engine", "Generate at least USD 5 in verified external revenue within seven days",
                "INSPECTION", "PASSED", "SANDBOX", 0, 0, 0, 0, now()))
            for i, name in enumerate(MILESTONES):
                state = "PASSED" if name == "INSPECTION" else "NOT_STARTED"
                c.execute("INSERT INTO milestones(ordinal,name,state,updated_at) VALUES(?,?,?,?)", (i, name, state, now()))
            agents = [
              ("venture-director", "Venture Director", "Set priorities, monitor progress, decide pivot/stop"),
              ("market-research", "Market Research Agent", "Collect observable demand evidence"),
              ("opportunity-analyst", "Opportunity Analyst", "Score and compare opportunities"),
              ("product-builder", "Product Builder Agent", "Build and version the minimum sellable product"),
              ("design-presentation", "Design and Presentation Agent", "Prepare buyer-facing presentation"),
              ("publishing", "Publishing Agent", "Publish only to approved free channels with an allowlisted target"),
              ("distribution", "Distribution Agent", "Prepare lawful, non-spam discovery drafts"),
              ("sales", "Sales Agent", "Prepare truthful buyer replies and orders"),
              ("delivery", "Delivery Agent", "Prepare delivery after owner payment confirmation"),
              ("quality-assurance", "Quality Assurance Agent", "Check links, files, claims, and readiness"),
              ("security-compliance", "Security and Compliance Agent", "Guard secrets, cost, permissions, and platform rules"),
              ("performance", "Performance Analyst", "Track funnel, costs, revenue, and pivot thresholds"),
            ]
            for aid, name, role in agents:
                c.execute("INSERT INTO agents(id,name,role,status,last_activity,permissions_json) VALUES(?,?,?,?,?,?)", (aid,name,role,"IDLE",now(),json.dumps(["read_state","write_assigned_records"])))
            log_event(c, "SYSTEM_INITIALIZED", "system", "venture", "1", "ok", "low", {"milestones": len(MILESTONES), "agents": len(agents)})

def log_event(c, event_type: str, actor: str, entity_type: str, entity_id: str, result: str, risk: str, details: dict | None = None) -> None:
    c.execute("INSERT INTO events(at,event_type,actor,entity_type,entity_id,result,risk_level,details_json) VALUES(?,?,?,?,?,?,?,?)", (now(),event_type,actor,entity_type,entity_id,result,risk,json.dumps(details or {}, sort_keys=True)))

def set_control(control: str, value: bool, actor: str = "owner") -> None:
    allowed = {"paused", "publishing_enabled", "outreach_enabled", "emergency_stop"}
    if control not in allowed: raise ValueError(f"unknown control: {control}")
    with connect() as c:
        c.execute(f"UPDATE venture_state SET {control}=?, updated_at=? WHERE id=1", (int(value), now()))
        c.execute("INSERT INTO controls_log(at,control,value,actor) VALUES(?,?,?,?)", (now(),control,int(value),actor))
        log_event(c, "CONTROL_CHANGED", actor, "venture", "1", "updated", "medium" if value else "low", {"control": control, "value": value})

def add_event(event_type: str, actor: str, entity_type: str, entity_id: str, result: str = "ok", risk: str = "low", details: dict | None = None) -> None:
    with connect() as c: log_event(c, event_type, actor, entity_type, entity_id, result, risk, details)

def guarded_state(c: sqlite3.Connection) -> sqlite3.Row:
    row = c.execute("SELECT * FROM venture_state WHERE id=1").fetchone()
    if row is None: raise RuntimeError("database not initialized")
    return row

def set_agent_status(agent_id: str, status: str, current_task: str = "", next_action: str = "", blocking_reason: str = "", retry_count: int | None = None, last_result: str = "") -> None:
    with connect() as c:
        agent = c.execute("SELECT retry_count FROM agents WHERE id=?", (agent_id,)).fetchone()
        if agent is None: raise KeyError(agent_id)
        retries = agent[0] if retry_count is None else retry_count
        c.execute("UPDATE agents SET status=?,current_task=?,last_activity=?,next_action=?,blocking_reason=?,retry_count=?,last_result=? WHERE id=?", (status,current_task,now(),next_action,blocking_reason,retries,last_result,agent_id))
        log_event(c, "AGENT_STATUS_CHANGED", agent_id, "agent", agent_id, status, "medium" if blocking_reason else "low", {"current_task": current_task, "next_action": next_action, "blocking_reason": blocking_reason, "retry_count": retries, "last_result": last_result})

def begin_milestone(name: str, actor: str = "venture-director") -> None:
    init_db()
    with connect() as c:
        state = guarded_state(c)
        milestone = c.execute("SELECT * FROM milestones WHERE name=?", (name,)).fetchone()
        if milestone is None: raise KeyError(name)
        if state["current_milestone"] != name: raise RuntimeError(f"current milestone is {state['current_milestone']}, not {name}")
        if milestone["state"] not in {"NOT_STARTED", "REOPENED", "FAILED", "REGRESSION_FAILED"}: return
        c.execute("UPDATE milestones SET state='INSPECTING',updated_at=? WHERE name=?", (now(),name))
        c.execute("UPDATE venture_state SET milestone_state='INSPECTING',updated_at=? WHERE id=1", (now(),))
        agent = c.execute("SELECT id FROM agents WHERE id=? OR name LIKE ?", (actor, "%" + name.title().replace("_", " ") + "%")).fetchone()
        if agent: c.execute("UPDATE agents SET status='WORKING',current_task=?,last_activity=?,next_action=?,blocking_reason='' WHERE id=?", (name,now(),"Execute acceptance checks and store evidence",agent[0]))
        log_event(c, "MILESTONE_STARTED", actor, "milestone", name, "INSPECTING", "low")

def pass_milestone(name: str, evidence: list[dict], actor: str = "venture-director") -> str | None:
    if not evidence: raise ValueError("milestone evidence is required")
    init_db()
    with connect() as c:
        state = guarded_state(c); milestone = c.execute("SELECT * FROM milestones WHERE name=?", (name,)).fetchone()
        if milestone is None: raise KeyError(name)
        if state["current_milestone"] != name: raise RuntimeError(f"cannot pass {name}; current is {state['current_milestone']}")
        if milestone["state"] not in {"INSPECTING", "IMPLEMENTING", "TESTING"}: raise RuntimeError(f"{name} is not under execution")
        c.execute("UPDATE milestones SET state='PASSED',evidence_json=?,updated_at=? WHERE name=?", (json.dumps(evidence, sort_keys=True),now(),name))
        ordinal = milestone["ordinal"]; next_row = c.execute("SELECT * FROM milestones WHERE ordinal=?", (ordinal+1,)).fetchone()
        next_name = next_row["name"] if next_row else None
        if next_row:
            c.execute("UPDATE milestones SET state='INSPECTING',updated_at=? WHERE ordinal=? AND state='NOT_STARTED'", (now(),ordinal+1))
        c.execute("UPDATE venture_state SET current_milestone=?,milestone_state=?,updated_at=? WHERE id=1", (next_name or name,"INSPECTING" if next_name else "PASSED",now()))
        c.execute("UPDATE agents SET status='COMPLETED',last_activity=?,last_result=? WHERE current_task=?", (now(),"PASSED",name))
        if next_name:
            c.execute("UPDATE agents SET status='WORKING',current_task=?,last_activity=?,next_action=?,blocking_reason='' WHERE id='venture-director'", (next_name,now(),"Execute acceptance checks and advance automatically",))
        log_event(c, "MILESTONE_PASSED", actor, "milestone", name, "PASSED", "low", {"evidence": evidence, "next_milestone": next_name})
        return next_name

def fail_milestone(name: str, reason: str, actor: str = "venture-director") -> None:
    with connect() as c:
        c.execute("UPDATE milestones SET state='FAILED',evidence_json=?,updated_at=? WHERE name=?", (json.dumps([{"error": reason}]),now(),name))
        c.execute("UPDATE venture_state SET milestone_state='FAILED',updated_at=? WHERE id=1", (now(),))
        log_event(c, "MILESTONE_FAILED", actor, "milestone", name, "FAILED", "medium", {"reason": reason})

def record_cost(category: str, amount_usd: float, note: str, task_id: str = "") -> None:
    if amount_usd < 0: raise ValueError("cost cannot be negative")
    with connect() as c:
        total = c.execute("SELECT COALESCE(SUM(amount_usd),0) FROM costs").fetchone()[0]
        if total + amount_usd > 3: raise PermissionError("USD 3 operating-cost ceiling would be exceeded")
        c.execute("INSERT INTO costs(at,category,amount_usd,task_id,note) VALUES(?,?,?,?,?)", (now(),category,amount_usd,task_id,note))
        log_event(c, "COST_RECORDED", "performance", "cost", str(c.lastrowid), "ok", "medium" if amount_usd else "low", {"amount_usd": amount_usd, "category": category})

def create_task(assigned_agent: str, objective: str, expected_output: str, priority: int = 5, input_data: dict | None = None, idempotency_key: str | None = None) -> str:
    tid = str(uuid.uuid4())
    with connect() as c:
        if idempotency_key and c.execute("SELECT id FROM tasks WHERE idempotency_key=?", (idempotency_key,)).fetchone(): return c.execute("SELECT id FROM tasks WHERE idempotency_key=?", (idempotency_key,)).fetchone()[0]
        c.execute("INSERT INTO tasks(id,assigned_agent,objective,input_json,expected_output,priority,status,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (tid,assigned_agent,objective,json.dumps(input_data or {}),expected_output,priority,"BACKLOG",idempotency_key,now(),now()))
        log_event(c, "TASK_CREATED", assigned_agent, "task", tid, "queued", "low", {"objective": objective})
    return tid

def transition_task(task_id: str, status: str, result: dict | None = None, verification: str = "UNVERIFIED") -> None:
    if status not in TASK_STATES: raise ValueError(f"invalid task state: {status}")
    with connect() as c:
        task = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task is None: raise KeyError(task_id)
        if status == "PUBLISHED":
            state = guarded_state(c)
            if not state["publishing_enabled"] or state["emergency_stop"]: raise PermissionError("publishing is disabled by control state")
        c.execute("UPDATE tasks SET status=?,result_json=?,verification_status=?,updated_at=? WHERE id=?", (status,json.dumps(result or {}),verification,now(),task_id))
        log_event(c, "TASK_TRANSITION", task["assigned_agent"], "task", task_id, status, "medium" if status in {"PUBLISHED","PAID"} else "low", {"verification": verification})

def create_order(product_id: str, customer_id: str, amount: float, profile_url: str = "", buyer_contact: str = "", is_sandbox: bool = False, customer_email: str = "", target_audience: str = "", preferred_tone: str = "", additional_context: str = "", consent_scope: str = "", purchased_version: str = "", referral_source: str = "direct", order_id: str = "") -> str:
    if amount <= 0: raise ValueError("amount must be positive")
    oid = order_id or "ord_" + uuid.uuid4().hex[:12]
    with connect() as c:
        if not consent_scope: raise ValueError("consent and scope acknowledgement is required")
        c.execute("INSERT INTO orders(id,anonymous_customer_id,product_id,quoted_amount_usd,payment_status,order_status,profile_url,buyer_contact,is_sandbox,customer_email,target_audience,preferred_tone,additional_context,consent_scope,purchased_version,referral_source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (oid,customer_id,product_id,amount,"UNVERIFIED","AWAITING_PAYMENT",profile_url,buyer_contact,int(is_sandbox),customer_email,target_audience,preferred_tone,additional_context,consent_scope,purchased_version,referral_source or "direct",now(),now()))
        log_event(c, "ORDER_CREATED", "sales", "order", oid, "AWAITING_PAYMENT", "medium", {"amount_usd": amount, "is_sandbox": is_sandbox})
    return oid

def confirm_payment(order_id: str, confirmed: bool, paypal_reference: str = "", actor: str = "owner") -> None:
    with connect() as c:
        state = guarded_state(c)
        if state["emergency_stop"]: raise PermissionError("emergency stop is active")
        order = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if order is None: raise KeyError(order_id)
        if confirmed and not paypal_reference.strip(): raise ValueError("PayPal reference is required for a PAID transition")
        payment = "PAID" if confirmed else "NOT_PAID"
        status = "PAID" if confirmed else "AWAITING_PAYMENT"
        c.execute("UPDATE orders SET payment_status=?,order_status=?,payment_reference=?,updated_at=? WHERE id=?", (payment,status,paypal_reference.strip() if confirmed else "",now(),order_id))
        log_event(c, "PAYMENT_CONFIRMED" if confirmed else "PAYMENT_NOT_CONFIRMED", actor, "order", order_id, payment, "high", {"owner_confirmed": True, "paypal_reference_present": bool(paypal_reference.strip())})

def record_publication(channel: str, url: str, content: str, approval_status: str = "AUTO_APPROVED", risk_level: str = "low", published_at: str | None = None, rollback_ref: str = "") -> str:
    publication_id = "pub_" + uuid.uuid4().hex[:12]
    with connect() as c:
        c.execute("INSERT INTO publications(id,channel,url,content,approval_status,risk_level,published_at,rollback_ref) VALUES(?,?,?,?,?,?,?,?)", (publication_id,channel,url,content,approval_status,risk_level,published_at or now(),rollback_ref))
        log_event(c, "PUBLICATION_RECORDED", "publishing", "publication", publication_id, "ok", risk_level, {"url": url, "channel": channel})
    return publication_id

def record_publication_check(publication_id: str, url: str, http_status: int, content_hash: str, result: str, details: dict | None = None) -> None:
    with connect() as c:
        c.execute("INSERT INTO publication_checks(publication_id,checked_at,url,http_status,content_hash,result,details_json) VALUES(?,?,?,?,?,?,?)", (publication_id,now(),url,http_status,content_hash,result,json.dumps(details or {}, sort_keys=True)))
        log_event(c, "PUBLICATION_CHECKED", "quality-assurance", "publication", publication_id, result, "low", {"url": url, "http_status": http_status, "content_hash": content_hash})

def update_product_publication(url: str, version: str | None = None) -> None:
    with connect() as c:
        c.execute("UPDATE products SET public_url=?,version=COALESCE(?,version) WHERE id=(SELECT id FROM products ORDER BY rowid DESC LIMIT 1)", (url,version))

def record_distribution_metric(channel: str, source: str, impressions: int | None = None, visits: int | None = None, clicks: int | None = None, inquiries: int | None = None, notes: str = "") -> None:
    with connect() as c:
        c.execute("INSERT INTO distribution_metrics(channel,source,recorded_at,impressions,visits,clicks,inquiries,notes) VALUES(?,?,?,?,?,?,?,?)", (channel,source,now(),impressions,visits,clicks,inquiries,notes))
        log_event(c, "DISTRIBUTION_METRIC_RECORDED", "performance", "distribution", channel, "ok", "low", {"source": source, "impressions": impressions, "visits": visits, "clicks": clicks, "inquiries": inquiries})

def record_feedback(order_id: str, feedback_text: str, permission_status: str = "REQUESTED", public_text: str = "") -> None:
    if not feedback_text.strip(): raise ValueError("feedback text is required")
    with connect() as c:
        c.execute("INSERT INTO feedback(order_id,feedback_text,permission_status,public_text,created_at) VALUES(?,?,?,?,?)", (order_id, feedback_text.strip(), permission_status, public_text.strip(), now()))

def dashboard_snapshot() -> dict:
    with connect() as c:
        state = dict(guarded_state(c))
        milestones = [dict(x) for x in c.execute("SELECT * FROM milestones ORDER BY ordinal")]
        agents = [dict(x) for x in c.execute("SELECT * FROM agents ORDER BY name")]
        tasks = [dict(x) for x in c.execute("SELECT * FROM tasks ORDER BY updated_at DESC LIMIT 25")]
        live_events = [dict(x) for x in c.execute("SELECT * FROM events WHERE event_type NOT LIKE 'SANDBOX_%' AND actor NOT LIKE 'sandbox%' ORDER BY id DESC LIMIT 40")]
        sandbox_events = [dict(x) for x in c.execute("SELECT * FROM events WHERE event_type LIKE 'SANDBOX_%' OR actor LIKE 'sandbox%' ORDER BY id DESC LIMIT 40")]
        orders = [dict(x) for x in c.execute("SELECT * FROM orders WHERE is_sandbox=0 ORDER BY updated_at DESC LIMIT 20")]
        sandbox_orders = [dict(x) for x in c.execute("SELECT * FROM orders WHERE is_sandbox=1 ORDER BY updated_at DESC LIMIT 20")]
        opportunities = [dict(x) for x in c.execute("SELECT * FROM opportunities ORDER BY probability DESC")]
        product = c.execute("SELECT * FROM products ORDER BY rowid DESC LIMIT 1").fetchone()
        publication = c.execute("SELECT p.id,p.channel,p.url,p.published_at,p.approval_status,pc.checked_at,pc.http_status,pc.result FROM publications p LEFT JOIN publication_checks pc ON pc.publication_id=p.id WHERE p.id=(SELECT id FROM publications ORDER BY rowid DESC LIMIT 1) ORDER BY pc.id DESC LIMIT 1").fetchone()
        distribution_metrics = [dict(x) for x in c.execute("SELECT * FROM distribution_metrics ORDER BY id DESC LIMIT 20")]
        feedback = [dict(x) for x in c.execute("SELECT order_id,permission_status,created_at,approved_at FROM feedback ORDER BY id DESC LIMIT 20")]
        funnel = dict(c.execute("SELECT COUNT(*) AS orders, COALESCE(SUM(CASE WHEN payment_status='UNVERIFIED' THEN 1 ELSE 0 END),0) AS awaiting_payment, COALESCE(SUM(CASE WHEN payment_status='PAID' THEN 1 ELSE 0 END),0) AS paid_orders, COALESCE(SUM(CASE WHEN order_status='COMPLETED' THEN 1 ELSE 0 END),0) AS fulfilled_orders FROM orders WHERE is_sandbox=0").fetchone())
        referral_sources = [dict(x) for x in c.execute("SELECT COALESCE(NULLIF(referral_source,''),'direct') AS source, COUNT(*) AS orders FROM orders WHERE is_sandbox=0 GROUP BY source ORDER BY orders DESC").fetchall()]
        worker_status = [dict(x) for x in c.execute("SELECT id,name,status,current_task,last_activity,next_action,retry_count,blocking_reason,last_result FROM agents WHERE status!='IDLE' ORDER BY last_activity DESC")]
        costs = c.execute("SELECT COALESCE(SUM(amount_usd),0) AS total FROM costs").fetchone()["total"]
        revenue = c.execute("SELECT COALESCE(SUM(quoted_amount_usd),0) AS total FROM orders WHERE payment_status='PAID' AND is_sandbox=0").fetchone()["total"]
        buyers = c.execute("SELECT COUNT(*) AS total FROM orders WHERE payment_status='PAID' AND is_sandbox=0").fetchone()["total"]
        offer = offer_config().get("offer", {})
        intake = {"public_url": offer.get("intake_url", ""), "api_url": offer.get("intake_api_url", ""), "hosted_backend_verified": bool(offer.get("hosted_intake_backend_verified", False)), "local_route": "/intake"}
        return {"state": state, "milestones": milestones, "agents": agents, "worker_status": worker_status, "tasks": tasks, "events": live_events, "sandbox_events": sandbox_events, "orders": orders, "sandbox_orders": sandbox_orders, "opportunities": opportunities, "product": dict(product) if product else None, "publication": dict(publication) if publication else None, "distribution_metrics": distribution_metrics, "funnel": funnel, "referral_sources": referral_sources, "feedback": feedback, "acquisition": acquisition_config(), "intake": intake, "financial": {"cost_usd": costs, "revenue_usd": revenue, "net_usd": revenue-costs, "budget_remaining_usd": max(0, 3-costs), "buyers": buyers}}

if __name__ == "__main__":
    init_db()
    print(DB_PATH)
