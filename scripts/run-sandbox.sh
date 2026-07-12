#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
cd "$ROOT"
SANDBOX_DB=${VENTURE_DB:-"$ROOT/data/sandbox.sqlite3"}
VENTURE_DB="$SANDBOX_DB" "$PYTHON" scripts/sandbox_workflow.py
