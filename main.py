import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import logging
import aiohttp
import os

from bot.db import (
    init_db, get_user, delete_user, set_notification_mode, set_creator_channel,
    get_creator_channel, set_premium_style, add_premium_channel, remove_premium_channel,
    get_premium_channels, set_ping_role
)
from bot.premium import is_premium, PREMIUM_SKU_ID
from bot.scheduler import start_scheduler

load_dotenv()

logging.getLogger("discord.ext.commands.bot").setLevel(logging.ERROR)

AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "https://auth-production-4018.up.railway.app")
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID", "0"))
BOT_OWNER_ID = 244962442008854540
BOT_VERSION = "1.0.0"
GITHUB_URL = "https://github.com/KumihoArts/CreatorAlert"
SUPPORT_SERVER = "https://discord.gg/KVcu3HvHB3"
DBL_TOKEN = os.getenv("DBL_TOKEN")
INVITE_PERMISSIONS = discord.Permissions(send_messages=True, embed_links=True, send_messages_in_threads=True)

DBL_COMMANDS = [
    {"name": "connect", "description": "Connect your Patreon account", "type": 1},
    {"name": "disconnect", "description": "Disconnect your Patreon account", "type": 1},
    {"name": "status", "description": "Check your Patreon connection status and notification settings", "type": 1},
    {"name": "notifications", "description": "Configure how you receive Patreon notifications (DM, channel, or both)", "type": 1},
    {"name": "setup", "description": "[Creator] Set a channel in your server for automatic Patreon post announcements", "type": 1},
    {"name": "premium", "description": "View or subscribe to CreatorAlert Premium", "type": 1},
    {"name": "customize", "description": "[Premium] Set a custom embed colour and notification message", "type": 1},
    {"name": "channels", "description": "[Premium] Manage multiple notification channels", "type": 1},
    {"name": "pingrole", "description": "[Premium] Set a role to ping in channel notifications instead of your username", "type": 1},
    {"name": "invite", "description": "Get the link to invite CreatorAlert to your server", "type": 1},
    {"name": "about", "description": "About CreatorAlert", "type": 1},
    {"name": "help", "description": "Show all available commands", "type": 1},
]

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


