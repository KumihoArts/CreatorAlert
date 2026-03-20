import aiohttp
import os

GUMROAD_API_BASE = "https://api.gumroad.com/v2"
GUMROAD_TOKEN_URL = "https://api.gumroad.com/oauth/token"


async def refresh_access_token(refresh_token: str) -> dict | None:
    """
    Gumroad tokens do not expire and there is no refresh token flow.
    This is a no-op stub to satisfy the platform interface.
    """
    return None


async def get_memberships(access_token: str) -> list[dict] | None:
    """
    Gumroad has no subscriber/membership concept accessible via OAuth.
    Returns an empty list — creator mode only.
    """
    return []


async def get_products(access_token: str) -> list[dict] | None:
    """
    Fetch all published products for the authenticated Gumroad creator.
    Returns a list of dicts with id, name, url, published_at.
    Returns None on 401.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{GUMROAD_API_BASE}/products",
            headers=headers,
        ) as resp:
            if resp.status == 401:
                return None
            if resp.status != 200:
                text = await resp.text()
                print(f"[gumroad] get_products failed: {resp.status} {text}")
                return []
            data = await resp.json()

    if not data.get("success"):
        print(f"[gumroad] get_products returned success=false: {data}")
        return []

    products = []
    for p in data.get("products", []):
        if not p.get("published", False):
            continue
        products.append({
            "id": p["id"],
            "title": p.get("name") or "New Product",
            "url": p.get("short_url", ""),
            "published_at": p.get("published_at", ""),
            "excerpt": p.get("description", "")[:300] if p.get("description") else "",
        })
    return products


async def get_recent_posts(access_token: str, campaign_id: str, limit: int = 10) -> list[dict] | None:
    """
    For Gumroad, 'posts' are products. campaign_id is unused — we always
    fetch the authenticated user's own products. This signature matches the
    platform interface used by the scheduler.
    Returns None on 401.
    """
    return await get_products(access_token)


async def get_own_campaign(access_token: str) -> dict | None:
    """
    Fetch the authenticated Gumroad user's identity.
    Returns a dict with campaign_id (user id) and vanity (name).
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{GUMROAD_API_BASE}/user",
            headers=headers,
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

    user = data.get("user", {})
    if not user:
        return None
    return {
        "campaign_id": user.get("user_id", ""),
        "vanity": user.get("name") or user.get("email", "Unknown"),
        "url": user.get("profile_url", ""),
    }
