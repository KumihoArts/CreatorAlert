import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import os

from bot.db import init_db, get_user, delete_user, set_notification_mode
from bot.scheduler import start_scheduler

load_dotenv()

AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "https://auth-production-4018.up.railway.app")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    await init_db()
    await bot.tree.sync()
    start_scheduler(bot)

# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

@bot.tree.command(name="connect", description="Connect your Patreon account")
async def connect(interaction: discord.Interaction):
    url = f"{AUTH_BASE_URL}/connect?discord_id={interaction.user.id}"
    embed = discord.Embed(
        title="Connect your Patreon",
        description=f"Click the link below to connect your Patreon account to CreatorAlert.\n\n[🔗 Connect Patreon]({url})",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="disconnect", description="Disconnect your Patreon account")
async def disconnect(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send(
            "❌ You don't have a Patreon account connected.", ephemeral=True
        )
        return
    await delete_user(interaction.user.id)
    await interaction.followup.send(
        "✅ Your Patreon account has been disconnected. You will no longer receive notifications.",
        ephemeral=True
    )


@bot.tree.command(name="status", description="Check your Patreon connection status")
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user = await get_user(interaction.user.id)
    if not user:
        embed = discord.Embed(
            title="Patreon Status",
            description="❌ No Patreon account connected.\n\nUse `/connect` to link your account.",
            color=discord.Color.red()
        )
    else:
        connected_at = user["connected_at"].strftime("%Y-%m-%d %H:%M UTC") if user.get("connected_at") else "Unknown"
        mode = user.get("notification_mode", "dm")
        mode_display = {"dm": "DM only", "channel": "Channel only", "both": "DM + Channel"}.get(mode, mode)
        channel_id = user.get("notification_channel_id")
        channel_str = f"<#{channel_id}>" if channel_id else "Not set"

        embed = discord.Embed(
            title="Patreon Status",
            description="✅ Patreon account connected.",
            color=discord.Color.green()
        )
        embed.add_field(name="Patreon User ID", value=user["patreon_user_id"], inline=False)
        embed.add_field(name="Connected since", value=connected_at, inline=False)
        embed.add_field(name="Notification mode", value=mode_display, inline=True)
        if mode in ("channel", "both"):
            embed.add_field(name="Notification channel", value=channel_str, inline=True)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="notifications", description="Configure how you receive Patreon notifications")
@app_commands.describe(
    mode="How you want to receive notifications",
    channel="Channel to send notifications in (required for 'channel' or 'both' modes)"
)
@app_commands.choices(mode=[
    app_commands.Choice(name="DM only", value="dm"),
    app_commands.Choice(name="Channel only", value="channel"),
    app_commands.Choice(name="DM + Channel", value="both"),
])
async def notifications(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
    channel: discord.TextChannel = None
):
    await interaction.response.defer(ephemeral=True)

    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send(
            "❌ You need to connect your Patreon account first. Use `/connect`.",
            ephemeral=True
        )
        return

    if mode.value in ("channel", "both") and channel is None:
        await interaction.followup.send(
            "❌ Please specify a channel when using 'Channel only' or 'DM + Channel' mode.",
            ephemeral=True
        )
        return

    channel_id = channel.id if channel else None
    await set_notification_mode(interaction.user.id, mode.value, channel_id)

    mode_display = {"dm": "DM only", "channel": "Channel only", "both": "DM + Channel"}.get(mode.value, mode.value)
    desc = f"✅ Notification mode set to **{mode_display}**."
    if channel:
        desc += f"\nNotifications will be sent to {channel.mention}."

    await interaction.followup.send(desc, ephemeral=True)


@bot.tree.command(name="setup", description="[Creator] Set the channel for Patreon post notifications")
async def setup(interaction: discord.Interaction):
    await interaction.response.send_message("Creator setup — coming soon!", ephemeral=True)


@bot.tree.command(name="help", description="Show help information")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="CreatorAlert Help",
        description="Get notified when Patreon creators you support post new content.",
        color=discord.Color.blurple()
    )
    embed.add_field(name="/connect", value="Link your Patreon account", inline=False)
    embed.add_field(name="/disconnect", value="Unlink your Patreon account", inline=False)
    embed.add_field(name="/status", value="Check your connection status", inline=False)
    embed.add_field(name="/notifications", value="Choose how to receive notifications (DM, channel, or both)", inline=False)
    embed.add_field(name="/setup", value="[Creator] Set notification channel for your server", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(os.getenv("DISCORD_TOKEN"))
