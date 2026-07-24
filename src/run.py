#!/usr/bin/env python3
"""
Scheduler entry point — run by the GitHub Action every 15 minutes.

Reads schedule.json, finds posts whose publish_at is due and still "scheduled",
publishes each to its platforms, records the result, and writes schedule.json +
the refreshed encrypted tokens back. The workflow then commits any changes.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import tokens as tok
import tiktok
import instagram

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCHEDULE = os.path.join(ROOT, "schedule.json")


def now_utc():
    return datetime.now(timezone.utc)


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def raw_url(media_rel):
    """Public GitHub raw URL for a repo file — used as Instagram's video_url."""
    repo = os.environ.get("GITHUB_REPOSITORY", "OWNER/REPO")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{media_rel.lstrip('/')}"


def due(post, now):
    return post.get("status") == "scheduled" and parse_iso(post["publish_at"]) <= now


def main():
    with open(SCHEDULE) as f:
        posts = json.load(f)

    now = now_utc()
    todo = [p for p in posts if due(p, now)]
    if not todo:
        print(f"[{now.isoformat()}] nothing due ({len(posts)} posts total).")
        return

    print(f"[{now.isoformat()}] {len(todo)} post(s) due.")
    tokens = tok.load()
    tokens, _ = tok.ensure_fresh(tokens)

    changed = False
    for p in todo:
        results, errors = {}, {}
        caption = p["caption"]
        media_abs = os.path.join(ROOT, p["media"])

        for platform in p["platforms"]:
            try:
                if platform == "tiktok":
                    if "tiktok" not in tokens:
                        raise RuntimeError("no tiktok token configured")
                    res = tiktok.publish_video(
                        tokens["tiktok"]["access_token"], media_abs, caption)
                elif platform == "instagram":
                    if "instagram" not in tokens:
                        raise RuntimeError("no instagram token configured")
                    ig = tokens["instagram"]
                    res = instagram.publish_reel(
                        ig["access_token"], ig["ig_user_id"], raw_url(p["media"]), caption)
                else:
                    raise RuntimeError(f"unknown platform '{platform}'")
                results[platform] = res
                print(f"  ✓ {p['id']} -> {platform}: {res}")
            except Exception as e:  # noqa: BLE001 keep going for other platforms
                errors[platform] = str(e)
                print(f"  ✗ {p['id']} -> {platform}: {e}")

        p["results"] = results
        p["errors"] = errors
        p["published_at"] = now.isoformat()
        if errors and results:
            p["status"] = "partial"
        elif errors:
            p["status"] = "error"
        else:
            p["status"] = "done"
        changed = True

    if changed:
        with open(SCHEDULE, "w") as f:
            json.dump(posts, f, indent=2)
    # always persist tokens (refresh may have rotated them)
    tok.save(tokens)
    print("done.")


if __name__ == "__main__":
    main()
