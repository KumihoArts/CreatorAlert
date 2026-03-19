import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import logging
import os

from bot.db import init_db, get_user, delete_user, set_notification_mode, set_creator_channel, get_creator_channel
from bot.scheduler import start_scheduler

load_dotenv()

# Suppress the misleading privileged intent warning — we intentionally don't use these
logging.getLogger("discord.ext.commands.bot").setLevel(logging.ERROR)

AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "https://auth-production-4018.up.railway.app")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", "0"))
BOT_OWNER_ID = 244962442008854540
BOT_VERSION = "1.0.0"
GITHUB_URL = "https://github.com/KumihoArts/CreatorAlert"
INVITE_PERMISSIONS = discord.Permissions(send_messages=True, embed_links=True, send_messages_in_threads=True)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    await init_db()
    if TEST_GUILD_ID:
        guild = discord.Object(id=TEST_GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"Commands synced to test guild {TEST_GUILD_ID}.")
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

    # Confirmation step
    view = ConfirmDisconnectView()
    await interaction.followup.send(
        "Are you sure you want to disconnect your Patreon account? "
        "This will stop all notifications and remove your stored data.",
        view=view,
        ephemeral=True
    )


class ConfirmDisconnectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="Yes, disconnect", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await delete_user(interaction.user.id)
        self.stop()
        await interaction.response.edit_message(
            content="✅ Your Patreon account has been disconnected. You will no longer receive notifications.",
            view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            content="Disconnect cancelled.",
            view=None
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


@bot.tree.command(name="setup", description="[Creator] Post Patreon updates to a channel in this server")
@app_commands.describe(channel="The channel to post new Patreon updates in")
@app_commands.default_permissions(manage_guild=True)
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)

    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send(
            "❌ You need to connect your Patreon account first. Use `/connect`.",
            ephemeral=True
        )
        return

    perms = channel.permissions_for(interaction.guild.me)
    if not perms.send_messages or not perms.embed_links:
        await interaction.followup.send(
            f"❌ I don't have permission to send messages or embed links in {channel.mention}. "
            "Please update the channel permissions and try again.",
            ephemeral=True
        )
        return

    # Check if there's already a channel set for this creator in this guild
    existing = await get_creator_channel(interaction.guild.id, user["patreon_user_id"])

    await set_creator_channel(interaction.guild.id, channel.id, user["patreon_user_id"])

    if existing and existing != channel.id:
        desc = (
            f"Notification channel updated to {channel.mention}.\n\n"
            f"Previously set to <#{existing}>."
        )
    else:
        desc = (
            f"New posts from your Patreon will be posted in {channel.mention}.\n\n"
            "Make sure your notification mode includes **Channel** — use `/notifications` to check."
        )

    embed = discord.Embed(
        title="✅ Creator channel set",
        description=desc,
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="invite", description="Get the link to invite CreatorAlert to your server")
async def invite(interaction: discord.Interaction):
    invite_url = discord.utils.oauth_url(
        bot.user.id,
        permissions=INVITE_PERMISSIONS,
        scopes=["bot", "applications.commands"]
    )
    embed = discord.Embed(
        title="Invite CreatorAlert",
        description=f"[Click here to add CreatorAlert to your server]({invite_url})\n\n"
                    "Once added, use `/connect` to link your Patreon account and start receiving notifications.",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="about", description="About CreatorAlert")
async def about(interaction: discord.Interaction):
    invite_url = discord.utils.oauth_url(
        bot.user.id,
        permissions=INVITE_PERMISSIONS,
        scopes=["bot", "applications.commands"]
    )
    embed = discord.Embed(
        title="CreatorAlert",
        description="Never miss a Patreon post. CreatorAlert notifies you on Discord whenever a creator you support publishes something new.",
        color=discord.Color.orange()
    )
    embed.add_field(name="Version", value=BOT_VERSION, inline=True)
    embed.add_field(name="Polling interval", value="Every 10 minutes", inline=True)
    embed.add_field(
        name="Links",
        value=f"[Invite]({invite_url}) · [GitHub]({GITHUB_URL}) · "
              f"[Privacy Notice]({GITHUB_URL}/blob/main/legal/PRIVACY_NOTICE.md) · "
              f"[Terms of Service]({GITHUB_URL}/blob/main/legal/TERMS_OF_SERVICE.md)",
        inline=False
    )
    embed.set_footer(text="Built by KumihoArts · Not affiliated with Patreon or Discord")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="testnotification", description="[Dev] Send a test notification to yourself")
async def testnotification(interaction: discord.Interaction):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ This command is restricted.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send("❌ No Patreon account connected.", ephemeral=True)
        return

    mode = user.get("notification_mode", "dm")
    channel_id = user.get("notification_channel_id")

    embed = discord.Embed(
        title="📬 New post from Test Creator",
        description="**This is a test notification from CreatorAlert!**",
        url="https://www.patreon.com",
        color=discord.Color.orange()
    )
    embed.set_footer(text="This is a test — real notifications will look just like this.")

    sent = []

    if mode in ("dm", "both"):
        try:
            await interaction.user.send(embed=embed)
            sent.append("DM ✅")
        except Exception as e:
            sent.append(f"DM failed: {e}")

    if mode in ("channel", "both") and channel_id:
        try:
            channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
            await channel.send(f"<@{interaction.user.id}>", embed=embed)
            sent.append(f"<#{channel_id}> ✅")
        except Exception as e:
            sent.append(f"Channel failed: {e}")

    if not sent:
        result = "Nothing sent — check your `/notifications` mode setting."
    else:
        result = ", ".join(sent)

    await interaction.followup.send(f"Test notification result: {result}", ephemeral=True)


@bot.tree.command(name="help", description="Show help information")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="CreatorAlert Help",
        description="Get notified when Patreon creators you support post new content.",
        color=discord.Color.blurple()
    )
    embed.add_field(name="/connect", value="Link your Patreon account", inline=False)
    embed.add_field(name="/disconnect", value="Unlink your Patreon account", inline=False)
    embed.add_field(name="/status", value="Check your connection status and notification settings", inline=False)
    embed.add_field(name="/notifications", value="Choose how to receive notifications (DM, channel, or both)", inline=False)
    embed.add_field(name="/setup", value="[Creator] Set a channel in this server to receive your Patreon updates", inline=False)
    embed.add_field(name="/invite", value="Get the link to invite CreatorAlert to your server", inline=False)
    embed.add_field(name="/about", value="About CreatorAlert", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(os.getenv("DISCORD_TOKEN"))
