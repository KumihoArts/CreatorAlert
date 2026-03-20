from flask import Flask, request, redirect, jsonify
from flask_cors import CORS
import os
import asyncpg
import asyncio
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")

# ---------------------------------------------------------------------------
# Patreon config
# ---------------------------------------------------------------------------
PATREON_CLIENT_ID = os.getenv("PATREON_CLIENT_ID")
PATREON_CLIENT_SECRET = os.getenv("PATREON_CLIENT_SECRET")
PATREON_REDIRECT_URI = os.getenv("PATREON_REDIRECT_URI")
PATREON_AUTH_URL = "https://www.patreon.com/oauth2/authorize"
PATREON_TOKEN_URL = "https://www.patreon.com/api/oauth2/token"
PATREON_IDENTITY_URL = "https://www.patreon.com/api/oauth2/v2/identity"

# ---------------------------------------------------------------------------
# SubscribeStar config
# ---------------------------------------------------------------------------
SUBSCRIBESTAR_CLIENT_ID = os.getenv("SUBSCRIBESTAR_CLIENT_ID")
SUBSCRIBESTAR_CLIENT_SECRET = os.getenv("SUBSCRIBESTAR_CLIENT_SECRET")
SUBSCRIBESTAR_REDIRECT_URI = os.getenv("SUBSCRIBESTAR_REDIRECT_URI")
SUBSCRIBESTAR_AUTH_URL = "https://www.subscribestar.com/oauth2/authorize"
SUBSCRIBESTAR_TOKEN_URL = "https://www.subscribestar.com/oauth2/token"
SUBSCRIBESTAR_API_URL = "https://www.subscribestar.com/api/graphql/v1"

# ---------------------------------------------------------------------------
# Gumroad config
# ---------------------------------------------------------------------------
GUMROAD_CLIENT_ID = os.getenv("GUMROAD_CLIENT_ID")
GUMROAD_CLIENT_SECRET = os.getenv("GUMROAD_CLIENT_SECRET")
GUMROAD_REDIRECT_URI = os.getenv("GUMROAD_REDIRECT_URI")
GUMROAD_AUTH_URL = "https://gumroad.com/oauth/authorize"
GUMROAD_TOKEN_URL = "https://api.gumroad.com/oauth/token"
GUMROAD_USER_URL = "https://api.gumroad.com/v2/user"

DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

async def get_db():
    return await asyncpg.connect(DATABASE_URL)


async def save_account(discord_id: int, platform: str, platform_user_id: str, access_token: str, refresh_token: str):
    conn = await get_db()
    try:
        await conn.execute("""
            INSERT INTO connected_accounts (
                discord_id, platform, platform_user_id, access_token, refresh_token
            ) VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (discord_id, platform) DO UPDATE SET
                platform_user_id = EXCLUDED.platform_user_id,
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                connected_at = NOW()
        """, discord_id, platform, platform_user_id, access_token, refresh_token)
    finally:
        await conn.close()

# ---------------------------------------------------------------------------
# Shared HTML responses
# ---------------------------------------------------------------------------

def success_page(platform_name: str, account_name: str) -> str:
    return f"""
    <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#1a1a2e;color:#eee;">
        <h2>✅ {platform_name} Connected!</h2>
        <p>Your {platform_name} account <strong>{account_name}</strong> has been linked to your Discord account.</p>
        <p>You can close this tab and return to Discord.</p>
    </body></html>
    """


def error_page(message: str) -> tuple:
    return f"""
    <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#1a1a2e;color:#eee;">
        <h2>❌ Something went wrong</h2>
        <p>{message}</p>
        <p>Please close this tab and try again in Discord.</p>
    </body></html>
    """, 500

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

# ---------------------------------------------------------------------------
# Patreon OAuth
# ---------------------------------------------------------------------------

@app.route("/connect/patreon")
def connect_patreon():
    discord_id = request.args.get("discord_id")
    if not discord_id:
        return "Missing discord_id parameter.", 400

    params = {
        "response_type": "code",
        "client_id": PATREON_CLIENT_ID,
        "redirect_uri": PATREON_REDIRECT_URI,
        "scope": "identity identity[email] identity.memberships",
        "state": discord_id,
    }
    return redirect(f"{PATREON_AUTH_URL}?{urlencode(params)}")


@app.route("/callback/patreon")
def callback_patreon():
    code = request.args.get("code")
    discord_id = request.args.get("state")
    error = request.args.get("error")

    if error:
        return f"Authorization cancelled or failed: {error}", 400
    if not code or not discord_id:
        return "Missing code or state parameter.", 400

    token_response = requests.post(PATREON_TOKEN_URL, data={
        "code": code,
        "grant_type": "authorization_code",
        "client_id": PATREON_CLIENT_ID,
        "client_secret": PATREON_CLIENT_SECRET,
        "redirect_uri": PATREON_REDIRECT_URI,
    })

    if token_response.status_code != 200:
        return error_page(f"Token exchange failed: {token_response.text}")

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    identity_response = requests.get(
        PATREON_IDENTITY_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"fields[user]": "full_name,email,url"}
    )

    if identity_response.status_code != 200:
        return error_page(f"Failed to fetch Patreon identity: {identity_response.text}")

    identity_data = identity_response.json()
    platform_user_id = identity_data.get("data", {}).get("id")
    account_name = identity_data.get("data", {}).get("attributes", {}).get("full_name", "Unknown")

    if not platform_user_id:
        return error_page("Could not retrieve Patreon user ID.")

    asyncio.run(save_account(int(discord_id), "patreon", platform_user_id, access_token, refresh_token))
    return success_page("Patreon", account_name), 200


