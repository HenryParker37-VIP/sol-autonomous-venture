#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
printf "Order ID: "; read -r order_id
printf "Payment confirmed yes/no: "; read -r answer
case "$answer" in yes|no) ;; *) echo "Use yes or no." >&2; exit 2;; esac
python3 - "$ROOT" "$order_id" "$answer" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import venture_db as db
db.init_db()
db.confirm_payment(sys.argv[2], sys.argv[3] == "yes")
print("Payment state recorded. Delivery may begin only when the answer was yes.")
PY
