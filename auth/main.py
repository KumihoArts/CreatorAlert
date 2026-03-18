from flask import Flask, request, redirect, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")

PATREON_CLIENT_ID = os.getenv("PATREON_CLIENT_ID")
PATREON_CLIENT_SECRET = os.getenv("PATREON_CLIENT_SECRET")
PATREON_REDIRECT_URI = os.getenv("PATREON_REDIRECT_URI")

# ---------------------------------------------------------------------------
# Routes (stubs — flesh out in later sessions)
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/connect")
def connect():
    """Redirect user to Patreon OAuth authorization page."""
    # TODO: build authorization URL and redirect
    return "Patreon connect — coming soon", 200

@app.route("/callback")
def callback():
    """Handle OAuth callback from Patreon."""
    # TODO: exchange code for token, store in DB, DM the user
    return "OAuth callback — coming soon", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
