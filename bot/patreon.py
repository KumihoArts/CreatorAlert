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

async def get_campaigns(access_token: str) -> list:
    """Fetch campaigns the user is a member of (subscriber mode)."""
    # TODO: implement campaign/membership fetch
    return []

async def get_recent_posts(access_token: str, campaign_id: str) -> list:
    """Fetch recent posts from a campaign."""
    # TODO: implement post fetch
    return []
