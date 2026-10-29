"""
cogs/social.py
Social intelligence, AFK auto-replies, and AI Aura / Vibecheck for Frielle.
Shares MongoDB collection 'ciel_afk_records'.
"""

import discord
from discord.ext import commands
import datetime
import time
import logging
from typing import Optional, Dict, Union

logger = logging.getLogger("Raziel.Social")


def format_duration(seconds: float) -> str:
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0:
        parts.append(f"{mins}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


class FrielleSocial(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._afk_cache: Dict[str, dict] = {}
        self._mention_cooldowns: Dict[str, float] = {}

    async def cog_load(self):
        await self._warm_afk_cache()

    async def _warm_afk_cache(self):
        db = getattr(self.bot.memory, "db", None) if hasattr(self.bot, "memory") else None
        if db is None:
            return
        try:
            coll = db["ciel_afk_records"]
            docs = await coll.find({}).to_list(length=1000)
            for doc in docs:
                key = f"{doc.get('guild_id', '')}:{doc.get('user_id', '')}"
                self._afk_cache[key] = doc
            logger.info(f"Warmed AFK cache: {len(docs)} records.")
        except Exception as e:
            logger.warning(f"Failed warming AFK cache: {e}")

    async def _get_afk(self, user_id: int, guild_id: int) -> Optional[dict]:
        key = f"{str(guild_id)}:{str(user_id)}"
        return self._afk_cache.get(key)

    async def _set_afk(self, user_id: int, guild_id: int, reason: str):
        u_str = str(user_id)
        g_str = str(guild_id)
        key = f"{g_str}:{u_str}"
        data = {
            "user_id": u_str,
            "guild_id": g_str,
            "reason": reason,
            "timestamp": time.time(),
            "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        }
        self._afk_cache[key] = data
        db = getattr(self.bot.memory, "db", None) if hasattr(self.bot, "memory") else None
        if db is not None:
            try:
                coll = db["ciel_afk_records"]
                await coll.update_one({"user_id": u_str, "guild_id": g_str}, {"$set": data}, upsert=True)
            except Exception as e:
                logger.warning(f"Failed setting AFK in DB: {e}")

    async def _remove_afk(self, user_id: int, guild_id: int):
        u_str = str(user_id)
        g_str = str(guild_id)
        key = f"{g_str}:{u_str}"
        self._afk_cache.pop(key, None)
        db = getattr(self.bot.memory, "db", None) if hasattr(self.bot, "memory") else None
        if db is not None:
            try:
                coll = db["ciel_afk_records"]
                await coll.delete_one({"user_id": u_str, "guild_id": g_str})
            except Exception as e:
                logger.warning(f"Failed clearing AFK in DB: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        author_id = message.author.id

        # 1. Author returning from AFK
        if not message.content.strip().startswith(("/afk", "!afk", "r!afk")):
            afk_data = await self._get_afk(author_id, guild_id)
            if afk_data:
                await self._remove_afk(author_id, guild_id)
                elapsed = time.time() - afk_data.get("timestamp", time.time())
                time_str = format_duration(elapsed)
                embed = discord.Embed(
                    title="WELCOME BACK",
                    description=(
                        f"Welcome back, {message.author.mention}. Your repose has ended.\n"
                        f"Time Away: `{time_str}`\n"
                        f"Note: *\"{afk_data.get('reason', 'AFK')}\"*"
                    ),
                    color=discord.Color.from_str("#D4AF37")
                )
                try:
                    await message.channel.send(embed=embed, delete_after=12)
                except Exception:
                    pass

        # 2. Check if author mentioned someone AFK
        if message.mentions:
            now = time.time()
            for mentioned in message.mentions:
                if mentioned.id == author_id or mentioned.bot:
                    continue
                afk_target = await self._get_afk(mentioned.id, guild_id)
                if afk_target:
                    cd_key = f"{guild_id}:{mentioned.id}:{author_id}"
                    if now - self._mention_cooldowns.get(cd_key, 0) < 60:
                        continue
                    self._mention_cooldowns[cd_key] = now
                    ts = int(afk_target.get("timestamp", now))
                    reason = afk_target.get("reason", "AFK")
                    embed = discord.Embed(
                        description=f"💤 **{mentioned.display_name}** is currently at repose: `{reason}` (<t:{ts}:R>)",
                        color=discord.Color.from_str("#A0AEC0")
                    )
                    try:
                        await message.channel.send(embed=embed, delete_after=15)
                    except Exception:
                        pass

    @commands.hybrid_command(name="afk", description="Set your AFK repose status. Clears when you speak.")
    async def afk(self, ctx: commands.Context, *, reason: str = "At repose"):
        clean_reason = reason.strip()[:150]
        guild_id = ctx.guild.id if ctx.guild else 0
        await self._set_afk(ctx.author.id, guild_id, clean_reason)
        embed = discord.Embed(
            title="AFK STATUS RECORDED",
            description=(
                f"{ctx.author.mention} has stepped away into repose.\n"
                f"Reason: *\"{clean_reason}\"*\n\n"
                f"*I shall inform anyone who inquires of your presence.*"
            ),
            color=discord.Color.from_str("#D4AF37")
        )
        if ctx.author.display_avatar:
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="vibecheck", description="Noble court inspection of a member's avatar, status, and aura.")
    async def vibecheck(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None):
        await ctx.defer()
        target = member or ctx.author
        if not isinstance(target, discord.Member) and ctx.guild:
            target = ctx.guild.get_member(target.id) or target

        status = getattr(target, "status", "offline")
        roles = [r.name for r in getattr(target, "roles", []) if r.name != "@everyone"]
        top_role = getattr(target.top_role, "name", "Unranked") if getattr(target, "top_role", None) else "Citizen"

        act_desc = []
        for a in getattr(target, "activities", []):
            if isinstance(a, discord.CustomActivity) and a.name:
                act_desc.append(f"Thought: '{a.name}'")
            elif isinstance(a, discord.Game):
                act_desc.append(f"Playing: {a.name}")
            elif isinstance(a, discord.Spotify):
                act_desc.append(f"Listening to: {a.title} by {a.artist}")

        ai_prompt = (
            f"Generate a witty, noble, and charming 2-sentence 'Court Aura Diagnostic' for member '{target.display_name}'.\n"
            f"Details: Top role '{top_role}', Total roles {len(roles)}, Status '{status}', Activities: {'; '.join(act_desc) or 'Resting in salon'}.\n"
            f"Voice: Frielle, carefree noble lady. Poised, playful, amusingly perceptive."
        )

        aura_text = await self.bot.ai_engine.generate(
            prompt=ai_prompt,
            system_instruction="You are Frielle, carefree noble lady. Write a 2-sentence court aura diagnostic.",
            temperature=0.8
        )

        embed = discord.Embed(
            title=f"COURT AURA DIAGNOSTIC // {target.display_name.upper()}",
            description=f"✦ **Inhabitant**: {target.mention}\n✦ **Standing**: `{top_role}`\n\n{aura_text}",
            color=discord.Color.from_str("#D4AF37")
        )
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FrielleSocial(bot))
