import asyncio
import discord

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
            print(f"Scheduler error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

async def _check_for_new_posts(bot: discord.Client):
    """Poll Patreon for new posts and dispatch notifications."""
    # TODO: query DB for all connected users, fetch posts, compare against seen_posts
    pass
