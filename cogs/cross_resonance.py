"""
cogs/cross_resonance.py
Ciel & Raziel cross-bot interaction engine.
Observes Ciel's messages and triggers natural sibling banter with strict debounce safeguards.
"""

import time
import random
import logging
import discord
from discord.ext import commands
from collections import defaultdict
from typing import Dict
from config import CIEL_BOT_IDS, CROSS_BOT_COOLDOWN_SECONDS, CROSS_BOT_CHANCE
from raziel_core.personality import detect_mode
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
        self.last_cross_bot_interaction: Dict[int, float] = defaultdict(float)
        self.consecutive_bot_turns: Dict[int, int] = defaultdict(int)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Detects messages sent by Ciel in community channels with per-channel loop caps."""
        # Reset consecutive bot turns in this specific channel when real humans speak
        if not message.author.bot:
            if message.channel.id in self.consecutive_bot_turns:
                self.consecutive_bot_turns[message.channel.id] = 0
            return

        # Ignore own messages
        if message.author.id == self.bot.user.id:
            return

        # Check if Ciel
        if message.author.id not in CIEL_BOT_IDS:
            return

        ch_id = message.channel.id

        # Bound per-channel tracking to prevent memory leakage
        if len(self.consecutive_bot_turns) > 500:
            for old_id in list(self.consecutive_bot_turns.keys())[:100]:
                self.consecutive_bot_turns.pop(old_id, None)
                self.last_cross_bot_interaction.pop(old_id, None)

        # Cap back-to-back bot banter at 2 turns in this channel until a human speaks
        if self.consecutive_bot_turns[ch_id] >= 2:
            logger.info(f"Paused cross-resonance in #{getattr(message.channel, 'name', ch_id)}: hit 2 consecutive bot turns. Waiting for a human chatter.")
            return

        logger.info(f"Detected Ciel message in #{getattr(message.channel, 'name', 'unknown')}: {message.clean_content[:50]}")

        # Do not process DMs
        if not message.guild:
            return

        # Strict channel whitelist: Sibling cross-resonance ONLY in designated main channels
        ch_name_clean = getattr(message.channel, 'name', '').lower()
        whitelisted_channels = {"chat-with-ciel", "the-void"}
        if not (any(w in ch_name_clean for w in whitelisted_channels) or ch_id in {1526241514190278799, 1491530690557378612}):
            return

        # Ignore system, log, bot-command, or administrative channels
        ignored_channel_keywords = ["log", "audit", "verify", "verification", "contract", "ticket", "rule", "welcome", "garden", "mod"]
        if any(kw in ch_name_clean for kw in ignored_channel_keywords):
            return

        now = time.time()
        is_mentioned = (
            (self.bot.user in message.mentions) or
            (self.bot.user.name.lower() in message.clean_content.lower()) or
            (f"<@{self.bot.user.id}>" in message.content)
        )

        last_int = self.last_cross_bot_interaction[ch_id]
        enforced_cooldown = max(CROSS_BOT_COOLDOWN_SECONDS, 3600)  # 1 hour minimum unprompted cooldown

        if not is_mentioned:
            # Enforce strict 1-hour cooldown between unprompted sibling interactions
            if (now - last_int) < enforced_cooldown:
                return

            ciel_text = message.clean_content.lower()

            # Check if Ciel is being particularly intense/stern
            is_intense = any(word in ciel_text for word in CIEL_INTENSITY_TRIGGERS)

            # If not intense, apply random participation chance
            if not is_intense and random.random() > CROSS_BOT_CHANCE:
                return
        else:
            # 30s debounce for direct pings to prevent loop recursion
            if (now - last_int) < 30.0:
                return

        # Set debounce timer immediately for this specific channel
        self.last_cross_bot_interaction[ch_id] = now
        self.consecutive_bot_turns[ch_id] += 1

        # Build context
        mode, system_instruction = detect_mode(message.clean_content, is_ciel_context=True)
        context_key = f"ch_{message.channel.id}"

        prompt = (
            f"=== CIEL (YOUR OLDER SISTER) JUST SENT THIS MESSAGE IN #{message.channel.name} ===\n"
            f"Ciel: {message.clean_content}\n\n"
            f"Reply DIRECTLY to Ciel as her younger brother (1-2 punchy sentences).\n"
            f"- Address Ciel directly (e.g. 'ciel you're doing the most right now'). NEVER speak to 'everyone', 'chat', or explain Ciel to an audience.\n"
            f"- React specifically to what she just talked about with effortless, teasing wit. Do NOT recycle clichés about ban hammers or prison wardens.\n"
            f"- Natural, grounded Discord cadence, relaxed smirk, zero asterisks, zero formal AI therapy talk."
        )

        try:
            async with message.channel.typing():
                reply = await self.ai.generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.85
                )

                # If generation failed or returned error fallback, do not spam chat
                if not reply or any(err in reply.lower() for err in ("connection lagged", "momentarily unplugged", "connection flickered")):
                    logger.warning("Cross-resonance generated empty or fallback reply. Skipping message to avoid spam.")
                    return

                if len(reply) > 1950:
                    reply = reply[:1947] + "..."

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
