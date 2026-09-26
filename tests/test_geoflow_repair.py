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
    RepairDecision,
    RepairKind,
    RepairViolation,
    apply_patch,
    decide,
    parse_patch,
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


def relation_patch(*updates):
    """관계 속성 수정안. 개념 전체를 다시 내놓지 않는다."""
    return {
        "updates": [
            {"concept_id": cid, "attribute": "od_role", "value": value}
            for cid, value in updates
        ]
    }


def factor_patch(**factors):
    return {"factors": dict(factors)}


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


class RepairPatchSchemaTest(unittest.TestCase):
    """A. 수정안 schema. 손댈 수 있는 표면을 여기서 좁힌다."""

    def setUp(self):
        self.relation_error = failure_of(
            [place("a", "동성로"), place("b", "신천동"), *TRIP_CONCEPTS],
            question=OD_QUESTION,
        )
        self.relation_decision = decide(self.relation_error)
        self.relation_before = ground(
            [place("a", "동성로"), place("b", "신천동"), *TRIP_CONCEPTS],
            question=OD_QUESTION,
        )
        self.factor_error = failure_of(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week"},
        )
        self.factor_decision = decide(self.factor_error)
        self.factor_before = ground(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week"},
        )

    def _relation(self, payload_dict):
        return parse_patch(
            payload_dict, self.relation_before, self.relation_decision,
        )

    def _factor(self, payload_dict):
        return parse_patch(
            payload_dict, self.factor_before, self.factor_decision,
        )

    # -- relation ---------------------------------------------------------

    def test_relation_patch_is_accepted(self):
        patch = self._relation(relation_patch(("a", "pickup"), ("b", "dropoff")))
        self.assertEqual(len(patch.updates), 2)
        self.assertEqual(patch.updates[0].concept_id, "a")
        self.assertEqual(patch.updates[0].attribute, "od_role")

    def test_unknown_concept_id_is_rejected(self):
        with self.assertRaises(RepairViolation) as caught:
            self._relation(relation_patch(("없는개념", "pickup")))
        self.assertIn("없는 개념", str(caught.exception))

    def test_concept_outside_the_target_is_rejected(self):
        with self.assertRaises(RepairViolation) as caught:
            self._relation(relation_patch(("e", "pickup")))
        self.assertIn("수정 대상이 아닙니다", str(caught.exception))

    def test_unknown_qualifier_is_rejected(self):
        with self.assertRaises(RepairViolation) as caught:
            self._relation({"updates": [
                {"concept_id": "a", "attribute": "made_up", "value": "x"},
            ]})
        self.assertIn("덧붙일 수 없는 속성", str(caught.exception))

    def test_overwriting_an_existing_qualifier_is_rejected(self):
        before = ground(
            [place("a", "동성로", od_role="pickup"), place("b", "신천동"),
             *TRIP_CONCEPTS],
            question=OD_QUESTION,
        )
        with self.assertRaises(RepairViolation) as caught:
            parse_patch(
                relation_patch(("a", "dropoff")), before,
                self.relation_decision,
            )
        self.assertIn("덮어쓸 수 없습니다", str(caught.exception))

    def test_extra_keys_are_rejected(self):
        with self.assertRaises(RepairViolation) as caught:
            self._relation({
                "updates": [{"concept_id": "a", "attribute": "od_role",
                             "value": "pickup"}],
                "factors": {"date": "20260530"},
            })
        self.assertIn("허용되지 않은 key", str(caught.exception))

    def test_empty_updates_are_rejected(self):
        with self.assertRaises(RepairViolation):
            self._relation({"updates": []})

    # -- factor -----------------------------------------------------------

    def test_factor_patch_is_accepted(self):
        patch = self._factor(factor_patch(rollup="avg"))
        self.assertEqual(patch.factors, {"rollup": "avg"})

    def test_factor_outside_the_missing_set_is_rejected(self):
        with self.assertRaises(RepairViolation) as caught:
            self._factor(factor_patch(rollup="avg", taxi_type="private"))
        self.assertIn("덧붙일 수 없는 조건", str(caught.exception))

    def test_overwriting_an_existing_factor_is_rejected(self):
        with self.assertRaises(RepairViolation) as caught:
            self._factor({"factors": {"bucket": "month"}})
        self.assertIn("덧붙일 수 없는 조건", str(caught.exception))

    def test_incomplete_factor_patch_is_rejected(self):
        with self.assertRaises(RepairViolation) as caught:
            self._factor({"factors": {}})
        self.assertIn("비어 있지 않은", str(caught.exception))

    def test_place_patch_is_accepted(self):
        before = ground([place("p", "대구시"), event("e", "trip"),
                         measure("m", "AMOUNT", "fare")])
        decision = RepairDecision(
            repairable=True, kind=RepairKind.PLACE_VALUE,
            reason="테스트", targets=("p",),
        )
        patch = parse_patch(
            {"concept_id": "p", "name": "대구", "region": ""},
            before, decision,
        )
        self.assertEqual((patch.name, patch.region), ("대구", ""))


