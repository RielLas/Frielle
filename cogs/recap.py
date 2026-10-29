"""
cogs/recap.py
AI Conversation Summarization, Channel History Digest, and Deep User Context Profiling.
Capable of reading 1,000+ past messages to build deep conversational context.
"""

import discord
from discord.ext import commands
import datetime
import logging
from typing import Optional

logger = logging.getLogger("Raziel.Recap")


class FrielleRecap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="recap",
        description="Generates an aristocratic catch-up digest of recent conversation in a channel."
    )
    async def recap(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None, hours: int = 6):
        await ctx.defer()
        target_channel = channel or ctx.channel
        if not isinstance(target_channel, discord.TextChannel):
            await ctx.send("Recaps can only be drawn from text parlors.", ephemeral=True)
            return

        hours = max(1, min(hours, 24))
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)

        lines = []
        authors = set()
        count = 0

        async for msg in target_channel.history(limit=150, after=cutoff, oldest_first=True):
            if msg.author.bot or not msg.clean_content.strip():
                continue
            if msg.clean_content.startswith(("/", "!", "r!")):
                continue
            count += 1
            authors.add(msg.author.display_name)
            lines.append(f"{msg.author.display_name}: {msg.clean_content}")

        if count < 3:
            embed = discord.Embed(
                title=f"PARLOR RECAP // #{target_channel.name.upper()}",
                description=f"The parlor has been quiet these past {hours} hours. Only `{count}` message(s) recorded.",
                color=discord.Color.from_str("#D4AF37")
            )
            await ctx.send(embed=embed)
            return

        transcript = "\n".join(lines[-80:])
        prompt = (
            f"Summarize the recent conversations in #{target_channel.name} over the past {hours} hours ({count} messages from {len(authors)} members).\n"
            f"Transcript:\n{transcript}\n\n"
            f"Format into 2 elegant sections: 1. Key Topics Discussed. 2. Notable Banter & Highlights.\n"
            f"Tone: Frielle, carefree noble lady. Poised, amusingly perceptive, never boring."
        )

        summary = await self.bot.ai_engine.generate(
            prompt=prompt,
            system_instruction="You are Frielle, carefree noble lady. Provide a stylish parlor digest.",
            temperature=0.7
        )

        embed = discord.Embed(
            title=f"COURT CHRONICLE // #{target_channel.name.upper()}",
            description=f"✦ **Timeframe**: Past `{hours}h` • `{count}` Messages • `{len(authors)}` Voices\n\n{summary}",
            color=discord.Color.from_str("#D4AF37")
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="dossier",
        description="Gathers a person's past 1,000 messages across the server for an AI profile."
    )
    async def dossier(self, ctx: commands.Context, member: discord.Member, topic: Optional[str] = None):
        """Pulls up to 1,000 past messages from MongoDB or live channels to summarize everything they talked about."""
        await ctx.defer()
        db = getattr(self.bot.memory, "db", None) if hasattr(self.bot, "memory") else None
        user_id_str = str(member.id)
        messages = []

        # 1. Query MongoDB chat_history collection first
        if db is not None:
            try:
                coll = db["chat_history"]
                cursor = coll.find({"user_id": user_id_str, "is_user": True}).sort("timestamp", -1).limit(1000)
                async for doc in cursor:
                    txt = str(doc.get("content", "")).strip()
                    if txt:
                        messages.append(txt)
            except Exception as e:
                logger.warning(f"Failed querying chat_history collection: {e}")

        # 2. If collection has fewer than 50 messages, supplement from current channel history
        if len(messages) < 50 and ctx.channel:
            try:
                async for m in ctx.channel.history(limit=500):
                    if m.author.id == member.id and m.clean_content.strip():
                        if not m.clean_content.startswith(("/", "!", "r!")):
                            messages.append(m.clean_content.strip())
                            if len(messages) >= 1000:
                                break
            except Exception:
                pass

        if not messages:
            await ctx.send(f"I found no recorded conversations from **{member.display_name}** in our archives.", ephemeral=True)
            return

        # Deduplicate while preserving order
        unique_messages = list(dict.fromkeys(messages))[:1000]
        sample_transcript = "\n".join(f"- {m}" for m in unique_messages[:200])

        topic_instruction = f"Focus specifically on their remarks regarding '{topic}'." if topic else "Provide a comprehensive dossier."
        ai_prompt = (
            f"Analyze {len(unique_messages)} past messages from server member '{member.display_name}' (ID: {member.id}).\n"
            f"{topic_instruction}\n\n"
            f"Recent message sample:\n{sample_transcript}\n\n"
            f"Provide an aristocratic court dossier covering:\n"
            f"1. Speech Pattern & Tone: How they communicate.\n"
            f"2. Core Interests & Topics: What they speak about most.\n"
            f"3. Frielle's Take: An amused, charming noble observation on their presence."
        )

        analysis = await self.bot.ai_engine.generate(
            prompt=ai_prompt,
            system_instruction="You are Frielle, carefree noble lady. Write an observant member dossier.",
            temperature=0.7
        )

        embed = discord.Embed(
            title=f"MEMBER DOSSIER // {member.display_name.upper()}",
            description=f"✦ **Inhabitant**: {member.mention}\n✦ **Archives Analyzed**: `{len(unique_messages)} messages`\n\n{analysis}",
            color=discord.Color.from_str("#D4AF37")
        )
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FrielleRecap(bot))
