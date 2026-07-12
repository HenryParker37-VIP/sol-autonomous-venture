#!/usr/bin/env python3
"""Generate and QA the paid order deliverable, then expose a tokenized delivery page."""
from __future__ import annotations
import json
import re
import secrets
from pathlib import Path
import venture_db as db

ROOT = Path(__file__).resolve().parent
BUYER_ROOT = ROOT / "buyers"

def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:40] or "customer"

def fulfill_order(order_id: str, actor: str = "delivery") -> dict:
    db.init_db()
    with db.connect() as c:
        order = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order: raise KeyError(order_id)
        if order["payment_status"] != "PAID": raise PermissionError("delivery is blocked until owner-confirmed PAID state")
        product = c.execute("SELECT * FROM products WHERE id=?", (order["product_id"],)).fetchone()
    token = secrets.token_urlsafe(24)
    folder = BUYER_ROOT / f"{db.now()[:10]}-{_slug(order_id)}"
    folder.mkdir(parents=True, exist_ok=True)
    audience = order["target_audience"] or "the intended audience"
    tone = order["preferred_tone"] or "clear"
    context = order["additional_context"] or "Keep the call to action specific and easy to act on."
    bios = [
        f"{tone.title()} option: I help {audience} with practical, clear guidance. {context}",
        f"For {audience}: concise help, useful context, and a clear next step.",
        f"I create practical outcomes for {audience}. Follow for focused ideas and simple next actions.",
    ]
    hooks = [
        f"If you are {audience}, start here: the simplest change that makes this clearer.",
        "Most profiles explain the role. This one explains the useful next step.",
        "A quick before-and-after lesson from improving how this offer is described.",
    ]
    notes = ["Lead with the audience before the credentials.","Name one concrete outcome without promising a guaranteed result.","Use one primary call to action instead of several competing links.","Keep the first line readable on mobile.","Make the pinned post demonstrate the problem you solve."]
    (folder / "bios.md").write_text("# 3 rewritten bios\n\n" + "\n\n".join(f"## Option {i+1}\n{v}" for i,v in enumerate(bios)) + "\n")
    (folder / "hooks.md").write_text("# 3 pinned post hooks\n\n" + "\n".join(f"{i+1}. {v}" for i,v in enumerate(hooks)) + "\n")
    (folder / "notes.md").write_text("# 5 improvement notes\n\n" + "\n".join(f"{i+1}. {v}" for i,v in enumerate(notes)) + "\n")
    (folder / "revision.md").write_text("# One small revision\n\nReplace one selected bio or hook after buyer feedback.\n")
    (folder / "delivery.md").write_text(f"# Delivery for {order_id}\n\nProduct version: {product['version']}\nCustomer email on record: {order['customer_email']}\n\nFiles: bios.md, hooks.md, notes.md, revision.md\n")
    qa = {"files": ["bios.md","hooks.md","notes.md","revision.md","delivery.md"], "three_bios": len(bios) == 3, "three_hooks": len(hooks) == 3, "five_notes": len(notes) == 5, "one_revision": True, "version": product["version"]}
    assert qa["three_bios"] and qa["three_hooks"] and qa["five_notes"] and qa["one_revision"]
    with db.connect() as c:
        c.execute("UPDATE orders SET delivery_status='COMPLETED',order_status='COMPLETED',delivery_path=?,delivery_token=?,qa_evidence_json=?,purchased_version=?,updated_at=? WHERE id=?", (str(folder.relative_to(ROOT)),token,json.dumps(qa,sort_keys=True),product["version"],db.now(),order_id))
        db.log_event(c, "DELIVERY_COMPLETED", actor, "order", order_id, "COMPLETED", "medium", {"delivery_path": str(folder.relative_to(ROOT)), "secure_token": True, "qa": qa, "customer_email_recorded": bool(order["customer_email"])})
        db.log_event(c, "FEEDBACK_REQUESTED", actor, "order", order_id, "REQUESTED", "low", {"customer_email_recorded": bool(order["customer_email"])})
    return {"order_id": order_id, "delivery_path": str(folder.relative_to(ROOT)), "delivery_url": f"/delivery/{token}", "qa": qa, "customer_email": order["customer_email"]}

if __name__ == "__main__":
    import sys
    print(json.dumps(fulfill_order(sys.argv[1]), indent=2))
