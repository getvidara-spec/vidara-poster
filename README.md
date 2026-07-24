# vidara-poster — a free, self-hosted TikTok + Instagram scheduler

A tiny in-house replacement for Metricool's auto-publish, with **no monthly post
cap**. It stores your scheduled posts in this repo and a **free GitHub Actions
cron** fires them at the right time — publishing straight to TikTok and Instagram
through the official APIs. Running cost: **$0**.

It does exactly what we used Metricool for (schedule a vertical video + caption
to TikTok and Instagram Reels, auto-publish), minus the 20-posts/month limit.

---

## ⚠️ Read this first — the honest trade-offs

Escaping the cap is free, but the official APIs impose real setup friction. None
of this is a blocker; it's just work you do once:

1. **TikTok public posting needs an app _audit_.** An un-audited TikTok app can
   only post as **private (SELF_ONLY)**. To post **public** videos (which you
   need for views/rewards) you submit the app for TikTok's audit — free, but can
   take several days. The code posts public automatically once you're audited,
   and falls back to private (so it still works) before then.
2. **Instagram needs a Business/Creator account** (switch @getvidara in the app),
   and for the API to pull your video it must be at a **public URL** — so **this
   repo should be _public_** (raw file URLs on a private repo aren't anonymously
   fetchable). Your secrets are safe: app secrets live only in GitHub Actions
   Secrets, and the access tokens are **encrypted** with a key that also lives
   only in Secrets. Only the videos + captions (which you're posting publicly
   anyway) are visible. Prefer a private repo? Host the videos on a public bucket
   (Cloudflare R2 / S3) instead and put that URL in `schedule.json`.
3. **GitHub cron isn't to-the-second** — it can lag a few minutes (occasionally
   more) under load. Fine for "post around 6 PM," not for exact timing.
4. **Instagram self-publishing works in the app's _Development_ mode** for your
   own account (you as admin/tester) — no full Meta App Review needed. Publishing
   to *other people's* accounts would need App Review; you don't.

---

## What's in here

```
src/run.py          scheduler: find due posts, publish, record result
src/tiktok.py       TikTok Content Posting API (direct byte upload)
src/instagram.py    Instagram Graph API (Reels from a public URL)
src/tokens.py       encrypted token store + auto-refresh
tools/auth_tiktok.py       one-time: mint a TikTok token
tools/auth_instagram.py    one-time: mint an Instagram token
tools/encrypt_tokens.py    encrypt tokens.json -> tokens.json.enc (+ --genkey)
tools/add_post.py          add a post to schedule.json (handles Cairo->UTC)
.github/workflows/publish.yml   the free cron (every 15 min)
schedule.json       your posts
media/              your video files (served publicly via raw URL for IG)
```

---

## Setup (once)

### 0. Put the code in a GitHub repo
Create a **public** repo (e.g. `vidara-poster`), then push this folder to it.
You need Python 3.11+ locally just for the one-time token step.

### 1. TikTok app
1. Go to **developers.tiktok.com** → Manage apps → create an app.
2. Add the **Content Posting API** product; enable **Direct Post**.
3. Add scopes: **`user.info.basic`** and **`video.publish`**.
4. Add a **Redirect URI**: `https://localhost/`.
5. Copy the **Client key** and **Client secret**.
6. Submit the app for **audit** when you're ready to go public (until then posts
   are private). Add @getvidara as a target user in the sandbox to test.

### 2. Instagram app
1. In the Instagram app, switch **@getvidara to a Business or Creator** account.
2. Go to **developers.facebook.com** → create an app → add the **Instagram**
   product using **Instagram Login** (API with Instagram Login).
3. Permissions: **`instagram_business_basic`**, **`instagram_business_content_publish`**.
4. Add an OAuth **Redirect URI**: `https://localhost/`.
5. Under Roles, add yourself/@getvidara as a **tester** and accept, so you can
   publish while the app is in Development mode.
6. Copy the **Instagram App ID** and **App secret**.

### 3. Mint the tokens (local, one time)
```bash
pip install -r requirements.txt

TIKTOK_CLIENT_KEY=xxx TIKTOK_CLIENT_SECRET=yyy python tools/auth_tiktok.py
IG_APP_ID=xxx IG_APP_SECRET=yyy python tools/auth_instagram.py
```
Each prints a JSON block. Copy `tokens.example.json` to `tokens.json` and paste
the two blocks in. Then encrypt it:
```bash
python tools/encrypt_tokens.py --genkey          # -> copy this key
TOKEN_ENC_KEY=<that key> python tools/encrypt_tokens.py   # writes tokens.json.enc
```
Commit **`tokens.json.enc`** (never `tokens.json` — it's git-ignored).

### 4. Add the GitHub Actions Secrets
Repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `TOKEN_ENC_KEY` | the key from `--genkey` |
| `TIKTOK_CLIENT_KEY` | TikTok client key |
| `TIKTOK_CLIENT_SECRET` | TikTok client secret |
| `IG_APP_ID` | Instagram app id |
| `IG_APP_SECRET` | Instagram app secret |

### 5. Turn it on
Repo → **Actions** tab → enable workflows. Click **publish-scheduled-posts** →
**Run workflow** to test immediately (or wait for the 15-min cron).

---

## Everyday use — schedule a post
```bash
python tools/add_post.py \
  --media ~/clips/CoD_G.mp4 \
  --caption "new MW4 Kill Block clip @callofduty
#Ad
#CallOfDuty #MW4 #gaming" \
  --at "2026-08-02 18:00" --tz Africa/Cairo \
  --platforms tiktok,instagram

git add media/ schedule.json && git commit -m "add post" && git push
```
The cron picks it up at the scheduled time, posts to both platforms, and commits
the result back (`status`: `done` / `partial` / `error`, with any error message).

To post to only one platform, use `--platforms tiktok` (or `instagram`).

---

## How it works
- `schedule.json` holds every post with a UTC `publish_at` and a `status`.
- Every 15 min the Action decrypts your tokens, refreshes any that are near
  expiry (TikTok access = 24 h, IG token = 60 days — handled automatically),
  finds posts whose time has passed and are still `scheduled`, and publishes them.
- **TikTok**: uploads the video bytes directly (no domain verification needed).
- **Instagram**: hands IG the public `raw.githubusercontent.com` URL of the file;
  IG downloads + posts it as a Reel.
- Results + rotated tokens are committed back so state persists between runs.

## Limits (all generous / free)
- TikTok: 6 API calls/min per token; a handful of posts/day is fine.
- Instagram: 100 API-published posts per rolling 24 h.
- GitHub Actions: 2,000 free minutes/month; each run is seconds. Effectively free.

## Troubleshooting
- **TikTok post is private** → app not audited yet; that's expected until audit.
- **IG "media not found / not fetchable"** → repo must be **public** so the raw
  URL is anonymous, and give the commit ~1 min to propagate before the post time.
- **`invalid_grant` on refresh** → the refresh token expired (TikTok 365 d, IG
  60 d without use). Re-run the `auth_*` scripts and re-encrypt.
- **Nothing posts** → check the Actions run log; confirm all 5 Secrets are set.

Cost: **$0** on the free tiers. No monthly post cap.
