# -*- coding: utf-8 -*-
"""계획 단계 재질의의 판정·범위·횟수 테스트.

여기서 지키는 것은 "실패를 최대한 성공으로 바꾼다"가 아니다. 다시 물어서
복구할 수 있는 실패와, 물어봐야 없는 관계를 꾸며 내게 만들 뿐인 실패를
가르는 것이다.
"""

import json
import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from build import build  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_handlers import get_tool_handlers  # noqa: E402

from geoflow.composer import MacroComposer  # noqa: E402
from geoflow.errors import CompositionError, GeoFlowError, PlannerError  # noqa: E402
from geoflow.grounding import parse_grounding  # noqa: E402
from geoflow.pipeline import (  # noqa: E402
    MAX_REPAIR_ATTEMPTS,
    STATUS_PLANNING_FAILED,
    GeoFlowPipeline,
    Stage,
)
from geoflow.planner import GeoFlowPlanner  # noqa: E402
from geoflow.repair import (  # noqa: E402
    RepairKind,
    RepairViolation,
    decide,
    registry_qualifiers,
    validate_repair_delta,
)

TOOLS, _PROMPT = build()


# -- fixture ----------------------------------------------------------------


def place(node_id, name, od_role=None):
    concept = {
        "id": node_id, "concept": "LOCATION", "subtype": "place",
        "role": "SUBCOND", "source": "user",
        "value": {"name": name, "region": ""},
    }
    if od_role is not None:
        concept["attributes"] = {"od_role": od_role}
    return concept


def event(node_id, subtype):
    return {
        "id": node_id, "concept": "EVENT", "subtype": subtype,
        "role": "SUPPORT", "source": "implicit",
    }


def measure(node_id, concept, subtype):
    return {
        "id": node_id, "concept": concept, "subtype": subtype,
        "role": "MEASURE", "source": "implicit",
    }


def payload(concepts, factors=None):
    return {"concepts": list(concepts), "factors": dict(factors or {})}


def ground(concepts, factors=None, question="테스트 질문"):
    return parse_grounding(payload(concepts, factors), question)


class ScriptedClient:
    model = "scripted-test-model"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("준비된 응답보다 많은 chat 호출이 발생했습니다.")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return {"message": {"content": json.dumps(response, ensure_ascii=False)}}


def new_pipeline(payloads):
    client = ScriptedClient(payloads)
    pipeline = GeoFlowPipeline(
        planner=GeoFlowPlanner(client=client),
        composer=MacroComposer(),
        tool_executor=ToolExecutor(tools=TOOLS, handlers=get_tool_handlers()),
    )
    return pipeline, client


def failure_of(concepts, factors=None, question="테스트 질문"):
    """합성이 실패할 때의 오류를 그대로 돌려준다."""
    grounding = ground(concepts, factors, question)
    try:
        MacroComposer().compose(grounding)
    except GeoFlowError as error:
        return error
    raise AssertionError("합성이 실패하지 않았습니다.")


OD_QUESTION = "동성로에서 출발하여 신천동에 도착한 실차 구간 건수는?"
TRIP_CONCEPTS = [event("e", "trip"), measure("m", "AMOUNT", "trip_count")]


