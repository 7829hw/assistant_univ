# -*- coding: utf-8 -*-
"""모델에게 전달하는 grounding 계약과 코드가 받는·요구하는 계약이 같은가(grounding_v4).

파서가 받는 factor·값, 검증이 요구하는 짝(factor 성립 조건과 Tool 계약), 재질의가 채울 수 있는 조건,
장소 역할 값이 모두 prompt에 있어야 한다. 모델이 모르는 필수 조건을 실행 직전에 요구해 재질의를 부르는
구조를 막는다. 두 집계 계약(flat, structured) 모두 본다.
"""

import unittest

from geoflow import structured_grounding
from geoflow.factors import (
    ALTERNATIVE_COMPANIONS,
    CONTRACT_COMPANIONS,
    FACTOR_CONSTRAINTS,
    FACTOR_SPECS,
    FLAT_PROMPT_EXCLUDED,
)
from geoflow.grounding import OD_ROLES
from geoflow.planner import GeoFlowPlanner


class _Client:
    model = "parity"


def prompt(mode):
    return GeoFlowPlanner(client=_Client(), aggregation_grounding=mode).system_prompt()


def advertised_factors(mode):
    excluded = set(FLAT_PROMPT_EXCLUDED)
    if mode == structured_grounding.STRUCTURED:
        excluded |= set(structured_grounding.EXCLUDED_FACTORS)
    return sorted(set(FACTOR_SPECS) - excluded)


class ContractParityTest(unittest.TestCase):
    MODES = (structured_grounding.FLAT, structured_grounding.STRUCTURED)

    def test_every_accepted_factor_and_value_is_in_the_prompt(self):
        for mode in self.MODES:
            text = prompt(mode)
            for name in advertised_factors(mode):
                with self.subTest(mode=mode, factor=name):
                    self.assertIn(f"- {name}:", text)
                    for value in FACTOR_SPECS[name].values:
                        self.assertIn(value, text)

    def test_flat_prompt_hides_nothing_the_parser_accepts(self):
        self.assertEqual(FLAT_PROMPT_EXCLUDED, frozenset())

    def test_every_enforced_companion_is_stated(self):
        """검증이 요구하는 짝(factor 성립 조건 + Tool 계약 짝)이 prompt의 [짝을 이루는 factor]에 있다."""
        for mode in self.MODES:
            text = prompt(mode)
            names = set(advertised_factors(mode))
            section = text[text.rindex("[짝을 이루는 factor]"):]
            for factor, constraint in FACTOR_CONSTRAINTS.items():
                if factor not in names or not set(constraint.requires) <= names:
                    continue
                with self.subTest(mode=mode, factor=factor):
                    self.assertIn(f"- {factor}를 넣으면", section)
            for factor, (requires, _) in CONTRACT_COMPANIONS.items():
                with self.subTest(mode=mode, contract=factor):
                    self.assertIn(f"- {factor}를 넣으면 {', '.join(requires)}", section)
            if mode == structured_grounding.FLAT:
                for factor, alternatives in ALTERNATIVE_COMPANIONS.items():
                    self.assertIn(f"- {factor}를 넣으면 {' 또는 '.join(alternatives)}", section)

    def test_repair_can_only_fill_what_the_prompt_describes(self):
        """factor 재질의가 채우는 조건은 모두 prompt에 안내된 factor다."""
        names = set(advertised_factors(structured_grounding.FLAT))
        fillable = {name for constraint in FACTOR_CONSTRAINTS.values() for name in constraint.requires}
        fillable |= {name for requires, _ in CONTRACT_COMPANIONS.values() for name in requires}
        fillable |= {name for group in ALTERNATIVE_COMPANIONS.values() for name in group}
        self.assertLessEqual(fillable, names)

    def test_every_place_role_is_in_the_prompt(self):
        for mode in self.MODES:
            text = prompt(mode)
            for role in OD_ROLES:
                with self.subTest(mode=mode, role=role):
                    self.assertIn(f'"{role}"', text)

    def test_both_contracts_can_state_the_answer_target(self):
        """값(최댓값)과 그 값을 가진 구간, 구간 안 집계 없음을 두 계약 모두 적을 수 있다."""
        flat, structured = prompt("flat"), prompt("structured")
        self.assertIn("- select:", flat)
        for word in ('"select"', "unspecified", "result"):
            self.assertIn(word, structured)


if __name__ == "__main__":
    unittest.main()
