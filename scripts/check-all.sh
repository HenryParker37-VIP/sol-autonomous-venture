#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
cd "$ROOT"
"$PYTHON" -m py_compile venture_db.py venture_server.py venture_worker.py scripts/sandbox_workflow.py
for script in scripts/*.sh; do sh -n "$script"; done
"$PYTHON" - <<'PY'
import venture_db as db
db.init_db()
s = db.dashboard_snapshot()
assert len(s['milestones']) == 17
assert len(s['agents']) == 12
assert s['state']['emergency_stop'] == 0
print('PASS: database initialization, milestone registry, agent registry, and controls')
PY
echo "PASS: Python compilation and core smoke test"
