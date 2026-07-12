#!/usr/bin/env python3
"""Exercise the real order path without pretending a buyer or payment exists."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import venture_db as db
import fulfillment

db.init_db()
with db.connect() as c:
    c.execute("DELETE FROM products")
    c.execute("DELETE FROM opportunities")
    c.execute("DELETE FROM orders")
    c.execute("DELETE FROM events WHERE event_type LIKE 'SANDBOX_%'")
    c.execute("INSERT INTO products(id,name,description,target_buyer,price_usd,version,files_json,public_url,build_status,qa_status) VALUES(?,?,?,?,?,?,?,?,?,?)", ("prod-bio-fix","$5 Bio Fix + Pinned Hook Pack","Manual profile copy improvement delivered within 24 hours","Creators and freelancers",5.0,"1.0.0",json.dumps(["product/intake.md","product/delivery-template.md"]),"https://henryparker37-vip.github.io/sol-autonomous-venture/","BUILT","PASSED"))
    c.execute("INSERT INTO opportunities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("opp-bio-fix","$5 Bio Fix service","Creators with vague profiles","Unclear bios reduce response clarity","Public profile pain points","Free alternatives exist",2.0,"Public creator communities",5.0,0.0,"Low legal risk; outreach risk controlled",0.78,"",1))
    db.log_event(c,"SANDBOX_PRODUCT_CREATED","sandbox","product","prod-bio-fix","ok","low",{"revenue_counted":False})
oid = db.create_order("prod-bio-fix", "sandbox_customer_001", 5.0, "https://example.invalid/profile", "sandbox@example.invalid", is_sandbox=True, customer_email="sandbox@example.invalid", target_audience="freelancers", preferred_tone="clear", additional_context="sandbox context", consent_scope="sandbox scope acknowledged", purchased_version="1.0.0")
db.add_event("SANDBOX_ORDER_CREATED", "sandbox", "order", oid, "ok", "low", {"revenue_counted": False})
with db.connect() as c:
    order = c.execute("SELECT payment_status FROM orders WHERE id=?", (oid,)).fetchone()
    assert order[0] == "UNVERIFIED"
db.add_event("SANDBOX_PAYMENT_REMAINED_UNVERIFIED", "sandbox", "order", oid, "ok", "low", {"revenue_counted": False})
db.confirm_payment(oid, True, "sandbox-paypal-reference", actor="sandbox-authorized-test")
with db.connect() as c:
    order = c.execute("SELECT payment_status,order_status FROM orders WHERE id=?", (oid,)).fetchone()
    assert order[0] == "PAID" and order[1] == "PAID"
db.add_event("SANDBOX_DELIVERY_PREPARED", "sandbox", "order", oid, "ok", "low", {"revenue_counted": False, "delivery_template": "product/delivery-template.md"})
delivery = fulfillment.fulfill_order(oid, actor="sandbox-authorized-test")
assert delivery["qa"]["three_bios"] and delivery["qa"]["three_hooks"] and delivery["qa"]["five_notes"]
with db.connect() as c:
    paid = c.execute("SELECT COALESCE(SUM(quoted_amount_usd),0) FROM orders WHERE payment_status='PAID' AND is_sandbox=1").fetchone()[0]
    assert paid == 5.0
db.add_event("SANDBOX_REVENUE_EXCLUDED", "sandbox", "venture", "1", "ok", "low", {"excluded_amount_usd": paid})
print(f"PASS: sandbox order {oid} completed through authorized test confirmation; sandbox revenue excluded from live metrics")
