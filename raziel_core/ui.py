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


def create_profile_embed(
    user: discord.User,
    tier_label: str,
    tier_badge: str,
    affinity: int,
    notes: Dict[str, str],
    recent_topics: List[str]
) -> discord.Embed:
    """Generates an aesthetic member connection and profile card."""
    embed = discord.Embed(
        title="╭・୨ MEMBER PROFILE ୧",
        description=f"> *\"I cherish every acquaintance who graces our halls.\"*\n\nMember: **{user.display_name}** (`@{user.name}`)",
        color=COLOR_PLATINUM
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(
        name="[TIER STANDING]",
        value=f"**{tier_badge}**\n`{tier_label}`",
        inline=True
    )
    embed.add_field(
        name="[CONNECTION LEVEL]",
        value=f"`{affinity} Interactions`",
        inline=True
    )
    if recent_topics:
        embed.add_field(
            name="[SHARED TOPICS]",
            value=" • ".join(f"`{t}`" for t in recent_topics[:4]),
            inline=False
        )
    if notes:
        note_str = "\n".join(f"• **{k}**: `{v}`" for k, v in list(notes.items())[:5])
        embed.add_field(name="[RECORDED ARCHIVES]", value=note_str, inline=False)

    embed.set_footer(text="Frielle // The Carefree Noble Lady of Wonderland")
    return embed


def create_about_embed() -> discord.Embed:
    """Generates Frielle's public identity card."""
    desc = (
        "> ❝ *Life is far too pleasant to spend it fussing over rules like my dearest sister does.* ❞ ₊˚✧\n\n"
        "I am **Frielle** — Ciel's carefree younger sister and the noble lady of Wonderland.\n\n"
        "╭・✦ ﹕ **MY REPOSE**\n"
        "┊ `[CONVERSATION]` : Relaxed banter, pleasant tea-time discussions, and charming company.\n"
        "┊ `[SANCTUARY]`    : Gentle reassurance, quiet comfort, and late-night listening in DMs.\n"
        "┊ `[SIBLING]`      : Watching Ciel issue decrees with an amused sip of afternoon tea.\n"
        "╰・✦ ﹕ Always pleased to make your acquaintance. Ping me or reply anytime."
    )
    embed = discord.Embed(
        title="╭・✦ ﹕ 𝐹𝓇𝒾𝑒𝓁𝓁𝑒 ₊˚✧",
        description=desc,
        color=COLOR_GOLD
    )
    embed.set_footer(text="[CAREFREE NOBLE LADY] // Wonderland Court")
    return embed
