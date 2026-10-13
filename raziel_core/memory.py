"""
raziel_core/memory.py
Persistent cognitive memory, sliding-window conversation buffer,
and per-user profile recall for Project Raziel.
Supports MongoDB Atlas (ciel_cluster) with seamless local JSON fallback.
"""

import os
import json
import logging
import asyncio
from collections import defaultdict, deque
from typing import List, Dict, Any, Optional
from config import (
    MAX_MEMORY_TURNS,
    MONGO_URI,
    DB_NAME,
    COGNITIVE_COLLECTION
)

logger = logging.getLogger("Raziel.Memory")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "raziel_memory.json")


class MemoryManager:
    """Manages conversational memory and persistent user knowledge across restarts."""

    def __init__(self, max_turns: int = MAX_MEMORY_TURNS, file_path: str = MEMORY_FILE):
        self.max_turns = max_turns
        self.file_path = file_path
        self.buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.max_turns))
        # Cached user records: { user_id_str: { "name": str, "affinity": int, "notes": {}, "topics": [] } }
        self.user_records: Dict[str, Dict[str, Any]] = {}
        self.db_client = None
        self.db = None
        self.collection = None

        # Always warm cache from disk first
        self._load_from_disk()

    async def init_database(self) -> bool:
        """Initializes async MongoDB Atlas connection if URI is configured."""
        if not MONGO_URI or MONGO_URI.startswith("${"):
            logger.info("MongoDB URI not provided. Operating with persistent local JSON storage.")
            return False

        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            self.db_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=4000)
            self.db = self.db_client[DB_NAME]
            self.collection = self.db[COGNITIVE_COLLECTION]

            # Fetch remote records to synchronize into local memory cache
            cursor = self.collection.find({})
            remote_count = 0
            async for doc in cursor:
                uid = str(doc.get("user_id") or doc.get("_id"))
                if uid:
                    # Merge remote records with local cache
                    if uid not in self.user_records:
                        self.user_records[uid] = {
                            "name": doc.get("name", ""),
                            "affinity": doc.get("affinity", 0),
                            "notes": doc.get("notes", {}),
                            "topics": doc.get("topics", [])
                        }
                    else:
                        local_notes = self.user_records[uid].setdefault("notes", {})
                        local_notes.update(doc.get("notes", {}))
                        self.user_records[uid]["affinity"] = max(
                            self.user_records[uid].get("affinity", 0),
                            doc.get("affinity", 0)
                        )
                    remote_count += 1

            logger.info(f"Connected to MongoDB Atlas ({DB_NAME}.{COGNITIVE_COLLECTION}). Synced {remote_count} records.")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to MongoDB Atlas: {e}. Falling back to local storage.")
            self.collection = None
            return False

    def _load_from_disk(self):
        """Loads persistent user memories from disk if available."""
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.user_records = data.get("users", {})
                logger.info(f"Loaded persistent memory for {len(self.user_records)} users from disk.")
        except Exception as e:
            logger.warning(f"Could not load memory file: {e}")

    def save_to_disk(self):
        """Persists current user knowledge state to JSON disk storage."""
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({"users": self.user_records}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save memory to disk: {e}")

    async def _sync_user_to_db(self, user_id_str: str, rec: Dict[str, Any]):
        """Persists a single user's record to MongoDB Atlas asynchronously."""
        if self.collection is None:
            return
        try:
            doc = {
                "user_id": user_id_str,
                "name": rec.get("name", ""),
                "affinity": rec.get("affinity", 0),
                "notes": rec.get("notes", {}),
                "topics": rec.get("topics", [])
            }
            await self.collection.update_one(
                {"user_id": user_id_str},
                {"$set": doc},
                upsert=True
            )
        except Exception as err:
            logger.error(f"Failed syncing user {user_id_str} to MongoDB: {err}")

    def add_turn(self, context_key: str, role: str, content: str, author_name: Optional[str] = None):
        """Adds a turn to the sliding context window."""
        self.buffers[context_key].append({
            "role": role,
            "content": content,
            "author": author_name or role
        })

    def get_history(self, context_key: str) -> List[Dict[str, str]]:
        """Returns the recent turns for formatting into the prompt context."""
        return list(self.buffers[context_key])

    def format_history_for_prompt(self, context_key: str) -> str:
        """Formats recent turns into a readable conversational transcript."""
        turns = self.get_history(context_key)
        if not turns:
            return ""

        formatted = []
        for t in turns:
            author = t.get("author", t["role"])
            formatted.append(f"{author}: {t['content']}")

        return "\n".join(formatted)

    def record_user_interaction(self, user_id: int, user_name: str, topic: Optional[str] = None):
        """Increments affinity and records interaction."""
        u_str = str(user_id)
        if u_str not in self.user_records:
            self.user_records[u_str] = {
                "name": user_name,
                "affinity": 0,
                "notes": {},
                "topics": []
            }

        rec = self.user_records[u_str]
        rec["name"] = user_name
        rec["affinity"] = rec.get("affinity", 0) + 1

        if topic and topic not in rec.setdefault("topics", []):
            rec["topics"].append(topic)
            if len(rec["topics"]) > 10:
                rec["topics"].pop(0)

        self.save_to_disk()

        if self.collection is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._sync_user_to_db(u_str, rec))
            except Exception:
                pass

    def update_user_note(self, user_id: int, key: str, value: Any):
        """Stores a persistent trait or personal note about a user."""
        u_str = str(user_id)
        if u_str not in self.user_records:
            self.user_records[u_str] = {"name": "", "affinity": 1, "notes": {}, "topics": []}

        self.user_records[u_str]["notes"][key] = value
        self.save_to_disk()

        if self.collection is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._sync_user_to_db(u_str, self.user_records[u_str]))
            except Exception:
                pass

    def get_user_profile_summary(self, user_id: int) -> str:
        """Formats stored knowledge about a user into an empathetic prompt addendum."""
        u_str = str(user_id)
        rec = self.user_records.get(u_str)
        if not rec:
            return ""

        notes = rec.get("notes", {})
        affinity = rec.get("affinity", 0)
        topics = rec.get("topics", [])

        lines = [f"[KNOWLEDGE OF {rec.get('name', 'User')}] (Affinity Tier: {affinity} interactions)"]
        if notes:
            for k, v in notes.items():
                lines.append(f"- {k}: {v}")
        if topics:
            lines.append(f"- Frequently discussed topics: {', '.join(topics[:5])}")

        return "\n".join(lines)
