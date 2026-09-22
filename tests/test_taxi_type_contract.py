# -*- coding: utf-8 -*-
"""택시 유형이 개념이 아니라 조건이라는 계약을 못박는다.

paired A/B 측정에서 전체 실패 30건 중 18건이 "개인택시/법인택시"를 factor가
아니라 concept node로 만든 것이었다. 어느 core concept에 붙이든 즉시 거부되어
합성 단계까지 조용히 흘러가지 않아야 한다.
"""

import dataclasses
import os
import pathlib
import unittest

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from geoflow.composer import MacroComposer
from geoflow.errors import PlannerError
from geoflow.factors import FACTOR_SPECS
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from geoflow.operator_registry import OPERATORS, get_operator
from geoflow.repair import decide
from geoflow.types import CONCEPT_SUBTYPES, CoreConcept

QUESTION = "법인택시의 평균 운행시간은?"

#: 측정값까지 갖춘 최소 grounding. 여기에 잘못된 개념 하나만 얹어 본다.
BASE_CONCEPTS = [
    {"id": "op", "concept": "EVENT", "subtype": "operation",
     "role": "SUPPORT", "source": "implicit"},
    {"id": "h", "concept": "AMOUNT", "subtype": "hours",
     "role": "MEASURE", "source": "implicit"},
]


def payload(extra=None, factors=None):
    concepts = list(BASE_CONCEPTS)
    if extra is not None:
        concepts = [extra] + concepts
    return {"concepts": concepts, "factors": dict(factors or {})}


class TaxiTypeVocabularyTest(unittest.TestCase):
    def test_allowed_values_come_from_the_factor_source(self):
        self.assertEqual(
            sorted(FACTOR_SPECS["taxi_type"].values),
            ["all", "corporate", "private"],
        )

    def test_every_operator_taking_taxi_type_agrees_on_the_values(self):
        """값 범위는 operator마다 따로 적히므로 어긋나지 않는지 확인한다."""
        taking = [get_operator(name) for name in OPERATORS
                  if "taxi_type" in get_operator(name).params]
        self.assertTrue(taking)
        for spec in taking:
            with self.subTest(operator=spec.name):
                self.assertEqual(
                    sorted(spec.param_enums["taxi_type"]),
                    sorted(FACTOR_SPECS["taxi_type"].values),
                )

    def test_object_has_no_usable_subtype(self):
        """OBJECT에 붙일 수 있는 TIMS subtype은 없다."""
        self.assertEqual(CONCEPT_SUBTYPES[CoreConcept.OBJECT], frozenset())


class TaxiTypeAsFactorTest(unittest.TestCase):
    def test_corporate_is_accepted_as_a_factor(self):
        grounding = parse_grounding(
            payload(factors={"taxi_type": "corporate"}), QUESTION,
        )
        self.assertEqual(grounding.factors["taxi_type"], "corporate")
        self.assertNotIn(
            "taxi_type", [item.subtype for item in grounding.concepts],
        )

    def test_private_reaches_the_tool_argument(self):
        """조건으로 적으면 그대로 Tool 인자가 된다."""
        grounding = parse_grounding(
            payload(factors={"taxi_type": "private", "aggregation": "avg"}),
            "개인택시의 평균 운행시간은?",
        )
        plan = MacroComposer(MacroLibrary.from_directory()).compose(grounding)
        params = plan.transformations[-1].params
        self.assertEqual(params["taxi_type"], "private")

    def test_value_outside_the_enum_is_rejected(self):
        for value in ("개인", "personal", "taxi_type"):
            with self.subTest(value=value):
                with self.assertRaises(PlannerError) as caught:
                    parse_grounding(payload(factors={"taxi_type": value}),
                                    QUESTION)
                self.assertEqual(caught.exception.code, "INVALID_FACTOR")


