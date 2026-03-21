import aiohttp
import os
import re

PATREON_API_BASE = "https://www.patreon.com/api/oauth2/v2"
PATREON_TOKEN_URL = "https://www.patreon.com/api/oauth2/token"

EXCERPT_MAX_CHARS = 300


def _extract_excerpt(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > EXCERPT_MAX_CHARS:
        text = text[:EXCERPT_MAX_CHARS].rsplit(" ", 1)[0] + "…"
    return text


async def refresh_access_token(refresh_token: str) -> dict | None:
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
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{PATREON_API_BASE}/identity",
            headers=headers,
            params={"fields[user]": "full_name,email,url"}
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_own_campaign(access_token: str) -> dict | None:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{PATREON_API_BASE}/identity",
            headers=headers,
            params={
                "include": "campaign",
                "fields[campaign]": "vanity,url",
            }
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

    for item in data.get("included", []):
        if item.get("type") == "campaign":
            return {
                "campaign_id": item["id"],
                "vanity": item.get("attributes", {}).get("vanity", ""),
                "url": item.get("attributes", {}).get("url", ""),
            }
    return None


async def get_memberships(access_token: str) -> list[dict] | None:
    """
    Fetch all campaigns the user is a member of, including free/follower tiers.
    Each entry includes is_follower and patron_status for optional filtering.
    Returns None on 401.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{PATREON_API_BASE}/identity",
            headers=headers,
            params={
                "include": "memberships,memberships.campaign",
                "fields[campaign]": "vanity,url,summary",
                "fields[member]": "patron_status,is_follower",
            }
        ) as resp:
            if resp.status == 401:
                return None
            if resp.status != 200:
                text = await resp.text()
                print(f"[patreon] get_memberships failed: {resp.status} {text}")
                return []
            data = await resp.json()

    included = data.get("included", [])

    # Build campaign lookup
    campaigns = {}
    for item in included:
        if item.get("type") == "campaign":
            attrs = item.get("attributes", {})
            campaigns[item["id"]] = {
                "campaign_id": item["id"],
                "vanity": attrs.get("vanity", "Unknown"),
                "url": attrs.get("url", ""),
            }

    # Walk member objects to get campaign + status
    memberships = []
    seen = set()
    for item in included:
        if item.get("type") == "member":
            attrs = item.get("attributes", {})
            campaign_rel = item.get("relationships", {}).get("campaign", {}).get("data", {})
            campaign_id = campaign_rel.get("id")
            if campaign_id and campaign_id not in seen and campaign_id in campaigns:
                seen.add(campaign_id)
                entry = campaigns[campaign_id].copy()
                entry["is_follower"] = attrs.get("is_follower", False)
                entry["patron_status"] = attrs.get("patron_status")  # active_patron, declined_patron, former_patron, or None
                memberships.append(entry)

    return memberships


async def get_recent_posts(access_token: str, campaign_id: str, limit: int = 10) -> list[dict] | None:
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "fields[post]": "title,url,published_at,content,is_public",
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
                return None
            if resp.status != 200:
                text = await resp.text()
                print(f"[patreon] get_recent_posts failed for campaign {campaign_id}: {resp.status} {text}")
                return []
            data = await resp.json()

    posts = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        raw_url = attrs.get("url", "")
        if raw_url and not raw_url.startswith("http"):
            raw_url = f"https://www.patreon.com{raw_url}"
        is_public = attrs.get("is_public", False)
        excerpt = _extract_excerpt(attrs.get("content", "")) if is_public else ""
        posts.append({
            "id": item["id"],
            "title": attrs.get("title") or "New Post",
            "url": raw_url,
            "published_at": attrs.get("published_at", ""),
            "is_public": is_public,
            "excerpt": excerpt,
        })
    return posts
