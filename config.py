"""
config.py
Configuration loader and constant registry for Project Raziel.
"""

import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

# Discord Configuration
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
GUILD_ID: int = int(os.getenv("GUILD_ID", "1491530689152024637"))
COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "r!")

# Known Entity IDs
CIEL_BOT_ID: int = int(os.getenv("CIEL_BOT_ID", "1502685311568707686"))
MASTER_RIEL_ID: int = int(os.getenv("MASTER_RIEL_ID", "575745179202355211"))

# Primary Channel Channels
CHANNEL_THE_VOID: int = int(os.getenv("CHANNEL_THE_VOID", "1491530690557378612"))
CHANNEL_WHISPERS: int = int(os.getenv("CHANNEL_WHISPERS", "1541137470027071668"))

# AI Architecture: Gemini Flash-Lite Priority Stack
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
# Support comma-separated pool for free-tier key cycling
GEMINI_API_KEYS: List[str] = [
    k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()
]
if GEMINI_API_KEY and GEMINI_API_KEY not in GEMINI_API_KEYS:
    GEMINI_API_KEYS.insert(0, GEMINI_API_KEY)

DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODELS: List[str] = [
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash"
]

# Personality Settings
CROSS_BOT_COOLDOWN_SECONDS: int = int(os.getenv("CROSS_BOT_COOLDOWN_SECONDS", "180"))
CROSS_BOT_CHANCE: float = float(os.getenv("CROSS_BOT_CHANCE", "0.35"))
MAX_MEMORY_TURNS: int = int(os.getenv("MAX_MEMORY_TURNS", "15"))