class RepairDecisionTest(unittest.TestCase):
    """A. 재질의 판정."""

    def test_missing_qualifier_with_od_role_is_repairable(self):
        error = failure_of(
            [place("p", "동성로"), *TRIP_CONCEPTS],
            question="동성로에서 출발한 실차 구간 건수는?",
        )
        self.assertEqual(error.code, "MISSING_RELATION_QUALIFIER")
        decision = decide(error)
        self.assertTrue(decision.repairable)
        self.assertEqual(decision.kind, RepairKind.RELATION_QUALIFIER)
        self.assertEqual(decision.targets, ("p",))
        self.assertEqual(decision.allowed_additions, ("od_role",))

    def test_ambiguous_with_od_role_requirement_is_repairable(self):
        """q27 형태. 관계를 적을 자리가 계약에 있다."""
        error = failure_of(
            [place("a", "초읍동"), place("b", "초량동"), *TRIP_CONCEPTS],
            question="초읍동에서 출발하여 초량동에 도착한 실차 구간 건수는?",
        )
        self.assertEqual(error.code, "AMBIGUOUS_LOCATION_RELATION")
        decision = decide(error)
        self.assertTrue(decision.repairable)
        self.assertEqual(decision.kind, RepairKind.RELATION_QUALIFIER)
        self.assertEqual(sorted(decision.targets), ["a", "b"])

    def test_ambiguous_without_any_qualifier_is_not_repairable(self):
        """b20 형태. 비교 관계를 적을 자리가 계약에 없다.

        같은 오류 코드지만 다시 물어봐야 소용이 없다. 요구하면 모델은 없는
        관계를 있는 것처럼 꾸며 내고, 지원하지 않는 질문이 그럴듯한 오답이
        된다.
        """
        error = failure_of(
            [place("a", "대구"), place("b", "부산"),
             event("e", "passage"), measure("m", "AMOUNT", "speed")],
            question="대구와 부산 중 어디가 더 빠른가요?",
        )
        self.assertEqual(error.code, "AMBIGUOUS_LOCATION_RELATION")
        self.assertEqual(error.context["required_qualifiers"], [])
        decision = decide(error)
        self.assertFalse(decision.repairable)
        self.assertIsNone(decision.kind)
        self.assertIn("없습니다", decision.reason)

    def test_factor_combination_is_repairable(self):
        error = failure_of(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week"},
        )
        self.assertEqual(error.code, "INVALID_FACTOR_COMBINATION")
        decision = decide(error)
        self.assertTrue(decision.repairable)
        self.assertEqual(decision.kind, RepairKind.FACTOR_COMPLETION)
        self.assertEqual(decision.allowed_additions, ("rollup",))

    def test_unknown_planning_error_is_not_repairable(self):
        for code in ("NO_OPERATOR", "NO_MACRO", "UNSUPPORTED_MEASURE",
                     "INVALID_SUBTYPE", "VALUELESS_CONCEPT", None):
            with self.subTest(code=code):
                decision = decide(
                    CompositionError("테스트", code=code, context={}),
                )
                self.assertFalse(decision.repairable)

    def test_qualifier_outside_the_registry_is_not_repairable(self):
        """registry가 쓰지 않는 속성을 요구하면 복구 대상이 아니다."""
        decision = decide(CompositionError(
            "테스트", code="MISSING_RELATION_QUALIFIER",
            context={"required_qualifiers": ["made_up"], "unqualified": ["p"]},
        ))
        self.assertFalse(decision.repairable)

    def test_registry_qualifiers_are_derived(self):
        self.assertEqual(registry_qualifiers(), frozenset({"od_role"}))


