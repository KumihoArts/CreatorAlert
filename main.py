import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import logging
import aiohttp
import os

from bot.db import (
    init_db, get_user, get_all_user_platforms, delete_user, set_premium_style,
    set_creator_channel, get_creator_channel, get_creator_channels_for_guild,
    set_creator_ping_role, mute_creator, unmute_creator, get_muted_creators,
    get_muted_creators_with_platform
)
from bot.platforms import PLATFORM_LABELS, PLATFORM_COLOURS, label as platform_label
from bot.premium import is_premium, PREMIUM_SKU_ID
from bot.scheduler import start_scheduler

load_dotenv()

logging.getLogger("discord.ext.commands.bot").setLevel(logging.ERROR)

AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "https://auth-production-4018.up.railway.app")
BOT_OWNER_ID = 244962442008854540
BOT_VERSION = "1.5.0"
GITHUB_URL = "https://github.com/KumihoArts/CreatorAlert"
SUPPORT_SERVER = "https://discord.gg/KVcu3HvHB3"
DBL_TOKEN = os.getenv("DBL_TOKEN")
INVITE_PERMISSIONS = discord.Permissions(send_messages=True, embed_links=True, send_messages_in_threads=True)

DBL_COMMANDS = [
    {"name": "connect", "description": "Connect a Patreon, SubscribeStar, or Gumroad account", "type": 1},
    {"name": "disconnect", "description": "Disconnect a connected account", "type": 1},
    {"name": "status", "description": "Check your connected accounts and notification settings", "type": 1},
    {"name": "setup", "description": "[Creator] Set a channel in your server for automatic post announcements", "type": 1},
    {"name": "pingrole", "description": "[Creator] Set a role to ping when new posts are announced in your server", "type": 1},
    {"name": "premium", "description": "View or subscribe to CreatorAlert Premium", "type": 1},
    {"name": "customize", "description": "[Premium] Set a custom embed colour and notification message", "type": 1},
    {"name": "mute", "description": "Mute notifications from a specific creator", "type": 1},
    {"name": "unmute", "description": "Restore notifications from a muted creator", "type": 1},
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
    await bot.tree.sync()
    print("Global commands synced.")
    await post_dbl_commands()
    start_scheduler(bot)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_premium(interaction: discord.Interaction) -> bool:
    return is_premium(interaction.user.id, list(interaction.entitlements))


# ---------------------------------------------------------------------------
# /connect
# ---------------------------------------------------------------------------

@bot.tree.command(name="connect", description="Connect a Patreon, SubscribeStar, or Gumroad account")
async def connect(interaction: discord.Interaction):
    view = ConnectPlatformView()
    await interaction.response.send_message(
        "Choose a platform to connect:",
        view=view,
        ephemeral=True
    )


class ConnectPlatformView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Patreon", style=discord.ButtonStyle.primary, emoji="🎨")
    async def connect_patreon(self, interaction: discord.Interaction, button: discord.ui.Button):
        url = f"{AUTH_BASE_URL}/connect/patreon?discord_id={interaction.user.id}"
        embed = discord.Embed(
            title="Connect your Patreon",
            description=f"Click the link below to connect your Patreon account to CreatorAlert.\n\n[🔗 Connect Patreon]({url})",
            color=discord.Color(PLATFORM_COLOURS["patreon"])
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)


    @discord.ui.button(label="SubscribeStar", style=discord.ButtonStyle.primary, emoji="⭐")
    async def connect_subscribestar(self, interaction: discord.Interaction, button: discord.ui.Button):
        url = f"{AUTH_BASE_URL}/connect/subscribestar?discord_id={interaction.user.id}"
        embed = discord.Embed(
            title="Connect your SubscribeStar",
            description=(
                f"Click the link below to connect your SubscribeStar account to CreatorAlert.\n\n"
                f"[🔗 Connect SubscribeStar]({url})\n\n"
                f"> ⚠️ **Note:** SubscribeStar's API does not currently expose post content, "
                f"so post notifications are not available for SubscribeStar at this time. "
                f"Your account will be saved and notifications enabled automatically if this changes."
            ),
            color=discord.Color(PLATFORM_COLOURS["subscribestar"])
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    @discord.ui.button(label="Gumroad", style=discord.ButtonStyle.primary, emoji="🛒")
    async def connect_gumroad(self, interaction: discord.Interaction, button: discord.ui.Button):
        url = f"{AUTH_BASE_URL}/connect/gumroad?discord_id={interaction.user.id}"
        embed = discord.Embed(
            title="Connect your Gumroad",
            description=f"Click the link below to connect your Gumroad account to CreatorAlert.\n\n[🔗 Connect Gumroad]({url})\n\n> **Note:** Gumroad is creator-only — it announces new products to a channel in your server. There are no subscriber DMs for Gumroad.",
            color=discord.Color(PLATFORM_COLOURS["gumroad"])
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)


# ---------------------------------------------------------------------------
# /disconnect
# ---------------------------------------------------------------------------

@bot.tree.command(name="disconnect", description="Disconnect a connected account")
async def disconnect(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    connected = await get_all_user_platforms(interaction.user.id)
    if not connected:
        await interaction.followup.send("❌ You don't have any accounts connected.", ephemeral=True)
        return

    if len(connected) == 1:
        view = ConfirmDisconnectView(connected[0])
        plabel = platform_label(connected[0])
        await interaction.followup.send(
            f"Are you sure you want to disconnect your **{plabel}** account? "
            "This will stop all notifications from that platform and remove your stored data.",
            view=view, ephemeral=True
        )
    else:
        view = DisconnectPlatformView(connected)
        await interaction.followup.send("Which account would you like to disconnect?", view=view, ephemeral=True)


class DisconnectPlatformView(discord.ui.View):
    def __init__(self, platforms: list[str]):
        super().__init__(timeout=60)
        for p in platforms:
            button = discord.ui.Button(
                label=platform_label(p),
                style=discord.ButtonStyle.danger,
                custom_id=f"disconnect_{p}"
            )
            button.callback = self._make_callback(p)
            self.add_item(button)

    def _make_callback(self, platform: str):
        async def callback(interaction: discord.Interaction):
            view = ConfirmDisconnectView(platform)
            plabel = platform_label(platform)
            await interaction.response.edit_message(
                content=f"Are you sure you want to disconnect your **{plabel}** account? "
                        "This will stop all notifications from that platform and remove your stored data.",
                view=view
            )
        return callback


class ConfirmDisconnectView(discord.ui.View):
    def __init__(self, platform: str):
        super().__init__(timeout=30)
        self.platform = platform

    @discord.ui.button(label="Yes, disconnect", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await delete_user(interaction.user.id, self.platform)
        self.stop()
        plabel = platform_label(self.platform)
        await interaction.response.edit_message(
            content=f"✅ Your **{plabel}** account has been disconnected. You will no longer receive notifications from that platform.",
            view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="Disconnect cancelled.", view=None)


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

@bot.tree.command(name="status", description="Check your connected accounts and notification settings")
async def status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    premium = _check_premium(interaction)
    connected = await get_all_user_platforms(interaction.user.id)

    if not connected:
        embed = discord.Embed(
            title="Connection Status",
            description="❌ No accounts connected.\n\nUse `/connect` to link a Patreon, SubscribeStar, or Gumroad account.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="Connection Status",
        description=f"✅ {len(connected)} account{'s' if len(connected) > 1 else ''} connected.",
        color=discord.Color.green()
    )

    for platform in connected:
        account = await get_user(interaction.user.id, platform)
        if not account:
            continue
        connected_at = account["connected_at"].strftime("%Y-%m-%d %H:%M UTC") if account.get("connected_at") else "Unknown"
        muted = await get_muted_creators(interaction.user.id, platform)
        value = f"ID: `{account['platform_user_id']}`\nConnected: {connected_at}"
        if muted:
            value += f"\nMuted creators: {len(muted)}"
        if premium and account.get("custom_message"):
            value += f"\nCustom message: *{account['custom_message']}*"
        if premium and account.get("embed_colour"):
            value += f"\nEmbed colour: `{account['embed_colour']}`"
        if interaction.guild:
            creator_ch = await get_creator_channels_for_guild(
                interaction.guild.id, account["platform_user_id"], platform
            )
            if creator_ch:
                value += f"\nAnnouncement channel: <#{creator_ch['channel_id']}>"
                if creator_ch.get("ping_role_id"):
                    value += f"\nPing role: <@&{creator_ch['ping_role_id']}>"
        embed.add_field(name=platform_label(platform), value=value, inline=False)

    embed.add_field(name="Premium", value="✅ Active" if premium else "❌ Not subscribed", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /setup
# ---------------------------------------------------------------------------

@bot.tree.command(name="setup", description="[Creator] Post your updates to a channel in this server")
@app_commands.describe(
    channel="The channel to post updates in",
    platform="Which platform to set up announcements for"
)
@app_commands.choices(platform=[
    app_commands.Choice(name="Patreon", value="patreon"),
    app_commands.Choice(name="SubscribeStar", value="subscribestar"),
    app_commands.Choice(name="Gumroad", value="gumroad"),
])
@app_commands.default_permissions(manage_guild=True)
async def setup(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    platform: app_commands.Choice[str] = None
):
    await interaction.response.defer(ephemeral=True)

    if platform is None:
        connected = await get_all_user_platforms(interaction.user.id)
        if not connected:
            await interaction.followup.send("❌ You need to connect an account first. Use `/connect`.", ephemeral=True)
            return
        if len(connected) > 1:
            await interaction.followup.send("❌ You have multiple platforms connected. Please specify the `platform` option.", ephemeral=True)
            return
        platform_str = connected[0]
    else:
        platform_str = platform.value

    account = await get_user(interaction.user.id, platform_str)
    if not account:
        plabel = platform_label(platform_str)
        await interaction.followup.send(f"❌ You don't have a {plabel} account connected. Use `/connect`.", ephemeral=True)
        return

    bot_perms = channel.permissions_for(interaction.guild.me)
    if not bot_perms.send_messages or not bot_perms.embed_links:
        await interaction.followup.send(
            f"❌ I don't have permission to send messages or embed links in {channel.mention}. "
            "Please update the channel permissions and try again.", ephemeral=True
        )
        return

    existing = await get_creator_channel(interaction.guild.id, account["platform_user_id"], platform_str)
    await set_creator_channel(interaction.guild.id, channel.id, account["platform_user_id"], platform_str)

    plabel = platform_label(platform_str)
    if existing and existing != channel.id:
        desc = f"Announcement channel updated to {channel.mention}.\n\nPreviously set to <#{existing}>."
    else:
        desc = (
            f"New posts from your {plabel} will be announced in {channel.mention}.\n\n"
            "Optionally use `/pingrole` to set a role to ping with each announcement."
        )

    embed = discord.Embed(title="✅ Creator channel set", description=desc, color=discord.Color.green())
    await interaction.followup.send(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /pingrole
# ---------------------------------------------------------------------------

@bot.tree.command(name="pingrole", description="[Creator] Set a role to ping when your posts are announced")
@app_commands.describe(
    role="The role to ping with each announcement (leave empty to clear)",
    platform="Which platform's announcements to configure"
)
@app_commands.choices(platform=[
    app_commands.Choice(name="Patreon", value="patreon"),
    app_commands.Choice(name="SubscribeStar", value="subscribestar"),
    app_commands.Choice(name="Gumroad", value="gumroad"),
])
@app_commands.default_permissions(manage_guild=True)
async def pingrole(
    interaction: discord.Interaction,
    role: discord.Role = None,
    platform: app_commands.Choice[str] = None
):
    await interaction.response.defer(ephemeral=True)

    if platform is None:
        connected = await get_all_user_platforms(interaction.user.id)
        if not connected:
            await interaction.followup.send("❌ You need to connect an account first. Use `/connect`.", ephemeral=True)
            return
        if len(connected) > 1:
            await interaction.followup.send("❌ You have multiple platforms connected. Please specify the `platform` option.", ephemeral=True)
            return
        platform_str = connected[0]
    else:
        platform_str = platform.value

    account = await get_user(interaction.user.id, platform_str)
    if not account:
        plabel = platform_label(platform_str)
        await interaction.followup.send(f"❌ You don't have a {plabel} account connected. Use `/connect`.", ephemeral=True)
        return

    existing_channel = await get_creator_channel(interaction.guild.id, account["platform_user_id"], platform_str)
    if not existing_channel:
        await interaction.followup.send("❌ You need to set up a creator channel first. Use `/setup` to designate one.", ephemeral=True)
        return

    if role is None:
        await set_creator_ping_role(interaction.guild.id, account["platform_user_id"], platform_str, None)
        await interaction.followup.send("✅ Ping role cleared. Announcements will no longer ping a role.", ephemeral=True)
        return

    if role.is_default() or role.name == "@everyone":
        await interaction.followup.send("❌ You cannot set `@everyone` as the ping role.", ephemeral=True)
        return

    if role >= interaction.guild.me.top_role:
        await interaction.followup.send(
            f"❌ I can't ping {role.mention} because it's higher than or equal to my own role. "
            "Please choose a lower role.", ephemeral=True
        )
        return

    await set_creator_ping_role(interaction.guild.id, account["platform_user_id"], platform_str, role.id)
    await interaction.followup.send(
        f"✅ Ping role set to {role.mention}. This role will be pinged with each new post announcement.",
        ephemeral=True
    )


# ---------------------------------------------------------------------------
# /mute
# ---------------------------------------------------------------------------

@bot.tree.command(name="mute", description="Mute notifications from a specific creator")
async def mute(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    connected = await get_all_user_platforms(interaction.user.id)
    if not connected:
        await interaction.followup.send("❌ You need to connect an account first. Use `/connect`.", ephemeral=True)
        return

    all_available = []
    for platform in connected:
        account = await get_user(interaction.user.id, platform)
        if not account:
            continue
        from bot.platforms import get_platform
        client = get_platform(platform)
        if not client:
            continue
        memberships = await client.get_memberships(account["access_token"])
        if not memberships:
            continue
        muted = await get_muted_creators(interaction.user.id, platform)
        for m in memberships:
            if m["campaign_id"] not in muted:
                all_available.append((platform, m))

    if not all_available:
        await interaction.followup.send(
            "No creators available to mute. Either you have no active memberships, or all are already muted. Use `/unmute` to restore notifications.",
            ephemeral=True
        )
        return

    options = [
        discord.SelectOption(
            label=m.get("vanity") or "Unknown Creator",
            value=f"{plat}:{m['campaign_id']}",
            description=f"{platform_label(plat)} · {m.get('url', '')[:80]}",
        )
        for plat, m in all_available[:25]
    ]

    view = MuteSelectView(options)
    await interaction.followup.send(
        "Select a creator to mute. You will no longer receive notifications from them.",
        view=view, ephemeral=True
    )


class MuteSelectView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        select = discord.ui.Select(placeholder="Choose a creator to mute...", options=options)
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        platform, campaign_id = value.split(":", 1)
        creator_name = next(
            (opt.label for opt in self.children[0].options if opt.value == value), "That creator"
        )
        await mute_creator(interaction.user.id, platform, campaign_id)
        self.stop()
        await interaction.response.edit_message(
            content=f"🔇 **{creator_name}** has been muted. You will no longer receive notifications from them.\n\nUse `/unmute` to restore notifications.",
            view=None
        )


# ---------------------------------------------------------------------------
# /unmute
# ---------------------------------------------------------------------------

@bot.tree.command(name="unmute", description="Restore notifications from a muted creator")
async def unmute(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    muted_list = await get_muted_creators_with_platform(interaction.user.id)
    if not muted_list:
        await interaction.followup.send(
            "You have no muted creators. Use `/mute` to mute notifications from a creator.", ephemeral=True
        )
        return

    name_lookup = {}
    connected = await get_all_user_platforms(interaction.user.id)
    for platform in connected:
        account = await get_user(interaction.user.id, platform)
        if not account:
            continue
        from bot.platforms import get_platform
        client = get_platform(platform)
        if not client:
            continue
        memberships = await client.get_memberships(account["access_token"]) or []
        for m in memberships:
            name_lookup[f"{platform}:{m['campaign_id']}"] = m.get("vanity") or "Unknown Creator"

    options = [
        discord.SelectOption(
            label=name_lookup.get(f"{plat}:{cid}", f"Creator ({cid})"),
            value=f"{plat}:{cid}",
            description=platform_label(plat),
        )
        for plat, cid in muted_list[:25]
    ]

    view = UnmuteSelectView(options)
    await interaction.followup.send(
        "Select a creator to unmute. Notifications will resume at the next poll.",
        view=view, ephemeral=True
    )


class UnmuteSelectView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        select = discord.ui.Select(placeholder="Choose a creator to unmute...", options=options)
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]
        platform, campaign_id = value.split(":", 1)
        creator_name = next(
            (opt.label for opt in self.children[0].options if opt.value == value), "That creator"
        )
        await unmute_creator(interaction.user.id, platform, campaign_id)
        self.stop()
        await interaction.response.edit_message(
            content=f"🔔 **{creator_name}** has been unmuted. Notifications will resume at the next poll.",
            view=None
        )


# ---------------------------------------------------------------------------
# /premium
# ---------------------------------------------------------------------------

@bot.tree.command(name="premium", description="Check your CreatorAlert Premium status")
async def premium_status(interaction: discord.Interaction):
    premium = _check_premium(interaction)
    if premium:
        embed = discord.Embed(
            title="✅ Premium Active",
            description=(
                "You have an active CreatorAlert Premium subscription.\n\n"
                "• Notifications checked every **3 minutes** instead of 10\n"
                "• Custom embed colour via `/customize`\n"
                "• Custom notification message via `/customize`"
            ),
            color=discord.Color.gold()
        )
    else:
        embed = discord.Embed(
            title="CreatorAlert Premium",
            description="Upgrade to Premium for faster notifications and custom styling.\n\nSubscribe via the button below.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Faster polling", value="Every 3 min instead of 10", inline=True)
        embed.add_field(name="Custom embed colour", value="Personalise your DM notifications", inline=True)
        embed.add_field(name="Custom message", value="Add a personal intro to every notification", inline=True)
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


# ---------------------------------------------------------------------------
# /customize
# ---------------------------------------------------------------------------

@bot.tree.command(name="customize", description="[Premium] Customize your notification embed colour and message")
@app_commands.describe(
    colour="Hex colour for your notification embeds (e.g. #ff6600)",
    message="Custom message prepended to every notification (e.g. 'New post!')",
    platform="Which platform to customize (applies to all platforms if not specified)"
)
@app_commands.choices(platform=[
    app_commands.Choice(name="Patreon", value="patreon"),
    app_commands.Choice(name="SubscribeStar", value="subscribestar"),
    app_commands.Choice(name="Gumroad", value="gumroad"),
])
async def customize(
    interaction: discord.Interaction,
    colour: str = None,
    message: str = None,
    platform: app_commands.Choice[str] = None
):
    await interaction.response.defer(ephemeral=True)
    if not _check_premium(interaction):
        await interaction.followup.send("❌ This feature requires **CreatorAlert Premium**. Use `/premium` to subscribe.", ephemeral=True)
        return

    if colour:
        colour = colour.strip()
        if not colour.startswith("#") or len(colour) != 7:
            await interaction.followup.send("❌ Invalid colour format. Please use a hex code like `#ff6600`.", ephemeral=True)
            return
        try:
            int(colour[1:], 16)
        except ValueError:
            await interaction.followup.send("❌ Invalid hex colour. Please use a format like `#ff6600`.", ephemeral=True)
            return

    if message and len(message) > 200:
        await interaction.followup.send("❌ Custom message must be 200 characters or fewer.", ephemeral=True)
        return

    connected = await get_all_user_platforms(interaction.user.id)
    if not connected:
        await interaction.followup.send("❌ You need to connect an account first. Use `/connect`.", ephemeral=True)
        return

    platforms_to_update = [platform.value] if platform else connected
    for p in platforms_to_update:
        if p in connected:
            await set_premium_style(interaction.user.id, p, colour, message)

    lines = ["✅ Customisation saved."]
    if colour:
        lines.append(f"Embed colour set to `{colour}`.")
    if message:
        lines.append(f"Custom message set to: *{message}*")
    if not colour and not message:
        lines = ["✅ Customisation cleared."]
    if len(platforms_to_update) > 1:
        lines.append(f"Applied to: {', '.join(platform_label(p) for p in platforms_to_update)}.")

    await interaction.followup.send("\n".join(lines), ephemeral=True)


# ---------------------------------------------------------------------------
# /invite, /about, /testnotification, /servers, /help
# ---------------------------------------------------------------------------

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
                    "Once added, use `/connect` to link your Patreon, SubscribeStar, or Gumroad account.",
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
        description="Never miss a post. CreatorAlert notifies you on Discord whenever a creator you support on Patreon or SubscribeStar publishes something new, or when a Gumroad creator releases a new product.",
        color=discord.Color.orange()
    )
    embed.add_field(name="Version", value=BOT_VERSION, inline=True)
    embed.add_field(name="Polling interval", value="Every 3 min (Premium) / 10 min (Free)", inline=True)
    embed.add_field(name="Platforms", value="Patreon · SubscribeStar · Gumroad", inline=True)
    embed.add_field(
        name="Links",
        value=f"[Invite]({invite_url}) · [Support Server]({SUPPORT_SERVER}) · [GitHub]({GITHUB_URL}) · "
              f"[Privacy Notice]({GITHUB_URL}/blob/main/legal/PRIVACY_NOTICE.md) · "
              f"[Terms of Service]({GITHUB_URL}/blob/main/legal/TERMS_OF_SERVICE.md)",
        inline=False
    )
    embed.set_footer(text="Built by KumihoArts · Not affiliated with Patreon, SubscribeStar, Gumroad, or Discord")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="testnotification", description="[Dev] Send a test notification to yourself")
async def testnotification(interaction: discord.Interaction):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ This command is restricted.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    connected = await get_all_user_platforms(interaction.user.id)
    if not connected:
        await interaction.followup.send("❌ No accounts connected.", ephemeral=True)
        return
    embed = discord.Embed(
        title="📬 New post from Test Creator",
        description="**This is a test notification from CreatorAlert!**",
        url="https://www.patreon.com",
        color=discord.Color.orange()
    )
    embed.set_footer(text="This is a test — real notifications will look just like this.")
    try:
        await interaction.user.send(embed=embed)
        await interaction.followup.send("✅ Test notification sent via DM.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ DM failed: {e}", ephemeral=True)


@bot.tree.command(name="servers", description="[Dev] List all servers the bot is in")
async def servers(interaction: discord.Interaction):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ This command is restricted.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    guilds = sorted(bot.guilds, key=lambda g: g.member_count, reverse=True)
    total_members = sum(g.member_count for g in guilds)
    lines = [f"**{g.name}** — {g.member_count:,} members (ID: `{g.id}`)" for g in guilds]
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > 1024:
            chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current.strip())
    embed = discord.Embed(
        title=f"Servers — {len(guilds)} total · {total_members:,} members",
        color=discord.Color.blurple()
    )
    for i, chunk in enumerate(chunks):
        embed.add_field(name="\u200b" if i > 0 else "Server list", value=chunk or "None", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="help", description="Show help information")
async def help_cmd(interaction: discord.Interaction):
    premium = _check_premium(interaction)
    embed = discord.Embed(
        title="CreatorAlert Help",
        description="Get notified when creators you support on Patreon or SubscribeStar post new content, or when a Gumroad creator releases a new product.",
        color=discord.Color.blurple()
    )
    embed.add_field(name="/connect", value="Link a Patreon, SubscribeStar, or Gumroad account", inline=False)
    embed.add_field(name="/disconnect", value="Unlink a connected account", inline=False)
    embed.add_field(name="/status", value="Check your connected accounts and settings", inline=False)
    embed.add_field(name="/setup", value="[Creator] Designate a channel for post announcements (requires Manage Server)", inline=False)
    embed.add_field(name="/pingrole", value="[Creator] Set a role to ping with each announcement (requires Manage Server)", inline=False)
    embed.add_field(name="/premium", value="View or subscribe to CreatorAlert Premium", inline=False)
    if premium:
        embed.add_field(name="/customize", value="[Premium] Set a custom embed colour and notification message", inline=False)
    embed.add_field(name="/mute", value="Mute notifications from a specific creator", inline=False)
    embed.add_field(name="/unmute", value="Restore notifications from a muted creator", inline=False)
    embed.add_field(name="/invite", value="Get the bot's invite link", inline=False)
    embed.add_field(name="/about", value="About CreatorAlert", inline=False)
    embed.set_footer(text=f"Need help? Join the support server: {SUPPORT_SERVER}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(os.getenv("DISCORD_TOKEN"))