# ---------------------------------------------------------------------------
# SubscribeStar OAuth
# ---------------------------------------------------------------------------

@app.route("/connect/subscribestar")
def connect_subscribestar():
    discord_id = request.args.get("discord_id")
    if not discord_id:
        return "Missing discord_id parameter.", 400

    params = {
        "response_type": "code",
        "client_id": SUBSCRIBESTAR_CLIENT_ID,
        "redirect_uri": SUBSCRIBESTAR_REDIRECT_URI,
        "scope": "user.read user.subscriptions.read subscriber.read",
        "state": discord_id,
    }
    return redirect(f"{SUBSCRIBESTAR_AUTH_URL}?{urlencode(params)}")


@app.route("/callback/subscribestar")
def callback_subscribestar():
    code = request.args.get("code")
    discord_id = request.args.get("state")
    error = request.args.get("error")

    if error:
        return f"Authorization cancelled or failed: {error}", 400
    if not code or not discord_id:
        return "Missing code or state parameter.", 400

    token_response = requests.post(
        SUBSCRIBESTAR_TOKEN_URL,
        params={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": SUBSCRIBESTAR_CLIENT_ID,
            "client_secret": SUBSCRIBESTAR_CLIENT_SECRET,
            "redirect_uri": SUBSCRIBESTAR_REDIRECT_URI,
        }
    )

    if token_response.status_code != 200:
        return error_page(f"Token exchange failed: {token_response.text}")

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    identity_response = requests.post(
        SUBSCRIBESTAR_API_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"query": "{ user { id name } }"}
    )

    if identity_response.status_code != 200:
        return error_page(f"Failed to fetch SubscribeStar identity: {identity_response.text}")

    identity_data = identity_response.json()
    try:
        user_data = identity_data["data"]["user"]
        platform_user_id = str(user_data["id"])
        account_name = user_data.get("name", "Unknown")
    except (KeyError, TypeError):
        return error_page("Could not retrieve SubscribeStar user ID.")

    asyncio.run(save_account(int(discord_id), "subscribestar", platform_user_id, access_token, refresh_token))
    return success_page("SubscribeStar", account_name), 200


# ---------------------------------------------------------------------------
# Gumroad OAuth
# ---------------------------------------------------------------------------

@app.route("/connect/gumroad")
def connect_gumroad():
    discord_id = request.args.get("discord_id")
    if not discord_id:
        return "Missing discord_id parameter.", 400

    params = {
        "client_id": GUMROAD_CLIENT_ID,
        "redirect_uri": GUMROAD_REDIRECT_URI,
        "scope": "view_profile",
        "state": discord_id,
    }
    return redirect(f"{GUMROAD_AUTH_URL}?{urlencode(params)}")


@app.route("/callback/gumroad")
def callback_gumroad():
    code = request.args.get("code")
    discord_id = request.args.get("state")
    error = request.args.get("error")

    if error:
        return f"Authorization cancelled or failed: {error}", 400
    if not code or not discord_id:
        return "Missing code or state parameter.", 400

    token_response = requests.post(GUMROAD_TOKEN_URL, data={
        "code": code,
        "grant_type": "authorization_code",
        "client_id": GUMROAD_CLIENT_ID,
        "client_secret": GUMROAD_CLIENT_SECRET,
        "redirect_uri": GUMROAD_REDIRECT_URI,
    })

    if token_response.status_code != 200:
        return error_page(f"Token exchange failed: {token_response.text}")

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    # Gumroad tokens don't expire — no refresh token
    refresh_token = token_data.get("refresh_token", "")

    identity_response = requests.get(
        GUMROAD_USER_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if identity_response.status_code != 200:
        return error_page(f"Failed to fetch Gumroad identity: {identity_response.text}")

    identity_data = identity_response.json()
    user = identity_data.get("user", {})
    platform_user_id = user.get("user_id")
    account_name = user.get("name") or user.get("email", "Unknown")

    if not platform_user_id:
        return error_page("Could not retrieve Gumroad user ID.")

    asyncio.run(save_account(int(discord_id), "gumroad", platform_user_id, access_token, refresh_token))
    return success_page("Gumroad", account_name), 200


# ---------------------------------------------------------------------------
# Legacy routes
# ---------------------------------------------------------------------------

@app.route("/connect")
def connect_legacy():
    discord_id = request.args.get("discord_id", "")
    return redirect(f"/connect/patreon?discord_id={discord_id}")


@app.route("/callback")
def callback_legacy():
    return redirect(f"/callback/patreon?{request.query_string.decode()}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
