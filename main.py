import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import logging
import aiohttp
import os

from bot.db import (
    init_db, get_user, delete_user, set_premium_style,
    set_creator_channel, get_creator_channel, set_creator_ping_role,
    mute_creator, unmute_creator, get_muted_creators
)
from bot.premium import is_premium, PREMIUM_SKU_ID
from bot.scheduler import start_scheduler

load_dotenv()

logging.getLogger("discord.ext.commands.bot").setLevel(logging.ERROR)

AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "https://auth-production-4018.up.railway.app")
BOT_OWNER_ID = 244962442008854540
BOT_VERSION = "1.2.0"
GITHUB_URL = "https://github.com/KumihoArts/CreatorAlert"
SUPPORT_SERVER = "https://discord.gg/KVcu3HvHB3"
DBL_TOKEN = os.getenv("DBL_TOKEN")
INVITE_PERMISSIONS = discord.Permissions(send_messages=True, embed_links=True, send_messages_in_threads=True)

DBL_COMMANDS = [
    {"name": "connect", "description": "Connect your Patreon account", "type": 1},
    {"name": "disconnect", "description": "Disconnect your Patreon account", "type": 1},
    {"name": "status", "description": "Check your Patreon connection status and notification settings", "type": 1},
    {"name": "setup", "description": "[Creator] Set a channel in your server for automatic Patreon post announcements", "type": 1},
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
        embed = discord.Embed(
            title="Patreon Status",
            description="✅ Patreon account connected.",
            color=discord.Color.green()
        )
        embed.add_field(name="Patreon User ID", value=user["patreon_user_id"], inline=False)
        embed.add_field(name="Connected since", value=connected_at, inline=False)
        embed.add_field(
            name="Notifications",
            value="Delivered via DM. Use `/setup` in a server to also post as a creator.",
            inline=False
        )
        embed.add_field(name="Premium", value="✅ Active" if premium else "❌ Not subscribed", inline=False)
        if premium:
            custom_msg = user.get("custom_message")
            colour = user.get("embed_colour")
            if custom_msg:
                embed.add_field(name="Custom message", value=custom_msg, inline=False)
            if colour:
                embed.add_field(name="Embed colour", value=colour, inline=True)

        muted = await get_muted_creators(interaction.user.id)
        if muted:
            embed.add_field(name="Muted creators", value=f"{len(muted)} muted — use `/unmute` to restore", inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="setup", description="[Creator] Post your Patreon updates to a channel in this server")
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
        desc = f"Announcement channel updated to {channel.mention}.\n\nPreviously set to <#{existing}>."
    else:
        desc = (
            f"New posts from your Patreon will be announced in {channel.mention}.\n\n"
            "Optionally use `/pingrole` to set a role to ping with each announcement."
        )

    embed = discord.Embed(title="✅ Creator channel set", description=desc, color=discord.Color.green())
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="pingrole", description="[Creator] Set a role to ping when your Patreon posts are announced")
@app_commands.describe(role="The role to ping with each announcement (leave empty to clear)")
@app_commands.default_permissions(manage_guild=True)
async def pingrole(interaction: discord.Interaction, role: discord.Role = None):
    await interaction.response.defer(ephemeral=True)

    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send(
            "❌ You need to connect your Patreon account first. Use `/connect`.", ephemeral=True
        )
        return

    existing_channel = await get_creator_channel(interaction.guild.id, user["patreon_user_id"])
    if not existing_channel:
        await interaction.followup.send(
            "❌ You need to set up a creator channel first. Use `/setup` to designate one.", ephemeral=True
        )
        return

    if role is None:
        await set_creator_ping_role(interaction.guild.id, user["patreon_user_id"], None)
        await interaction.followup.send(
            "✅ Ping role cleared. Announcements will no longer ping a role.", ephemeral=True
        )
        return

    if role.is_default() or role.name == "@everyone":
        await interaction.followup.send(
            "❌ You cannot set `@everyone` as the ping role.", ephemeral=True
        )
        return

    if role >= interaction.guild.me.top_role:
        await interaction.followup.send(
            f"❌ I can't ping {role.mention} because it's higher than or equal to my own role. "
            "Please choose a lower role.", ephemeral=True
        )
        return

    await set_creator_ping_role(interaction.guild.id, user["patreon_user_id"], role.id)
    await interaction.followup.send(
        f"✅ Ping role set to {role.mention}. This role will be pinged with each new post announcement.",
        ephemeral=True
    )


