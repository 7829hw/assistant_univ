# -*- coding: utf-8 -*-
"""grounding과 코드의 책임 경계(grounding_v3).

- 조건 계층은 질문에 **명시된** 조건(날짜·택시 유형·운행 상태)을 보존하고 장소 이름의 근거를 확인할 뿐이다.
  측정값·장소 역할·그룹·순위·집계는 모델 grounding의 몫이다. 모델 값이 틀려 보여도 조건 계층은 바꾸지 않는다.
- 형식 정규화는 뜻을 바꾸지 않는 자리 바로잡기다(질문 원문을 읽지 않는다).
- 같은 지역 안의 OD는 grounding 표현(od_role=both)으로 적고, 실행은 조회 한 번으로 두 인자를 채운다.
"""

import os
import unittest
from datetime import date

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from geoflow import conditions  # noqa: E402
from geoflow.errors import PlannerError  # noqa: E402
from geoflow.grounding import normalize_place_concepts, parse_grounding  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from tests.test_geoflow import ScriptedClient, new_tool_executor, planner_response  # noqa: E402

REF = date(2026, 9, 25)
TRIP = [{"id": "trip", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT",
         "source": "implicit"},
        {"id": "m", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE",
         "source": "implicit"}]


def place(name, region="", role=None, pid=None):
    item = {"id": pid or f"p_{name}", "concept": "LOCATION", "subtype": "place",
            "role": "SUBCOND", "source": "user", "value": {"name": name, "region": region}}
    if role:
        item["attributes"] = {"od_role": role}
    return item


class ConditionLayerScopeTest(unittest.TestCase):
    """질문과 모델 값이 달라 보여도 조건 계층은 관계·집계를 다시 읽지 않는다."""

    CASES = (
        # 질문, 개념, factor: 모두 모델이 틀렸거나 맞았거나와 무관하게 그대로 나와야 한다.
        ("부산에서 하차가 많은 읍면동 상위 3곳은?", [place("부산", role="pickup"), *TRIP],
         {"dimension": "emd", "dimension_target": "dropoff", "order": "top", "limit": 3}),
        ("대구 신천동에서 출발한 실차 구간의 하차 읍면동 하위 3곳은?",
         [place("신천동", "대구", "pickup"), *TRIP],
         {"dimension": "emd", "dimension_target": "dropoff", "order": "top", "limit": 3}),
        ("지난달 법인택시 가동률을 주 단위로 최저치를 뽑았을 때, 그 주별 최저치 중 가장 높은 건?",
         [{"id": "e", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
           "source": "implicit"},
          {"id": "m", "concept": "PROPORTION", "subtype": "active_taxi_ratio", "role": "MEASURE",
           "source": "implicit"}],
         {"date": "last_month", "taxi_type": "corporate", "bucket": "week", "aggregation": "min",
          "rollup": "max"}),
        ("작년 한 해 대구 수성구 내부 이동을 동 단위 출발·도착 쌍으로 나눴을 때 가장 적게 이용된 세 쌍은?",
         [place("수성구", "대구", "both"), *TRIP],
         {"date": "last_year", "dimension": "emd", "dimension_target": "both", "order": "bottom",
          "limit": 3}),
        ("주말 오후 6시부터 8시까지 부산 초읍동 어린이대공원 주변의 RPM 중간값은?",
         [place("어린이대공원", "부산 초읍동"),
          {"id": "e", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
           "source": "implicit"},
          {"id": "m", "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE",
           "source": "implicit"}],
         {"date": "weekend", "time": "180000-200000", "aggregation": "med", "vicinity": True}),
    )

    def test_relations_measures_and_aggregation_are_left_to_grounding(self):
        for question, concepts, factors in self.CASES:
            with self.subTest(question=question):
                payload = {"concepts": concepts, "factors": dict(factors)}
                fixed, audit = conditions.reconcile_payload(payload, question, reference_date=REF)
                self.assertEqual(fixed["concepts"], concepts)
                for key, value in factors.items():
                    self.assertEqual(fixed["factors"].get(key), value)
                self.assertEqual([c["condition"] for c in audit["corrections"]
                                  if c["condition"] not in conditions.OWNED_FACTORS], [])

    def test_explicit_conditions_are_still_preserved(self):
        payload = {"concepts": [place("수영구", "부산"),
                                {"id": "e", "concept": "EVENT", "subtype": "passage",
                                 "role": "SUPPORT", "source": "implicit"},
                                {"id": "m", "concept": "AMOUNT", "subtype": "passage_count",
                                 "role": "MEASURE", "source": "implicit"}], "factors": {}}
        fixed, audit = conditions.reconcile_payload(
            payload, "지난달 부산 수영구의 공차 개인택시 통행량은?", reference_date=REF)
        self.assertEqual(fixed["factors"], {"date": "last_month", "taxi_type": "private",
                                            "taxi_status": "vacant"})
        self.assertEqual(sorted(c["condition"] for c in audit["corrections"]),
                         ["date", "taxi_status", "taxi_type"])


