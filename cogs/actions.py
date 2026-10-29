"""
cogs/actions.py
Anime Roleplay Actions & Interactions for Frielle.
Shares MongoDB collection 'action_interactions' with Ciel.
"""

import discord
from discord.ext import commands
import random
import time
import logging
from typing import Optional, Union

logger = logging.getLogger("Raziel.Actions")

ANIME_ACTION_POOLS = {
    "tea": [
        "https://c.tenor.com/mxba4VudIzoAAAAC/frieren-fern.gif",
        "https://c.tenor.com/bu65TP3FPEEAAAAd/gyokuyou-apothecary-diaries.gif"
    ],
    "pat": [
        "https://c.tenor.com/zjKqtDCCGpoAAAAd/date-a-live-kurumi.gif",
        "https://c.tenor.com/-WK1hpKUeXYAAAAd/kurumi.gif",
        "https://c.tenor.com/dfH8Ah9orRAAAAAd/anime-head-pat.gif"
    ],
    "hug": [
        "https://c.tenor.com/c3mbgoaFXmwAAAAC/oshi-no-ko-aqua.gif",
        "https://c.tenor.com/w5TTA_fLV6UAAAAC/anime-hug-hug.gif",
        "https://c.tenor.com/wUQH5CF2DJ4AAAAC/horimiya-hug-anime.gif"
    ],
    "bonk": [
        "https://cdn.gifukai.com/bonk/a7bc23b9-b1f5-4204-9b38-45ec6386ff37.gif",
        "https://c.tenor.com/H5W2tYbC0AcAAAAC/anime-chunibyo.gif"
    ],
    "slap": [
        "https://c.tenor.com/V2aQ-PeFwwUAAAAd/slap.gif",
        "https://c.tenor.com/00huTPPw5HIAAAAC/nami-sanji.gif"
    ],
    "kiss": [
        "https://c.tenor.com/G9ZsCqsPazkAAAAd/kiss-anime-shido-and-kurumi.gif",
        "https://c.tenor.com/32RwFNRSx1EAAAAC/tomoe-nanami-love.gif"
    ],
    "stare": [
        "https://c.tenor.com/mxba4VudIzoAAAAC/frieren-fern.gif",
        "https://c.tenor.com/5q0lv--uUKUAAAAC/girls-last-tour-shoujo-shuumatsu-ryokou.gif"
    ],
    "pout": [
        "https://c.tenor.com/Fkgun6veQW0AAAAd/akane-kurokawa-kurokawa-akane.gif",
        "https://c.tenor.com/bu65TP3FPEEAAAAd/gyokuyou-apothecary-diaries.gif"
    ]
}


class FrielleActions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _record_interaction(self, actor_id: int, target_id: int, action: str, guild_id: int):
        db = getattr(self.bot.memory, "db", None) if hasattr(self.bot, "memory") else None
        if db is not None:
            try:
                coll = db["action_interactions"]
                key = f"{actor_id}:{target_id}:{action}"
                await coll.update_one(
                    {"key": key},
                    {
                        "$inc": {"count": 1},
                        "$set": {
                            "actor_id": str(actor_id),
                            "target_id": str(target_id),
                            "action": action,
                            "guild_id": str(guild_id),
                            "last_used": time.time()
                        }
                    },
                    upsert=True
                )
            except Exception:
                pass

    async def _execute_action(self, ctx: commands.Context, action: str, member: Optional[Union[discord.Member, discord.User]]):
        target = member or ctx.author
        is_self = target.id == ctx.author.id
        guild_id = ctx.guild.id if ctx.guild else 0

        pool = ANIME_ACTION_POOLS.get(action, ANIME_ACTION_POOLS["tea"])
        gif_url = random.choice(pool)

        if not is_self:
            await self._record_interaction(ctx.author.id, target.id, action, guild_id)

        desc = f"**{ctx.author.display_name}** shares a cup of noble tea."
        if action == "pat":
            desc = f"**{ctx.author.display_name}** gently pats **{target.display_name}**." if not is_self else f"**{ctx.author.display_name}** comforts themselves."
        elif action == "hug":
            desc = f"**{ctx.author.display_name}** warmly embraces **{target.display_name}**." if not is_self else f"**{ctx.author.display_name}** hugs themselves."
        elif action == "bonk":
            desc = f"**{ctx.author.display_name}** bonks **{target.display_name}** with noble poise." if not is_self else f"**{ctx.author.display_name}** bonks themselves."
        elif action == "slap":
            desc = f"**{ctx.author.display_name}** slaps **{target.display_name}** across the salon." if not is_self else f"**{ctx.author.display_name}** slaps sense into themselves."
        elif action == "kiss":
            desc = f"**{ctx.author.display_name}** kisses **{target.display_name}**." if not is_self else f"**{ctx.author.display_name}** blows a kiss into the breeze."
        elif action == "stare":
            desc = f"**{ctx.author.display_name}** watches **{target.display_name}** with quiet amusement." if not is_self else f"**{ctx.author.display_name}** gazes into the reflection."
        elif action == "pout":
            desc = f"**{ctx.author.display_name}** pouts gracefully at **{target.display_name}**." if not is_self else f"**{ctx.author.display_name}** pouts into their teacup."

        embed = discord.Embed(
            description=desc,
            color=discord.Color.from_str("#D4AF37")
        )
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pat", description="Pat someone with gentle elegance.")
    async def pat(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None):
        await self._execute_action(ctx, "pat", member)

    @commands.hybrid_command(name="hug", description="Embrace someone warmly.")
    async def hug(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None):
        await self._execute_action(ctx, "hug", member)

    @commands.hybrid_command(name="bonk", description="Deliver a disciplinary bonk.")
    async def bonk(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None):
        await self._execute_action(ctx, "bonk", member)

    @commands.hybrid_command(name="tea", description="Sip afternoon tea in noble repose.")
    async def tea(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None):
        await self._execute_action(ctx, "tea", member)


async def setup(bot):
    await bot.add_cog(FrielleActions(bot))
