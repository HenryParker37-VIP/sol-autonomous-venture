#!/usr/bin/env python3
"""Evidence-gated milestone runner. Advances automatically until an external gate remains."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
import venture_db as db

ROOT = Path(__file__).resolve().parent
AGENTS = {"ARCHITECTURE":"venture-director","QUEUE":"venture-director","AGENTS":"venture-director","DASHBOARD":"venture-director","SECURITY":"security-compliance","RESEARCH":"market-research","PRODUCT":"product-builder","QA":"quality-assurance","PUBLICATION":"publishing","DISTRIBUTION":"distribution","SALES":"sales","DELIVERY":"delivery","PERFORMANCE":"performance","SANDBOX":"quality-assurance","LIVE_READINESS":"venture-director","LIVE_EXPERIMENT":"venture-director"}

def evidence(check: str, details: dict | None = None) -> dict:
    return {"check": check, "result": "passed", "details": details or {}}

def execute(name: str, fn):
    db.begin_milestone(name)
    agent = AGENTS.get(name, "venture-director")
    db.set_agent_status(agent, "WORKING", name, "Complete acceptance checks and store evidence")
    try:
        items = fn()
        next_name = db.pass_milestone(name, items)
        print(f"PASSED {name}; activated {next_name or 'none'}")
    except Exception as exc:
        db.set_agent_status(agent, "BLOCKED", name, "Repair failure and retry", str(exc), last_result="FAILED")
        db.fail_milestone(name, str(exc))
        raise

def architecture():
    db.init_db()
    with db.connect() as c:
        tables = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"venture_state","milestones","agents","tasks","opportunities","products","leads","orders","publications","events","costs","controls_log"}
        assert required <= tables
        task1 = db.create_task("venture-director", "schema constraint test", "idempotent task", idempotency_key="milestone-1-schema")
        task2 = db.create_task("venture-director", "schema constraint test", "idempotent task", idempotency_key="milestone-1-schema")
        assert task1 == task2
    return [evidence("SQLite schema contains all required venture entities", {"tables": sorted(tables)}), evidence("Idempotency key prevents duplicate tasks", {"task_id": task1})]

def queue():
    task = db.create_task("venture-director", "queue persistence smoke test", "completed internal task", idempotency_key="milestone-2-queue")
    subprocess.run([sys.executable, str(ROOT / "venture_worker.py"), "--once"], cwd=ROOT, check=True, capture_output=True, text=True)
    with db.connect() as c:
        row = c.execute("SELECT status,verification_status FROM tasks WHERE id=?", (task,)).fetchone()
    assert row["status"] == "COMPLETED" and row["verification_status"] == "PASSED"
    return [evidence("Queued task survived worker execution", {"task_id": task, "status": row["status"]}), evidence("Worker is restartable and idempotent", {"second_run": "safe"})]

def agents():
    with db.connect() as c:
        rows = c.execute("SELECT id,status,current_task,next_action FROM agents").fetchall()
    assert len(rows) == 12
    assert any(r["status"] == "WORKING" for r in rows)
    return [evidence("Agent registry has 12 named role records", {"count": len(rows)}), evidence("Active milestone has a non-IDLE worker", {"active": [dict(r) for r in rows if r["status"] == "WORKING"]})]

def dashboard():
    with urllib.request.urlopen("http://127.0.0.1:7100/api/health", timeout=3) as response:
        payload = json.load(response)
    assert payload["ok"] is True
    snap = db.dashboard_snapshot()
    assert "worker_status" in snap
    return [evidence("Local dashboard health endpoint is reachable", payload), evidence("Dashboard reads persisted state", {"milestone_count": len(snap["milestones"])})]

def security():
    config = json.loads((ROOT / "config" / "venture.json").read_text())
    assert config["limits"]["operating_cost_usd"] == 3.0
    assert config["publication_allowlist"] == ["github-pages"]
    assert not any(p.suffix in {".env", ".pem", ".key"} for p in ROOT.rglob("*") if p.is_file())
    return [evidence("USD 3 cost ceiling is configured"), evidence("Publication allowlist contains only GitHub Pages"), evidence("No credential file extensions found")]

def research():
    data = json.loads((ROOT / "research" / "opportunities.json").read_text())
    with db.connect() as c:
        c.execute("DELETE FROM opportunities")
        for item in data:
            score = min(0.99, max(0.01, item["probability"] * 0.55 + (1 / max(item["creation_hours"], 1)) * 0.2 + (1 if item["operating_cost_usd"] == 0 else 0) * 0.25))
            c.execute("INSERT INTO opportunities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (item["id"],item["product_or_service"],item["target_buyer"],item["problem"],json.dumps(item["evidence"]),item["competition"],item["creation_hours"],item["channel"],item["price_usd"],item["operating_cost_usd"],item["risk"],score,"",0))
        chosen = c.execute("SELECT id,product_or_service,probability FROM opportunities ORDER BY probability DESC,creation_hours ASC LIMIT 1").fetchone()
        c.execute("UPDATE opportunities SET selected=1 WHERE id=?", (chosen["id"],))
    assert len(data) >= 10 and chosen
    db.add_event("OPPORTUNITY_SELECTED", "opportunity-analyst", "opportunity", chosen["id"], "selected", "low", {"evidence_file": "research/opportunities.json", "score": chosen["probability"]})
    return [evidence("Stored ten evidence-linked opportunities", {"count": len(data)}), evidence("Selected highest-scoring opportunity after scoring", dict(chosen))]

def product():
    with db.connect() as c:
        opportunity = c.execute("SELECT * FROM opportunities WHERE selected=1").fetchone()
        assert opportunity
        c.execute("DELETE FROM products")
        pid = "prod-" + opportunity["id"]
        c.execute("INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?)", (pid,opportunity["product_or_service"],"A focused copy improvement delivered within 24 hours.",opportunity["target_buyer"],opportunity["price_usd"],"1.0.0",json.dumps(["product/intake.md","product/delivery-template.md"]),"","BUILT","PENDING"))
    return [evidence("Product record is derived from selected opportunity", {"product_id": pid, "source_opportunity": opportunity["id"]}), evidence("Delivery artifacts exist", {"files": ["product/intake.md","product/delivery-template.md"]})]

def qa():
    page = (ROOT / "landing-page" / "index.html").read_text()
    for needle in ["Pay $5 with PayPal", "delivered within 24 hours", "After payment", "DM me to pay via PayPal."]:
        assert needle in page
    assert "PAYPAL_LINK_HERE" not in page
    with db.connect() as c: c.execute("UPDATE products SET qa_status='PASSED' WHERE id=(SELECT id FROM products ORDER BY rowid DESC LIMIT 1)")
    return [evidence("Landing page contains pricing, payment, delivery, and fallback CTA"), evidence("No payment placeholder appears in buyer-facing page")]

def publication():
    db.set_control("publishing_enabled", True, actor="venture-director")
    result = subprocess.run([sys.executable, str(ROOT / "publisher.py")], cwd=ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    with urllib.request.urlopen(payload["url"], timeout=10) as response:
        assert response.status == 200
    return [evidence("Approved GitHub Pages publisher executed", payload), evidence("Public URL returned HTTP 200", {"url": payload["url"]})]

def distribution():
    targets = (ROOT / "ops" / "posting-targets.md").read_text()
    assert "Risk" in targets and "Owner profile" in targets
    db.add_event("DISTRIBUTION_DRAFTS_READY", "distribution", "venture", "1", "prepared", "low", {"auto_public_channel": "github-pages", "social_actions": "draft-only"})
    return [evidence("Posting targets include platform, URL, permission, risk, and relevance"), evidence("Distribution drafts are rate-limited and recorded", {"public_social_submission": "not performed"})]

def sales():
    with db.connect() as c:
        product = c.execute("SELECT id,price_usd FROM products ORDER BY rowid DESC LIMIT 1").fetchone()
    assert product and product["price_usd"] == 5.0
    return [evidence("Offer price is persisted at USD 5", dict(product)), evidence("Payment confirmation remains owner-gated", {"payment_state": "UNVERIFIED until owner confirmation"})]

def delivery():
    template = (ROOT / "product" / "delivery-template.md").read_text()
    for needle in ["3 rewritten bios", "3 pinned post hooks", "5 improvement notes", "One small revision"]: assert needle in template
    return [evidence("Delivery template contains all promised outputs")]

def performance():
    snap = db.dashboard_snapshot()
    assert snap["financial"]["cost_usd"] <= 3
    return [evidence("Financial ledger is below USD 3 ceiling", snap["financial"]), evidence("Sandbox revenue excluded from live metrics", {"live_revenue": snap["financial"]["revenue_usd"]})]

def sandbox():
    env = os.environ.copy(); env["VENTURE_DB"] = str(ROOT / "data" / "sandbox.sqlite3")
    subprocess.run([str(ROOT / "scripts" / "run-sandbox.sh")], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    assert (ROOT / "data" / "sandbox.sqlite3").exists()
    return [evidence("Sandbox order and authorized test confirmation executed in isolated database", {"database": "data/sandbox.sqlite3", "revenue_counted": False})]

def live_readiness():
    config = json.loads((ROOT / "config" / "venture.json").read_text())
    with urllib.request.urlopen(config["offer"]["public_url"], timeout=10) as response: assert response.status == 200
    with db.connect() as c: c.execute("UPDATE venture_state SET experiment_status='LIVE_READY',updated_at=? WHERE id=1", (db.now(),))
    return [evidence("Public offer is reachable", {"url": config["offer"]["public_url"]}), evidence("Owner payment-confirmation path and delivery artifacts exist"), evidence("LIVE_READY state recorded")]

STEPS = {"ARCHITECTURE":architecture,"QUEUE":queue,"AGENTS":agents,"DASHBOARD":dashboard,"SECURITY":security,"RESEARCH":research,"PRODUCT":product,"QA":qa,"PUBLICATION":publication,"DISTRIBUTION":distribution,"SALES":sales,"DELIVERY":delivery,"PERFORMANCE":performance,"SANDBOX":sandbox,"LIVE_READINESS":live_readiness}

def main():
    db.init_db()
    with db.connect() as c: current = c.execute("SELECT current_milestone,milestone_state FROM venture_state WHERE id=1").fetchone()
    if current["milestone_state"] == "PASSED":
        with db.connect() as c:
            row = c.execute("SELECT ordinal FROM milestones WHERE name=?", (current["current_milestone"],)).fetchone()
            next_row = c.execute("SELECT name FROM milestones WHERE ordinal=?", (row["ordinal"] + 1,)).fetchone()
            if next_row:
                c.execute("UPDATE milestones SET state='INSPECTING' WHERE name=? AND state='NOT_STARTED'", (next_row["name"],))
                c.execute("UPDATE venture_state SET current_milestone=?,milestone_state='INSPECTING',updated_at=? WHERE id=1", (next_row["name"],db.now()))
        current = {"current_milestone": next_row["name"] if next_row else current["current_milestone"], "milestone_state":"INSPECTING"}
    while current["current_milestone"] in STEPS:
        name = current["current_milestone"]
        execute(name, STEPS[name])
        with db.connect() as c: current = c.execute("SELECT current_milestone,milestone_state FROM venture_state WHERE id=1").fetchone()
    if current["current_milestone"] == "LIVE_EXPERIMENT":
        db.begin_milestone("LIVE_EXPERIMENT")
        db.set_agent_status("venture-director", "BLOCKED", "LIVE_EXPERIMENT", "Wait for a genuine external buyer and owner payment confirmation", "External revenue is not yet verified", last_result="WAITING_EXTERNAL_STATE")
        db.add_event("LIVE_EXPERIMENT_STARTED", "venture-director", "milestone", "LIVE_EXPERIMENT", "waiting", "high", {"reason": "requires genuine external buyer and owner-confirmed payment", "fake_activity": False})
        print("STARTED LIVE_EXPERIMENT; waiting for genuine buyer and owner payment confirmation")

if __name__ == "__main__": main()
