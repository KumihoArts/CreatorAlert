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

PATREON_CLIENT_ID = os.getenv("PATREON_CLIENT_ID")
PATREON_CLIENT_SECRET = os.getenv("PATREON_CLIENT_SECRET")
PATREON_REDIRECT_URI = os.getenv("PATREON_REDIRECT_URI")
DATABASE_URL = os.getenv("DATABASE_URL")

PATREON_AUTH_URL = "https://www.patreon.com/oauth2/authorize"
PATREON_TOKEN_URL = "https://www.patreon.com/api/oauth2/token"
PATREON_IDENTITY_URL = "https://www.patreon.com/api/oauth2/v2/identity"

# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/connect")
def connect():
    """
    Entry point: user clicks 'Connect Patreon' from a Discord bot message.
    Expects ?discord_id=<user_id> query param.
    Redirects user to Patreon OAuth authorization page.
    """
    discord_id = request.args.get("discord_id")
    if not discord_id:
        return "Missing discord_id parameter.", 400

    params = {
        "response_type": "code",
        "client_id": PATREON_CLIENT_ID,
        "redirect_uri": PATREON_REDIRECT_URI,
        "scope": "identity identity[email] identity.memberships",
        "state": discord_id,  # pass discord_id through OAuth state param
    }
    auth_url = f"{PATREON_AUTH_URL}?{urlencode(params)}"
    return redirect(auth_url)


@app.route("/callback")
def callback():
    """
    Patreon redirects here after user authorizes.
    Exchanges code for tokens, stores them in DB, DMs the Discord user.
    """
    code = request.args.get("code")
    discord_id = request.args.get("state")
    error = request.args.get("error")

    if error:
        return f"Authorization cancelled or failed: {error}", 400

    if not code or not discord_id:
        return "Missing code or state parameter.", 400

    # Exchange code for access token
    token_response = requests.post(PATREON_TOKEN_URL, data={
        "code": code,
        "grant_type": "authorization_code",
        "client_id": PATREON_CLIENT_ID,
        "client_secret": PATREON_CLIENT_SECRET,
        "redirect_uri": PATREON_REDIRECT_URI,
    })

    if token_response.status_code != 200:
        return f"Token exchange failed: {token_response.text}", 500

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 0)

    # Fetch Patreon identity
    identity_response = requests.get(
        PATREON_IDENTITY_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"fields[user]": "full_name,email,url"}
    )

    if identity_response.status_code != 200:
        return f"Failed to fetch Patreon identity: {identity_response.text}", 500

    identity_data = identity_response.json()
    patreon_user_id = identity_data.get("data", {}).get("id")
    patreon_name = identity_data.get("data", {}).get("attributes", {}).get("full_name", "Unknown")

    if not patreon_user_id:
        return "Could not retrieve Patreon user ID.", 500

    # Store in database
    async def save_to_db():
        conn = await get_db()
        try:
            await conn.execute("""
                INSERT INTO patreon_users (
                    discord_id, patreon_user_id, access_token, refresh_token
                ) VALUES ($1, $2, $3, $4)
                ON CONFLICT (discord_id) DO UPDATE SET
                    patreon_user_id = EXCLUDED.patreon_user_id,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    connected_at = NOW()
            """, int(discord_id), patreon_user_id, access_token, refresh_token)
        finally:
            await conn.close()

    asyncio.run(save_to_db())

    return f"""
    <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#1a1a2e;color:#eee;">
        <h2>✅ Patreon Connected!</h2>
        <p>Your Patreon account <strong>{patreon_name}</strong> has been linked to your Discord account.</p>
        <p>You can close this tab and return to Discord.</p>
    </body></html>
    """, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
