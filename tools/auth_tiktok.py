#!/usr/bin/env python3
"""
One-time LOCAL helper: get a TikTok access + refresh token.

Prereqs (see README):
  - a TikTok developer app with the "Content Posting API" product and the
    scopes user.info.basic + video.publish
  - a Redirect URI registered on the app (use https://localhost/ for this flow)

Run:  TIKTOK_CLIENT_KEY=... TIKTOK_CLIENT_SECRET=... python tools/auth_tiktok.py
It prints a JSON block — paste it under "tiktok" in tokens.json.
"""
import os
import sys
import json
import time
import urllib.parse
import requests

REDIRECT = os.environ.get("TIKTOK_REDIRECT_URI", "https://localhost/")
CK = os.environ["TIKTOK_CLIENT_KEY"]
CS = os.environ["TIKTOK_CLIENT_SECRET"]

auth = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
    "client_key": CK,
    "scope": "user.info.basic,video.publish",
    "response_type": "code",
    "redirect_uri": REDIRECT,
    "state": "vidara",
})
print("\n1) Open this URL, log in as @getvidara, and approve:\n")
print("   " + auth + "\n")
print("2) You'll be redirected to a URL like  " + REDIRECT + "?code=XXXX&...")
code = input("3) Paste the value of `code` here: ").strip()
# TikTok URL-encodes the code with a trailing '*' sometimes; strip a stray fragment
code = urllib.parse.unquote(code).split("#")[0].strip()

r = requests.post(
    "https://open.tiktokapis.com/v2/oauth/token/",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={
        "client_key": CK,
        "client_secret": CS,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT,
    },
    timeout=30,
)
d = r.json()
if "access_token" not in d:
    print("ERROR:", json.dumps(d, indent=2)); sys.exit(1)

now = time.time()
block = {
    "access_token": d["access_token"],
    "refresh_token": d["refresh_token"],
    "access_expires_at": now + int(d.get("expires_in", 86400)),
    "refresh_expires_at": now + int(d.get("refresh_expires_in", 31536000)),
}
print("\n=== paste this under \"tiktok\" in tokens.json ===")
print(json.dumps(block, indent=2))
