import aiohttp

PATREON_API_BASE = "https://www.patreon.com/api/oauth2/v2"

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
    Returns a list of dicts with campaign_id and creator name.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "include": "currently_entitled_tiers,campaign",
        "fields[member]": "full_name,patron_status",
        "fields[campaign]": "summary,creation_name,vanity,url",
    }
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
