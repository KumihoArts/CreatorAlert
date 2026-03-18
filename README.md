# CreatorAlert

A Discord bot that notifies users when Patreon creators they follow post new content.

## Modes
- **Creator mode** — Add the bot to your server, connect Patreon, post notifications in a channel automatically.
- **Subscriber mode** — Connect your Patreon account, get DMs/pings when creators you back post something new.

## Architecture
- Bot: `main.py` — discord.py 2.3+, asyncpg, deployed as Railway service
- Auth server: `auth/main.py` — Flask + Gunicorn, handles Patreon OAuth, separate Railway service
- Database: PostgreSQL on Railway (shared via `DATABASE_URL`)

## Setup
1. Copy `.env.example` to `.env` and fill in your credentials
2. Register a Patreon OAuth client at https://www.patreon.com/portal/registration/register-clients
3. `pip install -r requirements.txt`
4. `python main.py`

## Deploy
Railway, two services:
- Bot service: root directory `/`, start command `python main.py`
- Auth service: root directory `/auth`, start command `gunicorn main:app --workers 2 --bind 0.0.0.0:5000`