class TaxiTypeAsConceptIsRejectedTest(unittest.TestCase):
    """factor를 개념으로 적은 형태는 전부 grounding 단계에서 막는다."""

    CASES = (
        ("OBJECT", "taxi_type"),
        ("OBJECT", "private"),
        ("OBJECT", "corporate"),
        ("LOCATION", "taxi_type"),
        ("FIELD", "taxi_type"),
        ("EVENT", "taxi_type"),
    )

    def test_rejected_at_grounding_with_invalid_subtype(self):
        for concept, subtype in self.CASES:
            with self.subTest(concept=concept, subtype=subtype):
                with self.assertRaises(PlannerError) as caught:
                    parse_grounding(
                        payload({"id": "t", "concept": concept,
                                 "subtype": subtype, "role": "COND",
                                 "source": "user", "value": "corporate"}),
                        QUESTION,
                    )
                self.assertEqual(caught.exception.code, "INVALID_SUBTYPE")
                # 원인을 바로 알 수 있어야 한다. 어느 concept이 문제인지와
                # 그 concept에 무엇을 붙일 수 있는지가 메시지에 있어야 한다.
                self.assertIn(concept, caught.exception.detail)
                self.assertIn(subtype, caught.exception.detail)

    def test_never_reaches_composition(self):
        """잘못된 개념이 조용히 macro로 흘러가지 않는다."""
        composer = MacroComposer(MacroLibrary.from_directory())
        for concept, subtype in self.CASES:
            with self.subTest(concept=concept, subtype=subtype):
                with self.assertRaises(PlannerError):
                    grounding = parse_grounding(
                        payload({"id": "t", "concept": concept,
                                 "subtype": subtype, "role": "COND",
                                 "source": "user", "value": "corporate"}),
                        QUESTION,
                    )
                    composer.compose(grounding)

    def test_is_not_opened_up_for_planning_repair(self):
        """개념을 조건으로 옮기는 것은 값 수정이 아니라 구조 변경이다."""
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(
                payload({"id": "t", "concept": "OBJECT",
                         "subtype": "corporate", "role": "COND",
                         "source": "user", "value": "corporate"}),
                QUESTION,
            )
        self.assertFalse(decide(caught.exception).repairable)


class TaxiTypePromptTest(unittest.TestCase):
    """Prompt의 설명은 factor 정의에서 나와야 한다."""

    def setUp(self):
        from geoflow.planner import GeoFlowPlanner

        class _Client:
            model = "test"

        self.prompt = GeoFlowPlanner(client=_Client()).system_prompt()

    def test_prompt_states_that_taxi_type_is_a_condition_not_a_concept(self):
        self.assertIn("개념이 아니다", self.prompt)
        self.assertIn("개인택시", self.prompt)
        self.assertIn("법인택시", self.prompt)
        self.assertIn("OBJECT/corporate", self.prompt)

    def test_prompt_text_comes_from_the_factor_definition(self):
        """설명을 바꾸면 prompt도 따라 바뀐다. 손으로 옮겨 적지 않았다는 뜻이다."""
        from geoflow.planner import GeoFlowPlanner

        class _Client:
            model = "test"

        original = FACTOR_SPECS["taxi_type"]
        marker = "표식-XYZ"
        FACTOR_SPECS["taxi_type"] = dataclasses.replace(original, meaning=marker)
        try:
            changed = GeoFlowPlanner(client=_Client()).system_prompt()
        finally:
            FACTOR_SPECS["taxi_type"] = original
        self.assertIn(marker, changed)
        self.assertNotIn(original.meaning, changed)

    def test_prompt_yaml_does_not_duplicate_the_factor_semantics(self):
        """같은 설명을 YAML에도 적어 두면 어휘가 바뀔 때 조용히 어긋난다."""
        text = pathlib.Path("prompts/geoflow_planner.yaml").read_text(
            encoding="utf-8",
        )
        self.assertNotIn("개념이 아니다", text)
        self.assertNotIn("OBJECT/corporate", text)


if __name__ == "__main__":
    unittest.main()
