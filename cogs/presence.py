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
    ("watching over the sanctuary | DM for a quiet ear", discord.ActivityType.watching),
    ("keeping Ciel from overcooking her circuits", discord.ActivityType.playing),
    ("listening to the void", discord.ActivityType.listening),
    ("saving chat from the ban hammer", discord.ActivityType.competing)
]


class PresenceCog(commands.Cog):
    """Rotates presence and maintains Raziel's active heartbeat."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.index = 0
        self.rotate_status.start()

    def cog_unload(self):
        self.rotate_status.cancel()

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


async def setup(bot: commands.Bot):
    await bot.add_cog(PresenceCog(bot))
