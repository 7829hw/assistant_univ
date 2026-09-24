# -*- coding: utf-8 -*-
"""H2 arm: 집계 계약만 바꾼 prompt와, 구조화 집계를 flat factor로 내리는 경로.

측정 뒤 H2가 production이 되었다. H0 arm은 그 이전 production을 저장한 문자열에서 만든다.
"""

import difflib
import json
import os
import unittest

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_plan as AP
import aggregation_prompt
import evaluate_prompt_ab as A
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary
from tests.test_prompt_ab_harness import FakeLLM, FakeServer, make_reset

ITEM = {
    "id": "x01_p0", "question": "월 단위로 합산한 택시 수입의 평균은?",
    "expected_concepts": ["EVENT/operation:SUPPORT", "AMOUNT/revenue:MEASURE"],
    "expected_macros": ["EVENT_TO_MEASURE"], "expected_operators": ["OPERATION_METRIC"],
    "expected_tool_args": {"metric": "revenue", "bucket": "month",
                           "aggregation": "sum", "rollup": "avg"},
}
CONCEPTS = [
    {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
     "source": "implicit"},
    {"id": "revenue", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
     "source": "implicit"},
]
PLAN = {"bucket": {"unit": "month", "reducer": "sum"}, "result": {"reducer": "avg"}}

#: H2가 바꿔도 되는 줄에 들어 있는 표현. 이 밖의 줄이 바뀌면 집계 계약 밖을 건드린 것이다.
_AGGREGATION_TOKENS = ("aggregation", "bucket", "rollup", "reducer", "result", "unit",
                       "집계", "구간", "원시 값", "day", "}", "방식")


def _observe(variant, factors):
    server = FakeServer()
    content = json.dumps({"concepts": CONCEPTS, "factors": factors}, ensure_ascii=False)
    return A.observe(ITEM, arm="A", variant=A.build_variant(variant), repetition=1,
                     position=1, pair_index=0, reset=make_reset(server),
                     client=FakeLLM([content], server),
                     composer=MacroComposer(MacroLibrary.from_directory()))


class PromptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.production = A._production_prompt()
        cls.h0 = A.build_variant("H0_AGG")
        cls.h2 = A.build_variant("H2_AGG")

    def test_h0_is_the_previous_production_contract(self):
        self.assertEqual(self.h0.prompt, A._h0_prompt())
        self.assertEqual(self.h0.aggregation_contract, "flat")

    def test_h2_is_the_current_production_contract(self):
        self.assertEqual(self.h2.prompt, self.production)
        self.assertEqual(self.h2.aggregation_contract, "plan")

    def test_both_arms_share_the_repair_contract(self):
        self.assertEqual(self.h0.repair_sha256, self.h2.repair_sha256)
        self.assertEqual(self.h2.repair_templates, {})

    def test_h2_changes_only_the_aggregation_contract(self):
        changed = [line[1:] for line in difflib.unified_diff(
            self.h0.prompt.splitlines(), self.h2.prompt.splitlines(), lineterm="", n=0)
            if line[:1] in "+-" and not line.startswith(("+++", "---"))]
        self.assertTrue(changed)
        for line in changed:
            if line.strip():
                with self.subTest(line=line):
                    self.assertTrue(any(token in line for token in _AGGREGATION_TOKENS))

    def test_h2_has_a_single_aggregation_source(self):
        self.assertNotIn("rollup", self.h2.prompt)
        self.assertNotIn('"aggregation":', self.h2.prompt)
        self.assertNotIn("- bucket:", self.h2.prompt)
        self.assertIn("aggregation_plan", self.h2.prompt)
        self.assertIn(AP.UNSPECIFIED, self.h2.prompt)

    def test_every_replacement_matches_exactly_once(self):
        with self.assertRaises(ValueError):
            aggregation_prompt.h2_prompt(self.h0.prompt.replace(
                "집계가 두 단계다.", "집계는 두 단계다."))


class AdapterTest(unittest.TestCase):
    def test_h2_plan_is_lowered_into_the_expected_tool_call(self):
        record = _observe("H2_AGG", {AP.PLAN_KEY: PLAN})
        self.assertEqual(record["status"], "OK")
        self.assertEqual(record["arg_mismatches"], [])
        self.assertEqual(record["final_tool_args"]["aggregation"], "sum")
        self.assertEqual(record["final_tool_args"]["rollup"], "avg")
        self.assertEqual(record["measurement"], A.VALID)

    def test_h0_takes_the_same_flat_factors(self):
        record = _observe("H0_AGG", AP.lower_plan(PLAN))
        self.assertEqual(record["status"], "OK")
        self.assertEqual(record["arg_mismatches"], [])

    def test_h2_rejects_flat_and_duplicate_sources_and_bad_values(self):
        cases = (
            ({"bucket": "month", "rollup": "avg"}, AP.FLAT_AGGREGATION_FACTOR),
            ({AP.PLAN_KEY: PLAN, "aggregation": "sum"}, AP.DUPLICATE_AGGREGATION_SOURCE),
            ({AP.PLAN_KEY: {"result": {"reducer": "unspecified"}}}, AP.LOWERING_ERROR),
        )
        for factors, code in cases:
            with self.subTest(code=code):
                record = _observe("H2_AGG", factors)
                self.assertEqual(record["status"], code)
                self.assertFalse(record["validated"])
                self.assertIsNone(record["final_tool_args"])

    def test_h0_does_not_read_the_plan(self):
        """H0 arm에 H2 모양이 오면 제품 grounding이 모르는 factor로 거부한다."""
        record = _observe("H0_AGG", {AP.PLAN_KEY: PLAN})
        self.assertNotEqual(record["status"], "OK")


if __name__ == "__main__":
    unittest.main()
