"""
Platform registry — maps platform names to their API client modules.
Each platform module must implement:
    get_memberships(access_token) -> list[dict] | None
    get_recent_posts(access_token, campaign_id) -> list[dict] | None
    refresh_access_token(refresh_token) -> dict | None

Membership dicts must contain: campaign_id, vanity, url
Post dicts must contain: id, title, url, published_at
"""

from bot.platforms import patreon, subscribestar

PLATFORMS = {
    "patreon": patreon,
    "subscribestar": subscribestar,
}

PLATFORM_LABELS = {
    "patreon": "Patreon",
    "subscribestar": "SubscribeStar",
}

PLATFORM_COLOURS = {
    "patreon": 0xF96854,   # Patreon orange
    "subscribestar": 0x47B5FF,  # SubscribeStar blue
}


def get_platform(platform: str):
    """Return the platform module for a given platform name."""
    return PLATFORMS.get(platform)


def label(platform: str) -> str:
    """Return the human-readable label for a platform."""
    return PLATFORM_LABELS.get(platform, platform.capitalize())
