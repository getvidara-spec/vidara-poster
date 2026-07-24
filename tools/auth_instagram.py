#!/usr/bin/env python3
"""
One-time LOCAL helper: get an Instagram long-lived token + ig_user_id.

Uses the "Instagram API with Instagram Login" flow (no Facebook Page needed).
Prereqs (see README):
  - a Meta app with the "Instagram" product, using Instagram Login
  - @getvidara switched to a Business/Creator account
  - scopes: instagram_business_basic, instagram_business_content_publish
  - an OAuth Redirect URI registered (use https://localhost/)

Run:  IG_APP_ID=... IG_APP_SECRET=... python tools/auth_instagram.py
Prints a JSON block — paste it under "instagram" in tokens.json.
"""
import os
import sys
import json
import time
import urllib.parse
import requests

REDIRECT = os.environ.get("IG_REDIRECT_URI", "https://localhost/")
APP_ID = os.environ["IG_APP_ID"]
APP_SECRET = os.environ["IG_APP_SECRET"]

auth = "https://www.instagram.com/oauth/authorize?" + urllib.parse.urlencode({
    "client_id": APP_ID,
    "redirect_uri": REDIRECT,
    "response_type": "code",
    "scope": "instagram_business_basic,instagram_business_content_publish",
})
print("\n1) Open this URL, log in as @getvidara (Business/Creator), approve:\n")
print("   " + auth + "\n")
print("2) You'll be redirected to  " + REDIRECT + "?code=XXXX")
code = input("3) Paste the value of `code` (drop any trailing '#_'): ").strip()
code = code.split("#")[0].strip()

# short-lived token
r = requests.post("https://api.instagram.com/oauth/access_token", data={
    "client_id": APP_ID, "client_secret": APP_SECRET,
    "grant_type": "authorization_code", "redirect_uri": REDIRECT, "code": code,
}, timeout=30)
d = r.json()
if "access_token" not in d:
    print("ERROR (short token):", json.dumps(d, indent=2)); sys.exit(1)
short = d["access_token"]

# exchange for long-lived (60 days)
r = requests.get("https://graph.instagram.com/access_token", params={
    "grant_type": "ig_exchange_token", "client_secret": APP_SECRET, "access_token": short,
}, timeout=30)
d = r.json()
if "access_token" not in d:
    print("ERROR (long token):", json.dumps(d, indent=2)); sys.exit(1)
long = d["access_token"]
expires = time.time() + int(d.get("expires_in", 5184000))

# fetch ig_user_id
me = requests.get("https://graph.instagram.com/v21.0/me",
                  params={"fields": "user_id,username", "access_token": long}, timeout=30).json()
ig_user_id = me.get("user_id") or me.get("id")

block = {"access_token": long, "expires_at": expires, "ig_user_id": str(ig_user_id)}
print(f"\n(connected as @{me.get('username')})")
print("\n=== paste this under \"instagram\" in tokens.json ===")
print(json.dumps(block, indent=2))
