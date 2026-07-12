#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
printf "Profile link: "; read -r profile
printf "Buyer email or DM platform: "; read -r contact
python3 - "$ROOT" "$profile" "$contact" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import venture_db as db
db.init_db()
with db.connect() as c:
    product = c.execute("SELECT id, price_usd FROM products ORDER BY rowid DESC LIMIT 1").fetchone()
if not product:
    raise SystemExit("No product is registered yet.")
oid = db.create_order(product[0], "customer_pending", float(product[1]), sys.argv[2], sys.argv[3])
print(f"Created {oid} in AWAITING_PAYMENT. Do not deliver until owner confirmation.")
PY