class RepairPatchApplyTest(unittest.TestCase):
    """B. 적용은 코드가 한다. 같은 수정안이면 항상 같은 결과가 나온다."""

    def setUp(self):
        self.before = ground(
            [place("a", "동성로"), place("b", "신천동"), *TRIP_CONCEPTS],
            question=OD_QUESTION,
        )
        self.decision = decide(failure_of(
            [place("a", "동성로"), place("b", "신천동"), *TRIP_CONCEPTS],
            question=OD_QUESTION,
        ))

    def test_relation_patch_adds_only_the_attribute(self):
        patch = parse_patch(
            relation_patch(("a", "pickup"), ("b", "dropoff")),
            self.before, self.decision,
        )
        after = apply_patch(self.before, patch)
        self.assertEqual(after.get("a").attributes, {"od_role": "pickup"})
        self.assertEqual(after.get("b").attributes, {"od_role": "dropoff"})
        # 나머지는 그대로다.
        for node_id in ("a", "b", "e", "m"):
            self.assertEqual(
                after.get(node_id).value, self.before.get(node_id).value,
            )
        self.assertEqual(after.factors, self.before.factors)

    def test_apply_does_not_mutate_the_input(self):
        patch = parse_patch(
            relation_patch(("a", "pickup")), self.before, self.decision,
        )
        apply_patch(self.before, patch)
        self.assertEqual(self.before.get("a").attributes, {})

    def test_apply_is_independent_of_key_order(self):
        """LLM 출력의 field 순서에 결과가 좌우되지 않는다."""
        first = apply_patch(self.before, parse_patch(
            {"updates": [
                {"concept_id": "a", "attribute": "od_role", "value": "pickup"},
                {"concept_id": "b", "attribute": "od_role", "value": "dropoff"},
            ]}, self.before, self.decision,
        ))
        second = apply_patch(self.before, parse_patch(
            {"updates": [
                {"value": "dropoff", "attribute": "od_role", "concept_id": "b"},
                {"value": "pickup", "concept_id": "a", "attribute": "od_role"},
            ]}, self.before, self.decision,
        ))
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_factor_patch_adds_only_the_factor(self):
        before = ground(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week", "taxi_type": "private"},
        )
        decision = decide(failure_of(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"bucket": "week", "taxi_type": "private"},
        ))
        after = apply_patch(before, parse_patch(
            factor_patch(rollup="avg"), before, decision,
        ))
        self.assertEqual(after.factors, {
            "bucket": "week", "taxi_type": "private", "rollup": "avg",
        })
        self.assertEqual(
            [item.id for item in after.concepts],
            [item.id for item in before.concepts],
        )

    def test_applied_result_passes_the_delta_guard(self):
        """schema를 통과해 적용된 결과도 두 번째 방어선을 지난다."""
        patch = parse_patch(
            relation_patch(("a", "pickup"), ("b", "dropoff")),
            self.before, self.decision,
        )
        after = apply_patch(self.before, patch)
        validate_repair_delta(self.before, after, self.decision)

    def test_delta_guard_still_rejects_a_bypassing_result(self):
        """patch 검증을 우회해 만든 결과도 delta guard가 거부한다."""
        bypassed = ground(
            [place("a", "다른곳", od_role="pickup"),
             place("b", "신천동", od_role="dropoff"), *TRIP_CONCEPTS],
            question=OD_QUESTION,
        )
        with self.assertRaises(RepairViolation):
            validate_repair_delta(self.before, bypassed, self.decision)


