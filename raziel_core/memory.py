"""
raziel_core/memory.py
Persistent cognitive memory, sliding-window conversation buffer,
and per-user profile recall for Project Raziel.
"""

import os
import json
import logging
from collections import defaultdict, deque
from typing import List, Dict, Any, Optional
from config import MAX_MEMORY_TURNS

logger = logging.getLogger("Raziel.Memory")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "raziel_memory.json")


class MemoryManager:
    """Manages conversational memory and persistent user knowledge across restarts."""

    def __init__(self, max_turns: int = MAX_MEMORY_TURNS, file_path: str = MEMORY_FILE):
        self.max_turns = max_turns
        self.file_path = file_path
        self.buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.max_turns))
        # Persistent user records: { user_id_str: { "notes": {}, "affinity": int, "last_seen": float } }
        self.user_records: Dict[str, Dict[str, Any]] = {}
        self._load_from_disk()

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
        """Increments affinity and records interaction timestamp."""
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

        # Periodic save
        self.save_to_disk()

    def update_user_note(self, user_id: int, key: str, value: Any):
        """Stores a persistent trait or personal note about a user."""
        u_str = str(user_id)
        if u_str not in self.user_records:
            self.user_records[u_str] = {"name": "", "affinity": 1, "notes": {}, "topics": []}

        self.user_records[u_str]["notes"][key] = value
        self.save_to_disk()

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
