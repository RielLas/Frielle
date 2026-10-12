"""
raziel_core/ui.py
Aesthetic embed generator and Discord presentation toolkit for Project Raziel.
Enforces AGENTS.md high-craft standards: zero generic emojis, semantic text badges,
and clean typography.
"""

import discord
from typing import Optional, List, Dict

COLOR_PLATINUM = discord.Color.from_str("#E2E8F0")
COLOR_TWILIGHT = discord.Color.from_str("#6366F1")
COLOR_GOLD = discord.Color.from_str("#D4AF37")
COLOR_VOID_DARK = discord.Color.from_str("#0F172A")


def create_safe_harbor_embed(
    title: str,
    description: str,
    footer_text: Optional[str] = None
) -> discord.Embed:
    """Generates a calming, high-craft Safe Harbor embed."""
    embed = discord.Embed(
        title=f"╭・୨ {title} ୧",
        description=description,
        color=COLOR_TWILIGHT
    )
    if footer_text:
        embed.set_footer(text=f"[HARBOR] {footer_text}")
    return embed


def create_dossier_embed(
    user: discord.User,
    affinity: int,
    notes: Dict[str, str],
    recent_topics: List[str]
) -> discord.Embed:
    """Generates an aesthetic user connection card."""
    embed = discord.Embed(
        title=f"╭・୨ CONNECTION DOSSIER ୧",
        description=f"> *\"I remember every conversation that passes through the harbor.\"*\n\nMember: **{user.display_name}** (`@{user.name}`)",
        color=COLOR_PLATINUM
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(
        name="[AFFINITY TIER]",
        value=f"`{affinity} Interactions`",
        inline=True
    )
    if recent_topics:
        embed.add_field(
            name="[SHARED TOPICS]",
            value=" • ".join(f"`{t}`" for t in recent_topics[:4]),
            inline=True
        )
    if notes:
        note_str = "\n".join(f"• **{k}**: `{v}`" for k, v in list(notes.items())[:5])
        embed.add_field(name="[OBSERVATIONS]", value=note_str, inline=False)

    embed.set_footer(text="Project Raziel // The Safe Harbor of Wonderland")
    return embed


def create_about_embed() -> discord.Embed:
    """Generates Raziel's public identity card."""
    desc = (
        "> ❝ *The secret is not in the stars, but in having someone who listens.* ❞ ₊˚✧\n\n"
        "I am **Raziel** — Keeper of Mysteries and the Safe Harbor of Wonderland.\n\n"
        "╭・✦ ﹕ **SANCTUARY ROLES**\n"
        "┊ `[PUBLIC]` : Banter, casual conversations, and creative discussions in <#1491530690557378612>.\n"
        "┊ `[HARBOR]` : Private listening, quiet reassurance, and late-night venting in DMs.\n"
        "┊ `[COUNCIL]` : Keeping Ciel from overcooking her circuits or erasing the inhabitants.\n"
        "╰・✦ ﹕ Zero judgments, zero unprompted advice. Talk to me anytime."
    )
    embed = discord.Embed(
        title="╭・✦ ﹕ 𝒫𝓇𝑜𝒿𝑒𝒸𝓉 𝑅𝒶𝓏𝒾𝑒𝓁 ₊˚✧",
        description=desc,
        color=COLOR_GOLD
    )
    embed.set_footer(text="[KEEPER OF MYSTERIES] // Wonderland Sanctuary")
    return embed
