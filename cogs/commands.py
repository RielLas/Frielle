"""
cogs/commands.py
Slash commands suite for Project Raziel.
Enables /about, /profile, /remember, and cross-bot /ciel & /setup tier administration
synced directly across both Ciel & Raziel via MongoDB Atlas (ciel_privileges).
"""

import logging
from typing import Literal, Optional, Union
import discord
from discord import app_commands
from discord.ext import commands

from raziel_core.ui import create_about_embed, create_profile_embed, create_safe_harbor_embed
from raziel_core.ai_engine import GeminiEngine
from raziel_core.memory import MemoryManager
from raziel_core.tiers import TierManager

logger = logging.getLogger("Raziel.Commands")


class RazielCommandsCog(commands.Cog):
    """Application command suite for Raziel."""

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

    def _is_authorized(self, user: Union[discord.User, discord.Member]) -> bool:
        """Only Sovereign (Riel) or First Lady (Lady Mae) may assign sanctuary privileges."""
        tier, _, _ = self.tiers.resolve_tier(user)
        return tier in ("sovereign", "first_lady")

    # ---------------------------------------------------------------------------
    # Core User Commands
    # ---------------------------------------------------------------------------
    @app_commands.command(name="about", description="Learn about Raziel and his role as the Safe Harbor.")
    async def about_cmd(self, interaction: discord.Interaction):
        embed = create_about_embed()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="Check your tier standing and what Raziel remembers about you.")
    async def profile_cmd(self, interaction: discord.Interaction):
        u_str = str(interaction.user.id)
        rec = self.memory.user_records.get(u_str, {})
        affinity = rec.get("affinity", 0)
        notes = rec.get("notes", {})
        topics = rec.get("topics", [])

        # Resolve tier
        _, tier_label, tier_badge = self.tiers.resolve_tier(interaction.user)

        embed = create_profile_embed(
            user=interaction.user,
            tier_label=tier_label,
            tier_badge=tier_badge,
            affinity=affinity,
            notes=notes,
            recent_topics=topics
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="remember", description="Tell Raziel a detail or preference to remember about you.")
    @app_commands.describe(key="The topic or trait (e.g. 'favorite anime', 'hobbies', 'timezone')", value="The detail to remember")
    async def remember_cmd(self, interaction: discord.Interaction, key: str, value: str):
        # Sanitize against delimiter injection and enforce length limits
        clean_key = key.replace("===", "").replace("[CONTEXT", "").replace("\n", " ").strip()[:32].title()
        clean_val = value.replace("===", "").replace("[CONTEXT", "").replace("\n", " ").strip()[:120]
        if not clean_key or not clean_val:
            await interaction.response.send_message("Please provide a valid detail to remember.", ephemeral=True)
            return

        self.memory.update_user_note(interaction.user.id, clean_key, clean_val)

        embed = create_safe_harbor_embed(
            title="MEMORY RECORDED",
            description=f"> *\"Tucked away in the archives.\"*\n\nI'll remember that your **{clean_key}** is: `{clean_val}`.",
            footer_text=f"Updated record for @{interaction.user.name}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------------------------------------------------------------------------
    # Cross-Bot Synchronized Privilege Administration (/ciel group)
    # Synced live across both Ciel & Raziel via shared ciel_privileges collection
    # ---------------------------------------------------------------------------
    raziel_group = app_commands.Group(name="raziel", description="Direct Raziel database & tier privilege suite")
    setup_group = app_commands.Group(name="setup", description="Sanctuary configuration and tier setup suite")

    async def _handle_role_add_id(
        self,
        interaction: discord.Interaction,
        target_id: str,
        target_type: Literal["role", "user"],
        tier: Literal["girlfriend", "duchess", "sister", "respected"],
        target_name: Optional[str] = None,
        reason: Optional[str] = "Permanent privilege promotion"
    ):
        if not self._is_authorized(interaction.user):
            await interaction.response.send_message(
                "`[UNAUTHORIZED]` Only Riel or Sovereign First Lady may assign permanent sanctuary tiers.",
                ephemeral=True
            )
            return

        clean_id = target_id.strip()
        clean_tier = tier.lower().strip()
        name = target_name or f"{target_type.title()} {clean_id}"

        # Write to shared MongoDB collection ciel_privileges
        success = await self.tiers.add_privilege(
            db=self.memory.db,
            target_id=clean_id,
            target_type=target_type,
            target_name=name,
            tier=clean_tier,
            granted_by_id=str(interaction.user.id),
            granted_by_name=interaction.user.name,
            reason=reason or "Permanent privilege promotion"
        )

        tier_badges = {
            "girlfriend": "[FIRST LADY]",
            "duchess": "[ESTEEMED DUCHESS]",
            "sister": "[CREATOR'S SISTER]",
            "respected": "[VALUED PATRON]"
        }
        badge = tier_badges.get(clean_tier, "[SANCTUARY REGULAR]")

        embed = discord.Embed(
            title="╭・୨ SANCTUARY PRIVILEGE SYNCHRONIZED ୧",
            description=(
                f"✦ **Target**: `{name}` (`ID: {clean_id}`)\n"
                f"✦ **Target Type**: `{target_type.upper()}`\n"
                f"✦ **Assigned Tier**: **{badge}** (`{clean_tier.upper()}`)\n"
                f"✦ **Reason**: *\"{reason}\"*\n\n"
                f"⚡ **Status**: Live & Synced across **Ciel** and **Raziel**."
            ),
            color=discord.Color.from_str("#6366F1")
        )
        embed.set_footer(text="MongoDB Atlas // Shared Cluster Synced")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @raziel_group.command(name="roleadd_id", description="Assign a permanent tier to a role ID or user ID (synced with Ciel).")
    @app_commands.describe(
        target_id="The Discord Role ID or User ID",
        target_type="Whether the target is a role or user",
        tier="Tier to assign (girlfriend, duchess, sister, respected)",
        target_name="Optional readable name for this role/user",
        reason="Reason or deal note for this privilege"
    )
    async def raziel_roleadd_id(
        self,
        interaction: discord.Interaction,
        target_id: str,
        target_type: Literal["role", "user"],
        tier: Literal["girlfriend", "duchess", "sister", "respected"],
        target_name: Optional[str] = None,
        reason: Optional[str] = "Permanent privilege promotion"
    ):
        await self._handle_role_add_id(interaction, target_id, target_type, tier, target_name, reason)

    @setup_group.command(name="roleadd_id", description="Assign a permanent tier to a role ID or user ID (synced with Ciel).")
    @app_commands.describe(
        target_id="The Discord Role ID or User ID",
        target_type="Whether the target is a role or user",
        tier="Tier to assign (girlfriend, duchess, sister, respected)",
        target_name="Optional readable name for this role/user",
        reason="Reason or deal note for this privilege"
    )
    async def setup_roleadd_id(
        self,
        interaction: discord.Interaction,
        target_id: str,
        target_type: Literal["role", "user"],
        tier: Literal["girlfriend", "duchess", "sister", "respected"],
        target_name: Optional[str] = None,
        reason: Optional[str] = "Permanent privilege promotion"
    ):
        await self._handle_role_add_id(interaction, target_id, target_type, tier, target_name, reason)

    @raziel_group.command(name="role_remove", description="Revoke permanent tier privileges from an ID (synced with Ciel).")
    @app_commands.describe(target_id="The Discord Role ID or User ID to remove")
    async def raziel_role_remove(self, interaction: discord.Interaction, target_id: str):
        if not self._is_authorized(interaction.user):
            await interaction.response.send_message("`[UNAUTHORIZED]` Only Riel or Sovereign First Lady may modify tiers.", ephemeral=True)
            return

        clean_id = target_id.strip()
        await self.tiers.remove_privilege(self.memory.db, clean_id)
        embed = discord.Embed(
            title="╭・୨ PRIVILEGE REVOKED ୧",
            description=f"Target ID `{clean_id}` has been removed from permanent privileges.\nSynced across **Ciel** and **Raziel**.",
            color=discord.Color.from_str("#E2E8F0")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @raziel_group.command(name="role_list", description="List all dynamic privileges currently active in MongoDB Atlas.")
    async def raziel_role_list(self, interaction: discord.Interaction):
        # Refresh from DB
        await self.tiers.sync_privileges_from_db(self.memory.db)
        dyn = self.tiers.dynamic_privileges

        lines = []
        for tier_key, badge in [
            ("girlfriend", "[FIRST LADY]"),
            ("duchess", "[ESTEEMED DUCHESS]"),
            ("sister", "[CREATOR'S SISTER]"),
            ("respected", "[VALUED PATRON]")
        ]:
            roles = dyn.get(f"{tier_key}_roles", set())
            users = dyn.get(f"{tier_key}_users", set())
            r_str = ", ".join(f"`Role:{r}`" for r in roles) if roles else "None"
            u_str = ", ".join(f"`User:{u}`" for u in users) if users else "None"
            lines.append(f"**{badge}**\n• Roles: {r_str}\n• Users: {u_str}")

        embed = discord.Embed(
            title="╭・୨ LIVE SANCTUARY PRIVILEGES (MONGODB) ୧",
            description="\n\n".join(lines),
            color=discord.Color.from_str("#6366F1")
        )
        embed.set_footer(text="Unified Ciel & Raziel Permissions")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setup_group.command(name="sync", description="Force real-time synchronization with Ciel's MongoDB Atlas database.")
    async def setup_sync(self, interaction: discord.Interaction):
        count = await self.tiers.sync_privileges_from_db(self.memory.db)
        await interaction.response.send_message(
            f"`[SYNC COMPLETE]` Successfully synchronized **{count}** dynamic privilege documents from `ciel_privileges`.",
            ephemeral=True
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
    await bot.add_cog(RazielCommandsCog(bot, ai_engine, memory, tier_manager))
