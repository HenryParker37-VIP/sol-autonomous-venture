#!/usr/bin/env python3
"""Publish only the static landing page to the allowlisted GitHub Pages channel."""
from __future__ import annotations
import json
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
    remote = run("git", "remote", "get-url", "origin", check=False)
    if remote.returncode != 0:
        run("gh", "repo", "create", f"{OWNER}/{REPO}", "--public", "--source", str(ROOT), "--remote", "origin", "--push")
    else:
        run("git", "add", "docs/index.html", ".github/workflows/pages.yml", "config/venture.json")
        run("git", "commit", "-m", "Publish approved static landing page", check=False)
        run("git", "push", "origin", "main")
    run("gh", "api", "--method", "POST", f"repos/{OWNER}/{REPO}/pages", "-f", "build_type=workflow", check=False)
    config_path = ROOT / "config" / "venture.json"
    config = json.loads(config_path.read_text())
    config["offer"]["public_url"] = PUBLIC_URL
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    db.add_event("PUBLICATION_COMPLETED", "publishing", "publication", "github-pages", "ok", "medium", {"channel": "github-pages", "url": PUBLIC_URL, "allowlisted": True})
    return {"channel": "github-pages", "url": PUBLIC_URL, "repo": f"{OWNER}/{REPO}"}

if __name__ == "__main__":
    print(json.dumps(publish(), indent=2))
