"""
cogs/commands.py
Slash commands (app_commands) suite for Project Raziel.
Enables /about, /vent, /dossier, /remember, and /talk.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

from raziel_core.ui import create_about_embed, create_dossier_embed, create_safe_harbor_embed
from raziel_core.personality import detect_mode
from raziel_core.ai_engine import GeminiEngine
from raziel_core.memory import MemoryManager

logger = logging.getLogger("Raziel.Commands")


class RazielCommandsCog(commands.Cog):
    """Application command suite for Raziel."""

    def __init__(self, bot: commands.Bot, ai_engine: GeminiEngine, memory: MemoryManager):
        self.bot = bot
        self.ai = ai_engine
        self.memory = memory

    @app_commands.command(name="about", description="Learn about Raziel and his role as the Safe Harbor.")
    async def about_cmd(self, interaction: discord.Interaction):
        embed = create_about_embed()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dossier", description="Check your connection level and what Raziel remembers about you.")
    async def dossier_cmd(self, interaction: discord.Interaction):
        u_str = str(interaction.user.id)
        rec = self.memory.user_records.get(u_str, {})
        affinity = rec.get("affinity", 0)
        notes = rec.get("notes", {})
        topics = rec.get("topics", [])

        embed = create_dossier_embed(
            user=interaction.user,
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

    @app_commands.command(name="vent", description="Privately vent or share something on your mind in safe harbor mode.")
    @app_commands.describe(thoughts="What's weighing on your mind?")
    async def vent_cmd(self, interaction: discord.Interaction, thoughts: str):
        await interaction.response.defer(ephemeral=True)

        mode, system_instruction = detect_mode(thoughts)
        user_name = interaction.user.display_name
        user_summary = self.memory.get_user_profile_summary(interaction.user.id)

        prompt = (
            f"=== PRIVATE SAFE HARBOR VENT ===\n"
            f"User: {user_name} (ID: {interaction.user.id})\n"
            f"{user_summary}\n\n"
            f"Thoughts shared:\n{thoughts}\n\n"
            f"Respond as Raziel with deep emotional presence, comfort, and grounded reassurance. No lists, no bullets."
        )

        reply = await self.ai.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.7
        )

        self.memory.record_user_interaction(interaction.user.id, user_name, topic="Late Night Vent")
        await interaction.followup.send(reply, ephemeral=True)

    @app_commands.command(name="talk", description="Speak directly with Raziel in this channel.")
    @app_commands.describe(message="What do you want to say to Raziel?")
    async def talk_cmd(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()

        mode, system_instruction = detect_mode(message)
        context_key = f"ch_{interaction.channel_id}"
        user_name = interaction.user.display_name
        history_str = self.memory.format_history_for_prompt(context_key)

        prompt = (
            f"=== CHANNEL CONVERSATION ===\n"
            f"{history_str}\n\n"
            f"User {user_name}: {message}\n\n"
            f"Respond as Raziel."
        )

        reply = await self.ai.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.85 if mode == "public_banter" else 0.7
        )

        self.memory.add_turn(context_key, "user", message, author_name=user_name)
        self.memory.add_turn(context_key, "assistant", reply, author_name="Raziel")
        self.memory.record_user_interaction(interaction.user.id, user_name)

        await interaction.followup.send(reply)


async def setup(bot: commands.Bot):
    ai_engine = getattr(bot, "ai_engine", None)
    memory = getattr(bot, "memory", None)
    if not ai_engine:
        ai_engine = GeminiEngine()
    if not memory:
        memory = MemoryManager()
    await bot.add_cog(RazielCommandsCog(bot, ai_engine, memory))
