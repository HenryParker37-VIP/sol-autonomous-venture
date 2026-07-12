#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
printf "Completed order ID: "; read -r order_id
printf "Feedback text: "; read -r feedback
printf "Permission to publish this feedback? yes/no: "; read -r permission
case "$permission" in yes) status=APPROVED;; no) status=DECLINED;; *) echo "Use yes or no." >&2; exit 2;; esac
PYTHONPATH="$ROOT" python3 - "$order_id" "$feedback" "$status" <<'PY'
import sys
import venture_db as db
db.init_db()
db.record_feedback(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[2] if sys.argv[3] == "APPROVED" else "")
print("Feedback recorded; public text is available only when permission is APPROVED.")
PY
