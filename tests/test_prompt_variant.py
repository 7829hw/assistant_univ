# -*- coding: utf-8 -*-
"""측정용 prompt 변형이 제품 Planner를 건드리지 않는지 확인한다.

이전 측정에서 harness가 제품과 다른 prompt를 "D"라고 부른 적이 있다. 그때는
factor 의미 절의 한 문단이 짧아진 상태였고, 그 문단이 바로 측정 대상이었다.
길이만 비교해서는 알아채기 어려우므로 여기서는 hash로 못박는다.
"""

import hashlib
import unittest

import evaluate_planner
from geoflow.planner import GeoFlowPlanner


class _Client:
    model = "test"


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PromptVariantTest(unittest.TestCase):
    def setUp(self):
        self.production = GeoFlowPlanner(client=_Client()).system_prompt()

    def test_variant_d_is_byte_identical_to_production(self):
        prompt = evaluate_planner.make_variant_planner("D", _Client()).system_prompt()
        self.assertEqual(_digest(prompt), _digest(self.production))
        self.assertEqual(len(prompt.encode("utf-8")),
                         len(self.production.encode("utf-8")))

    def test_variant_c_drops_only_the_semantics_section(self):
        prompt = evaluate_planner.make_variant_planner("C", _Client()).system_prompt()
        self.assertNotIn("[조건이 뜻하는 것]", prompt)
        # 들어낸 것은 그 절뿐이어야 한다. 앞뒤 절은 그대로 남는다.
        self.assertIn("[사용 가능한 factor]", prompt)
        self.assertIn("[짝을 이루는 factor]", prompt)
        self.assertLess(len(prompt), len(self.production))

    def test_unknown_variant_is_rejected(self):
        planner = evaluate_planner.make_variant_planner("D", _Client())
        planner.variant = "Z"
        with self.assertRaises(ValueError):
            planner.system_prompt()

    def test_production_planner_has_no_variant_knob(self):
        """제품 Planner에는 변형 선택이 없어야 한다."""
        planner = GeoFlowPlanner(client=_Client())
        self.assertFalse(hasattr(planner, "variant"))

    def test_building_a_variant_does_not_change_production_prompt(self):
        for variant in ("C", "D"):
            evaluate_planner.make_variant_planner(variant, _Client()).system_prompt()
        after = GeoFlowPlanner(client=_Client()).system_prompt()
        self.assertEqual(_digest(after), _digest(self.production))


if __name__ == "__main__":
    unittest.main()
