"""
cogs/persona.py
Inside-joke tracker, familiar phrases ledger, and spontaneous salon presence for Frielle.
Shares MongoDB collection 'ciel_internal_life'.
"""

import discord
from discord.ext import commands, tasks
import time
import logging

logger = logging.getLogger("Raziel.Persona")


class FriellePersona(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.inside_jokes = {}
        self.joke_prune_loop.start()

    def cog_unload(self):
        self.joke_prune_loop.cancel()

    @tasks.loop(hours=24)
    async def joke_prune_loop(self):
        now = time.time()
        cutoff = now - (14 * 24 * 3600)
        self.inside_jokes = {k: v for k, v in self.inside_jokes.items() if v.get("last_seen", 0) > cutoff}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return

        text = message.content.lower().strip()
        if len(text) < 5 or len(text) > 80:
            return

        now = time.time()
        if text not in self.inside_jokes:
            self.inside_jokes[text] = {"count": 0, "first_by": message.author.display_name, "last_seen": now}
        self.inside_jokes[text]["count"] += 1
        self.inside_jokes[text]["last_seen"] = now

        # Record into MongoDB ciel_internal_life if repeated 3+ times
        if self.inside_jokes[text]["count"] == 3:
            db = getattr(self.bot.memory, "db", None) if hasattr(self.bot, "memory") else None
            if db is not None:
                try:
                    coll = db["ciel_internal_life"]
                    await coll.update_one(
                        {"type": "lexicon_entry", "phrase": text},
                        {
                            "$set": {
                                "type": "lexicon_entry",
                                "phrase": text,
                                "origin_user": message.author.display_name,
                                "timestamp": now
                            },
                            "$inc": {"use_count": 3}
                        },
                        upsert=True
                    )
                except Exception:
                    pass

    @commands.hybrid_command(name="jokes", description="View recurring court inside jokes and salon phrases.")
    async def jokes(self, ctx: commands.Context):
        top = sorted(self.inside_jokes.items(), key=lambda x: x[1].get("count", 0), reverse=True)[:8]
        if not top:
            await ctx.send("No recurring salon phrases recorded yet.", ephemeral=True)
            return

        lines = [f"✦ *\"{phrase}\"* — `{data['count']}×` (by {data['first_by']})" for phrase, data in top]
        embed = discord.Embed(
            title="SALON LEXICON & INSIDE JOKES",
            description="\n".join(lines),
            color=discord.Color.from_str("#D4AF37")
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FriellePersona(bot))
