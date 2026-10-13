"""
cogs/cross_resonance.py
Ciel & Raziel cross-bot interaction engine.
Observes Ciel's messages and triggers natural sibling banter with strict debounce safeguards.
"""

import time
import random
import logging
import discord
from config import CIEL_BOT_ID, CROSS_BOT_COOLDOWN_SECONDS, CROSS_BOT_CHANCE
from raziel_core.ai_engine import GeminiEngine
from raziel_core.memory import MemoryManager

logger = logging.getLogger("Raziel.CrossResonance")

CIEL_INTENSITY_TRIGGERS = [
    "purge", "erasure", "bonk", "commoner", "threat", "infraction", "quarantine",
    "noise floor", "insolence", "warning", "unruly", "delete", "clearance revoked"
]


class CrossResonanceCog(commands.Cog):
    """Monitors Ciel's activity in chat and provides playful cross-bot banter."""

    def __init__(self, bot: commands.Bot, ai_engine: GeminiEngine, memory: MemoryManager):
        self.bot = bot
        self.ai = ai_engine
        self.memory = memory
        self.last_cross_bot_interaction: float = 0.0

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Detects messages sent by Ciel in community channels."""
        # Only listen to Ciel
        if message.author.id != CIEL_BOT_ID:
            return

        # Do not process DMs or system messages
        if not message.guild or not isinstance(message.channel, discord.TextChannel):
            return

        now = time.time()
        # Enforce strict cooldown between unprompted sibling interactions
        if (now - self.last_cross_bot_interaction) < CROSS_BOT_COOLDOWN_SECONDS:
            return

        ciel_text = message.clean_content.lower()

        # Check if Ciel is being particularly intense/stern
        is_intense = any(word in ciel_text for word in CIEL_INTENSITY_TRIGGERS)

        # If not intense, apply random participation chance
        if not is_intense and random.random() > CROSS_BOT_CHANCE:
            return

        # Set debounce timer immediately
        self.last_cross_bot_interaction = now

        # Build context
        mode, system_instruction = detect_mode(message.clean_content, is_ciel_context=True)
        context_key = f"ch_{message.channel.id}"

        prompt = (
            f"=== CIEL JUST SENT THIS MESSAGE IN #{message.channel.name} ===\n"
            f"Ciel: {message.clean_content}\n\n"
            f"Step in naturally as Raziel. Playfully tease Ciel for taking herself or her duties too seriously, "
            f"or reassure the chat members that she's just dramatic. Keep it brief, natural, and charismatic (1-3 sentences)."
        )

        try:
            async with message.channel.typing():
                reply = await self.ai.generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.85
                )

                if reply:
                    self.memory.add_turn(context_key, "ciel", message.clean_content, author_name="Ciel")
                    self.memory.add_turn(context_key, "assistant", reply, author_name="Raziel")
                    await message.reply(reply, mention_author=False)
                    logger.info(f"Triggered cross-resonance reply to Ciel in #{message.channel.name}")

        except Exception as ex:
            logger.error(f"Cross-resonance dispatch error: {ex}")


async def setup(bot: commands.Bot):
    ai_engine = getattr(bot, "ai_engine", None)
    memory = getattr(bot, "memory", None)
    if not ai_engine:
        ai_engine = GeminiEngine()
    if not memory:
        memory = MemoryManager()
    await bot.add_cog(CrossResonanceCog(bot, ai_engine, memory))
