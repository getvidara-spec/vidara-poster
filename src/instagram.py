"""
Instagram publisher — Instagram Graph API, Reels via a public video URL.

Instagram can ONLY publish from a publicly reachable URL (it fetches the file
itself; there is no byte-upload). A GitHub `raw` URL works fine.

We use the "Instagram API with Instagram Login" host (graph.instagram.com),
which does NOT require a linked Facebook Page. The account must be a
Business/Creator account. Scope: instagram_business_content_publish.

Flow:
  1. POST /{ig_user_id}/media   media_type=REELS, video_url, caption -> creation_id
  2. GET  /{creation_id}?fields=status_code  -> poll until FINISHED
  3. POST /{ig_user_id}/media_publish  creation_id -> published media id

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing/
"""
import time
import requests

# Meta bumps the version periodically; keep this current.
GRAPH = "https://graph.instagram.com/v21.0"


def publish_reel(access_token, ig_user_id, video_url, caption, share_to_feed=True):
    # 1. Create the media container
    r = requests.post(
        f"{GRAPH}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
            "access_token": access_token,
        },
        timeout=60,
    )
    _raise(r, "create container")
    creation_id = r.json()["id"]

    # 2. Poll container status (IG downloads + transcodes the video)
    for _ in range(20):  # ~ up to 5 min
        s = requests.get(f"{GRAPH}/{creation_id}",
                         params={"fields": "status_code,status",
                                 "access_token": access_token}, timeout=30)
        _raise(s, "status")
        code = s.json().get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"IG container {code}: {s.json()}")
        time.sleep(15)
    else:
        raise RuntimeError("IG container not FINISHED after ~5 min")

    # 3. Publish
    p = requests.post(f"{GRAPH}/{ig_user_id}/media_publish",
                      data={"creation_id": creation_id, "access_token": access_token},
                      timeout=60)
    _raise(p, "publish")
    return {"ok": True, "media_id": p.json().get("id"), "creation_id": creation_id}


def _raise(resp, stage):
    if resp.status_code >= 400:
        raise RuntimeError(f"IG {stage} failed: {resp.status_code} {resp.text[:400]}")
