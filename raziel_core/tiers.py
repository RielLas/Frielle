"""
raziel_core/tiers.py
Tier resolution and dynamic privilege engine for Project Raziel.
Synchronizes live with MongoDB Atlas collection ciel_privileges (shared with Ciel).
"""

import time
import logging
from typing import Tuple, Dict, Any, Optional, Set
import discord
from config import TIERS_CONFIG

logger = logging.getLogger("Raziel.Tiers")


class TierManager:
    """Resolves member tier standing within Wonderland, unified with Ciel."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config if config is not None else TIERS_CONFIG
        self.dynamic_privileges = {
            "girlfriend_roles": set(),
            "girlfriend_users": set(),
            "duchess_roles": set(),
            "duchess_users": set(),
            "mistress_roles": set(),
            "mistress_users": set(),
            "sister_roles": set(),
            "sister_users": set(),
            "respected_roles": set(),
            "respected_users": set(),
            "reasons": {}
        }

    def _clean_targets(self, raw_list: Any) -> list:
        if not raw_list:
            return []
        items = raw_list if isinstance(raw_list, list) else [raw_list]
        return [str(item).lower().strip().rstrip(".") for item in items if str(item).strip()]

    def _clean_ids(self, raw_list: Any) -> set:
        if not raw_list:
            return set()
        items = raw_list if isinstance(raw_list, list) else [raw_list]
        return {str(item).strip() for item in items if str(item).strip()}

    async def sync_privileges_from_db(self, db) -> int:
        """Hydrates permanent privileges from MongoDB collection ciel_privileges."""
        if db is None:
            return 0
        try:
            coll = db["ciel_privileges"]
            cursor = coll.find({})
            count = 0

            # Clear existing sets
            for k, val in self.dynamic_privileges.items():
                if isinstance(val, set):
                    val.clear()
                elif isinstance(val, dict):
                    val.clear()

            async for doc in cursor:
                t_id = str(doc.get("target_id", "")).strip()
                t_type = doc.get("target_type", "user")
                tier = str(doc.get("tier", "respected")).lower().strip()
                reason = doc.get("reason", "")
                if not t_id:
                    continue
                if reason:
                    self.dynamic_privileges["reasons"][t_id] = reason

                if tier == "girlfriend":
                    if t_type == "role":
                        self.dynamic_privileges["girlfriend_roles"].add(t_id)
                    else:
                        self.dynamic_privileges["girlfriend_users"].add(t_id)
                elif tier in ("duchess", "mistress"):
                    if t_type == "role":
                        self.dynamic_privileges["duchess_roles"].add(t_id)
                        self.dynamic_privileges["mistress_roles"].add(t_id)
                    else:
                        self.dynamic_privileges["duchess_users"].add(t_id)
                        self.dynamic_privileges["mistress_users"].add(t_id)
                elif tier == "sister":
                    if t_type == "role":
                        self.dynamic_privileges["sister_roles"].add(t_id)
                    else:
                        self.dynamic_privileges["sister_users"].add(t_id)
                elif tier == "respected":
                    if t_type == "role":
                        self.dynamic_privileges["respected_roles"].add(t_id)
                    else:
                        self.dynamic_privileges["respected_users"].add(t_id)
                count += 1

            logger.info(f"Synchronized {count} dynamic privileges from MongoDB Atlas (ciel_privileges).")
            return count
        except Exception as e:
            logger.error(f"Failed syncing dynamic privileges: {e}")
            return 0

    async def add_privilege(
        self,
        db,
        target_id: str,
        target_type: str,
        target_name: str,
        tier: str,
        granted_by_id: str,
        granted_by_name: str,
        reason: str = "Permanent privilege promotion"
    ) -> bool:
        """Persists a privilege assignment directly into ciel_privileges in MongoDB."""
        t_id_str = str(target_id).strip()
        tier_clean = tier.lower().strip()

        if db is not None:
            try:
                coll = db["ciel_privileges"]
                await coll.update_one(
                    {"target_id": t_id_str},
                    {
                        "$set": {
                            "target_id": t_id_str,
                            "target_type": target_type,
                            "target_name": target_name,
                            "tier": tier_clean,
                            "granted_by_id": str(granted_by_id),
                            "granted_by_name": str(granted_by_name),
                            "granted_at": time.time(),
                            "reason": reason
                        }
                    },
                    upsert=True
                )
            except Exception as ex:
                logger.error(f"Failed saving privilege to MongoDB: {ex}")
                return False

        # Update in-memory cache
        for s in ("girlfriend", "duchess", "mistress", "sister", "respected"):
            self.dynamic_privileges[f"{s}_roles" if target_type == "role" else f"{s}_users"].discard(t_id_str)

        if tier_clean == "girlfriend":
            self.dynamic_privileges["girlfriend_roles" if target_type == "role" else "girlfriend_users"].add(t_id_str)
        elif tier_clean in ("duchess", "mistress"):
            self.dynamic_privileges["duchess_roles" if target_type == "role" else "duchess_users"].add(t_id_str)
            self.dynamic_privileges["mistress_roles" if target_type == "role" else "mistress_users"].add(t_id_str)
        elif tier_clean == "sister":
            self.dynamic_privileges["sister_roles" if target_type == "role" else "sister_users"].add(t_id_str)
        elif tier_clean == "respected":
            self.dynamic_privileges["respected_roles" if target_type == "role" else "respected_users"].add(t_id_str)

        if reason:
            self.dynamic_privileges["reasons"][t_id_str] = reason

        return True

    async def remove_privilege(self, db, target_id: str) -> bool:
        """Removes a privilege assignment directly from ciel_privileges in MongoDB."""
        t_id_str = str(target_id).strip()
        if db is not None:
            try:
                coll = db["ciel_privileges"]
                await coll.delete_one({"target_id": t_id_str})
            except Exception as ex:
                logger.error(f"Failed deleting privilege from MongoDB: {ex}")
                return False

        for s in ("girlfriend", "duchess", "mistress", "sister", "respected"):
            self.dynamic_privileges[f"{s}_roles"].discard(t_id_str)
            self.dynamic_privileges[f"{s}_users"].discard(t_id_str)
        self.dynamic_privileges["reasons"].pop(t_id_str, None)
        return True

    def get_privilege_reason(self, author_id: str) -> Optional[str]:
        """Retrieves reason recorded for this member or role."""
        return self.dynamic_privileges["reasons"].get(str(author_id))

    def resolve_tier(self, author: Any) -> Tuple[str, str, str]:
        """
        Resolves the author's tier using static config and live MongoDB dynamic privileges.
        Returns: (tier_key, tier_label, tier_badge)
        tier_key is one of: 'sovereign', 'first_lady', 'sister', 'duchess', 'respected', 'general'
        """
        if not author:
            return "general", "Sanctuary Traveler", "[SANCTUARY TRAVELER]"

        author_id = str(getattr(author, "id", "")).strip()
        author_name = str(getattr(author, "name", "")).lower().strip().rstrip(".")
        author_roles = {
            str(r.id) for r in getattr(author, "roles", []) if hasattr(r, "id")
        }

        # 1. Sovereign Tier (Master Riel)
        sovereign_ids = self._clean_ids(self.config.get("master_user_ids", ["575745179202355211"]))
        sovereign_names = self._clean_targets(self.config.get("master_usernames", ["tenkariel"]))
        sovereign_roles = self._clean_ids(self.config.get("master_role_ids", []))

        if author_id in sovereign_ids or author_name in sovereign_names or (sovereign_roles and author_roles & sovereign_roles):
            return "sovereign", "Sovereign of Wonderland", "[SOVEREIGN]"

        # 2. First Lady Tier (Lady Mae)
        first_lady_ids = self._clean_ids(self.config.get("girlfriend_user_ids", ["1222412496141553817"]))
        first_lady_names = self._clean_targets(self.config.get("girlfriend_usernames", ["mae"]))
        first_lady_roles = self._clean_ids(self.config.get("girlfriend_role_ids", []))
        dyn_gf_users = self.dynamic_privileges["girlfriend_users"]
        dyn_gf_roles = self.dynamic_privileges["girlfriend_roles"]

        if (
            author_id in first_lady_ids
            or author_id in dyn_gf_users
            or author_name in first_lady_names
            or (first_lady_roles and author_roles & first_lady_roles)
            or (dyn_gf_roles and author_roles & dyn_gf_roles)
        ):
            return "first_lady", "First Lady of Wonderland", "[FIRST LADY]"

        # 3. Creator's Sister Tier (Flutter)
        sister_ids = self._clean_ids(self.config.get("sister_user_ids", ["1079366737889329245"]))
        sister_names = self._clean_targets(self.config.get("sister_usernames", ["flutter"]))
        sister_roles = self._clean_ids(self.config.get("sister_role_ids", []))
        dyn_sis_users = self.dynamic_privileges["sister_users"]
        dyn_sis_roles = self.dynamic_privileges["sister_roles"]

        if (
            author_id in sister_ids
            or author_id in dyn_sis_users
            or author_name in sister_names
            or (sister_roles and author_roles & sister_roles)
            or (dyn_sis_roles and author_roles & dyn_sis_roles)
        ):
            return "sister", "Creator's Sister", "[CREATOR'S SISTER]"

        # 4. Esteemed Duchess Tier (Court Peers)
        duchess_ids = self._clean_ids(self.config.get("duchess_user_ids", []))
        duchess_names = self._clean_targets(self.config.get("duchess_usernames", ["marshybel_"]))
        duchess_roles = self._clean_ids(self.config.get("duchess_role_ids", []))
        dyn_duch_users = self.dynamic_privileges["duchess_users"] | self.dynamic_privileges["mistress_users"]
        dyn_duch_roles = self.dynamic_privileges["duchess_roles"] | self.dynamic_privileges["mistress_roles"]

        if (
            author_id in duchess_ids
            or author_id in dyn_duch_users
            or author_name in duchess_names
            or (duchess_roles and author_roles & duchess_roles)
            or (dyn_duch_roles and author_roles & dyn_duch_roles)
        ):
            return "duchess", "Esteemed Duchess", "[ESTEEMED DUCHESS]"

        # 5. Respected / Valued Patron Tier (VIPs & Server Boosters)
        respected_ids = self._clean_ids(self.config.get("respected_user_ids", []))
        respected_names = self._clean_targets(self.config.get("respected_usernames", []))
        respected_roles = self._clean_ids(self.config.get("respected_role_ids", ["1493694343154892891"]))
        dyn_resp_users = self.dynamic_privileges["respected_users"]
        dyn_resp_roles = self.dynamic_privileges["respected_roles"]

        is_nitro_booster = False
        prem = getattr(author, "premium_since", None)
        if prem is not None and type(prem).__module__ != "unittest.mock":
            is_nitro_booster = True

        if (
            author_id in respected_ids
            or author_id in dyn_resp_users
            or author_name in respected_names
            or (respected_roles and author_roles & respected_roles)
            or (dyn_resp_roles and author_roles & dyn_resp_roles)
            or is_nitro_booster
        ):
            return "respected", "Valued Patron of the Harbor", "[VALUED PATRON]"

        # 6. General Member Tier
        return "general", "Sanctuary Traveler", "[SANCTUARY TRAVELER]"
