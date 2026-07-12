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
          next_action TEXT NOT NULL DEFAULT '', cost_usd REAL NOT NULL DEFAULT 0,
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
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS publications (
          id TEXT PRIMARY KEY, channel TEXT NOT NULL, url TEXT NOT NULL, content TEXT NOT NULL,
          approval_status TEXT NOT NULL, risk_level TEXT NOT NULL, published_at TEXT,
          rollback_ref TEXT NOT NULL DEFAULT ''
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
        """)
        order_columns = {row[1] for row in c.execute("PRAGMA table_info(orders)")}
        if "is_sandbox" not in order_columns:
            c.execute("ALTER TABLE orders ADD COLUMN is_sandbox INTEGER NOT NULL DEFAULT 0")
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
              ("publishing", "Publishing Agent", "Prepare free public publication; manual submit required"),
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

def create_order(product_id: str, customer_id: str, amount: float, profile_url: str = "", buyer_contact: str = "", is_sandbox: bool = False) -> str:
    if amount <= 0: raise ValueError("amount must be positive")
    oid = "ord_" + uuid.uuid4().hex[:12]
    with connect() as c:
        c.execute("INSERT INTO orders(id,anonymous_customer_id,product_id,quoted_amount_usd,payment_status,order_status,profile_url,buyer_contact,is_sandbox,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (oid,customer_id,product_id,amount,"UNVERIFIED","AWAITING_PAYMENT",profile_url,buyer_contact,int(is_sandbox),now(),now()))
        log_event(c, "ORDER_CREATED", "sales", "order", oid, "AWAITING_PAYMENT", "medium", {"amount_usd": amount})
    return oid

def confirm_payment(order_id: str, confirmed: bool, actor: str = "owner") -> None:
    with connect() as c:
        state = guarded_state(c)
        if state["emergency_stop"]: raise PermissionError("emergency stop is active")
        order = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if order is None: raise KeyError(order_id)
        payment = "PAID" if confirmed else "NOT_PAID"
        status = "PAID" if confirmed else "AWAITING_PAYMENT"
        c.execute("UPDATE orders SET payment_status=?,order_status=?,updated_at=? WHERE id=?", (payment,status,now(),order_id))
        log_event(c, "PAYMENT_CONFIRMED" if confirmed else "PAYMENT_NOT_CONFIRMED", actor, "order", order_id, payment, "high", {"owner_confirmed": True})

def dashboard_snapshot() -> dict:
    with connect() as c:
        state = dict(guarded_state(c))
        milestones = [dict(x) for x in c.execute("SELECT * FROM milestones ORDER BY ordinal")]
        agents = [dict(x) for x in c.execute("SELECT * FROM agents ORDER BY name")]
        tasks = [dict(x) for x in c.execute("SELECT * FROM tasks ORDER BY updated_at DESC LIMIT 25")]
        events = [dict(x) for x in c.execute("SELECT * FROM events ORDER BY id DESC LIMIT 40")]
        orders = [dict(x) for x in c.execute("SELECT * FROM orders ORDER BY updated_at DESC LIMIT 20")]
        opportunities = [dict(x) for x in c.execute("SELECT * FROM opportunities ORDER BY probability DESC")]
        product = c.execute("SELECT * FROM products ORDER BY rowid DESC LIMIT 1").fetchone()
        costs = c.execute("SELECT COALESCE(SUM(amount_usd),0) AS total FROM costs").fetchone()["total"]
        revenue = c.execute("SELECT COALESCE(SUM(quoted_amount_usd),0) AS total FROM orders WHERE payment_status='PAID' AND is_sandbox=0").fetchone()["total"]
        buyers = c.execute("SELECT COUNT(*) AS total FROM orders WHERE payment_status='PAID' AND is_sandbox=0").fetchone()["total"]
        return {"state": state, "milestones": milestones, "agents": agents, "tasks": tasks, "events": events, "orders": orders, "opportunities": opportunities, "product": dict(product) if product else None, "financial": {"cost_usd": costs, "revenue_usd": revenue, "net_usd": revenue-costs, "budget_remaining_usd": max(0, 3-costs), "buyers": buyers}}

if __name__ == "__main__":
    init_db()
    print(DB_PATH)
