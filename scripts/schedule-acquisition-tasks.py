#!/usr/bin/env python3
"""Seed idempotent acquisition tasks in the HP OS task queue."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import venture_db as db

ROOT = Path(__file__).resolve().parents[1]


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def task(agent: str, objective: str, expected: str, scheduled: datetime, key: str, **input_data: object) -> str:
    return db.create_task(
        agent,
        objective,
        expected,
        priority=2,
        input_data={"scheduled_for": scheduled.isoformat(), "timezone": "America/New_York", **input_data},
        idempotency_key=key,
    )


def schedule_post_followups(post_url: str, posted_at: datetime) -> list[str]:
    slug = post_url.rstrip("/").split("/")[-1].replace(":", "-")
    ids = []
    for offset, label in ((timedelta(hours=5), "5h"), (timedelta(hours=24), "24h")):
        ids.append(task(
            "performance", f"Read LinkedIn post analytics at +{label}",
            "Persist impressions, reactions, comments, reposts, profile views, referral visits, CTA clicks, form starts, orders, payments, sales, comparison, and bottleneck",
            posted_at + offset, f"linkedin-analytics-{label}-{slug}", post_url=post_url, check_type=label,
        ))
    return ids


def seed(post_url: str, posted_at: datetime) -> dict:
    db.init_db()
    ids = schedule_post_followups(post_url, posted_at)
    next_window = datetime.fromisoformat("2026-07-14T09:00:00-04:00")
    ids.append(task(
        "distribution", "Find up to five relevant public LinkedIn discussions",
        "At most five non-repetitive value-first comments; stop on warning, rate limit, CAPTCHA, or suspicious activity",
        posted_at + timedelta(hours=24), "linkedin-comments-next-business-pass", max_comments=5, max_age_days=14,
    ))
    ids.append(task(
        "performance", "Complete U.S. business-day acquisition review",
        "Best post/comment, strongest buyer signal, wasted actions, bottleneck, and tomorrow plan persisted",
        posted_at + timedelta(hours=24), "linkedin-daily-review-2026-07-13",
    ))
    ids.append(task(
        "publishing", "Prepare next rotated LinkedIn post in the preferred window",
        "One new content type with a new hook, body, example, and single objective; never publish before 24 hours",
        next_window, "linkedin-next-post-window-2026-07-14", content_rotation=True, approval_required=True,
    ))
    ids.append(task(
        "performance", "Make seven-day acquisition decision",
        "Choose CONTINUE, NARROW_SEGMENT, CHANGE_MESSAGE, CHANGE_CHANNEL, CHANGE_PRICE, CHANGE_OFFER, or TERMINATE from observed metrics and fulfillment quality",
        parse_time("2026-07-19T17:26:38+00:00"), "linkedin-seven-day-decision-2026-07-19",
    ))
    return {"task_ids": ids, "count": len(ids), "timezone": "America/New_York"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-url", default="https://www.linkedin.com/feed/update/urn:li:share:7482152003985633280")
    parser.add_argument("--posted-at", default="2026-07-12T19:22:39+00:00")
    args = parser.parse_args()
    print(json.dumps(seed(args.post_url, parse_time(args.posted_at)), indent=2))
