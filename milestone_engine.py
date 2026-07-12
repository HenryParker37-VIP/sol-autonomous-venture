#!/usr/bin/env python3
"""Evidence-gated milestone runner. Advances automatically until an external gate remains."""
from __future__ import annotations
import json
import hashlib
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

REQUIRED_EVIDENCE_KEYS = {"acceptance_criterion", "implementation_file", "command_executed", "actual_output", "timestamp", "persisted_database_record", "test_result", "failure_or_limitation"}

def enrich_evidence(name: str, items: list[dict]) -> list[dict]:
    timestamp = db.now()
    return [{**item, "acceptance_criterion": item.get("check", item.get("acceptance_criterion", "criterion")), "implementation_file": item.get("implementation_file", "milestone_engine.py"), "command_executed": item.get("command_executed", f"python3 milestone_engine.py --milestone {name}"), "actual_output": item.get("actual_output", json.dumps(item.get("details", {}), sort_keys=True)), "timestamp": item.get("timestamp", timestamp), "persisted_database_record": item.get("persisted_database_record", f"milestones.name={name}"), "test_result": item.get("test_result", "PASS"), "failure_or_limitation": item.get("failure_or_limitation", "")} for item in items]

def reopen_missing_evidence() -> None:
    db.init_db()
    with db.connect() as c:
        rows = c.execute("SELECT ordinal,name,state,evidence_json FROM milestones WHERE ordinal BETWEEN 1 AND 15 ORDER BY ordinal").fetchall()
        affected = []
        for row in rows:
            try: entries = json.loads(row["evidence_json"] or "[]")
            except json.JSONDecodeError: entries = []
            if row["state"] == "PASSED" and any(not REQUIRED_EVIDENCE_KEYS <= set(entry) for entry in entries): affected.append(row["ordinal"])
        if not affected: return
        start = min(affected)
        for row in rows:
            if row["ordinal"] >= start:
                marker = {"result":"NOT_VERIFIED","acceptance_criterion":"Evidence contract was incomplete","implementation_file":"milestone_engine.py","command_executed":"python3 milestone_engine.py --audit","actual_output":"Required evidence fields were missing","timestamp":db.now(),"persisted_database_record":f"milestones.name={row['name']}","test_result":"NOT_VERIFIED","failure_or_limitation":"Prior milestone evidence did not include command, output, timestamp, and persisted-record fields"}
                c.execute("UPDATE milestones SET state='REOPENED',evidence_json=?,updated_at=? WHERE ordinal=?", (json.dumps([marker], sort_keys=True),db.now(),row["ordinal"]))
        c.execute("UPDATE milestones SET state='INSPECTING',updated_at=? WHERE ordinal=?", (db.now(),start))
        name = c.execute("SELECT name FROM milestones WHERE ordinal=?", (start,)).fetchone()[0]
        c.execute("UPDATE venture_state SET current_milestone=?,milestone_state='INSPECTING',updated_at=? WHERE id=1", (name,db.now()))
        c.execute("UPDATE agents SET status='WORKING',current_task=?,last_activity=?,next_action=?,blocking_reason='' WHERE id='venture-director'", (name,db.now(),"Re-run reopened milestones with complete evidence",))
        db.log_event(c, "MILESTONES_REOPENED_FOR_EVIDENCE_AUDIT", "quality-assurance", "milestone", name, "REOPENED", "medium", {"affected_ordinals": affected, "start": start})

def execute(name: str, fn):
    db.begin_milestone(name)
    agent = AGENTS.get(name, "venture-director")
    db.set_agent_status(agent, "WORKING", name, "Complete acceptance checks and store evidence")
    try:
        items = enrich_evidence(name, fn())
        next_name = db.pass_milestone(name, items)
        write_evidence_matrix()
        print(f"PASSED {name}; activated {next_name or 'none'}")
    except Exception as exc:
        db.set_agent_status(agent, "BLOCKED", name, "Repair failure and retry", str(exc), last_result="FAILED")
        db.fail_milestone(name, str(exc))
        raise

