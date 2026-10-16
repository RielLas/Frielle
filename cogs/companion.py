"""
cogs/companion.py
Primary conversational listener for Project Raziel.
Handles pure mentions, message replies, DMs, natural typing indicators,
tiered dynamics, and Safe Harbor routing.
"""

import time
import logging
import discord
from discord.ext import commands
from config import CIEL_BOT_IDS
from raziel_core.personality import detect_mode
from raziel_core.ai_engine import GeminiEngine
from raziel_core.memory import MemoryManager
from raziel_core.tiers import TierManager

logger = logging.getLogger("Raziel.Companion")


class CompanionCog(commands.Cog):
    """Core companion interaction listener."""

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
        # Per-user cooldown: 2 messages per 6 seconds
        self.cd_mapping = commands.CooldownMapping.from_cooldown(
            rate=2,
            per=6.0,
            type=commands.BucketType.user
        )
        self.cooldown_warned: dict = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Processes incoming messages for mentions, direct messages, and conversational replies."""
        # Ignore bots, self, webhooks, or Ciel (handled by cross_resonance)
        if message.author.bot or message.author.id == self.bot.user.id or getattr(message, "webhook_id", None) or message.author.id in CIEL_BOT_IDS:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        is_reply = False
        is_mentioned = (
            (self.bot.user in message.mentions) or
            (f"<@{self.bot.user.id}>" in message.content) or
            (f"@{self.bot.user.name.lower()}" in message.clean_content.lower())
        )

        if message.reference and message.reference.resolved:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message) and resolved.author.id == self.bot.user.id:
                is_reply = True

        # Only process if directly addressed or in DM (like Ciel)
        if not (is_dm or is_mentioned or is_reply):
            return

        # Resolve member's tier
        tier_key, tier_label, tier_badge = self.tiers.resolve_tier(message.author)

        # Enforce per-user cooldown (exempt Riel / sovereign)
        if tier_key != "sovereign":
            bucket = self.cd_mapping.get_bucket(message)
            retry_after = bucket.update_rate_limit()
            if retry_after:
                now = time.time()
                last_warn = self.cooldown_warned.get(message.author.id, 0.0)
                if (now - last_warn) > 10.0:
                    self.cooldown_warned[message.author.id] = now
                    await message.reply("Give me just a second to catch up with you, typing as fast as I can.", mention_author=False)
                return

        # Prune cooldown cache if it grows past 100 entries to prevent memory leaks
        if len(self.cooldown_warned) > 100:
            cutoff = time.time() - 60.0
            self.cooldown_warned = {uid: ts for uid, ts in self.cooldown_warned.items() if ts > cutoff}

        import re
        clean_content = re.sub(rf"@?{re.escape(self.bot.user.name)}", "", message.clean_content, flags=re.IGNORECASE).strip()
        clean_content = clean_content.replace("===", "").replace("[CONTEXT", "").strip() or "Hey Raziel."

        # Cap message input size to protect against token bloat & injection
        if len(clean_content) > 800:
            clean_content = clean_content[:800] + "..."

        context_key = f"dm_{message.author.id}" if is_dm else f"ch_{message.channel.id}"
        author_display = message.author.display_name.replace("===", "").replace("\n", " ").strip()[:32]

        # Detect tone mode (Safe Harbor vs Public Banter) incorporating tier context
        mode, system_instruction = detect_mode(clean_content, user_tier=tier_key)

        prompt_parts = []

        # Retrieve stored user profile & affinity
        user_summary = self.memory.get_user_profile_summary(message.author.id)
        if user_summary:
            prompt_parts.append(f"=== STORED KNOWLEDGE OF USER ===\n{user_summary}\n")

        # Retrieve conversational history buffer
        history_str = self.memory.format_history_for_prompt(context_key)
        if history_str:
            prompt_parts.append(f"=== RECENT CONVERSATION CONTEXT ===\n{history_str}\n")

        channel_desc = "Direct Message (Private Safe Harbor)" if is_dm else f"#{message.channel.name}"
        prompt_parts.append(
            f"=== CURRENT MESSAGE ===\n"
            f"Author: {author_display} (ID: {message.author.id})\n"
            f"Standing: {tier_badge} - {tier_label}\n"
            f"Channel: {channel_desc}\n"
            f"Respond naturally in character as Raziel (1-2 punchy sentences max).\n"
            f"- Speak directly 1-on-1. NEVER address a crowd or talk to 'everyone'.\n"
            f"- Do NOT repeat the user's name if you are already mid-conversation.\n"
            f"- Do NOT compulsively end with an interview question. Let reactions and witty observations stand on their own.\n"
            f"- NO robotic therapist reflections. React with authentic wit, charisma, and relaxed presence.\n"
            f"- NO asterisks, NO 'bro', NO rude internet slang."
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
                    self.memory.record_user_interaction(
                        message.author.id,
                        author_display,
                        context_key=context_key,
                        ai_engine=self.ai
                    )

                    # Deliver response safely within Discord limit
                    if len(reply) > 1950:
                        reply = reply[:1947] + "..."

                    if is_dm:
                        await message.channel.send(reply)
                    else:
                        await message.reply(reply, mention_author=False)

            except Exception as ex:
                logger.error(f"Companion response failed: {ex}")
                await message.reply(
                    "lost my train of thought for a sec, my bad. what was that?",
                    mention_author=False
                )


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
    await bot.add_cog(CompanionCog(bot, ai_engine, memory, tier_manager))
