#!/usr/bin/env python3
"""Publish only the static landing page to the allowlisted GitHub Pages channel."""
from __future__ import annotations
import json
import hashlib
import shutil
import subprocess
from pathlib import Path
import venture_db as db

ROOT = Path(__file__).resolve().parent
OWNER = "HenryParker37-VIP"
REPO = "sol-autonomous-venture"
REMOTE = f"https://github.com/{OWNER}/{REPO}.git"
PUBLIC_URL = f"https://{OWNER.lower()}.github.io/{REPO}/"

def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)

def publish() -> dict:
    db.init_db()
    with db.connect() as c:
        state = db.guarded_state(c)
        if not state["publishing_enabled"] or state["emergency_stop"]:
            raise PermissionError("publishing control is not enabled or emergency stop is active")
    shutil.copy2(ROOT / "landing-page" / "index.html", ROOT / "docs" / "index.html")
    shutil.copy2(ROOT / "intake.html", ROOT / "docs" / "intake.html")
    remote = run("git", "remote", "get-url", "origin", check=False)
    if remote.returncode != 0:
        run("gh", "repo", "create", f"{OWNER}/{REPO}", "--public", "--source", str(ROOT), "--remote", "origin", "--push")
    else:
        run("git", "add", "docs/index.html", "docs/intake.html", "docs/resources/bio-clarity-checklist.html", ".github/workflows/pages.yml", "config/venture.json")
        run("git", "commit", "-m", "Publish approved static landing page", check=False)
        run("git", "push", "origin", "main")
    run("gh", "api", "--method", "POST", f"repos/{OWNER}/{REPO}/pages", "-f", "build_type=workflow", check=False)
    config_path = ROOT / "config" / "venture.json"
    config = json.loads(config_path.read_text())
    config["offer"]["public_url"] = PUBLIC_URL
    config["offer"]["intake_url"] = PUBLIC_URL + "intake.html"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    publication_id = db.record_publication("github-pages", PUBLIC_URL, "landing-page/index.html + intake.html + resources/bio-clarity-checklist.html", "AUTO_APPROVED", "medium", rollback_ref=f"git:{REPO}:main")
    db.update_product_publication(PUBLIC_URL)
    db.add_event("PUBLICATION_COMPLETED", "publishing", "publication", publication_id, "ok", "medium", {"channel": "github-pages", "url": PUBLIC_URL, "allowlisted": True, "timestamped": True})
    db.record_distribution_metric("github-pages", "public-landing-page", notes="Publication is measurable; visitor counts remain unknown until analytics evidence exists")
    return {"channel": "github-pages", "url": PUBLIC_URL, "intake_url": PUBLIC_URL + "intake.html", "repo": f"{OWNER}/{REPO}", "publication_id": publication_id}

if __name__ == "__main__":
    print(json.dumps(publish(), indent=2))
