#!/usr/bin/env python3
"""Externally verify the hosted order path and close the hosted-intake gates."""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
import urllib.request
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import venture_db as db

BASE = os.environ.get("HP_OS_HOSTED_API_URL", "https://hp-os-bio-fix.netlify.app/api/orders")
TOKEN = os.environ["HP_OS_HOSTED_OWNER_TOKEN"]
payload = {"customer_email":"external-verification@example.invalid","profile_url":"https://example.com/verification-profile","target_audience":"freelancers testing profile clarity","preferred_tone":"clear","additional_context":"External acceptance test only.","consent_scope":"External sandbox verification consent.","referral_source":"bio-checklist-external"}
request = urllib.request.Request(BASE, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
with urllib.request.urlopen(request, timeout=20) as response:
    created = json.load(response)
order_id = created["order_id"]
lookup = urllib.request.Request(f"{BASE}/{order_id}", headers={"x-hp-owner-token": TOKEN})
with urllib.request.urlopen(lookup, timeout=20) as response:
    stored = json.load(response)["order"]
assert stored["id"] == order_id and stored["order_status"] == "AWAITING_PAYMENT"
db.init_db()
evidence = {"acceptance_criterion":"Public hosted intake creates and persists a server-side AWAITING_PAYMENT order", "implementation_file":"netlify/functions/orders.mjs + intake.html + scripts/sync-hosted-order.sh", "command_executed":"python3 scripts/verify-hosted-intake.py", "actual_output":json.dumps({"external_post":created,"owner_lookup":stored}, sort_keys=True), "timestamp":db.now(), "persisted_database_record":f"Netlify Blobs key={order_id}; referral_source={stored['referral_source']}", "test_result":"PASS", "failure_or_limitation":"The external acceptance record uses a clearly labelled test email; no payment or revenue is claimed."}
with db.connect() as c:
    for name in ("SALES", "LIVE_READINESS"):
        c.execute("UPDATE milestones SET state='PASSED',evidence_json=?,updated_at=? WHERE name=?", (json.dumps([evidence], sort_keys=True), db.now(), name))
        db.log_event(c, "MILESTONE_PASSED", "quality-assurance", "milestone", name, "PASSED", "low", {"external_order_id": order_id})
    c.execute("UPDATE venture_state SET current_milestone='LIVE_EXPERIMENT',milestone_state='INSPECTING',experiment_status='LIVE_EXPERIMENT',publishing_enabled=1,outreach_enabled=1,updated_at=? WHERE id=1", (db.now(),))
db.set_agent_status("sales", "COMPLETED", "LIVE_EXPERIMENT", "Monitor new hosted orders and referral sources", "", last_result="HOSTED_INTAKE_VERIFIED")
db.set_agent_status("venture-director", "WAITING_ON_MARKET", "LIVE_EXPERIMENT", "Monitor hosted orders, lawful discovery, funnel signals, and pivots", "", last_result="HOSTED_INTAKE_VERIFIED")
print(json.dumps({"ok":True,"order_id":order_id,"public_endpoint":BASE,"payment_state":stored["payment_status"],"milestones":["SALES","LIVE_READINESS"],"experiment_status":"LIVE_EXPERIMENT"}, indent=2))