async def post_dbl_commands():
    if not DBL_TOKEN:
        return
    url = f"https://discordbotlist.com/api/v1/bots/{bot.user.id}/commands"
    headers = {"Authorization": f"Bot {DBL_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=DBL_COMMANDS) as resp:
            if resp.status == 200:
                print("Commands posted to discordbotlist.com.")
            else:
                text = await resp.text()
                print(f"Failed to post commands to discordbotlist.com: {resp.status} {text}")


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
    await post_dbl_commands()
    start_scheduler(bot)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_premium(interaction: discord.Interaction) -> bool:
    return is_premium(interaction.user.id, list(interaction.entitlements))


async def _check_channel_access(
    interaction: discord.Interaction,
    channel: discord.TextChannel
) -> str | None:
    """
    Verify both the user and the bot can send messages in the channel.
    Returns an error message string if denied, None if allowed.
    """
    # User must be able to send messages in the channel themselves
    user_perms = channel.permissions_for(interaction.user)
    if not user_perms.send_messages:
        return f"❌ You don't have permission to send messages in {channel.mention}. You can only set notification channels you have access to."

    # Bot must also be able to send and embed
    bot_perms = channel.permissions_for(interaction.guild.me)
    if not bot_perms.send_messages or not bot_perms.embed_links:
        return f"❌ I don't have permission to send messages or embed links in {channel.mention}. Please update the channel permissions and try again."

    return None


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
        await interaction.response.edit_message(content="Disconnect cancelled.", view=None)


@bot.tree.command(name="status", description="Check your Patreon connection status")
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user = await get_user(interaction.user.id)
    premium = _check_premium(interaction)

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
        embed.add_field(name="Premium", value="✅ Active" if premium else "❌ Not subscribed", inline=False)

        if premium:
            extra_channels = await get_premium_channels(interaction.user.id)
            if extra_channels:
                embed.add_field(
                    name="Extra channels",
                    value=", ".join(f"<#{ch}>" for ch in extra_channels),
                    inline=False
                )
            ping_role_id = user.get("ping_role_id")
            custom_msg = user.get("custom_message")
            colour = user.get("embed_colour")
            if ping_role_id:
                embed.add_field(name="Ping role", value=f"<@&{ping_role_id}>", inline=True)
            if custom_msg:
                embed.add_field(name="Custom message", value=custom_msg, inline=False)
            if colour:
                embed.add_field(name="Embed colour", value=colour, inline=True)

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
            "❌ You need to connect your Patreon account first. Use `/connect`.", ephemeral=True
        )
        return
    if mode.value in ("channel", "both") and channel is None:
        await interaction.followup.send(
            "❌ Please specify a channel when using 'Channel only' or 'DM + Channel' mode.", ephemeral=True
        )
        return
    if channel is not None:
        error = await _check_channel_access(interaction, channel)
        if error:
            await interaction.followup.send(error, ephemeral=True)
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
            "❌ You need to connect your Patreon account first. Use `/connect`.", ephemeral=True
        )
        return
    # /setup already requires manage_guild permission, so the user check is implicitly covered.
    # Just check bot permissions.
    bot_perms = channel.permissions_for(interaction.guild.me)
    if not bot_perms.send_messages or not bot_perms.embed_links:
        await interaction.followup.send(
            f"❌ I don't have permission to send messages or embed links in {channel.mention}. "
            "Please update the channel permissions and try again.", ephemeral=True
        )
        return
    existing = await get_creator_channel(interaction.guild.id, user["patreon_user_id"])
    await set_creator_channel(interaction.guild.id, channel.id, user["patreon_user_id"])
    if existing and existing != channel.id:
        desc = f"Notification channel updated to {channel.mention}.\n\nPreviously set to <#{existing}>."
    else:
        desc = (
            f"New posts from your Patreon will be posted in {channel.mention}.\n\n"
            "Make sure your notification mode includes **Channel** — use `/notifications` to check."
        )
    embed = discord.Embed(title="✅ Creator channel set", description=desc, color=discord.Color.green())
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="premium", description="Check your CreatorAlert Premium status")
async def premium_status(interaction: discord.Interaction):
    premium = _check_premium(interaction)
    if premium:
        embed = discord.Embed(
            title="✅ Premium Active",
            description=(
                "You have an active CreatorAlert Premium subscription. "
                "Your notifications are checked every 3 minutes.\n\n"
                "Use `/customize` to set a custom embed colour or notification message.\n"
                "Use `/channels` to manage multiple notification channels.\n"
                "Use `/pingrole` to set a role to ping in channel notifications."
            ),
            color=discord.Color.gold()
        )
    else:
        embed = discord.Embed(
            title="CreatorAlert Premium",
            description="Upgrade to Premium for faster notifications, custom styling, and more.\n\nSubscribe via the button below.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Faster polling", value="Every 3 min instead of 10", inline=True)
        embed.add_field(name="Multiple channels", value="Notify as many channels as you want", inline=True)
        embed.add_field(name="Custom colour", value="Set your embed colour", inline=True)
        embed.add_field(name="Custom message", value="Add a personal intro to notifications", inline=True)
        embed.add_field(name="Role ping", value="Ping a role instead of your username", inline=True)
    await interaction.response.send_message(
        embed=embed,
        view=PremiumSubscribeView() if not premium else None,
        ephemeral=True
    )


class PremiumSubscribeView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.Button(
            label="Subscribe to Premium",
            style=discord.ButtonStyle.premium,
            sku_id=PREMIUM_SKU_ID
        ))


@bot.tree.command(name="customize", description="[Premium] Customize your notification embed colour and message")
@app_commands.describe(
    colour="Hex colour for your notification embeds (e.g. #ff6600)",
    message="Custom message prepended to every notification (e.g. 'New post!')"
)
async def customize(
    interaction: discord.Interaction,
    colour: str = None,
    message: str = None
):
    await interaction.response.defer(ephemeral=True)
    if not _check_premium(interaction):
        await interaction.followup.send(
            "❌ This feature requires **CreatorAlert Premium**. Use `/premium` to subscribe.", ephemeral=True
        )
        return
    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send(
            "❌ You need to connect your Patreon account first. Use `/connect`.", ephemeral=True
        )
        return
    if colour:
        colour = colour.strip()
        if not colour.startswith("#") or len(colour) != 7:
            await interaction.followup.send(
                "❌ Invalid colour format. Please use a hex code like `#ff6600`.", ephemeral=True
            )
            return
        try:
            int(colour[1:], 16)
        except ValueError:
            await interaction.followup.send(
                "❌ Invalid hex colour. Please use a format like `#ff6600`.", ephemeral=True
            )
            return
    if message and len(message) > 200:
        await interaction.followup.send(
            "❌ Custom message must be 200 characters or fewer.", ephemeral=True
        )
        return
    await set_premium_style(interaction.user.id, colour, message)
    lines = ["✅ Customisation saved."]
    if colour:
        lines.append(f"Embed colour set to `{colour}`.")
    if message:
        lines.append(f"Custom message set to: *{message}*")
    if not colour and not message:
        lines = ["✅ Customisation cleared."]
    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="pingrole", description="[Premium] Set a role to ping in channel notifications instead of your username")