class SameAreaRepresentationTest(unittest.TestCase):
    def run_pipeline(self, question, places, factors):
        payload = {"concepts": [*places, *TRIP], "factors": factors}
        return GeoFlowPipeline.create(
            client=ScriptedClient([planner_response(payload)]),
            tool_executor=new_tool_executor(), clock=lambda: REF,
            condition_check=True).run(question)

    def test_both_fills_pickup_and_dropoff_with_one_lookup(self):
        within = self.run_pipeline("지난달 대구 안에서 이동한 읍면동 간 노선 상위 3개는?",
                                   [place("대구", role="both")],
                                   {"dimension": "emd", "order": "top", "limit": 3})
        between = self.run_pipeline("지난달 대구에서 부산으로 이동한 읍면동 간 노선 상위 3개는?",
                                    [place("대구", role="pickup"), place("부산", role="dropoff")],
                                    {"dimension": "emd", "order": "top", "limit": 3})
        for run in (within, between):
            self.assertEqual(run.outcome, "answered", run.error)
        tools = [h for h in within.hop_log if h.get("phase") == "tool"]
        self.assertEqual([h["tool"] for h in tools], ["get_place_scope", "get_trip_count"])
        self.assertEqual(tools[-1]["arguments"]["scope_pickup"], tools[-1]["arguments"]["scope_dropoff"])
        final = [h for h in between.hop_log if h.get("phase") == "tool"][-1]["arguments"]
        self.assertNotEqual(final["scope_pickup"], final["scope_dropoff"])

    def test_two_copies_of_one_place_are_looked_up_once(self):
        run = self.run_pipeline("부산 안에서 이동한 실차 건수는?",
                                [place("부산", role="pickup", pid="a"),
                                 place("부산", role="dropoff", pid="b")], {})
        self.assertEqual(run.outcome, "answered", run.error)
        self.assertEqual([h.get("phase") for h in run.hop_log
                          if h["tool"] == "get_place_scope"], ["tool", "reuse"])


class FormatNormalizationTest(unittest.TestCase):
    """질문 원문을 보지 않는 자리 바로잡기. 뜻이 같을 때만."""

    def test_default_target_without_dimension_is_dropped(self):
        payload = {"concepts": [place("수영구", "부산", "pickup"), place("동구", "대구", "dropoff"),
                                *TRIP], "factors": {"dimension_target": "both"}}
        grounding = parse_grounding(payload, "q")
        self.assertNotIn("dimension_target", grounding.factors)
        from geoflow.factors import validate_factors

        kept = parse_grounding({**payload, "factors": {"dimension_target": "pickup"}}, "q")
        with self.assertRaises(PlannerError):   # 뜻이 있는 값은 짝 검사가 재질의로 보낸다
            validate_factors(kept.factors)

    def test_unit_word_with_an_existing_place_as_region_is_not_a_new_place(self):
        concepts = [place("부산", role="pickup"),
                    {**place("시군구", "부산", role="dropoff"), "id": "d", "source": "implicit"}]
        cleaned, notes = normalize_place_concepts(concepts, {"dimension": "sigungu"})
        self.assertEqual([c["value"]["name"] for c in cleaned], ["부산"])
        self.assertEqual(notes[0]["rule"], "unit_word_place_duplicate_dropped")


class GoldThroughConditionLayerTest(unittest.TestCase):
    """정답 grounding을 조건 계층에 넣으면 아무것도 바뀌지 않는다(실행기 평가와 별개).

    grounding_v2의 의미 재해석은 처음 보는 2차 독립셋에서 m14·m17·m22의 맞는 grounding을 바꾸거나 멈췄다.
    """

    FILES = ("evaluation/vendor100/gold.yaml", "evaluation/grounding_v1/holdout_questions.yaml",
             "evaluation/grounding_v2/contrast_questions.yaml",
             "evaluation/grounding_v2/independent_questions.yaml",
             "evaluation/grounding_v2/independent_v3_questions.yaml")

    def test_gold_groundings_are_left_unchanged(self):
        import evaluate_vendor100 as E

        for path in self.FILES:
            for item in E.load_gold(path)["items"]:
                payload = E.gold_grounding(item)
                if payload is None:
                    continue
                with self.subTest(item=item["id"]):
                    try:
                        _, audit = conditions.reconcile_payload(
                            payload, item["question"], reference_date=REF)
                    except PlannerError as error:
                        self.assertNotEqual(item.get("expected_outcome", "answered"), "answered",
                                            error.code)
                        continue
                    self.assertEqual(audit["corrections"], [])


