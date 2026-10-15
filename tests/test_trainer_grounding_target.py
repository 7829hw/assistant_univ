# -*- coding: utf-8 -*-
"""trainer_common의 grounding_target 분기(결정 111, pilot_006 C6). 기본값 full은 trunk 동작 그대로."""
import hashlib
import unittest

from training.trainer_common import expected_system_prompt, grounding_target
from training.data.common import production_prompt


class GroundingTargetTest(unittest.TestCase):
    def test_default_full(self):
        self.assertEqual(grounding_target({"data": {}}), "full")
        self.assertEqual(expected_system_prompt("full"), production_prompt())

    def test_partial_prompt_is_p0_3(self):
        self.assertEqual(grounding_target({"data": {"grounding_target": "partial"}}), "partial")
        self.assertTrue(hashlib.sha256(expected_system_prompt("partial").encode()).hexdigest().startswith("8b157c9a"))

    def test_unknown_rejected(self):
        with self.assertRaises(ValueError):
            grounding_target({"data": {"grounding_target": "p0"}})


if __name__ == "__main__":
    unittest.main()
