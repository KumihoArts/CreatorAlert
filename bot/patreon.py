import aiohttp
import os

PATREON_API_BASE = "https://www.patreon.com/api/oauth2/v2"
PATREON_TOKEN_URL = "https://www.patreon.com/api/oauth2/token"


async def refresh_access_token(refresh_token: str) -> dict | None:
    """
    Exchange a refresh token for a new access + refresh token pair.
    Returns dict with access_token, refresh_token, expires_in or None on failure.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(PATREON_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": os.getenv("PATREON_CLIENT_ID"),
            "client_secret": os.getenv("PATREON_CLIENT_SECRET"),
        }) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"[patreon] Token refresh failed: {resp.status} {text}")
                return None
            return await resp.json()


async def get_identity(access_token: str) -> dict:
    """Fetch the authenticated user's Patreon identity."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{PATREON_API_BASE}/identity",
            headers=headers,
            params={"fields[user]": "full_name,email,url"}
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_memberships(access_token: str) -> list[dict]:
    """
    Fetch the campaigns the user is a member of (i.e. creators they support).
    Returns a list of dicts with campaign_id, vanity, and url.
    Returns None if the token is invalid/revoked (401).
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{PATREON_API_BASE}/identity",
            headers=headers,
            params={
                "include": "memberships.campaign",
                "fields[campaign]": "vanity,url,summary",
                "fields[member]": "patron_status",
            }
        ) as resp:
            if resp.status == 401:
                return None  # Signal revoked/expired token
            if resp.status != 200:
                text = await resp.text()
                print(f"[patreon] get_memberships failed: {resp.status} {text}")
                return []
            data = await resp.json()

    memberships = []
    included = data.get("included", [])
    for item in included:
        if item.get("type") == "campaign":
            memberships.append({
                "campaign_id": item["id"],
                "vanity": item.get("attributes", {}).get("vanity", "Unknown"),
                "url": item.get("attributes", {}).get("url", ""),
            })
    return memberships


async def get_recent_posts(access_token: str, campaign_id: str, limit: int = 10) -> list[dict]:
    """
    Fetch recent posts from a campaign.
    Returns a list of dicts with post id, title, url, and published_at.
    Returns None if token is invalid/revoked (401).
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "fields[post]": "title,url,published_at,content",
        "page[count]": limit,
        "sort": "-published_at",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{PATREON_API_BASE}/campaigns/{campaign_id}/posts",
            headers=headers,
            params=params
        ) as resp:
            if resp.status == 401:
                return None  # Signal revoked/expired token
            if resp.status != 200:
                text = await resp.text()
                print(f"[patreon] get_recent_posts failed for campaign {campaign_id}: {resp.status} {text}")
                return []
            data = await resp.json()

    posts = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        posts.append({
            "id": item["id"],
            "title": attrs.get("title") or "New Post",
            "url": attrs.get("url", ""),
            "published_at": attrs.get("published_at", ""),
        })
    return posts
