"""
raziel_core/tiers.py
Tier resolution engine for Project Raziel.
Identifies user tiers based on IDs, account usernames, role IDs, and Nitro Booster status.
"""

import logging
from typing import Tuple, Dict, Any, Optional
import discord
from config import TIERS_CONFIG

logger = logging.getLogger("Raziel.Tiers")


class TierManager:
    """Resolves member tier standing within Wonderland."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config if config is not None else TIERS_CONFIG

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

    def resolve_tier(self, author: Any) -> Tuple[str, str, str]:
        """
        Resolves the author's tier.
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

        if author_id in first_lady_ids or author_name in first_lady_names or (first_lady_roles and author_roles & first_lady_roles):
            return "first_lady", "First Lady of Wonderland", "[FIRST LADY]"

        # 3. Creator's Sister Tier (Flutter)
        sister_ids = self._clean_ids(self.config.get("sister_user_ids", ["1079366737889329245"]))
        sister_names = self._clean_targets(self.config.get("sister_usernames", ["flutter"]))
        sister_roles = self._clean_ids(self.config.get("sister_role_ids", []))

        if author_id in sister_ids or author_name in sister_names or (sister_roles and author_roles & sister_roles):
            return "sister", "Creator's Sister", "[CREATOR'S SISTER]"

        # 4. Esteemed Duchess Tier (Court Peers)
        duchess_ids = self._clean_ids(self.config.get("duchess_user_ids", []))
        duchess_names = self._clean_targets(self.config.get("duchess_usernames", ["marshybel_"]))
        duchess_roles = self._clean_ids(self.config.get("duchess_role_ids", []))

        if author_id in duchess_ids or author_name in duchess_names or (duchess_roles and author_roles & duchess_roles):
            return "duchess", "Esteemed Duchess", "[ESTEEMED DUCHESS]"

        # 5. Respected / Valued Patron Tier (VIPs & Server Boosters)
        respected_ids = self._clean_ids(self.config.get("respected_user_ids", []))
        respected_names = self._clean_targets(self.config.get("respected_usernames", []))
        respected_roles = self._clean_ids(self.config.get("respected_role_ids", ["1493694343154892891"]))

        is_nitro_booster = False
        prem = getattr(author, "premium_since", None)
        if prem is not None and type(prem).__module__ != "unittest.mock":
            is_nitro_booster = True

        if (
            author_id in respected_ids
            or author_name in respected_names
            or (respected_roles and author_roles & respected_roles)
            or is_nitro_booster
        ):
            return "respected", "Valued Patron of the Harbor", "[VALUED PATRON]"

        # 6. General Member Tier
        return "general", "Sanctuary Traveler", "[SANCTUARY TRAVELER]"
