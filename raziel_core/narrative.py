"""
raziel_core/narrative.py
Episodic narrative thread tracker and milestone callback system for Frielle.
Synchronizes with shared MongoDB collection 'ciel_narrative_threads'.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Raziel.Narrative")


@dataclass
class NarrativeThread:
    thread_id: str
    owner_id: str
    title: str
    summary: str
    status: str = "open"
    created_at: float = field(default_factory=time.time)
    last_mentioned: float = field(default_factory=time.time)
    last_referenced: float = 0.0
    times_referenced: int = 0
    callback_prompt: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NarrativeThread:
        return cls(
            thread_id=str(data.get("thread_id") or data.get("_id", "")),
            owner_id=str(data.get("owner_id", "")),
            title=str(data.get("title", "Untitled Thread")),
            summary=str(data.get("summary", "")),
            status=str(data.get("status", "open")),
            created_at=float(data.get("created_at", time.time())),
            last_mentioned=float(data.get("last_mentioned", time.time())),
            last_referenced=float(data.get("last_referenced", 0.0)),
            times_referenced=int(data.get("times_referenced", 0)),
            callback_prompt=str(data.get("callback_prompt", "")),
            tags=list(data.get("tags") or []),
        )


class NarrativeEngine:
    def __init__(self, db: Any = None, collection_name: str = "ciel_narrative_threads"):
        self.db = db
        self.collection_name = collection_name

    def _get_coll(self) -> Optional[Any]:
        if self.db is None:
            return None
        return getattr(self.db, self.collection_name, None) if not hasattr(self.db, "__getitem__") else self.db[self.collection_name]

    async def get_active_threads(self, owner_id: str, limit: int = 5) -> List[NarrativeThread]:
        coll = self._get_coll()
        if coll is None:
            return []
        try:
            cursor = coll.find({"owner_id": str(owner_id), "status": "open"}).sort("last_mentioned", -1).limit(limit)
            threads = []
            async for doc in cursor:
                threads.append(NarrativeThread.from_dict(doc))
            return threads
        except Exception as e:
            logger.debug(f"Failed fetching narrative threads: {e}")
            return []

    async def record_thread(self, thread: NarrativeThread) -> bool:
        coll = self._get_coll()
        if coll is None:
            return False
        try:
            doc = thread.to_dict()
            doc["_id"] = thread.thread_id
            await coll.update_one({"_id": thread.thread_id}, {"$set": doc}, upsert=True)
            return True
        except Exception as e:
            logger.debug(f"Failed recording narrative thread: {e}")
            return False
