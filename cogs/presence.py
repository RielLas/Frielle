"""
cogs/presence.py
Rich status management and presence rotation for Project Raziel.
"""

import asyncio
import logging
import discord
from discord.ext import commands, tasks

logger = logging.getLogger("Raziel.Presence")

STATUS_ROTATION = [
    ("chilling | mention or DM me", discord.ActivityType.watching),
    ("keeping my big sis Ciel from banning everyone", discord.ActivityType.playing),
    ("listening to chat chaos", discord.ActivityType.listening),
    ("teasing Ciel", discord.ActivityType.playing)
]


class PresenceCog(commands.Cog):
    """Rotates presence and maintains Raziel's active heartbeat."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.index = 0
        self.rotate_status.start()
        self.sync_privileges.start()

    def cog_unload(self):
        self.rotate_status.cancel()
        self.sync_privileges.cancel()

    @tasks.loop(minutes=15)
    async def rotate_status(self):
        """Periodically rotates custom activity."""
        await self.bot.wait_until_ready()
        try:
            status_text, activity_type = STATUS_ROTATION[self.index % len(STATUS_ROTATION)]
            self.index += 1

            activity = discord.Activity(type=activity_type, name=status_text)
            await self.bot.change_presence(status=discord.Status.online, activity=activity)
            logger.info(f"Updated presence to: {status_text}")
        except Exception as e:
            logger.warning(f"Failed to update presence: {e}")

    @rotate_status.before_loop
    async def before_rotate(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def sync_privileges(self):
        """Periodically syncs dynamic privileges from MongoDB ciel_privileges to catch updates from Ciel."""
        await self.bot.wait_until_ready()
        try:
            tm = getattr(self.bot, "tier_manager", getattr(self.bot, "tiers", None))
            if tm and hasattr(self.bot, "memory") and self.bot.memory.db is not None:
                count = await tm.sync_privileges_from_db(self.bot.memory.db)
                logger.info(f"Periodic privilege sync refreshed {count} privileges from ciel_privileges.")
        except Exception as e:
            logger.warning(f"Error in periodic privilege sync: {e}")

    @sync_privileges.before_loop
    async def before_sync(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(PresenceCog(bot))
