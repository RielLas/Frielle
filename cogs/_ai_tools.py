"""
cogs/_ai_tools.py
Autonomous tool execution matrix for Frielle.
Supports: member forensics, live server pulse, web grounding search.
"""

import discord
import logging
import re
from typing import Optional, Any
from ._ai_search import web_search_summary

logger = logging.getLogger("Raziel.AITools")


async def execute_agent_tool(
    bot: Any,
    tool_name: str,
    args: dict,
    context_message: Optional[discord.Message] = None,
) -> str:
    tool_name = (tool_name or "").strip().lower()
    logger.info(f"[FRIELLE TOOL] Executing tool '{tool_name}' with args {args}")

    try:
        # 1. Member Forensics / Telemetry
        if tool_name in ("inspect_member", "member_forensics", "user_lookup"):
            user_query = str(args.get("user") or args.get("username") or args.get("target") or "").strip()
            guild = getattr(context_message, "guild", None)
            target = None

            if guild and user_query:
                clean_id = re.sub(r'[<@!&>]', '', user_query)
                if clean_id.isdigit():
                    target = guild.get_member(int(clean_id))
                if not target:
                    target = discord.utils.find(
                        lambda m: m.name.lower() == user_query.lower() or m.display_name.lower() == user_query.lower() or user_query.lower() in m.display_name.lower(),
                        guild.members
                    )

            if not target and context_message:
                target = context_message.author

            if not target:
                return f"Member '{user_query}' not found in the court."

            account_age = (discord.utils.utcnow() - target.created_at).days
            joined_days = (discord.utils.utcnow() - target.joined_at).days if target.joined_at else 0
            roles = [r.name for r in target.roles if r.name != "@everyone"]
            top_role = target.top_role.name if target.top_role and target.top_role.name != "@everyone" else "Unranked"

            devices = []
            if getattr(target, "desktop_status", discord.Status.offline) != discord.Status.offline:
                devices.append("Desktop")
            if getattr(target, "mobile_status", discord.Status.offline) != discord.Status.offline:
                devices.append("Mobile")
            if getattr(target, "web_status", discord.Status.offline) != discord.Status.offline:
                devices.append("Web")
            device_str = ", ".join(devices) if devices else "Offline"

            status_act = []
            for a in getattr(target, "activities", []):
                if isinstance(a, discord.CustomActivity) and a.name:
                    status_act.append(f"Custom: '{a.name}'")
                elif isinstance(a, discord.Game):
                    status_act.append(f"Playing: {a.name}")
                elif isinstance(a, discord.Spotify):
                    status_act.append(f"Listening: {a.title} by {a.artist}")

            return (
                f"[COURT DOSSIER: {target.display_name}]\n"
                f"- Account Age: {account_age} days old (In Server: {joined_days} days)\n"
                f"- Presence Devices: {device_str}\n"
                f"- Standing / Top Role: {top_role} (Total roles: {len(roles)})\n"
                f"- Current Activity: {'; '.join(status_act) if status_act else 'At repose'}"
            )

        # 2. Server Pulse
        elif tool_name in ("server_pulse", "server_stats", "guild_vibe"):
            guild = getattr(context_message, "guild", None)
            if guild:
                online = sum(1 for m in guild.members if m.status != discord.Status.offline and not m.bot)
                in_vc = sum(len(vc.members) for vc in guild.voice_channels)
                return (
                    f"[WONDERLAND COURT PULSE]\n"
                    f"- Total Inhabitants: {guild.member_count}\n"
                    f"- Citizens Awakened Online: {online}\n"
                    f"- In Voice Parlors: {in_vc}\n"
                    f"- Total Channels: {len(guild.text_channels)}"
                )
            return "Server court context unavailable."

        # 3. Live Web Search
        elif tool_name in ("web_search", "google_search", "search_web"):
            query = str(args.get("query") or "").strip()
            if query:
                summary = await web_search_summary(query)
                return f"[RECORDS FOUND for '{query}']\n{summary}" if summary else f"No records found for '{query}'."
            return "Empty search query."

        else:
            return f"Unrecognized capability '{tool_name}'."

    except Exception as e:
        logger.warning(f"Error executing tool '{tool_name}': {e}")
        return f"Error executing '{tool_name}': {e}"
