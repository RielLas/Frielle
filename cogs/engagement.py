"""
cogs/engagement.py
Reaction roulette (emoji micro-expressions) and anonymous confessions for Frielle.
"""

import discord
from discord.ext import commands
import random
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger("Raziel.Engagement")


class ConfessionView(discord.ui.View):
    def __init__(self, bot=None, confession_id: Optional[int] = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.confession_id = confession_id

    async def _handle_vote(self, interaction: discord.Interaction, vote_type: str):
        msg = interaction.message
        if not msg:
            await interaction.response.send_message("Confession not found.", ephemeral=True)
            return
        msg_id = str(msg.id)
        uid = str(interaction.user.id)
        db = getattr(self.bot.memory, "db", None) if self.bot and hasattr(self.bot, "memory") else None

        votes: Dict[str, str] = {}
        if db is not None:
            try:
                coll = db["ciel_confessions"]
                await coll.update_one({"_id": msg_id}, {"$set": {f"votes.{uid}": vote_type}}, upsert=True)
                doc = await coll.find_one({"_id": msg_id})
                if doc and "votes" in doc:
                    votes = doc["votes"]
            except Exception:
                pass

        n_real = sum(1 for v in votes.values() if v == "real")
        n_down_bad = sum(1 for v in votes.values() if v == "down_bad")
        n_jail = sum(1 for v in votes.values() if v == "jail")
        total = n_real + n_down_bad + n_jail

        pct_real = round((n_real / total) * 100) if total > 0 else 0
        pct_down_bad = round((n_down_bad / total) * 100) if total > 0 else 0
        pct_jail = round((n_jail / total) * 100) if total > 0 else 0

        verdict_val = (
            f"**Real** ({pct_real}%) `{n_real}` • "
            f"**Down Bad** ({pct_down_bad}%) `{n_down_bad}` • "
            f"**Jail** ({pct_jail}%) `{n_jail}`\n"
            f"`Total Votes: {total}`"
        )

        if msg.embeds:
            embed = msg.embeds[0]
            if len(embed.fields) >= 1:
                embed.set_field_at(0, name="✦ Court Verdict", value=verdict_val, inline=False)
            else:
                embed.add_field(name="✦ Court Verdict", value=verdict_val, inline=False)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Verdict recorded.", ephemeral=True)

    @discord.ui.button(label="Real", style=discord.ButtonStyle.secondary, custom_id="btn_confess_real")
    async def vote_real(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "real")

    @discord.ui.button(label="Down Bad", style=discord.ButtonStyle.secondary, custom_id="btn_confess_down_bad")
    async def vote_down_bad(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "down_bad")

    @discord.ui.button(label="Jail", style=discord.ButtonStyle.secondary, custom_id="btn_confess_jail")
    async def vote_jail(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "jail")


class FrielleEngagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(ConfessionView(bot=self.bot))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Reaction roulette: 12% chance to add subtle noble reaction
        if random.random() < 0.12:
            text = message.content.lower()
            REACTION_MAP = {
                "?": ["🤔", "☕"],
                "!": ["✨", "😮"],
                "lol": ["🤭", "✨"],
                "tea": ["🫖", "☕"],
                "ciel": ["👀", "🤭"],
                "love": ["💖", "🌹"],
                "nice": ["✨", "👌"],
                "sleep": ["💤", "🌙"]
            }
            for kw, emojis in REACTION_MAP.items():
                if kw in text:
                    try:
                        await message.add_reaction(random.choice(emojis))
                    except Exception:
                        pass
                    break

    @commands.hybrid_command(name="confess", description="Submit an anonymous secret or confession to the salon.")
    async def confess(self, ctx: commands.Context, *, secret: str):
        await ctx.defer(ephemeral=True)
        clean_secret = secret.strip()
        if len(clean_secret) < 5:
            await ctx.send("Your confession is too short to dispatch.", ephemeral=True)
            return

        confession_id = random.randint(1000, 9999)
        embed = discord.Embed(
            title=f"ANONYMOUS CONFESSION #{confession_id}",
            description=f"*\"{clean_secret}\"*",
            color=discord.Color.from_str("#D4AF37"),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="✦ Court Verdict",
            value="**Real** (0%) `0` • **Down Bad** (0%) `0` • **Jail** (0%) `0`\n`Total Votes: 0`",
            inline=False
        )

        view = ConfessionView(bot=self.bot, confession_id=confession_id)
        target_channel = (
            discord.utils.get(ctx.guild.text_channels, name="✧・confessions")
            or discord.utils.get(ctx.guild.text_channels, name="confessions")
            or ctx.channel
        )

        sent_msg = await target_channel.send(embed=embed, view=view)
        db = getattr(self.bot.memory, "db", None) if hasattr(self.bot, "memory") else None
        if db is not None:
            try:
                coll = db["ciel_confessions"]
                await coll.insert_one({
                    "_id": str(sent_msg.id),
                    "confession_id": confession_id,
                    "created_at": time.time(),
                    "votes": {}
                })
            except Exception:
                pass

        await ctx.send("Your confession has been delivered anonymously to the salon.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(FrielleEngagement(bot))