if __name__ == "__main__":
    unittest.main()


class FlatSelectionTest(unittest.TestCase):
    """"가장 큰 값"(answer=value)과 "그 값을 가진 주"(answer=bucket)를 flat grounding에서 구분한다(grounding_v4).

    표현은 grounding이, 실행 가능 여부는 provider 계약이 정한다. 원문 패턴으로 미리 거부하지 않는다.
    """

    def payload(self, **aggregation):
        return {"concepts": [
            {"id": "place", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
             "source": "user", "value": {"name": "가람구"}},
            {"id": "operation", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
             "source": "implicit"},
            {"id": "revenue", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
             "source": "implicit"}],
            "factors": {"date": "last_month", "taxi_type": "private", "bucket": "week",
                        "aggregation": "sum", **aggregation}}

    def run_with(self, payload, profile, executor):
        return GeoFlowPipeline.create(
            client=ScriptedClient([planner_response(payload)]), tool_executor=executor,
            clock=lambda: REF, execution_profile=profile).run("지난달 가람구 개인택시 매출 합계가 가장 큰 주는?")

    def test_flat_select_matches_the_structured_selection_on_the_reference_provider(self):
        from geoflow.providers import REFERENCE, profile_for
        from tests.test_reference_provider import Q4_MAX_WEEKLY_SUM, WEEKS, reference_executor

        result = self.run_with(self.payload(rollup="max", answer="bucket"), profile_for(REFERENCE),
                               reference_executor())
        self.assertEqual(result.outcome, "answered", result.runtime_error)
        value = result.hop_log[-1]["result"]
        self.assertEqual(value["value"], Q4_MAX_WEEKLY_SUM)
        self.assertEqual([group["label"] for group in value["groups"]], WEEKS[1:3])
        # 같은 질문의 값(rollup=max)은 구간이 아니라 스칼라다.
        rolled = self.run_with(self.payload(rollup="max"), profile_for(REFERENCE),
                               reference_executor())
        self.assertEqual(rolled.outcome, "answered", rolled.runtime_error)
        self.assertNotIsInstance(rolled.hop_log[-1]["result"], dict)

    def test_tims_contract_decides_that_selection_is_not_executable(self):
        """TIMS bucket/rollup 호출은 대표값만 돌려주고, 로컬 재계산의 근거(day_records)는 계약에 없다."""
        run = self.run_with(self.payload(rollup="max", answer="bucket"), None, new_tool_executor())
        self.assertEqual(run.outcome, "unsupported")
        self.assertEqual(run.error["code"], "UNVERIFIED_TIMS_CONTRACT")

    def test_bucket_answer_needs_a_max_or_min(self):
        from geoflow.aggregation import from_flat
        from geoflow.factors import validate_factors

        with self.assertRaises(PlannerError) as caught:
            validate_factors({"bucket": "week", "rollup": "avg", "answer": "bucket"})
        self.assertEqual(caught.exception.code, "INVALID_ANSWER_TARGET")
        # answer를 생략하면 값이다(단순한 질문은 answer 없이 그대로 쓴다).
        self.assertIsNone(from_flat({"bucket": "week", "aggregation": "sum", "rollup": "max"}).select)
        self.assertEqual(from_flat({"bucket": "week", "aggregation": "sum", "rollup": "max",
                                    "answer": "bucket"}).select, "max")


class RankingCountContractTest(unittest.TestCase):
    def test_order_without_limit_goes_to_factor_completion(self):
        """업체 규칙: 순위에는 개수를 적는다(하나만이면 1). 비면 모델에게 그 값만 되묻는다."""
        from geoflow.factors import validate_factors
        from geoflow.repair import RepairKind, decide

        with self.assertRaises(PlannerError) as caught:
            validate_factors({"dimension": "emd", "order": "top"})
        decision = decide(caught.exception)
        self.assertTrue(decision.repairable)
        self.assertEqual((decision.kind, decision.allowed_additions),
                         (RepairKind.FACTOR_COMPLETION, ("limit",)))
