"""
cogs/commands.py
Slash commands suite for Project Raziel.
Enables /about, /profile, and /remember.
Conversations occur purely via mentions, replies, and DMs.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from raziel_core.ui import create_about_embed, create_profile_embed, create_safe_harbor_embed
from raziel_core.ai_engine import GeminiEngine
from raziel_core.memory import MemoryManager
from raziel_core.tiers import TierManager

logger = logging.getLogger("Raziel.Commands")


class RazielCommandsCog(commands.Cog):
    """Application command suite for Raziel."""

    def __init__(
        self,
        bot: commands.Bot,
        ai_engine: GeminiEngine,
        memory: MemoryManager,
        tier_manager: TierManager
    ):
        self.bot = bot
        self.ai = ai_engine
        self.memory = memory
        self.tiers = tier_manager

    @app_commands.command(name="about", description="Learn about Raziel and his role as the Safe Harbor.")
    async def about_cmd(self, interaction: discord.Interaction):
        embed = create_about_embed()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="Check your tier standing and what Raziel remembers about you.")
    async def profile_cmd(self, interaction: discord.Interaction):
        u_str = str(interaction.user.id)
        rec = self.memory.user_records.get(u_str, {})
        affinity = rec.get("affinity", 0)
        notes = rec.get("notes", {})
        topics = rec.get("topics", [])

        # Resolve tier
        _, tier_label, tier_badge = self.tiers.resolve_tier(interaction.user)

        embed = create_profile_embed(
            user=interaction.user,
            tier_label=tier_label,
            tier_badge=tier_badge,
            affinity=affinity,
            notes=notes,
            recent_topics=topics
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="remember", description="Tell Raziel a detail or preference to remember about you.")
    @app_commands.describe(key="The topic or trait (e.g. 'favorite anime', 'hobbies', 'timezone')", value="The detail to remember")
    async def remember_cmd(self, interaction: discord.Interaction, key: str, value: str):
        clean_key = key.strip().title()
        clean_val = value.strip()
        self.memory.update_user_note(interaction.user.id, clean_key, clean_val)

        embed = create_safe_harbor_embed(
            title="MEMORY RECORDED",
            description=f"> *\"Tucked away in the archives.\"*\n\nI'll remember that your **{clean_key}** is: `{clean_val}`.",
            footer_text=f"Updated record for @{interaction.user.name}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    ai_engine = getattr(bot, "ai_engine", None)
    memory = getattr(bot, "memory", None)
    tier_manager = getattr(bot, "tier_manager", None)
    if not ai_engine:
        ai_engine = GeminiEngine()
    if not memory:
        memory = MemoryManager()
    if not tier_manager:
        tier_manager = TierManager()
    await bot.add_cog(RazielCommandsCog(bot, ai_engine, memory, tier_manager))