@bot.tree.command(name="mute", description="Mute notifications from a specific creator")
async def mute(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send(
            "❌ You need to connect your Patreon account first. Use `/connect`.", ephemeral=True
        )
        return

    from bot.patreon import get_memberships
    memberships = await get_memberships(user["access_token"])
    if not memberships:
        await interaction.followup.send(
            "❌ No creators found. Make sure you are actively supporting creators on Patreon.", ephemeral=True
        )
        return

    muted = await get_muted_creators(interaction.user.id)
    available = [m for m in memberships if m["campaign_id"] not in muted]

    if not available:
        await interaction.followup.send(
            "All creators you follow are already muted. Use `/unmute` to restore notifications.", ephemeral=True
        )
        return

    options = [
        discord.SelectOption(
            label=m.get("vanity") or "Unknown Creator",
            value=m["campaign_id"],
            description=m.get("url", "")[:100] or None
        )
        for m in available[:25]
    ]

    view = MuteSelectView(options)
    await interaction.followup.send(
        "Select a creator to mute. You will no longer receive notifications from them.",
        view=view,
        ephemeral=True
    )


class MuteSelectView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        select = discord.ui.Select(
            placeholder="Choose a creator to mute...",
            options=options
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        campaign_id = interaction.data["values"][0]
        creator_name = next(
            (opt.label for opt in self.children[0].options if opt.value == campaign_id),
            "That creator"
        )
        await mute_creator(interaction.user.id, campaign_id)
        self.stop()
        await interaction.response.edit_message(
            content=f"🔇 **{creator_name}** has been muted. You will no longer receive notifications from them.\n\nUse `/unmute` to restore notifications.",
            view=None
        )


@bot.tree.command(name="unmute", description="Restore notifications from a muted creator")
async def unmute(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user = await get_user(interaction.user.id)
    if not user:
        await interaction.followup.send(
            "❌ You need to connect your Patreon account first. Use `/connect`.", ephemeral=True
        )
        return

    muted = await get_muted_creators(interaction.user.id)
    if not muted:
        await interaction.followup.send(
            "You have no muted creators. Use `/mute` to mute notifications from a creator.", ephemeral=True
        )
        return

    from bot.patreon import get_memberships
    memberships = await get_memberships(user["access_token"])
    name_lookup = {m["campaign_id"]: m.get("vanity") or "Unknown Creator" for m in (memberships or [])}

    options = [
        discord.SelectOption(
            label=name_lookup.get(cid, f"Creator ({cid})"),
            value=cid
        )
        for cid in muted[:25]
    ]

    view = UnmuteSelectView(options)
    await interaction.followup.send(
        "Select a creator to unmute. Notifications will resume at the next poll.",
        view=view,
        ephemeral=True
    )


class UnmuteSelectView(discord.ui.View):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        select = discord.ui.Select(
            placeholder="Choose a creator to unmute...",
            options=options
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        campaign_id = interaction.data["values"][0]
        creator_name = next(
            (opt.label for opt in self.children[0].options if opt.value == campaign_id),
            "That creator"
        )
        await unmute_creator(interaction.user.id, campaign_id)
        self.stop()
        await interaction.response.edit_message(
            content=f"🔔 **{creator_name}** has been unmuted. Notifications will resume at the next poll.",
            view=None
        )


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
        description="Get notified when Patreon creators you support post new content.",
        color=discord.Color.blurple()
    )
    embed.add_field(name="/connect", value="Link your Patreon account", inline=False)
    embed.add_field(name="/disconnect", value="Unlink your Patreon account", inline=False)
    embed.add_field(name="/status", value="Check your connection status", inline=False)
    embed.add_field(
        name="/setup",
        value="[Creator] Designate a channel in this server for your Patreon post announcements (requires Manage Server)",
        inline=False
    )
    embed.add_field(
        name="/pingrole",
        value="[Creator] Set a role to ping with each announcement in this server (requires Manage Server)",
        inline=False
    )
    embed.add_field(name="/premium", value="View or subscribe to CreatorAlert Premium", inline=False)
    if premium:
        embed.add_field(name="/customize", value="[Premium] Set a custom embed colour and notification message", inline=False)
    embed.add_field(name="/mute", value="Mute notifications from a specific creator", inline=False)
    embed.add_field(name="/unmute", value="Restore notifications from a muted creator", inline=False)
    embed.add_field(name="/invite", value="Get the link to invite CreatorAlert to your server", inline=False)
    embed.add_field(name="/about", value="About CreatorAlert", inline=False)
    embed.set_footer(text=f"Need help? Join the support server: {SUPPORT_SERVER}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(os.getenv("DISCORD_TOKEN"))
