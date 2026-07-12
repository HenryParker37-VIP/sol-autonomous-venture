#!/usr/bin/env python3
"""Small local control center. No third-party runtime required."""
from __future__ import annotations
import json
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
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/venture", "/venture/"):
            raw = (ROOT / "dashboard" / "index.html").read_bytes(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if path == "/favicon.ico":
            self.send_response(204); self.end_headers(); return
        if path == "/api/health": self.send_json({"ok": True, "db": str(db.DB_PATH)}); return
        if path == "/api/snapshot": self.send_json(db.dashboard_snapshot()); return
        self.send_error(404)
    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0")); body = json.loads(self.rfile.read(length) or b"{}")
        try:
            if path == "/api/control": db.set_control(body["control"], bool(body["value"])); self.send_json({"ok":True}); return
            if path == "/api/event": db.add_event(body["event_type"], body.get("actor","dashboard"), body.get("entity_type","venture"), body.get("entity_id","1"), body.get("result","ok"), body.get("risk_level","low"), body.get("details",{})); self.send_json({"ok":True}); return
            self.send_error(404)
        except (KeyError, ValueError, PermissionError) as exc: self.send_json({"ok":False,"error":str(exc)}, 400)

def main():
    db.init_db(); server = ThreadingHTTPServer(("127.0.0.1", 7100), Handler); print("Venture control center: http://127.0.0.1:7100/venture", flush=True); server.serve_forever()

if __name__ == "__main__": main()