class RepairMutationGuardTest(unittest.TestCase):
    """B. 허용 범위를 코드로 강제한다."""

    def setUp(self):
        self.error = failure_of(
            [place("a", "동성로"), place("b", "신천동"), *TRIP_CONCEPTS],
            question=OD_QUESTION,
        )
        self.decision = decide(self.error)
        self.before = ground(
            [place("a", "동성로"), place("b", "신천동"), *TRIP_CONCEPTS],
            question=OD_QUESTION,
        )

    def _after(self, concepts, factors=None):
        return ground(concepts, factors, question=OD_QUESTION)

    def test_adding_only_the_qualifier_is_valid(self):
        after = self._after([
            place("a", "동성로", od_role="pickup"),
            place("b", "신천동", od_role="dropoff"),
            *TRIP_CONCEPTS,
        ])
        validate_repair_delta(self.before, after, self.decision)

    def test_changing_a_place_name_is_rejected(self):
        after = self._after([
            place("a", "다른곳", od_role="pickup"),
            place("b", "신천동", od_role="dropoff"),
            *TRIP_CONCEPTS,
        ])
        with self.assertRaises(RepairViolation) as caught:
            validate_repair_delta(self.before, after, self.decision)
        self.assertIn("값은 바꿀 수 없습니다", str(caught.exception))

    def test_adding_a_concept_is_rejected(self):
        after = self._after([
            place("a", "동성로", od_role="pickup"),
            place("b", "신천동", od_role="dropoff"),
            place("c", "대구", od_role="pickup"),
            *TRIP_CONCEPTS,
        ])
        with self.assertRaises(RepairViolation) as caught:
            validate_repair_delta(self.before, after, self.decision)
        self.assertIn("더하거나 뺄 수 없습니다", str(caught.exception))

    def test_removing_a_concept_is_rejected(self):
        after = self._after([
            place("a", "동성로", od_role="pickup"), *TRIP_CONCEPTS,
        ])
        with self.assertRaises(RepairViolation):
            validate_repair_delta(self.before, after, self.decision)

    def test_changing_the_measure_subtype_is_rejected(self):
        after = self._after([
            place("a", "동성로", od_role="pickup"),
            place("b", "신천동", od_role="dropoff"),
            event("e", "trip"), measure("m", "AMOUNT", "fare"),
        ])
        with self.assertRaises(RepairViolation) as caught:
            validate_repair_delta(self.before, after, self.decision)
        self.assertIn("subtype", str(caught.exception))

    def test_changing_factors_during_relation_repair_is_rejected(self):
        after = self._after([
            place("a", "동성로", od_role="pickup"),
            place("b", "신천동", od_role="dropoff"),
            *TRIP_CONCEPTS,
        ], {"date": "20260530"})
        with self.assertRaises(RepairViolation) as caught:
            validate_repair_delta(self.before, after, self.decision)
        self.assertIn("조건(factor)", str(caught.exception))

    # -- factor -----------------------------------------------------------

    def _factor_case(self):
        error = failure_of(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week"},
        )
        before = ground(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week"},
        )
        return before, decide(error)

    def test_adding_only_the_missing_factor_is_valid(self):
        before, decision = self._factor_case()
        after = ground(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week", "rollup": "avg"},
        )
        validate_repair_delta(before, after, decision)

    def test_changing_the_existing_factor_is_rejected(self):
        before, decision = self._factor_case()
        after = ground(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "month", "rollup": "avg"},
        )
        with self.assertRaises(RepairViolation) as caught:
            validate_repair_delta(before, after, decision)
        self.assertIn("값을 바꿨습니다", str(caught.exception))

    def test_adding_an_unrelated_factor_is_rejected(self):
        before, decision = self._factor_case()
        after = ground(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week", "rollup": "avg", "taxi_type": "private"},
        )
        with self.assertRaises(RepairViolation) as caught:
            validate_repair_delta(before, after, decision)
        self.assertIn("허용되지 않은 조건", str(caught.exception))

    def test_still_missing_factor_is_rejected(self):
        before, decision = self._factor_case()
        after = ground(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week"},
        )
        with self.assertRaises(RepairViolation) as caught:
            validate_repair_delta(before, after, decision)
        self.assertIn("그대로입니다", str(caught.exception))

    def test_changing_a_concept_during_factor_repair_is_rejected(self):
        before, decision = self._factor_case()
        after = ground(
            [event("e", "operation"), measure("m", "AMOUNT", "hours")],
            {"bucket": "week", "rollup": "avg"},
        )
        with self.assertRaises(RepairViolation):
            validate_repair_delta(before, after, decision)


