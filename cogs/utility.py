"""
cogs/utility.py
Profile visualizer, avatar/banner inspect, and full-resolution asset grabber for Frielle.
"""

import discord
from discord.ext import commands
from typing import Optional, Union


class AvatarFormatView(discord.ui.View):
    def __init__(self, asset: discord.Asset):
        super().__init__(timeout=180)
        self.add_item(discord.ui.Button(label="Open High-Res", url=asset.url, style=discord.ButtonStyle.link))


class FrielleUtility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="avatar", aliases=["av", "pfp"], description="Inspect and download a member's full-resolution avatar.")
    async def avatar(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None):
        await ctx.defer()
        target = member or ctx.author
        global_av = target.avatar.url if target.avatar else target.default_avatar.url
        guild_av = getattr(target, "guild_avatar", None)
        guild_av_url = guild_av.url if guild_av else None

        desc = [f"✦ **Global Avatar**: [Download Resolution]({global_av})"]
        if guild_av_url:
            desc.append(f"✦ **Server Avatar**: [Download Resolution]({guild_av_url})")

        embed = discord.Embed(
            title=f"AVATAR DOSSIER // {target.display_name.upper()}",
            description="\n".join(desc),
            color=discord.Color.from_str("#D4AF37")
        )
        embed.set_image(url=guild_av_url or global_av)
        asset = getattr(target, "guild_avatar", None) or target.avatar or target.default_avatar
        view = AvatarFormatView(asset=asset)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="banner", description="Inspect and download a member's profile or server banner.")
    async def banner(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None):
        await ctx.defer()
        target = member or ctx.author
        user_obj = await self.bot.fetch_user(target.id) if hasattr(self.bot, "fetch_user") else target
        banner_url = user_obj.banner.url if getattr(user_obj, "banner", None) else None

        if not banner_url:
            await ctx.send(f"**{target.display_name}** has no custom profile banner displayed.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"BANNER ARCHIVE // {target.display_name.upper()}",
            description=f"✦ **Banner Asset**: [Download Full Resolution]({banner_url})",
            color=discord.Color.from_str("#D4AF37")
        )
        embed.set_image(url=banner_url)
        view = AvatarFormatView(asset=user_obj.banner)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(FrielleUtility(bot))
