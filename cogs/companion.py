"""
cogs/companion.py
Primary conversational listener for Project Raziel.
Handles mentions, replies, DMs, natural typing indicators, and Safe Harbor routing.
"""

import logging
import discord
from discord.ext import commands
from raziel_core.personality import detect_mode
from raziel_core.ai_engine import GeminiEngine
from raziel_core.memory import MemoryManager

logger = logging.getLogger("Raziel.Companion")


class CompanionCog(commands.Cog):
    """Core companion interaction listener."""

    def __init__(self, bot: commands.Bot, ai_engine: GeminiEngine, memory: MemoryManager):
        self.bot = bot
        self.ai = ai_engine
        self.memory = memory

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Processes incoming messages for mentions, direct messages, and conversational replies."""
        if message.author.bot or message.author.id == self.bot.user.id:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.bot.user in message.mentions
        is_reply = False

        if message.reference and message.reference.resolved:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message) and resolved.author.id == self.bot.user.id:
                is_reply = True

        # Only process if directly addressed or in DM
        if not (is_dm or is_mentioned or is_reply):
            return

        clean_content = message.clean_content.replace(f"@{self.bot.user.name}", "").strip()
        if not clean_content:
            clean_content = "Hey Raziel."

        context_key = f"dm_{message.author.id}" if is_dm else f"ch_{message.channel.id}"
        author_display = message.author.display_name

        # Detect tone mode (Safe Harbor vs Public Banter)
        mode, system_instruction = detect_mode(clean_content)

        # Retrieve stored user profile & affinity
        user_summary = self.memory.get_user_profile_summary(message.author.id)
        if user_summary:
            prompt_parts.append(f"=== STORED KNOWLEDGE OF USER ===\n{user_summary}\n")

        # Retrieve conversational history buffer
        history_str = self.memory.format_history_for_prompt(context_key)
        if history_str:
            prompt_parts.append(f"=== RECENT CONVERSATION CONTEXT ===\n{history_str}\n")

        prompt_parts.append(
            f"=== CURRENT MESSAGE ===\n"
            f"User: {author_display} (ID: {message.author.id})\n"
            f"Channel: {'Direct Message (Private Safe Harbor)' if is_dm else message.channel.name}\n"
            f"Message: {clean_content}\n\n"
            f"Respond as Raziel directly to {author_display}."
        )

        full_prompt = "\n".join(prompt_parts)

        # Natural typing indicator
        async with message.channel.typing():
            try:
                reply = await self.ai.generate(
                    prompt=full_prompt,
                    system_instruction=system_instruction,
                    temperature=0.85 if mode == "public_banter" else 0.7
                )

                if reply:
                    # Update memory buffer with turn
                    self.memory.add_turn(context_key, "user", clean_content, author_name=author_display)
                    self.memory.add_turn(context_key, "assistant", reply, author_name="Raziel")
                    self.memory.record_user_interaction(message.author.id, author_display)

                    # Deliver response
                    if is_dm:
                        await message.channel.send(reply)
                    else:
                        await message.reply(reply, mention_author=False)

            except Exception as ex:
                logger.error(f"Companion response failed: {ex}")
                await message.reply(
                    "*(Raziel blinks, rubbing the back of his neck with an amused smirk)* "
                    "Lost my train of thought for a second there. Hit me again?",
                    mention_author=False
                )


async def setup(bot: commands.Bot):
    ai_engine = getattr(bot, "ai_engine", None)
    memory = getattr(bot, "memory", None)
    if not ai_engine:
        ai_engine = GeminiEngine()
    if not memory:
        memory = MemoryManager()
    await bot.add_cog(CompanionCog(bot, ai_engine, memory))