class PlanningRepairPipelineTest(unittest.TestCase):
    """C. 파이프라인에서의 재질의 횟수와 경로."""

    def test_relation_repair_succeeds_and_executes(self):
        pipeline, client = new_pipeline([
            payload([place("a", "동성로"), place("b", "신천동"),
                     *TRIP_CONCEPTS]),
            payload([place("a", "동성로", od_role="pickup"),
                     place("b", "신천동", od_role="dropoff"),
                     *TRIP_CONCEPTS]),
        ])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(
            run.repairs["relation_qualifier"],
            {"attempted": 1, "succeeded": 1},
        )
        self.assertEqual(
            [entry["tool"] for entry in run.hop_log][:3],
            ["get_place_scope", "get_place_scope", "get_trip_count"],
        )

    def test_factor_repair_succeeds_and_executes(self):
        pipeline, client = new_pipeline([
            payload([event("e", "operation"),
                     measure("m", "AMOUNT", "revenue")], {"bucket": "week"}),
            payload([event("e", "operation"),
                     measure("m", "AMOUNT", "revenue")],
                    {"bucket": "week", "rollup": "avg"}),
        ])
        run = pipeline.run("주 단위로 집계한 택시 수입의 평균은?")
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(
            run.repairs["factor_completion"],
            {"attempted": 1, "succeeded": 1},
        )

    def test_repaired_grounding_still_passes_every_guard(self):
        """재질의 결과라고 검증을 건너뛰지 않는다."""
        pipeline, _client = new_pipeline([
            payload([place("a", "동성로"), place("b", "신천동"),
                     *TRIP_CONCEPTS]),
            payload([place("a", "동성로", od_role="pickup"),
                     place("b", "신천동", od_role="dropoff"),
                     *TRIP_CONCEPTS]),
        ])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(run.validation["status"], "OK")
        self.assertEqual(len(run.validation["checked_rules"]), 6)
        self.assertTrue(run.execution_plan["steps"])

    def test_second_planning_failure_is_not_repaired_again(self):
        """재질의 결과가 또 실패해도 다시 묻지 않는다."""
        pipeline, client = new_pipeline([
            payload([place("a", "동성로"), place("b", "신천동"),
                     *TRIP_CONCEPTS]),
            payload([place("a", "동성로"), place("b", "신천동"),
                     *TRIP_CONCEPTS]),
        ])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(run.repair_count, MAX_REPAIR_ATTEMPTS)
        self.assertIsNotNone(run.runtime_error)
        self.assertEqual(
            run.attempts[-1]["status"], STATUS_PLANNING_FAILED,
        )
        self.assertFalse(run.attempts[-1]["repair_attempted"])

    def test_planning_repair_consumes_the_tool_repair_budget(self):
        """계획 재질의를 쓰면 실행 실패에는 재질의가 남지 않는다.

        한 질문에 재계획은 최대 한 번이라는 성질을 지킨다.
        """
        pipeline, client = new_pipeline([
            # 1) od_role 누락 → 계획 재질의
            payload([place("a", "대구시"), *TRIP_CONCEPTS]),
            # 2) 속성은 채웠지만 장소가 조회되지 않는다 → 실행 실패
            payload([place("a", "대구시", od_role="pickup"), *TRIP_CONCEPTS]),
        ])
        run = pipeline.run("대구시에서 출발한 실차 구간 건수는?")
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(run.repair_count, 1)
        self.assertIsNotNone(run.runtime_error)
        self.assertEqual(run.attempts[-1]["status"], "repair_skipped")
        self.assertIn("소진", run.attempts[-1]["reason"])

    def test_tool_repair_still_works_when_planning_succeeds(self):
        """계획이 한 번에 만들어지면 실행 실패에 재질의를 쓸 수 있다."""
        pipeline, client = new_pipeline([
            payload([place("a", "대구시", od_role="pickup"), *TRIP_CONCEPTS]),
            payload([place("a", "대구", od_role="pickup"), *TRIP_CONCEPTS]),
        ])
        run = pipeline.run("대구시에서 출발한 실차 구간 건수는?")
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(
            run.repairs["place_value"], {"attempted": 1, "succeeded": 1},
        )

    def test_out_of_scope_repair_keeps_the_original_error(self):
        pipeline, _client = new_pipeline([
            payload([place("a", "동성로"), *TRIP_CONCEPTS]),
            payload([place("a", "다른곳", od_role="pickup"), *TRIP_CONCEPTS]),
        ])
        run = pipeline.run("동성로에서 출발한 실차 구간 건수는?")
        self.assertEqual(run.error["code"], "MISSING_RELATION_QUALIFIER")
        self.assertEqual(
            run.repairs["relation_qualifier"],
            {"attempted": 1, "succeeded": 0},
        )
        self.assertEqual(run.attempts[-1]["repair_result"], "repair_failed")
        self.assertEqual(
            run.attempts[-1]["repair_error"]["code"], "REPAIR_OUT_OF_SCOPE",
        )

    def test_attempt_record_carries_diagnostics(self):
        pipeline, _client = new_pipeline([
            payload([place("a", "동성로"), *TRIP_CONCEPTS]),
            payload([place("a", "동성로", od_role="pickup"), *TRIP_CONCEPTS]),
        ])
        run = pipeline.run("동성로에서 출발한 실차 구간 건수는?")
        record = run.attempts[0]
        for key in ("index", "stage", "error_code", "repair_kind",
                    "repair_attempted", "repair_result"):
            self.assertIn(key, record)
        self.assertEqual(record["stage"], "composition")
        self.assertEqual(record["error_code"], "MISSING_RELATION_QUALIFIER")
        self.assertEqual(record["repair_kind"], RepairKind.RELATION_QUALIFIER)

    def test_run_record_is_json_serializable(self):
        pipeline, _client = new_pipeline([
            payload([place("a", "동성로"), *TRIP_CONCEPTS]),
            payload([place("a", "동성로", od_role="pickup"), *TRIP_CONCEPTS]),
        ])
        run = pipeline.run("동성로에서 출발한 실차 구간 건수는?")
        json.dumps(run.to_dict(), ensure_ascii=False)


