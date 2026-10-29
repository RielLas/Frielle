"""
config.py
Configuration loader and constant registry for Project Raziel.
Ingests config.json and dynamically overlays environment variables.
"""

import os
import json
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger("Raziel.Config")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config() -> Dict[str, Any]:
    """Loads configuration from config.json with fallback defaults."""
    if not os.path.exists(CONFIG_FILE):
        logger.warning(f"Configuration file '{CONFIG_FILE}' missing. Using defaults.")
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {CONFIG_FILE}: {e}")
        return {}


CONFIG_DATA = load_config()

# ---------------------------------------------------------------------------
# Discord Configuration
# ---------------------------------------------------------------------------
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "") or os.getenv("RAZIEL_BOT_TOKEN", "")
bot_settings = CONFIG_DATA.get("bot_settings", {})
COMMAND_PREFIX: str = str(bot_settings.get("command_prefix", "r!"))
CIEL_BOT_ID: int = int(os.getenv("CIEL_BOT_ID", str(bot_settings.get("ciel_bot_id", 1502567501555568680))))
CIEL_BOT_IDS = {CIEL_BOT_ID, 1502567501555568680, 1502685311568707686}
MASTER_RIEL_ID: int = int(os.getenv("MASTER_RIEL_ID", "575745179202355211"))

# ---------------------------------------------------------------------------
# MongoDB Atlas Database Configuration (Shared with Ciel cluster)
# ---------------------------------------------------------------------------
db_settings = CONFIG_DATA.get("database", {})
MONGO_URI: str = os.getenv("MONGO_URI", "") or os.getenv("CIEL_MONGO_URI", "") or os.getenv("RAZIEL_MONGO_URI", "")
if not MONGO_URI and not db_settings.get("mongo_uri", "").startswith("${"):
    MONGO_URI = db_settings.get("mongo_uri", "")

DB_NAME: str = os.getenv("DB_NAME", db_settings.get("db_name", "ciel_cluster"))
COGNITIVE_COLLECTION: str = os.getenv("COGNITIVE_COLLECTION", db_settings.get("cognitive_collection", "ciel_cognitive_archive"))
CHAT_HISTORY_COLLECTION: str = os.getenv("CHAT_HISTORY_COLLECTION", db_settings.get("chat_history_collection", "ciel_chat_history"))

# ---------------------------------------------------------------------------
# AI Architecture: Gemini Flash-Lite Priority Stack
# ---------------------------------------------------------------------------
ai_settings = CONFIG_DATA.get("ai_module", {})
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "") or os.getenv("CIEL_GEMINI_API_KEY", "")
raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("CIEL_GEMINI_API_KEYS", "")
GEMINI_API_KEYS: List[str] = [k.strip() for k in raw_keys.split(",") if k.strip()]
if GEMINI_API_KEY and GEMINI_API_KEY not in GEMINI_API_KEYS:
    GEMINI_API_KEYS.insert(0, GEMINI_API_KEY)

DEFAULT_MODEL: str = ai_settings.get("default_model", "gemini-3.5-flash-lite")
FALLBACK_MODELS: List[str] = ai_settings.get("fallback_models", [
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash"
])

# ---------------------------------------------------------------------------
# Behavior & Personality Settings
# ---------------------------------------------------------------------------
CROSS_BOT_COOLDOWN_SECONDS: int = int(os.getenv("CROSS_BOT_COOLDOWN_SECONDS", str(bot_settings.get("cross_bot_cooldown_seconds", 180))))
CROSS_BOT_CHANCE: float = float(os.getenv("CROSS_BOT_CHANCE", str(bot_settings.get("cross_bot_chance", 0.35))))
MAX_MEMORY_TURNS: int = int(os.getenv("MAX_MEMORY_TURNS", str(bot_settings.get("max_memory_turns", 15))))

# ---------------------------------------------------------------------------
# Tiers Configuration
# ---------------------------------------------------------------------------
TIERS_CONFIG: Dict[str, Any] = CONFIG_DATA.get("tiers", {})
