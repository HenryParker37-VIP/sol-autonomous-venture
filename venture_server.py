#!/usr/bin/env python3
"""Small local control center. No third-party runtime required."""
from __future__ import annotations
import json
import hashlib
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import venture_db as db

ROOT = Path(__file__).resolve().parent

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): return
    def send_json(self, payload, status=200):
        raw = json.dumps(payload, default=str).encode()
        self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def send_file(self, path: Path, content_type: str):
        raw = path.read_bytes(); self.send_response(200); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/venture", "/venture/"):
            self.send_file(ROOT / "dashboard" / "index.html", "text/html; charset=utf-8"); return
        if path in ("/intake", "/intake/"):
            self.send_file(ROOT / "intake.html", "text/html; charset=utf-8"); return
        if path.startswith("/delivery/"):
            token = path.rsplit("/", 1)[-1]
            with db.connect() as c:
                order = c.execute("SELECT delivery_path,delivery_status FROM orders WHERE delivery_token=? AND payment_status='PAID'", (token,)).fetchone()
            if not order or order["delivery_status"] != "COMPLETED": self.send_error(404); return
            delivery_file = ROOT / order["delivery_path"] / "delivery.md"
            if not delivery_file.is_file(): self.send_error(404); return
            self.send_file(delivery_file, "text/markdown; charset=utf-8"); return
        if path == "/favicon.ico":
            self.send_response(204); self.end_headers(); return
        if path == "/api/health": self.send_json({"ok": True, "db": str(db.DB_PATH)}); return
        if path == "/api/snapshot": self.send_json(db.dashboard_snapshot()); return
        self.send_error(404)
    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0")); body = json.loads(self.rfile.read(length) or b"{}")
        try:
            if path == "/api/orders":
                required = ["customer_email","profile_url","target_audience","preferred_tone","consent_scope"]
                missing = [key for key in required if not str(body.get(key, "")).strip()]
                if missing: raise ValueError("missing required fields: " + ", ".join(missing))
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", body["customer_email"]): raise ValueError("invalid customer email")
                if not str(body["profile_url"]).startswith(("http://", "https://")): raise ValueError("profile URL must be public http(s)")
                with db.connect() as c: product = c.execute("SELECT id,price_usd,version FROM products ORDER BY rowid DESC LIMIT 1").fetchone()
                if not product: raise ValueError("offer is not ready")
                order_id = db.create_order(product["id"], "customer_" + hashlib.sha256(body["customer_email"].encode()).hexdigest()[:10], product["price_usd"], body["profile_url"], body.get("contact_channel", "intake-form"), bool(body.get("sandbox", False)), body["customer_email"], body["target_audience"], body["preferred_tone"], body.get("additional_context", ""), body["consent_scope"], product["version"], body.get("referral_source", "direct"))
                db.add_event("ORDER_CREATED", "public-intake", "order", order_id, "AWAITING_PAYMENT", "low", {"referral_source": body.get("referral_source", "direct")})
                self.send_json({"ok": True, "order_id": order_id, "price_usd": product["price_usd"], "payment_state": "AWAITING_PAYMENT", "payment_url": db.offer_config().get("offer", {}).get("paypal_url", ""), "payment_instruction": f"Pay via the public PayPal link and include order ID {order_id} in the PayPal note/reference."}); return
            if path == "/api/owner/confirm-payment":
                db.confirm_payment(body["order_id"], bool(body.get("confirmed")), body.get("paypal_reference", ""), actor="owner")
                self.send_json({"ok": True, "order_id": body["order_id"], "payment_state": "PAID" if body.get("confirmed") else "NOT_PAID"}); return
            if path == "/api/control": db.set_control(body["control"], bool(body["value"])); self.send_json({"ok":True}); return
            if path == "/api/event": db.add_event(body["event_type"], body.get("actor","dashboard"), body.get("entity_type","venture"), body.get("entity_id","1"), body.get("result","ok"), body.get("risk_level","low"), body.get("details",{})); self.send_json({"ok":True}); return
            self.send_error(404)
        except (KeyError, ValueError, PermissionError) as exc: self.send_json({"ok":False,"error":str(exc)}, 400)

def main():
    db.init_db(); server = ThreadingHTTPServer(("127.0.0.1", 7100), Handler); print("Venture control center: http://127.0.0.1:7100/venture", flush=True); server.serve_forever()

if __name__ == "__main__": main()
