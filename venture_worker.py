#!/usr/bin/env python3
"""Minimal restartable worker for internal, non-public tasks."""
from __future__ import annotations
import argparse
import json
import time
from datetime import datetime, timezone
import venture_db as db


def is_due(task) -> bool:
    try:
        scheduled = json.loads(task["input_json"]).get("scheduled_for")
        if not scheduled:
            return True
        when = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return when <= datetime.now(timezone.utc)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False

def work_once(task_id: str | None = None) -> int:
    db.init_db()
    with db.connect() as c:
        state = c.execute("SELECT paused, emergency_stop FROM venture_state WHERE id=1").fetchone()
        if state[0] or state[1]:
            db.add_event("WORKER_PAUSED", "worker", "venture", "1", "skipped", "medium", {"paused": bool(state[0]), "emergency_stop": bool(state[1])})
            return 0
        if task_id:
            task = c.execute("SELECT * FROM tasks WHERE id=? AND status='BACKLOG'", (task_id,)).fetchone()
        else:
            candidates = c.execute("SELECT * FROM tasks WHERE status='BACKLOG' ORDER BY priority ASC, created_at ASC").fetchall()
            task = next((candidate for candidate in candidates if is_due(candidate)), None)
        if task is not None and not is_due(task):
            task = None
    if not task:
        db.add_event("WORKER_HEALTHCHECK", "worker", "venture", "1", "idle", "low")
        with db.connect() as c:
            state = c.execute("SELECT current_milestone FROM venture_state WHERE id=1").fetchone()
        if state and state[0] == "LIVE_EXPERIMENT":
            db.set_agent_status("venture-director", "ACQUISITION_ACTIVE", "SCHEDULED_ACQUISITION", "Wait for the next due task; monitor analytics and lawful public discovery", "", last_result="HEALTHCHECK_OK")
        return 0
    db.transition_task(task["id"], "BUILDING", {"worker":"local"}, "QUEUED")
    db.transition_task(task["id"], "COMPLETED", {"worker":"local", "note":"internal task completed; no public side effect"}, "PASSED")
    return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--task-id")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if args.once:
        print(f"Processed {work_once(args.task_id)} task(s)")
    else:
        while True:
            work_once()
            time.sleep(max(1, args.interval))
