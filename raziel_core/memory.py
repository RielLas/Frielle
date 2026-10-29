"""
raziel_core/memory.py
Persistent cognitive memory, sliding-window conversation buffer,
and per-user profile recall for Project Raziel.
Supports MongoDB Atlas (ciel_cluster) with seamless local JSON fallback.
"""

import os
import re
import json
import logging
import asyncio
import threading
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
MAX_USER_NOTES = 10


def sanitize_memory_field(text: Any, max_len: int = 80) -> str:
    """Strips delimiters, brackets, system headers, and newlines to prevent prompt injection via memory."""
    if not text:
        return ""
    s = str(text)
    # Strip structural delimiters and section headers
    s = s.replace("===", "").replace("[CONTEXT", "").replace("[SYSTEM", "").replace("[SOVEREIGN", "")
    s = s.replace("[", "").replace("]", "")
    # Strip newlines and carriage returns
    s = re.sub(r"[\r\n]+", " ", s)
    # Collapse multiple whitespaces
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()[:max_len]


class MemoryManager:
    """Manages conversational memory and persistent user knowledge across restarts."""

    def __init__(self, max_turns: int = MAX_MEMORY_TURNS, file_path: str = MEMORY_FILE):
        self.max_turns = max_turns
        self.file_path = file_path
        self._disk_lock = threading.Lock()
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
            self.db_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.db = self.db_client[DB_NAME]
            self.collection = self.db[COGNITIVE_COLLECTION]
            # Ping database to confirm connection
            await self.db.command("ping")
            logger.info(f"Connected to MongoDB Atlas ({DB_NAME}.{COGNITIVE_COLLECTION}).")
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
        """Persists current user knowledge state to JSON disk storage safely and atomically."""
        # Deep-copy nested dicts/lists to prevent 'dict changed size during iteration' in thread pool
        snapshot = {
            uid: {
                "name": rec.get("name", ""),
                "affinity": rec.get("affinity", 0),
                "notes": dict(rec.get("notes", {})),
                "topics": list(rec.get("topics", []))
            }
            for uid, rec in self.user_records.items()
        }

        def _write(data):
            with self._disk_lock:
                try:
                    os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
                    tmp_file = f"{self.file_path}.tmp"
                    with open(tmp_file, "w", encoding="utf-8") as f:
                        json.dump({"users": data}, f, indent=2, ensure_ascii=False)
                    os.replace(tmp_file, self.file_path)
                except Exception as e:
                    logger.error(f"Failed to save memory to disk: {e}")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_in_executor(None, _write, snapshot)
            else:
                _write(snapshot)
        except Exception:
            _write(snapshot)

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
        """Adds a turn to the sliding context window, bounding active buffers."""
        # Bound active memory buffers to prevent memory leaks in massive servers
        if len(self.buffers) > 500:
            for old_key in list(self.buffers.keys())[:100]:
                self.buffers.pop(old_key, None)

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

    def record_user_interaction(
        self,
        user_id: int,
        user_name: str,
        topic: Optional[str] = None,
        context_key: Optional[str] = None,
        ai_engine: Optional[Any] = None
    ):
        """Increments affinity and records interaction, triggering automated semantic extraction periodically."""
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

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                if self.collection is not None:
                    asyncio.create_task(self._sync_user_to_db(u_str, rec))
                # Trigger semantic memory extraction every 10 interactions (or on 5th initial interaction)
                affinity = rec["affinity"]
                if (affinity == 5 or affinity % 10 == 0) and context_key and ai_engine:
                    asyncio.create_task(self.extract_semantic_notes(user_id, user_name, context_key, ai_engine))
        except Exception:
            pass

    async def extract_semantic_notes(self, user_id: int, user_name: str, context_key: str, ai_engine: Any):
        """
        Asynchronously extracts 1-2 key personal facts/preferences about a specific user
        from recent conversation turns in a non-blocking background task.
        """
        if not ai_engine:
            return
        turns = self.get_history(context_key)
        if not turns or len(turns) < 3:
            return

        safe_user_name = sanitize_memory_field(user_name, max_len=32) or "the user"
        recent_dialogue = "\n".join([f"{t.get('author', t['role'])}: {t['content']}" for t in turns[-12:]])
        extraction_prompt = (
            f"Analyze the recent dialogue between Raziel and server members.\n"
            f"Extract 1-2 new, concrete personal facts, preferences, or hobbies specifically about the user named '{safe_user_name}' (ignore statements made by other chatters and ignore Raziel).\n"
            "Return ONLY a clean JSON object where keys are the trait/topic (e.g. 'favorite game', 'timezone', 'hobby', 'pet') "
            "and values are short strings (under 60 chars).\n"
            f"If no clear personal facts were revealed about '{safe_user_name}', return an empty JSON object: {{}}\n\n"
            f"=== RECENT DIALOGUE ===\n{recent_dialogue}\n"
        )
        try:
            raw_json = await ai_engine.generate(
                prompt=extraction_prompt,
                system_instruction="You are a silent semantic memory extraction worker. Output ONLY valid JSON, nothing else.",
                temperature=0.2
            )
            if not raw_json:
                return
            match = re.search(r"\{.*?\}", raw_json, flags=re.DOTALL)
            if match:
                extracted = json.loads(match.group(0))
                if isinstance(extracted, dict) and extracted:
                    u_str = str(user_id)
                    rec = self.user_records.setdefault(u_str, {"name": "", "affinity": 1, "notes": {}, "topics": []})
                    user_notes = rec.setdefault("notes", {})
                    updated = False
                    for k, v in extracted.items():
                        clean_k = sanitize_memory_field(k, max_len=24).title()
                        clean_v = sanitize_memory_field(v, max_len=80)
                        if clean_k and clean_v:
                            user_notes[clean_k] = clean_v
                            updated = True

                    # Bound notes dictionary (FIFO eviction of oldest notes) to protect prompt token budget
                    while len(user_notes) > MAX_USER_NOTES:
                        oldest_key = next(iter(user_notes))
                        user_notes.pop(oldest_key, None)

                    if updated:
                        logger.info(f"Organically extracted semantic memory for user {user_id}: {user_notes}")
                        self.save_to_disk()
                        if self.collection is not None:
                            await self._sync_user_to_db(u_str, rec)
        except Exception as e:
            logger.debug(f"Semantic memory extraction skipped or failed: {e}")

    def update_user_note(self, user_id: int, key: str, value: Any):
        """Stores a persistent trait or personal note about a user with injection sanitization and size bounding."""
        u_str = str(user_id)
        if u_str not in self.user_records:
            self.user_records[u_str] = {"name": "", "affinity": 1, "notes": {}, "topics": []}

        clean_k = sanitize_memory_field(key, max_len=24).title()
        clean_v = sanitize_memory_field(value, max_len=80)
        if not clean_k or not clean_v:
            return

        notes = self.user_records[u_str].setdefault("notes", {})
        notes[clean_k] = clean_v

        # Evict oldest notes if exceeding capacity limit
        while len(notes) > MAX_USER_NOTES:
            oldest_key = next(iter(notes))
            notes.pop(oldest_key, None)

        self.save_to_disk()

        if self.collection is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._sync_user_to_db(u_str, self.user_records[u_str]))
            except Exception:
                pass

    async def get_ciel_profile(self, user_id: int) -> Dict[str, List[str]]:
        """Queries ciel_cognitive_archive in real-time for personal facts, intel, and lore."""
        u_str = str(user_id)
        results = {"personal": [], "intel": []}
        if self.collection is None:
            return results
        try:
            cursor = self.collection.find({"owner_id": u_str}).limit(20)
            async for doc in cursor:
                mtype = doc.get("memory_type", "personal")
                content = doc.get("content") or doc.get("remark") or ""
                clean_txt = sanitize_memory_field(content, max_len=120)
                if clean_txt:
                    if mtype == "personal":
                        results["personal"].append(clean_txt)
                    else:
                        results["intel"].append(clean_txt)
        except Exception as e:
            logger.debug(f"Failed fetching Ciel cognitive profile for {user_id}: {e}")
        return results

    def get_user_profile_summary(self, user_id: int, ciel_memories: Optional[Dict[str, List[str]]] = None) -> str:
        """Formats stored knowledge and shared Ciel cognitive archive into an aristocratic prompt context."""
        u_str = str(user_id)
        rec = self.user_records.get(u_str, {})

        notes = rec.get("notes", {})
        affinity = rec.get("affinity", 0)
        topics = rec.get("topics", [])
        user_name = sanitize_memory_field(rec.get('name', 'User'), max_len=32)

        lines = [f"[KNOWLEDGE OF {user_name}] (Connection Level: {affinity} interactions)"]

        # 1. Ciel's Shared Cognitive Archive (Personal facts & claims)
        if ciel_memories:
            personal = ciel_memories.get("personal", [])
            intel = ciel_memories.get("intel", [])
            if personal:
                for p in personal[:5]:
                    lines.append(f"- Known trait / lore: {sanitize_memory_field(p, 100)}")
            if intel:
                for i in intel[:3]:
                    lines.append(f"- Server record: {sanitize_memory_field(i, 100)}")

        # 2. Local / ongoing notes
        if notes:
            for k, v in list(notes.items())[:MAX_USER_NOTES]:
                lines.append(f"- {sanitize_memory_field(k, 24)}: {sanitize_memory_field(v, 80)}")
        if topics:
            clean_topics = [sanitize_memory_field(t, 24) for t in topics[:4] if t]
            if clean_topics:
                lines.append(f"- Familiar topics: {', '.join(clean_topics)}")

        return "\n".join(lines)
