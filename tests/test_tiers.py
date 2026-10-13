"""
tests/test_tiers.py
Unit tests for Raziel's Tier Resolution, Personality Matrix, and Memory Subsystem.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from raziel_core.tiers import TierManager
from raziel_core.personality import detect_mode, TIER_DEMEANORS
from raziel_core.memory import MemoryManager


class MockUser:
    def __init__(self, uid: int, name: str, roles: list = None, premium_since=None):
        self.id = uid
        self.name = name
        self.display_name = name
        self.roles = roles or []
        self.premium_since = premium_since


class MockRole:
    def __init__(self, rid: int, name: str):
        self.id = rid
        self.name = name


class TestRazielTiers(unittest.TestCase):

    def setUp(self):
        self.tier_manager = TierManager()

    def test_sovereign_resolution_by_id(self):
        user = MockUser(575745179202355211, "tenkariel")
        tier, label, badge = self.tier_manager.resolve_tier(user)
        self.assertEqual(tier, "sovereign")
        self.assertIn("Sovereign", label)
        self.assertEqual(badge, "[SOVEREIGN]")

    def test_sovereign_resolution_by_username(self):
        user = MockUser(999999999, "tenkariel.")
        tier, label, badge = self.tier_manager.resolve_tier(user)
        self.assertEqual(tier, "sovereign")

    def test_first_lady_resolution(self):
        user = MockUser(1222412496141553817, "mae")
        tier, label, badge = self.tier_manager.resolve_tier(user)
        self.assertEqual(tier, "first_lady")
        self.assertIn("First Lady", label)
        self.assertEqual(badge, "[FIRST LADY]")

    def test_sister_resolution(self):
        user = MockUser(1079366737889329245, "flutter")
        tier, label, badge = self.tier_manager.resolve_tier(user)
        self.assertEqual(tier, "sister")
        self.assertIn("Sister", label)
        self.assertEqual(badge, "[CREATOR'S SISTER]")

    def test_duchess_resolution(self):
        user = MockUser(888888888, "marshybel_")
        tier, label, badge = self.tier_manager.resolve_tier(user)
        self.assertEqual(tier, "duchess")
        self.assertIn("Duchess", label)
        self.assertEqual(badge, "[ESTEEMED DUCHESS]")

    def test_respected_resolution_by_username(self):
        user = MockUser(777777777, "caffeine_1ncarnate")
        tier, label, badge = self.tier_manager.resolve_tier(user)
        self.assertEqual(tier, "respected")
        self.assertEqual(badge, "[VALUED PATRON]")

    def test_respected_resolution_by_role(self):
        role = MockRole(1493694343154892891, "Respected")
        user = MockUser(666666666, "someone_cool", roles=[role])
        tier, label, badge = self.tier_manager.resolve_tier(user)
        self.assertEqual(tier, "respected")

    def test_respected_resolution_by_nitro_booster(self):
        user = MockUser(555555555, "random_booster", premium_since="2026-01-01")
        tier, label, badge = self.tier_manager.resolve_tier(user)
        self.assertEqual(tier, "respected")

    def test_general_resolution(self):
        user = MockUser(111111111, "sanctuary_guest")
        tier, label, badge = self.tier_manager.resolve_tier(user)
        self.assertEqual(tier, "general")
        self.assertIn("Traveler", label)
        self.assertEqual(badge, "[SANCTUARY TRAVELER]")

    def test_sovereign_prompt_no_master_glazing(self):
        mode, instruction = detect_mode("Hey Raziel, how are things?", user_tier="sovereign")
        self.assertEqual(mode, "public_banter")
        # Ensure 'NEVER call him 'Master'' rule is enforced
        self.assertIn("NEVER call him 'Master'", instruction)
        self.assertIn("camaraderie", instruction.lower())

    def test_general_prompt_is_humane_and_charming(self):
        mode, instruction = detect_mode("Hey Raziel, look at this sketch!", user_tier="general")
        self.assertEqual(mode, "public_banter")
        self.assertIn("HUMANE, CHARMING, AND WELCOMING", instruction)
        self.assertIn("For the girls", instruction)
        self.assertIn("For the boys", instruction)

    def test_safe_harbor_mode_trigger(self):
        mode, instruction = detect_mode("I am so burned out and exhausted today...", user_tier="general")
        self.assertEqual(mode, "safe_harbor")
        self.assertIn("SAFE HARBOR - ACTIVE", instruction)

    def test_ciel_interplay_trigger(self):
        mode, instruction = detect_mode("Silence, mortal!", is_ciel_context=True)
        self.assertEqual(mode, "ciel_interplay")
        self.assertIn("CIEL SIBLING INTERPLAY", instruction)


if __name__ == "__main__":
    unittest.main()