class FactorCompletionReproducerTest(unittest.TestCase):
    """E. b24 형태를 LLM 없이 재현한다."""

    QUESTION = "2026년 7~8월, 월 단위로 집계한 개인택시 수입의 최대값은?"
    CONCEPTS = [event("e", "operation"), measure("m", "AMOUNT", "revenue")]
    # 구간을 나누려면 기간이 필요하다. 기간이 없으면 계획 전에 거부된다.
    FACTORS = {"bucket": "month", "aggregation": "max", "taxi_type": "private",
               "date": "20260701-20260831"}

    def test_bucket_only_is_repaired_by_a_factor_patch(self):
        pipeline, client = new_pipeline([
            payload(self.CONCEPTS, self.FACTORS),
            factor_patch(rollup="max"),
        ])
        run = pipeline.run(self.QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(
            run.repairs["factor_completion"],
            {"attempted": 1, "succeeded": 1},
        )
        # 보완된 rollup은 구간별 값의 집계가 된다. TIMS bucket 경계가 확인되지 않아
        # 호출 하나로 합치지 않고 하루마다 부른다.
        steps = run.execution_plan["steps"]
        tool_steps = [step for step in steps if step["kind"] == "tool"]
        self.assertEqual(len(tool_steps), 62)
        self.assertEqual(steps[-1]["operator"], "REDUCE_GROUPS")
        self.assertEqual(steps[-1]["arguments"], {"reducer": "max"})
        for step in tool_steps:
            self.assertNotIn("bucket", step["arguments"])
            # 기존 조건은 그대로 살아 있다.
            self.assertEqual(step["arguments"]["taxi_type"], "private")
            self.assertEqual(step["arguments"]["aggregation"], "max")

    def test_wrong_rollup_value_is_rejected(self):
        """bucket 단위를 rollup에 넣는 혼동은 값 검증이 막는다.

        실측에서 모델이 rollup에 "month"를 넣은 적이 있다. 적용 결과를 다시
        읽어 들이므로 factor 값 검증이 그대로 적용된다.
        """
        pipeline, _client = new_pipeline([
            payload(self.CONCEPTS, self.FACTORS),
            factor_patch(rollup="month"),
        ])
        run = pipeline.run(self.QUESTION)
        self.assertIsNotNone(run.runtime_error)
        error = run.attempts[-1]["repair_error"]
        self.assertEqual(error["code"], "INVALID_FACTOR")
        self.assertIn("rollup", error["detail"])
        # 계획은 만들어지지 않았고 Tool도 부르지 않았다.
        self.assertEqual(run.hop_log, [])

    def test_repair_request_states_the_allowed_values(self):
        """허용값은 factor 정의에서 만들어 요청문에 넣는다."""
        from geoflow.factors import describe_factor

        pipeline, client = new_pipeline([
            payload(self.CONCEPTS, self.FACTORS),
            factor_patch(rollup="max"),
        ])
        pipeline.run(self.QUESTION)
        instruction = client.calls[-1][-1]["content"]
        self.assertIn(describe_factor("rollup"), instruction)
        self.assertNotIn("concepts", instruction)


class PlanningRepairPipelineTest(unittest.TestCase):
    """C. 파이프라인에서의 재질의 횟수와 경로."""

    def test_relation_repair_succeeds_and_executes(self):
        pipeline, client = new_pipeline([
            payload([place("a", "동성로"), place("b", "신천동"),
                     *TRIP_CONCEPTS]),
            relation_patch(("a", "pickup"), ("b", "dropoff")),
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
                     measure("m", "AMOUNT", "revenue")],
                    {"bucket": "week", "aggregation": "sum",
                     "date": "20260801-20260831"}),
            factor_patch(rollup="avg"),
        ])
        run = pipeline.run("2026년 8월 주 단위로 합산한 택시 수입의 평균은?")
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
            relation_patch(("a", "pickup"), ("b", "dropoff")),
        ])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(run.validation["status"], "OK")
        self.assertEqual(len(run.validation["checked_rules"]), 7)
        self.assertTrue(run.execution_plan["steps"])

    def test_second_planning_failure_is_not_repaired_again(self):
        """수정안을 받았는데도 또 실패하면 다시 묻지 않는다.

        두 장소 중 하나만 구분을 채워 오면 나머지가 그대로 남아 같은
        이유로 다시 실패한다. 이때 재질의 예산은 이미 소진되어 있다.
        """
        pipeline, client = new_pipeline([
            payload([place("a", "동성로"), place("b", "신천동"),
                     *TRIP_CONCEPTS]),
            relation_patch(("a", "pickup")),
        ])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(run.repair_count, MAX_REPAIR_ATTEMPTS)
        self.assertIsNotNone(run.runtime_error)
        last = run.attempts[-1]
        self.assertEqual(last["status"], STATUS_PLANNING_FAILED)
        self.assertFalse(last["repair_attempted"])
        self.assertIn("소진", last["reason"])

    def test_malformed_patch_is_rejected_before_it_is_applied(self):
        """수정안 schema가 첫 번째 방어선이다."""
        pipeline, client = new_pipeline([
            payload([place("a", "동성로"), place("b", "신천동"),
                     *TRIP_CONCEPTS]),
            {"updates": []},
        ])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(run.repair_count, 0)
        self.assertEqual(
            run.attempts[-1]["repair_error"]["code"], "REPAIR_OUT_OF_SCOPE",
        )

    def test_planning_repair_consumes_the_tool_repair_budget(self):
        """계획 재질의를 쓰면 실행 실패에는 재질의가 남지 않는다.

        한 질문에 재계획은 최대 한 번이라는 성질을 지킨다.
        """
        pipeline, client = new_pipeline([
            # 1) od_role 누락 → 계획 재질의
            payload([place("a", "대구시"), *TRIP_CONCEPTS]),
            # 2) 속성은 채웠지만 장소가 조회되지 않는다 → 실행 실패
            relation_patch(("a", "pickup")),
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
            {"concept_id": "a", "name": "대구", "region": ""},
        ])
        run = pipeline.run("대구시에서 출발한 실차 구간 건수는?")
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(
            run.repairs["place_value"], {"attempted": 1, "succeeded": 1},
        )

    def test_out_of_scope_repair_keeps_the_original_error(self):
        # 수정안이 개념 값을 바꾸려 하면 schema가 받지 않는다.
        pipeline, _client = new_pipeline([
            payload([place("a", "동성로"), *TRIP_CONCEPTS]),
            {"updates": [{"concept_id": "a", "attribute": "od_role",
                          "value": "pickup"}],
             "concepts": [place("a", "다른곳")]},
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
            relation_patch(("a", "pickup")),
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
            relation_patch(("a", "pickup")),
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
