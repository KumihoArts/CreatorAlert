import asyncio
import discord

from bot.db import get_all_users, is_post_seen, mark_post_seen
from bot.patreon import get_memberships, get_recent_posts

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


async def _check_for_new_posts(bot: discord.Client):
    users = await get_all_users()
    if not users:
        return

    for user in users:
        discord_id = user["discord_id"]
        access_token = user["access_token"]
        mode = user.get("notification_mode", "dm")
        channel_id = user.get("notification_channel_id")

        try:
            memberships = await get_memberships(access_token)
        except Exception as e:
            print(f"[scheduler] Failed to get memberships for {discord_id}: {e}")
            continue

        for membership in memberships:
            campaign_id = membership["campaign_id"]
            creator_name = membership.get("vanity") or "A creator"
            creator_url = membership.get("url", "")

            try:
                posts = await get_recent_posts(access_token, campaign_id)
            except Exception as e:
                print(f"[scheduler] Failed to get posts for campaign {campaign_id}: {e}")
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