class UnsupportedComparisonTest(unittest.TestCase):
    """D. b20은 재질의로 억지로 성공시키지 않는다."""

    QUESTION = "대구와 부산 중 어디가 더 빠른가요?"
    CONCEPTS = [
        place("a", "대구"), place("b", "부산"),
        event("e", "passage"), measure("m", "AMOUNT", "speed"),
    ]

    def test_comparison_question_is_not_repaired(self):
        pipeline, client = new_pipeline([payload(self.CONCEPTS)])
        run = pipeline.run(self.QUESTION)
        self.assertEqual(run.stage, Stage.COMPOSITION)
        self.assertEqual(run.error["code"], "AMBIGUOUS_LOCATION_RELATION")
        # Planner를 다시 부르지 않았다.
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(run.repair_count, 0)
        self.assertEqual(run.repairs, {})

    def test_attempt_record_says_why_it_was_not_repaired(self):
        pipeline, _client = new_pipeline([payload(self.CONCEPTS)])
        run = pipeline.run(self.QUESTION)
        record = run.attempts[-1]
        self.assertFalse(record["repairable"])
        self.assertFalse(record["repair_attempted"])
        self.assertIsNone(record["repair_kind"])
        self.assertIn("없습니다", record["repair_reason"])

    def test_no_tool_was_called(self):
        pipeline, _client = new_pipeline([payload(self.CONCEPTS)])
        run = pipeline.run(self.QUESTION)
        self.assertEqual(run.hop_log, [])
        self.assertIsNone(run.final_answer)

    def test_user_message_is_explicit_about_being_unsupported(self):
        pipeline, _client = new_pipeline([payload(self.CONCEPTS)])
        run = pipeline.run(self.QUESTION)
        self.assertIn("관계", run.error["user_message"])

    def test_comparison_is_not_turned_into_an_od_query(self):
        """관계를 od_role로 바꿔 성공시키지 않는다."""
        pipeline, _client = new_pipeline([payload(self.CONCEPTS)])
        run = pipeline.run(self.QUESTION)
        self.assertIsNone(run.plan)
        self.assertIsNone(run.execution_plan)


if __name__ == "__main__":
    unittest.main()
