PREMIUM_BYPASS_IDS = {
    244962442008854540,  # Sly (bot owner)
    927037270098341919,  # heavenlywits
}

def is_premium(discord_id: int) -> bool:
    """Return True if the user has premium access."""
    if discord_id in PREMIUM_BYPASS_IDS:
        return True
    # TODO: check active Patreon subscription to the CreatorAlert tier
    return False
