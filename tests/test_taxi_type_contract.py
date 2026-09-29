# -*- coding: utf-8 -*-
"""택시 유형은 factor이고 개념 node가 아니라는 계약을 못박는다.

모델이 "개인택시/법인택시"를 OBJECT/private 같은 개념으로 적는 실패는 prompt
문구와 무관하게 나온다. 어느 core concept에 붙이든 grounding에서 즉시 거부되어
합성 단계까지 조용히 흘러가지 않아야 한다.

prompt에 이 구분을 길게 적는 것은 도움이 되지 않았다. 모델 상태를 비운
paraphrase 측정에서, 틀린 형태를 보여 준 문구는 오히려 그 형태를 만들게 했고
긍정문으로 바꾼 문구도 새 intent에서는 짧은 정의를 넘지 못했다.
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

QUESTION = "법인택시의 평균 수입은?"

#: 측정값까지 갖춘 최소 grounding. 여기에 잘못된 개념 하나만 얹어 본다.
BASE_CONCEPTS = [
    {"id": "op", "concept": "EVENT", "subtype": "operation",
     "role": "SUPPORT", "source": "implicit"},
    {"id": "h", "concept": "AMOUNT", "subtype": "revenue",
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
            "개인택시의 평균 수입은?",
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


class TaxiTypeAsConceptTest(unittest.TestCase):
    """factor를 개념으로 적은 형태는 개념으로 합성 단계에 가지 않는다.

    2026-09-29 개정: 값이 조건 enum으로 정해지는 형태(OBJECT/corporate, <concept>/taxi_type +
    value corporate)는 거부하지 않고 factor로 옮긴다(``grounding.hoist_condition_concepts``, 기록
    ``normalizations``). 근거: 업체 100문항 실측에서 이 형태가 질문의 조건을 온전히 담은 채
    거부되었다(014, 043, 100). 조건을 잃지 않으므로 "조용히 흘러가는" 것이 아니다. 값이 없거나
    다른 값과 충돌하면 이전처럼 INVALID_SUBTYPE으로 거부한다.
    """

    CASES = (
        ("OBJECT", "taxi_type"),
        ("OBJECT", "private"),
        ("OBJECT", "corporate"),
        ("LOCATION", "taxi_type"),
        ("FIELD", "taxi_type"),
        ("EVENT", "taxi_type"),
    )

    def concept(self, concept, subtype, value="corporate"):
        return {"id": "t", "concept": concept, "subtype": subtype, "role": "COND",
                "source": "user", **({"value": value} if value is not None else {})}

    def test_recoverable_forms_become_the_factor(self):
        composer = MacroComposer(MacroLibrary.from_directory())
        for concept, subtype in self.CASES:
            with self.subTest(concept=concept, subtype=subtype):
                grounding = parse_grounding(payload(self.concept(concept, subtype)), QUESTION)
                expected = subtype if subtype in ("private", "corporate") else "corporate"
                self.assertEqual(grounding.factors["taxi_type"], expected)
                self.assertTrue(all(c.id != "t" for c in grounding.concepts))
                self.assertEqual(grounding.normalizations[0]["rule"],
                                 "condition_concept_to_factor")
                plan = composer.compose(grounding)
                self.assertEqual(plan.transformations[-1].params["taxi_type"], expected)

    def test_unrecoverable_or_conflicting_forms_are_rejected(self):
        cases = (
            (self.concept("OBJECT", "taxi_type", value=None), {}),       # 값이 어디에도 없음
            (self.concept("OBJECT", "private"), {"taxi_type": "corporate"}),  # 충돌
            (self.concept("OBJECT", "taxi_type", value="회사"), {}),     # enum 밖의 값
        )
        for extra, factors in cases:
            with self.subTest(extra=extra, factors=factors):
                with self.assertRaises(PlannerError) as caught:
                    parse_grounding(payload(extra, factors), QUESTION)
                self.assertEqual(caught.exception.code, "INVALID_SUBTYPE")
                # 원인을 바로 알 수 있어야 한다. 어느 concept이 문제인지와
                # 그 concept에 무엇을 붙일 수 있는지가 메시지에 있어야 한다.
                self.assertIn(extra["concept"], caught.exception.detail)
                self.assertIn(extra["subtype"], caught.exception.detail)

    def test_rejected_forms_are_not_opened_up_for_planning_repair(self):
        """개념을 조건으로 옮기는 것은 값 수정이 아니라 구조 변경이다. 재질의로 하지 않는다."""
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(payload(self.concept("OBJECT", "taxi_type", value=None)), QUESTION)
        self.assertFalse(decide(caught.exception).repairable)


class TaxiTypePromptTest(unittest.TestCase):
    """Prompt의 설명은 factor 정의에서 나오고, 만들면 안 되는 형태를 보여 주지 않는다."""

    def setUp(self):
        from geoflow.planner import GeoFlowPlanner

        class _Client:
            model = "test"

        self.prompt = GeoFlowPlanner(client=_Client()).system_prompt()

    def test_prompt_does_not_show_the_forms_it_must_not_produce(self):
        """틀린 출력을 예시로 적으면 모델이 바로 그 형태를 만든다.

        0ccabc3의 "(OBJECT/corporate, OBJECT/taxi_type으로 적지 않는다)"가 그랬다.
        그 한 조각만 뺀 변형에서 b24가 회복됐다.
        """
        for form in ("OBJECT/corporate", "OBJECT/private", "OBJECT/taxi_type"):
            self.assertNotIn(form, self.prompt)

    def test_prompt_keeps_the_value_mapping(self):
        """개인/법인을 어떤 값으로 적는지는 기본 prompt의 해석 규칙이 알려 준다."""
        self.assertIn("개인=private", self.prompt)
        self.assertIn("corporate", self.prompt)
        self.assertEqual(FACTOR_SPECS["taxi_type"].meaning, "택시 유형 조건.")

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
