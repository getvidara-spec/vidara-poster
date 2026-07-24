"""
TikTok publisher — Content Posting API (Direct Post), FILE_UPLOAD source.

Why FILE_UPLOAD and not PULL_FROM_URL:
  PULL_FROM_URL requires the video's domain to be verified in the TikTok
  developer portal (you must own the domain). We can't verify a GitHub URL,
  so we upload the raw bytes directly instead — no domain verification needed.

Docs: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
"""
import os
import time
import requests

API = "https://open.tiktokapis.com"


def _auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"}


def query_creator_info(access_token):
    """Required before a Direct Post: returns allowed privacy levels + limits."""
    r = requests.post(f"{API}/v2/post/publish/creator_info/query/",
                      headers=_auth_headers(access_token), timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok creator_info error: {data['error']}")
    return data.get("data", {})


def publish_video(access_token, file_path, caption,
                  privacy="PUBLIC_TO_EVERYONE",
                  disable_comment=False, disable_duet=False, disable_stitch=False):
    """
    Full Direct Post flow:
      1. creator_info/query  -> confirm the chosen privacy level is allowed
      2. video/init/         -> get publish_id + upload_url (FILE_UPLOAD)
      3. PUT bytes           -> single chunk (our clips are small)
      4. status/fetch/       -> poll until PUBLISH_COMPLETE
    Returns the final publish status dict.

    NOTE: Until your TikTok app passes AUDIT, posts are forced to SELF_ONLY
    (private). Public posting requires the app to be audited by TikTok.
    """
    info = query_creator_info(access_token)
    allowed = info.get("privacy_level_options") or []
    if allowed and privacy not in allowed:
        # App not audited yet -> only SELF_ONLY is available. Fall back so the
        # call still succeeds (the post will be private until you're audited).
        privacy = "SELF_ONLY" if "SELF_ONLY" in allowed else allowed[0]

    size = os.path.getsize(file_path)
    body = {
        "post_info": {
            "title": caption[:2200],
            "privacy_level": privacy,
            "disable_comment": disable_comment,
            "disable_duet": disable_duet,
            "disable_stitch": disable_stitch,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,        # single chunk (clips are < 64 MB)
            "total_chunk_count": 1,
        },
    }
    r = requests.post(f"{API}/v2/post/publish/video/init/",
                      headers=_auth_headers(access_token), json=body, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init error: {data['error']}")
    publish_id = data["data"]["publish_id"]
    upload_url = data["data"]["upload_url"]

    # 3. Upload the bytes (single chunk)
    with open(file_path, "rb") as f:
        video_bytes = f.read()
    put_headers = {
        "Content-Type": "video/mp4",
        "Content-Length": str(size),
        "Content-Range": f"bytes 0-{size - 1}/{size}",
    }
    up = requests.put(upload_url, headers=put_headers, data=video_bytes, timeout=300)
    if up.status_code not in (200, 201, 206):
        raise RuntimeError(f"TikTok upload failed: {up.status_code} {up.text[:300]}")

    # 4. Poll status
    return _poll_status(access_token, publish_id)


def _poll_status(access_token, publish_id, tries=20, delay=6):
    last = None
    for _ in range(tries):
        r = requests.post(f"{API}/v2/post/publish/status/fetch/",
                          headers=_auth_headers(access_token),
                          json={"publish_id": publish_id}, timeout=30)
        r.raise_for_status()
        data = r.json().get("data", {})
        last = data
        status = data.get("status")
        if status in ("PUBLISH_COMPLETE",):
            return {"ok": True, "status": status, "publish_id": publish_id,
                    "post_id": (data.get("publicaly_available_post_id") or
                                data.get("publicly_available_post_id"))}
        if status in ("FAILED",):
            raise RuntimeError(f"TikTok publish FAILED: {data}")
        time.sleep(delay)
    return {"ok": False, "status": last.get("status") if last else "TIMEOUT",
            "publish_id": publish_id, "detail": last}
