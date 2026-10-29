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

import aiohttp
from cogs._attachments import extract_attachment_text, _IMAGE_ATTACHMENT_EXTS, _TEXT_ATTACHMENT_EXTS
from cogs._ai_search import looks_fact_based, is_explicit_search, distill_query, web_search_summary
from cogs._ai_tools import execute_agent_tool

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

        # Process attachments (images & text documents)
        image_payloads = []
        attachment_texts = []
        if message.attachments:
            async with aiohttp.ClientSession() as session:
                for att in message.attachments[:3]:
                    fname = att.filename.lower()
                    try:
                        async with session.get(att.url, timeout=10) as resp:
                            if resp.status == 200:
                                att_data = await resp.read()
                                if any(fname.endswith(ext) for ext in _IMAGE_ATTACHMENT_EXTS):
                                    mime = att.content_type or ("image/gif" if fname.endswith(".gif") else "image/jpeg")
                                    image_payloads.append({"data": att_data, "mime_type": mime})
                                elif any(fname.endswith(ext) for ext in _TEXT_ATTACHMENT_EXTS):
                                    parsed = extract_attachment_text(att.filename, att_data)
                                    if parsed:
                                        attachment_texts.append(f"[ATTACHMENT: {att.filename}]\n{parsed}")
                    except Exception as att_err:
                        logger.warning(f"Failed fetching attachment {att.filename}: {att_err}")

        # Passive or explicit web search grounding
        grounded_context = ""
        if is_explicit_search(clean_content) or (looks_fact_based(clean_content) and not is_dm):
            dq = distill_query(clean_content)
            if dq:
                grounded_context = await web_search_summary(dq)

        prompt_parts = []

        if grounded_context:
            prompt_parts.append(f"=== GROUNDED INTEL & WEB SEARCH ===\n{grounded_context}\n")

        if attachment_texts:
            prompt_parts.append(f"=== ATTACHMENT EXCERPTS ===\n" + "\n\n".join(attachment_texts) + "\n")

        # Retrieve stored user profile & affinity (including Ciel's shared cognitive archive)
        ciel_memories = await self.memory.get_ciel_profile(message.author.id)
        user_summary = self.memory.get_user_profile_summary(message.author.id, ciel_memories=ciel_memories)
        if user_summary:
            prompt_parts.append(f"=== STORED KNOWLEDGE OF USER ===\n{user_summary}\n")

        # Resonant Neural Synapses activation
        if hasattr(self.bot, "synapse_mesh") and self.bot.synapse_mesh:
            try:
                recent_turns = [t.get("content", "") for t in self.memory.get_history(context_key)[-5:]]
                spikes = self.bot.synapse_mesh.resolve_spikes(
                    clean_content,
                    owner_id=str(message.author.id),
                    recent_transcript=recent_turns
                )
                if spikes:
                    synapse_facts = [f"- [{s.canonical.upper()}]: {s.remark}" for s in spikes if s.remark]
                    if synapse_facts:
                        prompt_parts.append(f"=== RESONANT MEMORY SYNAPSES ===\n" + "\n".join(synapse_facts) + "\n")
            except Exception as syn_err:
                logger.debug(f"Synapse activation skipped: {syn_err}")

        # Active Narrative Threads & life callbacks
        if hasattr(self.bot, "narrative_engine") and self.bot.narrative_engine:
            try:
                threads = await self.bot.narrative_engine.get_active_threads(str(message.author.id), limit=2)
                if threads:
                    th_lines = [f"- {t.title}: {t.summary}" for t in threads]
                    prompt_parts.append(f"=== ACTIVE LIFE THREADS & TOPICS ===\n" + "\n".join(th_lines) + "\n")
            except Exception as narr_err:
                logger.debug(f"Narrative retrieval skipped: {narr_err}")

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
            f"Respond naturally in character as Frielle (1-2 punchy sentences max).\n"
            f"- Carefree Noble Lady: Poised, warm, witty, and effortlessly aristocratic.\n"
            f"- Speak directly 1-on-1. NEVER address a crowd or talk to 'everyone'.\n"
            f"- Do NOT repeat the user's name if you are already mid-conversation.\n"
            f"- Do NOT compulsively end with an interview question. Let reactions and observations stand on their own.\n"
            f"- NO robotic therapist reflections. React with genuine poise and warmth.\n"
            f"- NO asterisks (*sips tea*), NO 'bro', NO rude internet slang."
        )

        full_prompt = "\n".join(prompt_parts)

        # Natural typing indicator
        async with message.channel.typing():
            try:
                reply = await self.ai.generate(
                    prompt=full_prompt,
                    system_instruction=system_instruction,
                    temperature=0.85 if mode == "public_banter" else 0.7,
                    images=image_payloads if image_payloads else None
                )

                if reply:
                    # Update memory buffer with turn
                    self.memory.add_turn(context_key, "user", clean_content, author_name=author_display)
                    self.memory.add_turn(context_key, "assistant", reply, author_name="Frielle")
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
                    "Forgive me, I was lost in thought for a moment. What were you saying?",
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
