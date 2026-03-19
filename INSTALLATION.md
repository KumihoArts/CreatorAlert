# CreatorAlert — Installation Guide

This guide covers everything needed to run your own instance of CreatorAlert. If you just want to use the bot, [invite it here](https://discord.com/oauth2/authorize?client_id=1483970800477409422&permissions=277025392640&scope=bot+applications.commands) instead.

---

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 14 or higher
- A [Discord Developer account](https://discord.com/developers/applications)
- A [Patreon Developer account](https://www.patreon.com/portal/registration/register-clients)
- A [Railway account](https://railway.app) (or another hosting provider)

---

## Step 1 — Clone the repository

```bash
git clone https://github.com/KumihoArts/CreatorAlert.git
cd CreatorAlert
```

---

## Step 2 — Create a Discord bot application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Go to the **Bot** tab
4. Click **Reset Token** and copy the token — this is your `DISCORD_TOKEN`
5. Under **Privileged Gateway Intents**, leave all three intents **off** (CreatorAlert does not need them)
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot` + `applications.commands`
   - Bot permissions: `Send Messages`, `Send Messages in Threads`, `Embed Links`
7. Copy the generated URL to invite the bot to your server

---

## Step 3 — Register a Patreon OAuth client

1. Go to [patreon.com/portal/registration/register-clients](https://www.patreon.com/portal/registration/register-clients)
2. Fill in the form:
   - **App Name:** your bot name
   - **Description:** a short description
   - **Redirect URI:** `https://your-auth-service-url/callback` (you'll update this after deployment)
   - **Client API Version:** 2
3. After creating the client, copy the **Client ID** and **Client Secret**

---

## Step 4 — Set up environment variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Fill in the values:

```env
DISCORD_TOKEN=        # From Step 2
DATABASE_URL=         # Your PostgreSQL connection string
AUTH_BASE_URL=        # The public URL of your auth service (from Step 6)
TEST_GUILD_ID=        # Optional: your test server ID for instant command sync
PATREON_CLIENT_ID=    # From Step 3
PATREON_CLIENT_SECRET=# From Step 3
DBL_TOKEN=            # Optional: your discordbotlist.com API token
```

For the auth service, copy `auth/.env.example` to `auth/.env`:

```env
DATABASE_URL=              # Same as above
PATREON_CLIENT_ID=         # Same as above
PATREON_CLIENT_SECRET=     # Same as above
PATREON_REDIRECT_URI=      # https://your-auth-service-url/callback
FLASK_SECRET_KEY=          # Any long random string
```

---

## Step 5 — Install dependencies

**Bot service:**
```bash
pip install -r requirements.txt
```

**Auth service:**
```bash
pip install -r auth/requirements.txt
```

---

## Step 6 — Deploy on Railway

CreatorAlert runs as two separate Railway services from the same GitHub repository.

### Create the project

1. Go to [railway.app](https://railway.app) and create a **New Project**
2. Select **Deploy from GitHub repo** and connect `KumihoArts/CreatorAlert`

### Add a PostgreSQL database

Inside the project, click **New Service → Database → PostgreSQL**. Once created, note the `DATABASE_URL` from the service's **Variables** tab.

### Configure the Bot service

In the auto-created service from your repo:
- **Name:** `bot`
- **Root Directory:** `/` (default)
- **Branch:** `main`
- **Start command:** handled by `railway.json` automatically

Add these environment variables:
| Variable | Value |
|---|---|
| `DISCORD_TOKEN` | Your bot token |
| `DATABASE_URL` | Link from PostgreSQL service (`${{Postgres.DATABASE_URL}}`) |
| `AUTH_BASE_URL` | Your auth service public URL (set after Step 6c) |
| `PATREON_CLIENT_ID` | Your Patreon client ID |
| `PATREON_CLIENT_SECRET` | Your Patreon client secret |
| `TEST_GUILD_ID` | Optional: your test server ID |
| `DBL_TOKEN` | Optional: discordbotlist.com token |

### Configure the Auth service

Add a second service to the same Railway project:
- **New Service → GitHub Repo** → same repo
- **Name:** `auth`
- **Root Directory:** `/auth`
- **Branch:** `main`

Railway will automatically use `auth/railway.toml` for the start command.

Add these environment variables:
| Variable | Value |
|---|---|
| `DATABASE_URL` | Link from PostgreSQL service (`${{Postgres.DATABASE_URL}}`) |
| `PATREON_CLIENT_ID` | Your Patreon client ID |
| `PATREON_CLIENT_SECRET` | Your Patreon client secret |
| `PATREON_REDIRECT_URI` | `https://your-auth-domain/callback` |
| `FLASK_SECRET_KEY` | Any long random string |

### Generate a public domain for the Auth service

In the auth service → **Settings → Networking → Generate Domain**. This gives you the public URL (e.g. `https://auth-xxxx.up.railway.app`).

- Set this as `AUTH_BASE_URL` in the bot service variables
- Set `https://your-auth-domain/callback` as `PATREON_REDIRECT_URI` in the auth service variables
- Go back to your Patreon OAuth client and update the **Redirect URI** to match exactly

> **Important:** Do not assign a public domain to the bot service — only the auth service needs one.

---

## Step 7 — Verify deployment

Check the bot service logs. A successful startup looks like:

```
Logged in as YourBot#1234 (123456789)
Database initialised.
Commands synced to test guild ...
Scheduler started.
```

Check the auth service logs for:
```
Starting gunicorn 25.x.x
Listening at: http://0.0.0.0:8080
```

Visit `https://your-auth-domain/health` — it should return `{"status": "ok"}`.

---

## Step 8 — Test the bot

1. Invite the bot to your server using the OAuth2 URL from Step 2
2. Run `/connect` — you should receive an embed with a Patreon link
3. Click the link and authorise — you should see the success page
4. Run `/status` — should show your connected Patreon account

---

## Keeping the bot up to date

The recommended workflow:

```bash
git checkout dev        # work on dev branch
# make your changes
git add .
git commit -m "your message"
git push
gh pr create --base main --head dev --title "your message" --body ""
gh pr merge --merge --delete-branch=false
```

Railway auto-deploys both services whenever `main` is updated.

---

## Architecture overview

```
CreatorAlert/
  main.py              — Discord bot, all slash commands, scheduler startup
  railway.json         — Bot service Railway config
  requirements.txt     — Bot dependencies
  auth/
    main.py            — Flask OAuth server (Patreon connect + callback)
    railway.toml       — Auth service Railway config
    requirements.txt   — Auth service dependencies
  bot/
    db.py              — PostgreSQL layer (all database queries)
    patreon.py         — Patreon API client (memberships, posts, token refresh)
    scheduler.py       — Background polling loop
    premium.py         — Premium/SKU gating
  legal/
    TERMS_OF_SERVICE.md
    PRIVACY_NOTICE.md
```

---

## Support

Join the [KumihoArts support server](https://discord.gg/KVcu3HvHB3) if you run into any issues.