@app_commands.describe(role="The role to ping when a new post notification is sent (leave empty to clear)")
async def pingrole(
    interaction: discord.Interaction,
    role: discord.Role = None
):
    await interaction.response.defer(ephemeral=True)
    if not _check_premium(interaction):
        await interaction.followup.send(
            "❌ This feature requires **CreatorAlert Premium**. Use `/premium` to subscribe.", ephemeral=True
        )
        return
    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send(
            "❌ You need to connect your Patreon account first. Use `/connect`.", ephemeral=True
        )
        return
    if role is None:
        await set_ping_role(interaction.user.id, None)
        await interaction.followup.send(
            "✅ Ping role cleared. Channel notifications will ping you directly.", ephemeral=True
        )
        return
    await set_ping_role(interaction.user.id, role.id)
    await interaction.followup.send(
        f"✅ Ping role set to {role.mention}. Channel notifications will ping this role instead of your username.",
        ephemeral=True
    )


@bot.tree.command(name="channels", description="[Premium] Manage additional notification channels")
@app_commands.describe(action="Add or remove a channel", channel="The channel to add or remove")
@app_commands.choices(action=[
    app_commands.Choice(name="Add channel", value="add"),
    app_commands.Choice(name="Remove channel", value="remove"),
    app_commands.Choice(name="List channels", value="list"),
])
async def channels(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
    channel: discord.TextChannel = None
):
    await interaction.response.defer(ephemeral=True)
    if not _check_premium(interaction):
        await interaction.followup.send(
            "❌ This feature requires **CreatorAlert Premium**. Use `/premium` to subscribe.", ephemeral=True
        )
        return
    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send(
            "❌ You need to connect your Patreon account first. Use `/connect`.", ephemeral=True
        )
        return
    if action.value == "list":
        extra = await get_premium_channels(interaction.user.id)
        if not extra:
            await interaction.followup.send("You have no extra notification channels set up.", ephemeral=True)
        else:
            channel_list = "\n".join(f"• <#{ch}>" for ch in extra)
            await interaction.followup.send(f"Your extra notification channels:\n{channel_list}", ephemeral=True)
        return
    if channel is None:
        await interaction.followup.send("❌ Please specify a channel.", ephemeral=True)
        return
    if action.value == "add":
        error = await _check_channel_access(interaction, channel)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        await add_premium_channel(interaction.user.id, channel.id)
        await interaction.followup.send(f"✅ {channel.mention} added to your notification channels.", ephemeral=True)
    elif action.value == "remove":
        await remove_premium_channel(interaction.user.id, channel.id)
        await interaction.followup.send(f"✅ {channel.mention} removed from your notification channels.", ephemeral=True)


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
    embed.set_footer(text=f"Need help? Join the support server: {SUPPORT_SERVER}")
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
    embed.add_field(name="Polling interval", value="Every 3 min (Premium) / 10 min (Free)", inline=True)
    embed.add_field(
        name="Links",
        value=f"[Invite]({invite_url}) · [Support Server]({SUPPORT_SERVER}) · [GitHub]({GITHUB_URL}) · "
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
    premium = _check_premium(interaction)
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
    embed.add_field(name="/premium", value="View or subscribe to CreatorAlert Premium", inline=False)
    if premium:
        embed.add_field(name="/customize", value="[Premium] Set a custom embed colour and notification message", inline=False)
        embed.add_field(name="/channels", value="[Premium] Manage multiple notification channels", inline=False)
        embed.add_field(name="/pingrole", value="[Premium] Set a role to ping in channel notifications", inline=False)
    embed.add_field(name="/invite", value="Get the link to invite CreatorAlert to your server", inline=False)
    embed.add_field(name="/about", value="About CreatorAlert", inline=False)
    embed.set_footer(text=f"Need help? Join the support server: {SUPPORT_SERVER}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(os.getenv("DISCORD_TOKEN"))
