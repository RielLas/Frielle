"""
main.py
Core entry point for Project Raziel.
Initializes Discord client, mounts Gemini Flash-Lite AI engine,
Tier Manager, MongoDB/Local memory subsystems, and boots cogs.
"""

import sys
import asyncio
import logging
import discord
from discord.ext import commands

from config import DISCORD_TOKEN, COMMAND_PREFIX, DEFAULT_MODEL, GEMINI_API_KEYS
from raziel_core.ai_engine import GeminiEngine
from raziel_core.memory import MemoryManager
from raziel_core.tiers import TierManager

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Raziel.Main")

# Intents configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# Attach Core AI, Tier, & Memory subsystems to bot instance
bot.ai_engine = GeminiEngine(api_keys=GEMINI_API_KEYS, default_model=DEFAULT_MODEL)
bot.memory = MemoryManager()
bot.tier_manager = TierManager()

INITIAL_EXTENSIONS = [
    "cogs.companion",
    "cogs.cross_resonance",
    "cogs.presence",
    "cogs.commands"
]


@bot.event
async def on_ready():
    logger.info("=" * 60)
    logger.info(f"✨ PROJECT RAZIEL ONLINE // Logged in as: {bot.user} (ID: {bot.user.id})")
    logger.info(f"🧠 AI Engine: Gemini ({bot.ai_engine.model}) | Keys Loaded: {len(bot.ai_engine.api_keys)}")
    db_mode = "MongoDB Atlas" if bot.memory.collection is not None else "Local JSON"
    logger.info(f"💾 Memory Subsystem: {db_mode}")
    logger.info("🛡️ Safe Harbor, Tier Matrix & Cross-Bot Resonance Active")

    try:
        synced = await bot.tree.sync()
        logger.info(f"⚡ Synced {len(synced)} application slash commands.")
    except Exception as sync_err:
        logger.warning(f"Failed syncing command tree: {sync_err}")

    logger.info("=" * 60)


async def main():
    # Initialize database connection asynchronously
    await bot.memory.init_database()

    async with bot:
        for ext in INITIAL_EXTENSIONS:
            try:
                await bot.load_extension(ext)
                logger.info(f"Successfully loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}")

        if not DISCORD_TOKEN:
            logger.warning("DISCORD_TOKEN is missing in .env! Please configure your bot token.")
            print("\n[!] NOTICE: Raziel is ready, but DISCORD_TOKEN is not set in .env yet.")
            print("    Add your bot token to 'd:\\Wonderland Discord\\Projects\\Raziel\\.env' and run main.py!\n")
            return

        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Raziel shutting down gracefully.")
