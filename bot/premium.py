import discord

PREMIUM_BYPASS_IDS = {
    244962442008854540,  # Sly (bot owner)
    718280099245588480,  # Lillio
    284735066167574570,  # ChainZ
    217133180707274752,  # NiiChan
    546692443513421836,  # Fouetty
    636756508587196428,  # Jestur
    543504165779931157,  # Caribdis
    695322948856316016,  # GDC
}

PREMIUM_SKU_ID = 1484207527494287523


def is_premium(discord_id: int, entitlements: list[discord.Entitlement] = None) -> bool:
    """
    Return True if the user has premium access.
    Checks hardcoded bypass IDs first, then Discord entitlements.
    """
    if discord_id in PREMIUM_BYPASS_IDS:
        return True

    if entitlements:
        for entitlement in entitlements:
            if entitlement.sku_id == PREMIUM_SKU_ID and not entitlement.is_consumed():
                return True

    return False
