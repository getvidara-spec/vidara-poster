#!/usr/bin/env python3
"""
Add a post to schedule.json (and copy its video into media/).

Example:
  python tools/add_post.py \
      --media ~/clips/CoD_G.mp4 \
      --caption "new MW4 Kill Block clip @callofduty
#Ad
#CallOfDuty #MW4" \
      --at "2026-07-31 18:00" --tz Africa/Cairo \
      --platforms tiktok,instagram

Times are entered in --tz and stored as UTC. Then: commit media/ + schedule.json.
"""
import argparse
import json
import os
import re
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCHEDULE = os.path.join(ROOT, "schedule.json")
MEDIA_DIR = os.path.join(ROOT, "media")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True, help="path to the video file")
    ap.add_argument("--caption", required=True)
    ap.add_argument("--at", required=True, help='local time "YYYY-MM-DD HH:MM"')
    ap.add_argument("--tz", default="Africa/Cairo")
    ap.add_argument("--platforms", default="tiktok,instagram")
    ap.add_argument("--id", default=None)
    args = ap.parse_args()

    os.makedirs(MEDIA_DIR, exist_ok=True)
    fname = os.path.basename(args.media)
    dest = os.path.join(MEDIA_DIR, fname)
    if os.path.abspath(args.media) != os.path.abspath(dest):
        shutil.copy2(args.media, dest)

    local = datetime.strptime(args.at, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(args.tz))
    publish_at = local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    pid = args.id or re.sub(r"\W+", "_", os.path.splitext(fname)[0]).lower()
    post = {
        "id": pid,
        "platforms": [p.strip() for p in args.platforms.split(",") if p.strip()],
        "media": f"media/{fname}",
        "caption": args.caption,
        "publish_at": publish_at,
        "status": "scheduled",
    }

    posts = []
    if os.path.exists(SCHEDULE):
        with open(SCHEDULE) as f:
            posts = json.load(f)
    posts = [p for p in posts if p.get("id") != pid]  # replace same id
    posts.append(post)
    posts.sort(key=lambda p: p["publish_at"])
    with open(SCHEDULE, "w") as f:
        json.dump(posts, f, indent=2)

    print(f"Added '{pid}' for {publish_at} (UTC)  ->  {post['platforms']}")
    print("Now: git add media/ schedule.json && git commit && git push")


if __name__ == "__main__":
    main()
