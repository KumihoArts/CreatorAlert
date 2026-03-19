import asyncio
import discord

from bot.db import get_all_users, is_post_seen, mark_post_seen, update_tokens, delete_user
from bot.patreon import get_memberships, get_recent_posts, refresh_access_token

POLL_INTERVAL_SECONDS = 600  # 10 minutes


def start_scheduler(bot: discord.Client):
    bot.loop.create_task(_polling_loop(bot))


async def _polling_loop(bot: discord.Client):
    await bot.wait_until_ready()
    print("Scheduler started.")
    while not bot.is_closed():
        try:
            await _check_for_new_posts(bot)
        except Exception as e:
            print(f"[scheduler] Polling error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _try_refresh_token(user: dict) -> str | None:
    """
    Attempt to refresh a user's access token.
    Returns the new access token on success, None on failure.
    """
    discord_id = user["discord_id"]
    result = await refresh_access_token(user["refresh_token"])
    if result:
        new_access = result.get("access_token")
        new_refresh = result.get("refresh_token", user["refresh_token"])
        await update_tokens(discord_id, new_access, new_refresh)
        print(f"[scheduler] Refreshed token for user {discord_id}.")
        return new_access
    return None


async def _notify_revoked(bot: discord.Client, discord_id: int):
    """DM the user to let them know their Patreon connection needs to be re-linked."""
    try:
        discord_user = await bot.fetch_user(discord_id)
        embed = discord.Embed(
            title="⚠️ Patreon Connection Lost",
            description=(
                "Your Patreon account has been disconnected from CreatorAlert, "
                "likely because you revoked access on Patreon's side.\n\n"
                "Use `/connect` to re-link your account and resume notifications."
            ),
            color=discord.Color.red()
        )
        await discord_user.send(embed=embed)
    except Exception as e:
        print(f"[scheduler] Could not notify {discord_id} of revoked token: {e}")


async def _check_for_new_posts(bot: discord.Client):
    users = await get_all_users()
    if not users:
        return

    for user in users:
        discord_id = user["discord_id"]
        access_token = user["access_token"]
        mode = user.get("notification_mode", "dm")
        channel_id = user.get("notification_channel_id")

        # Fetch memberships — returns None on 401
        memberships = await get_memberships(access_token)

        if memberships is None:
            # Token expired or revoked — try refresh first
            print(f"[scheduler] Token invalid for {discord_id}, attempting refresh...")
            new_token = await _try_refresh_token(user)
            if new_token:
                memberships = await get_memberships(new_token)
                if memberships is None:
                    # Refresh worked but token still invalid — fully revoked
                    print(f"[scheduler] Token fully revoked for {discord_id}, removing and notifying.")
                    await delete_user(discord_id)
                    await _notify_revoked(bot, discord_id)
                    continue
                access_token = new_token
            else:
                # Refresh failed — token is fully revoked
                print(f"[scheduler] Token refresh failed for {discord_id}, removing and notifying.")
                await delete_user(discord_id)
                await _notify_revoked(bot, discord_id)
                continue

        for membership in memberships:
            campaign_id = membership["campaign_id"]
            creator_name = membership.get("vanity") or "A creator"
            creator_url = membership.get("url", "")

            posts = await get_recent_posts(access_token, campaign_id)

            if posts is None:
                # Shouldn't happen since we just validated the token, but handle gracefully
                print(f"[scheduler] Unexpected 401 on posts for campaign {campaign_id}, skipping.")
                continue

            for post in posts:
                post_id = post["id"]

                if await is_post_seen(post_id):
                    continue

                await mark_post_seen(post_id, campaign_id)

                embed = discord.Embed(
                    title=f"📬 New post from {creator_name}",
                    description=f"**{post['title']}**",
                    url=post["url"],
                    color=discord.Color.orange()
                )
                if creator_url:
                    embed.set_footer(text=creator_url)

                # Send DM
                if mode in ("dm", "both"):
                    try:
                        discord_user = await bot.fetch_user(discord_id)
                        await discord_user.send(embed=embed)
                    except Exception as e:
                        print(f"[scheduler] Failed to DM {discord_id}: {e}")

                # Send to channel
                if mode in ("channel", "both") and channel_id:
                    try:
                        channel = bot.get_channel(channel_id)
                        if channel is None:
                            channel = await bot.fetch_channel(channel_id)
                        await channel.send(f"<@{discord_id}>", embed=embed)
                    except Exception as e:
                        print(f"[scheduler] Failed to send to channel {channel_id}: {e}")