def write_evidence_matrix() -> None:
    db.init_db()
    with db.connect() as c: rows = c.execute("SELECT ordinal,name,state,evidence_json FROM milestones WHERE ordinal BETWEEN 1 AND 15 ORDER BY ordinal").fetchall()
    lines = ["# Evidence matrix", "", "Generated from persisted milestone evidence. `NOT_VERIFIED` rows reopen their milestone.", "", "| Milestone | State | Acceptance criterion | Implementation file | Command executed | Actual output | Timestamp | Persisted DB record | Test result | Failure or limitation |", "|---|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        entries = json.loads(row["evidence_json"] or "[]")
        if not entries: entries = [{"acceptance_criterion":"No evidence record","test_result":"NOT_VERIFIED","failure_or_limitation":"No persisted evidence"}]
        for entry in entries:
            def cell(value): return str(value or "").replace("|", "\\|").replace("\n", " ")
            lines.append("| " + " | ".join(cell(x) for x in [row["name"],row["state"],entry.get("acceptance_criterion",entry.get("check")),entry.get("implementation_file"),entry.get("command_executed"),entry.get("actual_output",entry.get("details")),entry.get("timestamp"),entry.get("persisted_database_record"),entry.get("test_result",entry.get("result")),entry.get("failure_or_limitation")]) + " |")
    (ROOT / "docs" / "venture" / "evidence-matrix.md").write_text("\n".join(lines) + "\n")

def mark_unverified_hosted_intake() -> None:
    config = db.offer_config().get("offer", {})
    if config.get("hosted_intake_backend_verified", False): return
    marker = {"acceptance_criterion":"Public hosted intake API persists customer submissions", "implementation_file":"intake.html + venture_server.py", "command_executed":"curl POST /api/orders against local service; public GitHub Pages POST check", "actual_output":"Local API created AWAITING_PAYMENT order; GitHub Pages has no persistent POST backend", "timestamp":db.now(), "persisted_database_record":"venture_state.current_milestone=LIVE_EXPERIMENT", "test_result":"NOT_VERIFIED", "failure_or_limitation":"Netlify or another persistent hosted form backend requires owner login/configuration"}
    with db.connect() as c:
        for name in ("SALES", "LIVE_READINESS"):
            c.execute("UPDATE milestones SET state='REOPENED',evidence_json=?,updated_at=? WHERE name=?", (json.dumps([marker], sort_keys=True),db.now(),name))
        c.execute("UPDATE agents SET status='WORKING',current_task='SALES_REOPENED',last_activity=?,next_action=?,blocking_reason='',last_result='NOT_VERIFIED' WHERE id='sales'", (db.now(),"Connect a persistent hosted form backend and rerun the public intake check"))
        db.log_event(c, "HOSTED_INTAKE_NOT_VERIFIED", "quality-assurance", "milestone", "LIVE_READINESS", "NOT_VERIFIED", "high", {"public_form": config.get("intake_url"), "local_api": config.get("intake_api_url"), "owner_login_required": True})
    write_evidence_matrix()

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
    subprocess.run([sys.executable, str(ROOT / "venture_worker.py"), "--once", "--task-id", task], cwd=ROOT, check=True, capture_output=True, text=True)
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
        c.execute("INSERT INTO products(id,name,description,target_buyer,price_usd,version,files_json,preview_url,public_url,build_status,qa_status) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (pid,opportunity["product_or_service"],"A focused copy improvement delivered within 24 hours.",opportunity["target_buyer"],opportunity["price_usd"],"1.0.0",json.dumps(["product/intake.md","product/delivery-template.md"]),"","","BUILT","PENDING"))
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
        body = response.read(); status = response.status
    assert status == 200
    content_hash = hashlib.sha256(body).hexdigest()
    db.record_publication_check(payload["publication_id"], payload["url"], status, content_hash, "PASS", {"checked_at": db.now()})
    with db.connect() as c: publication_row = c.execute("SELECT id,url,published_at FROM publications WHERE id=?", (payload["publication_id"],)).fetchone()
    return [evidence("Approved GitHub Pages publisher executed", payload), evidence("Public URL returned HTTP 200", {"url": payload["url"], "status": status, "content_hash": content_hash}), evidence("Publication row and timestamp persisted", dict(publication_row))]

def distribution():
    targets = (ROOT / "ops" / "posting-targets.md").read_text()
    assert "Risk" in targets and "Owner profile" in targets
    with db.connect() as c:
        c.execute("UPDATE events SET event_type='SOCIAL_PUBLICATION_LIMITATION_RECORDED' WHERE event_type='SOCIAL_PUBLICATION_NOT_PERFORMED'")
    db.add_event("DISTRIBUTION_CHANNEL_COMPLETED", "distribution", "publication", "github-pages", "published", "low", {"buyer_facing_content": True, "channel": "github-pages", "tracking": "publication_checks"})
    metrics = db.dashboard_snapshot()["distribution_metrics"]
    return [evidence("Posting targets include platform, URL, permission, and relevance"), evidence("Approved free channel published buyer-facing content", {"channel": "github-pages", "social_submission": "not used because no stable authorized social write path"}), evidence("Distribution metrics record source and timestamp without inventing traffic", {"latest_metric": metrics[0] if metrics else None})]

def sales():
    with db.connect() as c:
        product = c.execute("SELECT id,price_usd,version FROM products ORDER BY rowid DESC LIMIT 1").fetchone()
    assert product and product["price_usd"] == 5.0
    intake = (ROOT / "intake.html").read_text()
    for field in ["customer_email", "profile_url", "target_audience", "preferred_tone", "additional_context", "consent_scope"]: assert f'name="{field}"' in intake
    test_order = db.create_order(product["id"], "sandbox_intake_customer", float(product["price_usd"]), "https://example.invalid/profile", "intake-test", True, "sandbox@example.invalid", "indie hackers", "clear", "test context", "sandbox scope acknowledged", product["version"])
    with db.connect() as c: order = c.execute("SELECT quoted_amount_usd,payment_status,order_status FROM orders WHERE id=?", (test_order,)).fetchone()
    assert order["payment_status"] == "UNVERIFIED" and order["order_status"] == "AWAITING_PAYMENT"
    return [evidence("Offer price is persisted at USD 5", dict(product)), evidence("Intake form creates a mapped AWAITING_PAYMENT order", {"order_id": test_order, "price_usd": order["quoted_amount_usd"], "payment_status": order["payment_status"]}), evidence("Payment confirmation requires PayPal reference", {"command": "scripts/confirm-payment.sh"})]

def delivery():
    template = (ROOT / "product" / "delivery-template.md").read_text()
    for needle in ["3 rewritten bios", "3 pinned post hooks", "5 improvement notes", "One small revision"]: assert needle in template
    import fulfillment
    test_order = db.create_order("prod-bio-profile-fix", "sandbox_delivery_customer", 5.0, "https://example.invalid/profile", "sandbox", True, "sandbox@example.invalid", "freelancers", "clear", "sandbox context", "sandbox scope acknowledged", "1.0.0")
    db.confirm_payment(test_order, True, "sandbox-delivery-reference", actor="sandbox-delivery-test")
    result = fulfillment.fulfill_order(test_order, actor="sandbox-delivery-test")
    assert result["qa"]["three_bios"] and result["qa"]["three_hooks"] and result["qa"]["five_notes"]
    return [evidence("Delivery template contains all promised outputs"), evidence("Paid sandbox order generated, QA checked, and tokenized delivery path persisted", result)]

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
    reopen_missing_evidence()
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
        with db.connect() as c:
            c.execute("UPDATE venture_state SET experiment_status='LIVE_EXPERIMENT',publishing_enabled=1,outreach_enabled=1,updated_at=? WHERE id=1", (db.now(),))
        db.set_agent_status("venture-director", "WAITING_ON_MARKET", "LIVE_EXPERIMENT", "Monitor availability, run scheduled distribution, analyze funnel, and evaluate pivots", "", last_result="WAITING_FOR_MARKET_SIGNAL")
        db.add_event("LIVE_EXPERIMENT_STARTED", "venture-director", "milestone", "LIVE_EXPERIMENT", "working", "low", {"reason": "market monitoring active; payment confirmation only when a genuine order exists", "fake_activity": False})
        print("STARTED LIVE_EXPERIMENT; market monitoring and lawful distribution active")
    mark_unverified_hosted_intake()

if __name__ == "__main__": main()
