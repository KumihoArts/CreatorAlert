import aiohttp
import os

SUBSCRIBESTAR_API_URL = "https://www.subscribestar.com/api/graphql/v1"
SUBSCRIBESTAR_TOKEN_URL = "https://www.subscribestar.com/oauth2/token"


async def refresh_access_token(refresh_token: str) -> dict | None:
    """
    Exchange a SubscribeStar refresh token for a new access + refresh token pair.
    Returns dict with access_token, refresh_token, expires_in or None on failure.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            SUBSCRIBESTAR_TOKEN_URL,
            params={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": os.getenv("SUBSCRIBESTAR_CLIENT_ID"),
                "client_secret": os.getenv("SUBSCRIBESTAR_CLIENT_SECRET"),
                "redirect_uri": os.getenv("SUBSCRIBESTAR_REDIRECT_URI"),
            }
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"[subscribestar] Token refresh failed: {resp.status} {text}")
                return None
            return await resp.json()


async def _graphql(access_token: str, query: str) -> dict | None:
    """
    Execute a GraphQL query against the SubscribeStar API.
    Returns the response data dict, or None on 401.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            SUBSCRIBESTAR_API_URL,
            headers=headers,
            json={"query": query}
        ) as resp:
            if resp.status == 401:
                return None
            if resp.status != 200:
                text = await resp.text()
                print(f"[subscribestar] GraphQL request failed: {resp.status} {text}")
                return {}
            return await resp.json()


async def get_memberships(access_token: str) -> list[dict] | None:
    """
    Fetch the stars (creators) the user is subscribed to on SubscribeStar.
    Returns a list of dicts with campaign_id, vanity, and url.
    Returns None if the token is invalid/revoked (401).
    """
    query = """
    {
        user {
            subscriptions {
                edges {
                    node {
                        star {
                            id
                            name
                            star_page
                        }
                    }
                }
            }
        }
    }
    """
    data = await _graphql(access_token, query)
    if data is None:
        return None  # 401 — token invalid

    memberships = []
    try:
        edges = data["data"]["user"]["subscriptions"]["edges"]
        for edge in edges:
            star = edge["node"]["star"]
            memberships.append({
                "campaign_id": str(star["id"]),
                "vanity": star.get("name", "Unknown"),
                "url": star.get("star_page", ""),
            })
    except (KeyError, TypeError) as e:
        print(f"[subscribestar] Failed to parse memberships: {e} | data: {data}")
        return []

    return memberships


async def get_recent_posts(access_token: str, campaign_id: str, limit: int = 10) -> list[dict] | None:
    """
    Fetch recent posts from a SubscribeStar creator by their star ID.
    Returns a list of dicts with post id, title, url, and published_at.
    Returns None if token is invalid/revoked (401).
    """
    query = f"""
    {{
        star(id: {campaign_id}) {{
            posts(first: {limit}) {{
                edges {{
                    node {{
                        id
                        title
                        url
                        created_at
                    }}
                }}
            }}
        }}
    }}
    """
    data = await _graphql(access_token, query)
    if data is None:
        return None  # 401 — token invalid

    posts = []
    try:
        edges = data["data"]["star"]["posts"]["edges"]
        for edge in edges:
            node = edge["node"]
            posts.append({
                "id": str(node["id"]),
                "title": node.get("title") or "New Post",
                "url": node.get("url", ""),
                "published_at": node.get("created_at", ""),
            })
    except (KeyError, TypeError) as e:
        print(f"[subscribestar] Failed to parse posts for star {campaign_id}: {e} | data: {data}")
        return []

    return posts
