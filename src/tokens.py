"""
Encrypted token store + auto-refresh.

Tokens live in an encrypted file (tokens.json.enc) committed to the repo.
The GitHub Action decrypts it with TOKEN_ENC_KEY (a repo Secret), refreshes any
token that is close to expiry, uses it, then re-encrypts + commits it back.
This keeps everything self-contained — no external database, no PAT needed.

tokens.json shape:
{
  "tiktok":    {"access_token","refresh_token","access_expires_at","refresh_expires_at"},
  "instagram": {"access_token","expires_at","ig_user_id"}
}
(expiry values are unix epoch seconds)
"""
import json
import os
import time
import base64
import requests
from cryptography.fernet import Fernet

ENC_PATH = os.path.join(os.path.dirname(__file__), "..", "tokens.json.enc")
REFRESH_MARGIN = 3600  # refresh if a token expires within the next hour


# ---------- encryption ----------
def _fernet():
    key = os.environ["TOKEN_ENC_KEY"].strip()
    # allow either a raw Fernet key or any passphrase (we normalise to 32 bytes)
    if len(key) == 44 and key.endswith("="):
        return Fernet(key.encode())
    digest = base64.urlsafe_b64encode(key.encode().ljust(32, b"0")[:32])
    return Fernet(digest)


def load():
    with open(ENC_PATH, "rb") as f:
        return json.loads(_fernet().decrypt(f.read()).decode())


def save(tokens):
    blob = _fernet().encrypt(json.dumps(tokens, indent=2).encode())
    with open(ENC_PATH, "wb") as f:
        f.write(blob)


# ---------- refresh ----------
def ensure_fresh(tokens):
    """Refresh whatever is near expiry. Returns (tokens, changed_bool)."""
    changed = False
    now = time.time()

    tk = tokens.get("tiktok")
    if tk and tk.get("access_expires_at", 0) - now < REFRESH_MARGIN:
        tokens["tiktok"] = _refresh_tiktok(tk)
        changed = True

    ig = tokens.get("instagram")
    if ig and ig.get("expires_at", 0) - now < REFRESH_MARGIN:
        tokens["instagram"] = _refresh_instagram(ig)
        changed = True

    return tokens, changed


def _refresh_tiktok(tk):
    r = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": os.environ["TIKTOK_CLIENT_KEY"],
            "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": tk["refresh_token"],
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"TikTok refresh failed: {d}")
    now = time.time()
    return {
        "access_token": d["access_token"],
        "refresh_token": d.get("refresh_token", tk["refresh_token"]),  # rotates
        "access_expires_at": now + int(d.get("expires_in", 86400)),
        "refresh_expires_at": now + int(d.get("refresh_expires_in", 31536000)),
    }


def _refresh_instagram(ig):
    # long-lived token refresh (returns a fresh 60-day token)
    r = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": ig["access_token"]},
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"IG refresh failed: {d}")
    return {
        "access_token": d["access_token"],
        "expires_at": time.time() + int(d.get("expires_in", 5184000)),
        "ig_user_id": ig["ig_user_id"],
    }
