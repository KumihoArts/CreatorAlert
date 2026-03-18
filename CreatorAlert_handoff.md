# CreatorAlert — New Bot Handoff Document

## Context
This document is for building **CreatorAlert**, a new Discord bot that notifies users when Patreon creators they follow post new content. It is being built by Daniël (Discord: Sly, user ID `244962442008854540`), who also built **AniAlarm** — a fully deployed anime tracking bot. CreatorAlert should follow the same architecture and workflow patterns as AniAlarm.

---

## Developer Info
- **Name:** Daniël / Sly
- **GitHub:** KumihoArts
- **Bot owner Discord ID:** `244962442008854540`
- **Local project root:** `C:\Tools\` (new bot should go in `C:\Tools\CreatorAlert\`)
- **Filesystem access:** Claude has direct access to `C:\`, `D:\`, `F:\`, `G:\`

---

## AniAlarm Architecture (reference for CreatorAlert)

AniAlarm runs as **two Railway services** from the same GitHub repo:

### Service 1 — Bot (`main.py`)
- Python, discord.py 2.3+, asyncpg for PostgreSQL
- All slash commands defined in `main.py`
- Background tasks started in `on_ready`
- Railway config: `railway.json` in root, start command `python main.py`

### Service 2 — Flask OAuth server (`auth/main.py`)
- Flask + Gunicorn, handles OAuth callbacks and webhooks
- Root directory set to `/auth` in Railway service settings
- Config: `auth/railway.toml`, start command `gunicorn main:app --workers 2 --bind 0.0.0.0:5000`
- Handles: `/connect`, `/callback`, `/vote`, `/health` routes

### Shared database
- PostgreSQL on Railway, shared between both services via `DATABASE_URL` env var
- asyncpg connection pool in `bot/db.py`
- Tables initialised on bot startup via `init_db()`

---

## Deployment Workflow
- GitHub repo with branch protection on `main`
- All work on `dev` branch, merged to `main` via PR
- Railway auto-deploys from `main`
- GitHub CLI (`gh`) is installed and authenticated

**Standard deploy command:**
```bash
cd C:\Tools\CreatorAlert
git checkout dev
git add .
git commit -m "your message"
git push
gh pr create --base main --head dev --title "your message" --body ""
gh pr merge --merge --delete-branch=false
```

---

## Railway Environment Variables Pattern

**Bot service:**
- `DISCORD_TOKEN`
- `DATABASE_URL` (linked from Postgres service)
- Any OAuth redirect URIs the bot needs to build links

**Flask/auth service:**
- `DATABASE_URL` (same Postgres)
- OAuth client credentials
- Webhook secrets
- `PORT=5000`

---

## Premium System Pattern (AniAlarm reference)
AniAlarm uses Discord's built-in entitlement system (SKU-based). For CreatorAlert, Patreon subscriptions are the monetisation model instead — so the premium check will be different (check if user has an active Patreon subscription to a specific tier, or use a hardcoded bypass set).

**Hardcoded bypass IDs for CreatorAlert** (always have premium):
- `244962442008854540` — Sly (bot owner)
- `927037270098341919` — heavenlywits

---

## Key Lessons from AniAlarm Build

### File editing — CRITICAL
- **Never use `Filesystem:write_file` to make partial edits** — it overwrites the entire file
- Correct workflow for edits:
  1. `Filesystem:copy_file_user_to_claude` to copy file to Claude's computer
  2. Edit using `bash_tool` with Python string replacement or `sed`
  3. Verify the result
  4. `Filesystem:write_file` only when you have the complete correct content ready
- `str_replace` tool does NOT support Windows paths — can't use it directly on user files

### Railway gotchas
- `railway.json` in root applies to ALL services — use per-service root directory setting to isolate the Flask service
- Flask service root directory must be set to `/auth` in Railway → Settings → Source → Root Directory
- `RAILWAY_RUN_COMMAND` env var does NOT reliably override the start command — use `railway.toml` instead
- Railway labels all PostgreSQL output as "error" severity — checkpoint logs are harmless

### AniList OAuth lessons (relevant for Patreon OAuth)
- Redirect URI in developer settings must match EXACTLY (no trailing slash, correct https://)
- `client_id` must be sent as integer not string in token exchange requests
- URL-encode the redirect_uri parameter when building the authorize URL using `urlencode()`
- The `invalid_client` error almost always means the redirect URI doesn't match

### Flask/Gunicorn
- Flask development server is single-threaded — use Gunicorn in production
- `flask-cors` is needed for cross-origin POST requests (e.g. vote webhooks)
- Gunicorn start: `gunicorn main:app --workers 2 --bind 0.0.0.0:5000`

---

## CreatorAlert — What We Want to Build

### Two modes:
1. **Creator mode** — Creator adds bot to their Discord server, connects their Patreon, bot posts in a channel when they publish a new update
2. **Subscriber mode** — Regular user connects their Patreon account, bot DMs or pings them when any creator they back posts something new

### Core flow:
- Patreon OAuth2 for account linking (same Flask server pattern as AniAlarm's AniList OAuth)
- PostgreSQL to store connected accounts and seen post IDs
- Scheduler that polls Patreon API periodically for new posts
- Discord bot handling commands and notifications

### Patreon API notes:
- Official API at `patreon.com/portal/registration/register-clients`
- OAuth2 Authorization Code flow (same as AniList)
- Can fetch a user's followed campaigns and their recent posts
- Rate limits apply — polling interval should be reasonable (every 5-15 minutes)

---

## File Structure to Create

```
C:\Tools\CreatorAlert\
  main.py                 — Bot entry point, all slash commands
  railway.json            — Bot service Railway config
  requirements.txt        — Bot dependencies
  .env                    — Local secrets (gitignored)
  .env.example            — Placeholder template
  .gitignore
  auth/
    main.py               — Flask OAuth server for Patreon
    requirements.txt      — Flask service dependencies
    railway.toml          — Flask service Railway config (root dir = /auth)
  bot/
    db.py                 — PostgreSQL layer
    patreon.py            — Patreon API client
    scheduler.py          — Background polling loop
    premium.py            — Premium/bypass checks
  assets/
    CreatorAlert.png      — Bot logo
  legal/
    TERMS_OF_SERVICE.md
    PRIVACY_NOTICE.md
  README.md
  LICENSE
```

---

## Starting Point for New Chat

In the new conversation, paste this document and say:
> "I want to build CreatorAlert — a Discord bot for Patreon creator notifications. Here's my handoff document with all the context. Let's start from scratch, following the same architecture as AniAlarm."

Claude will then have full context to start building immediately.
