import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio

from bot.db import init_db
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
    await interaction.response.send_message("Disconnect — coming soon!", ephemeral=True)

@bot.tree.command(name="status", description="Check your connection status")
async def status(interaction: discord.Interaction):
    await interaction.response.send_message("Status — coming soon!", ephemeral=True)

@bot.tree.command(name="setup", description="[Creator] Set the channel for Patreon post notifications")
async def setup(interaction: discord.Interaction):
    await interaction.response.send_message("Creator setup — coming soon!", ephemeral=True)

@bot.tree.command(name="help", description="Show help information")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("Help — coming soon!", ephemeral=True)

bot.run(os.getenv("DISCORD_TOKEN"))
