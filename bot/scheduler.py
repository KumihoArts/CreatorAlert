import asyncio
import discord

from bot.db import get_all_users, is_post_seen, mark_post_seen, update_tokens, delete_user, get_premium_channels
from bot.patreon import get_memberships, get_recent_posts, refresh_access_token
from bot.premium import is_premium, PREMIUM_SKU_ID

FREE_POLL_INTERVAL = 600    # 10 minutes
PREMIUM_POLL_INTERVAL = 180 # 3 minutes


def start_scheduler(bot: discord.Client):
    bot.loop.create_task(_polling_loop(bot))


async def _polling_loop(bot: discord.Client):
    await bot.wait_until_ready()
    print("Scheduler started.")

    cycle = 0
    while not bot.is_closed():
        try:
            await _check_for_new_posts(bot, premium_only=(cycle % 2 == 1))
        except Exception as e:
            print(f"[scheduler] Polling error: {e}")

        # Run every 3 minutes; free users only checked every other cycle (6 min effective,
        # close enough to 10 — adjust cycle modulo below to taste)
        cycle += 1
        await asyncio.sleep(PREMIUM_POLL_INTERVAL)


async def _try_refresh_token(user: dict) -> str | None:
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


async def _check_for_new_posts(bot: discord.Client, premium_only: bool = False):
    users = await get_all_users()
    if not users:
        return

    for user in users:
        discord_id = user["discord_id"]

        # Determine premium status from bypass IDs
        # (entitlements not available in scheduler, bypass IDs cover owner/testers)
        user_is_premium = discord_id in __import__("bot.premium", fromlist=["PREMIUM_BYPASS_IDS"]).PREMIUM_BYPASS_IDS

        # Skip free users on premium-only cycles
        if premium_only and not user_is_premium:
            continue

        access_token = user["access_token"]
        mode = user.get("notification_mode", "dm")
        channel_id = user.get("notification_channel_id")
        embed_colour = user.get("embed_colour")
        custom_message = user.get("custom_message")

        memberships = await get_memberships(access_token)

        if memberships is None:
            print(f"[scheduler] Token invalid for {discord_id}, attempting refresh...")
            new_token = await _try_refresh_token(user)
            if new_token:
                memberships = await get_memberships(new_token)
                if memberships is None:
                    print(f"[scheduler] Token fully revoked for {discord_id}, removing and notifying.")
                    await delete_user(discord_id)
                    await _notify_revoked(bot, discord_id)
                    continue
                access_token = new_token
            else:
                print(f"[scheduler] Token refresh failed for {discord_id}, removing and notifying.")
                await delete_user(discord_id)
                await _notify_revoked(bot, discord_id)
                continue

        # Resolve notification colour
        if embed_colour and user_is_premium:
            try:
                colour = discord.Color(int(embed_colour.strip("#"), 16))
            except Exception:
                colour = discord.Color.orange()
        else:
            colour = discord.Color.orange()

        # Get all channels to notify
        channels_to_notify = []
        if mode in ("channel", "both") and channel_id:
            channels_to_notify.append(channel_id)
        if user_is_premium:
            extra_channels = await get_premium_channels(discord_id)
            for ch in extra_channels:
                if ch not in channels_to_notify:
                    channels_to_notify.append(ch)

        for membership in memberships:
            campaign_id = membership["campaign_id"]
            creator_name = membership.get("vanity") or "A creator"
            creator_url = membership.get("url", "")

            posts = await get_recent_posts(access_token, campaign_id)

            if posts is None:
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
                    color=colour
                )
                if creator_url:
                    embed.set_footer(text=creator_url)

                # Custom message prefix (premium)
                content_prefix = custom_message if (custom_message and user_is_premium) else None

                # Send DM
                if mode in ("dm", "both"):
                    try:
                        discord_user = await bot.fetch_user(discord_id)
                        await discord_user.send(
                            content=content_prefix,
                            embed=embed
                        )
                    except Exception as e:
                        print(f"[scheduler] Failed to DM {discord_id}: {e}")

                # Send to channels
                for ch_id in channels_to_notify:
                    try:
                        channel = bot.get_channel(ch_id)
                        if channel is None:
                            channel = await bot.fetch_channel(ch_id)
                        await channel.send(
                            content=f"{content_prefix or ''}<@{discord_id}>".strip(),
                            embed=embed
                        )
                    except Exception as e:
                        print(f"[scheduler] Failed to send to channel {ch_id}: {e}")
