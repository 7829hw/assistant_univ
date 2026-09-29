# -*- coding: utf-8 -*-
"""질문의 관계 읽기(geoflow/relations.py)와 조건 계층의 누락·충돌 처리.

LLM을 부르지 않는다. 각 시험은 모델이 실제로 낸 형태(개발셋 기록)를 본뜬 payload를 넣고,
- 뜻이 바뀌는 대조(출발↔도착, 상위↔하위, 같은 지역↔다른 지역, 집계어 더하기·빼기)에서 결과가
  달라지는지,
- 근거가 분명한 누락은 채우고 충돌은 바로잡되, 표현이 서로 어긋나면 확인을 요청하는지,
- 모든 변경이 근거 표현·전후 값·이유를 남기는지,
- 정답 grounding에는 아무것도 바꾸지 않는지(잘못된 보정 0)
를 본다.
"""

import os
import unittest
from datetime import date

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from geoflow import conditions, relations  # noqa: E402
from geoflow.errors import PlannerError  # noqa: E402
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


def reconcile(concepts, factors, question):
    return conditions.reconcile_payload({"concepts": concepts, "factors": dict(factors)},
                                        question, reference_date=REF)


def roles(fixed):
    return sorted(((c["value"]["name"], (c.get("attributes") or {}).get("od_role"))
                   for c in fixed["concepts"] if c.get("concept") == "LOCATION"), key=str)


class PlaceRoleTest(unittest.TestCase):
    """장소의 역할은 조사 하나가 아니라 조사 + 서술어로 정한다."""

    def test_the_verb_after_the_particle_decides_the_role(self):
        cases = (
            ("부산에서 하차가 많은 읍면동 상위 3곳은?", "부산", "dropoff"),
            ("부산에서 승차가 많은 읍면동 상위 3곳은?", "부산", "pickup"),
            ("대구 수성구에서 출발한 실차의 도착 읍면동 상위 2곳은?", "수성구", "pickup"),
            ("대구 수성구에 도착한 실차의 출발 읍면동 상위 2곳은?", "수성구", "dropoff"),
            ("주말 부산 초량동으로 들어온 실차 구간 건수는?", "초량동", "dropoff"),
            ("이번 주 대구 동인동에서 나간 실차 구간 건수는?", "동인동", "pickup"),
            ("휴일 부산의 승차 읍면동 중 가장 많은 곳은?", "부산", "pickup"),
        )
        for question, name, role in cases:
            with self.subTest(question=question):
                region = "대구" if name == "수성구" or name == "동인동" else (
                    "부산" if name == "초량동" else "")
                fixed, audit = reconcile([place(name, region), *TRIP],
                                         {"dimension": "emd"} if "읍면동" in question else {},
                                         question)
                self.assertEqual(roles(fixed), [(name, role)])
                (record,) = audit["od_roles"]
                self.assertEqual(record["action"], "filled")
                self.assertTrue(record["evidence"][0]["text"].startswith(
                    question[question.index(region or name):][:2]))

    def test_origin_destination_pairs_follow_the_particles_both_ways(self):
        for question, pickup, dropoff in (
                ("대구 신천동에서 부산 초량동까지의 실차 구간 건수는?", "신천동", "초량동"),
                ("부산 초량동에서 대구 신천동까지의 실차 구간 건수는?", "초량동", "신천동"),
                ("대구 신천동에서 부산 초량동에 도착한 실차 구간 건수는?", "신천동", "초량동"),
                ("대구에서 부산으로 이동한 실차 구간 건수는?", "대구", "부산"),
                ("대구 출발 부산 도착 실차 구간 건수는?", "대구", "부산")):
            with self.subTest(question=question):
                concepts = [place(pickup), place(dropoff), *TRIP]
                fixed, _ = reconcile(concepts, {}, question)
                self.assertEqual(roles(fixed), sorted([(pickup, "pickup"), (dropoff, "dropoff")],
                                                      key=str))

    def test_a_clear_expression_corrects_the_model_value(self):
        """모델이 반대 역할을 적었다(기존 44 g11). 근거가 분명하면 바로잡고 이전 값을 남긴다."""
        question = "주말 부산 초량동으로 들어온 실차 구간 건수는?"
        fixed, audit = reconcile([place("초량동", "부산", "pickup"), *TRIP], {}, question)
        self.assertEqual(roles(fixed), [("초량동", "dropoff")])
        correction = next(c for c in audit["corrections"] if c["condition"] == "od_role")
        self.assertEqual((correction["from"], correction["to"], correction["action"]),
                         ("pickup", "dropoff", "corrected"))
        self.assertIn("초량동으로 들어", correction["evidence"][0]["text"])

    def test_unread_phrasing_keeps_the_model_value(self):
        """문형 밖이면 읽지 않는다. 모델 값을 두고, 없으면 기존 재질의가 맡는다."""
        question = "부산 광안동 쪽 실차 구간 건수는?"
        fixed, audit = reconcile([place("광안동", "부산", "pickup"), *TRIP], {}, question)
        self.assertEqual(roles(fixed), [("광안동", "pickup")])
        self.assertEqual(audit["od_roles"][0]["action"], "none")

    def test_roles_on_measures_that_take_no_roles_are_removed_only_without_od_words(self):
        speed = [{"id": "e", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
                  "source": "implicit"},
                 {"id": "m", "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE",
                  "source": "implicit"}]
        fixed, audit = reconcile([place("어린이대공원", "부산 초읍동", "pickup"), *speed],
                                 {"vicinity": True}, "지난주 부산 초읍동 어린이대공원 근처의 택시 속도는?")
        self.assertEqual(roles(fixed), [("어린이대공원", None)])
        self.assertEqual(audit["od_roles"][0]["action"], "removed_no_evidence")
        fixed, audit = reconcile([place("동성로", "", "pickup"), *speed], {},
                                 "동성로에서 출발한 택시의 속도는?")
        self.assertEqual(roles(fixed), [("동성로", "pickup")])   # 합성 단계가 지원 여부를 정한다


class SameAreaTest(unittest.TestCase):
    def test_within_one_area_the_place_takes_both_roles(self):
        question = "이번 달 부산 안에서 이용이 적은 읍면동 간 OD 노선 하위 2개는?"
        fixed, audit = reconcile([place("부산"), *TRIP],
                                 {"dimension": "emd", "order": "bottom", "limit": 2}, question)
        self.assertEqual(roles(fixed), [("부산", "dropoff"), ("부산", "pickup")])
        self.assertEqual(audit["od_roles"][0]["value"], ["dropoff", "pickup"])
        self.assertEqual(len({c["id"] for c in fixed["concepts"]}), len(fixed["concepts"]))

    def test_two_unassigned_copies_of_one_place_are_split(self):
        question = "주말 대구 안에서 이용이 많은 읍면동 간 OD 노선 상위 3개는?"
        fixed, _ = reconcile([place("대구", pid="a"), place("대구", pid="b"), *TRIP],
                             {"dimension": "emd", "order": "top", "limit": 3}, question)
        self.assertEqual(roles(fixed), [("대구", "dropoff"), ("대구", "pickup")])

    def test_without_route_context_within_means_the_event_location(self):
        question = "이번 달 부산 안에서 승차가 많은 읍면동 상위 3곳은?"
        fixed, _ = reconcile([place("부산"), *TRIP], {"dimension": "emd"}, question)
        self.assertEqual(roles(fixed), [("부산", "pickup")])

    def test_same_or_different_area_changes_the_call_and_the_scope_is_looked_up_once(self):
        def run(question, concepts):
            payload = {"concepts": [*concepts, *TRIP],
                       "factors": {"dimension": "emd", "order": "top", "limit": 3}}
            pipeline = GeoFlowPipeline.create(
                client=ScriptedClient([planner_response(payload)]),
                tool_executor=new_tool_executor(), clock=lambda: REF, condition_check=True)
            return pipeline.run(question)

        within = run("지난달 대구 안에서 이동한 읍면동 간 노선 상위 3개는?", [place("대구")])
        between = run("지난달 대구에서 부산으로 이동한 읍면동 간 노선 상위 3개는?",
                      [place("대구"), place("부산")])
        self.assertEqual(within.outcome, "answered", within.error)
        self.assertEqual(between.outcome, "answered", between.error)
        lookups = [h for h in within.hop_log if h.get("phase") == "tool"
                   and h["tool"] == "get_place_scope"]
        reused = [h for h in within.hop_log if h.get("phase") == "reuse"]
        self.assertEqual((len(lookups), len(reused)), (1, 1))
        final = [h for h in within.hop_log if h.get("phase") == "tool"][-1]["arguments"]
        self.assertEqual(final["scope_pickup"], final["scope_dropoff"])
        final = [h for h in between.hop_log if h.get("phase") == "tool"][-1]["arguments"]
        self.assertNotEqual(final["scope_pickup"], final["scope_dropoff"])


class GroupingTargetTest(unittest.TestCase):
    def test_filter_end_and_grouping_end_are_read_separately(self):
        cases = (
            ("대구 수성구에서 출발한 실차의 도착 읍면동 상위 2곳은?", "pickup", "dropoff"),
            ("대구 수성구에 도착한 실차의 출발 읍면동 상위 2곳은?", "dropoff", "pickup"),
            ("대구 수성구에서 하차한 실차의 승차 읍면동 상위 2곳은?", "dropoff", "pickup"),
            ("대구 수성구에서 출발한 실차의 읍면동 간 노선 상위 2개는?", "pickup", "both"),
            ("부산에서 하차가 많은 읍면동 상위 3곳은?", "dropoff", "dropoff"),
        )
        for question, role, target in cases:
            with self.subTest(question=question):
                name = "수성구" if "수성구" in question else "부산"
                fixed, audit = reconcile([place(name, "대구" if name == "수성구" else ""), *TRIP],
                                         {"dimension": "emd", "dimension_target": "pickup"},
                                         question)
                self.assertEqual(roles(fixed), [(name, role)])
                self.assertEqual(fixed["factors"].get("dimension_target"), target)

    def test_a_dimension_value_in_the_wrong_slot_is_corrected(self):
        """모델이 dimension에 both를 적었다(개발셋 006). 단위 말이 하나면 그 값이 dimension이다."""
        question = "대구에서 부산으로 이동한 읍면동 간 OD 노선 상위 3개는?"
        fixed, audit = reconcile([place("대구", role="pickup"), place("부산", role="dropoff"),
                                  TRIP[0]],
                                 {"dimension": "both", "dimension_target": "pickup",
                                  "order": "top", "limit": 3}, question)
        self.assertEqual(fixed["factors"]["dimension"], "emd")
        self.assertEqual(fixed["factors"]["dimension_target"], "both")
        # 측정값 개념이 빠졌지만 "OD 노선"(trip_count)과 사건 trip이 함께 있어 채운다.
        self.assertEqual([c["subtype"] for c in fixed["concepts"] if c["role"] == "MEASURE"],
                         ["trip_count"])
        self.assertEqual(audit["measure"]["action"], "filled")


class OrderAndAggregationTest(unittest.TestCase):
    PASSAGE = [{"id": "e", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
                "source": "implicit"},
               {"id": "m", "concept": "AMOUNT", "subtype": "passage_count", "role": "MEASURE",
                "source": "implicit"}]
    BILLING = [{"id": "e", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
                "source": "implicit"},
               {"id": "m", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
                "source": "implicit"}]

    def test_ranking_direction_follows_the_question(self):
        for question, llm, value in (("대구의 시군구별 택시 통행량 상위 2곳은?", "bottom", "top"),
                                     ("대구의 시군구별 택시 통행량 하위 2곳은?", "top", "bottom"),
                                     ("대구에서 택시 통행량이 가장 적은 시군구는?", None, "bottom")):
            with self.subTest(question=question):
                factors = {"dimension": "sigungu", **({"order": llm} if llm else {})}
                fixed, _ = reconcile([place("대구"), *self.PASSAGE], factors, question)
                self.assertEqual(fixed["factors"]["order"], value)

    def test_aggregation_words_are_not_ranking_direction(self):
        """"최대 수입이 가장 낮은 곳" = 측정값은 최대, 순위는 낮은 쪽."""
        fixed, _ = reconcile(list(self.BILLING),
                             {"aggregation": "max", "rollup": "min"},
                             "지난달 시도별 최대 수입이 가장 낮은 곳은?")
        self.assertEqual(fixed["factors"], {"aggregation": "max", "dimension": "sido",
                                            "order": "bottom", "limit": 1, "date": "last_month"})

    def test_contradicting_direction_words_ask_instead_of_guessing(self):
        with self.assertRaises(PlannerError) as caught:
            reconcile([place("대구"), *self.PASSAGE], {"dimension": "sigungu", "order": "top"},
                      "대구의 시군구별 택시 통행량이 많은 하위 2곳은?")
        self.assertEqual(caught.exception.code, "RELATION_EXPRESSION_AMBIGUOUS")
        self.assertTrue(caught.exception.context["needs_clarification"])

    def test_stated_aggregation_is_filled_and_invented_one_removed(self):
        fixed, audit = reconcile(list(self.BILLING),
                                 {"dimension": "sido", "order": "top", "limit": 1},
                                 "지난달 시도별 개인택시 총 수입이 가장 많은 곳은?")
        self.assertEqual(fixed["factors"]["aggregation"], "sum")
        fixed, audit = reconcile([place("대구"), *self.PASSAGE],
                                 {"dimension": "sigungu", "order": "top", "aggregation": "sum"},
                                 "주중 대구의 시군구별 택시 통행량이 가장 많은 곳은?")
        self.assertNotIn("aggregation", fixed["factors"])
        self.assertEqual(audit["aggregation"]["action"], "removed_no_evidence")
        # 생략과 Tool 기본값(avg)은 같은 뜻이다. 바꾸지 않고 같다고 적는다.
        fixed, audit = reconcile(list(self.BILLING), {}, "지난달 부산 소속 택시의 평균 수입은?")
        self.assertNotIn("aggregation", fixed["factors"])
        self.assertEqual(audit["aggregation"]["action"], "confirmed_equivalent")
        self.assertEqual(audit["corrections"], [{"condition": "date", "from": None,
                                                 "to": "last_month", "action": "filled",
                                                 "basis": "question_expression",
                                                 "evidence": audit["corrections"][0]["evidence"]}]
                         if audit["corrections"] else [])

    def test_two_stage_words_follow_their_positions(self):
        cases = (("지난해 월별 법인택시 수입 합계의 평균은?", {}, "sum", "avg"),
                 ("지난해 월별 평균 법인택시 수입 중 가장 작은 값은?", {"rollup": "avg"}, "avg", "min"),
                 ("지난해 월별 법인택시 총 수입 중 가장 큰 값은?", {"aggregation": "max"}, "sum", "max"),
                 ("올해 법인택시 수입을 달마다 모두 더한 값 가운데 가장 작은 값은?", {}, "sum", "min"))
        for question, llm, inner, outer in cases:
            with self.subTest(question=question):
                fixed, _ = reconcile(list(self.BILLING), {"bucket": "month", **llm}, question)
                self.assertEqual((fixed["factors"].get("aggregation"),
                                  fixed["factors"].get("rollup")), (inner, outer))

    def test_a_missing_inner_aggregation_is_not_made_up(self):
        """"주별 수입의 평균"에는 구간 안 집계가 없다(기존 44 g44). 모델이 채운 값을 지운다."""
        fixed, audit = reconcile(list(self.BILLING),
                                 {"bucket": "week", "aggregation": "avg"},
                                 "지난달 주별 개인택시 수입의 평균은?")
        self.assertNotIn("aggregation", fixed["factors"])
        self.assertEqual(fixed["factors"]["rollup"], "avg")
        self.assertEqual(audit["aggregation"]["action"], "removed_no_evidence")

    def test_a_question_about_which_bucket_is_refused_in_flat_grounding(self):
        with self.assertRaises(PlannerError) as caught:
            reconcile(list(self.BILLING), {"bucket": "week", "aggregation": "sum", "rollup": "max"},
                      "지난달 대구 소속 택시의 수입 합계가 가장 큰 주는?")
        self.assertEqual(caught.exception.code, "BUCKET_SELECTION_UNSUPPORTED")
        # 지역·요일을 고르는 순위는 dimension으로 답할 수 있다.
        fixed, _ = reconcile(list(self.BILLING), {"dimension": "dayofweek", "order": "top"},
                             "이번 달 요일별 법인택시 평균 수입 중 가장 높은 요일은?")
        self.assertEqual(fixed["factors"]["limit"], 1)
        # 구조화 표기는 구간 선택을 표현하므로 여기서 막지 않는다(합성 단계가 정한다).
        payload = {"concepts": list(self.BILLING), "factors": {"aggregation_plan": {
            "bucket": {"unit": "week", "reducer": "sum"}, "result": {"select": "max"}}}}
        conditions.reconcile_payload(payload, "지난달 대구 수입 합계가 가장 큰 주는?",
                                     reference_date=REF, structured=True)


class MeasureTest(unittest.TestCase):
    def test_same_family_measure_is_corrected_other_families_ask(self):
        speed = [{"id": "e", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
                  "source": "implicit"},
                 {"id": "m", "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE",
                  "source": "implicit"}]
        fixed, audit = reconcile(speed, {"aggregation": "med"},
                                 "주말 부산 초읍동 어린이대공원 주변의 RPM 중간값은?")
        self.assertEqual(fixed["concepts"][1]["subtype"], "rpm")
        self.assertEqual(audit["measure"]["action"], "corrected")
        with self.assertRaises(PlannerError) as caught:
            reconcile(list(TRIP), {}, "동성로의 실차 통행량은?")
        self.assertEqual(caught.exception.code, "MEASURE_EXPRESSION_CONFLICT")

    def test_implicit_event_follows_a_confirmed_measure(self):
        """"실차 택시 통행량"에 EVENT/trip(기존 44 g04). 측정값이 질문의 말과 맞으면 사건을 맞춘다."""
        concepts = [{"id": "trip", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT",
                     "source": "implicit"},
                    {"id": "m", "concept": "AMOUNT", "subtype": "passage_count", "role": "MEASURE",
                     "source": "implicit"}]
        fixed, audit = reconcile(concepts, {"dimension": "sigungu", "order": "top"},
                                 "주중 대구의 시군구별 실차 택시 통행량이 가장 많은 곳은?")
        self.assertEqual(fixed["concepts"][0]["subtype"], "passage")
        self.assertEqual(audit["event"]["action"], "corrected")


class GoldSilenceTest(unittest.TestCase):
    """정답 grounding을 넣으면 조건 계층은 아무것도 바꾸지 않는다(잘못된 보정 0).

    업체 100문항, 기존 44문항, 대조 사례 전부. 새 독립셋은 최종 후보 실행 전까지 보지 않으므로 넣지 않는다.
    """

    FILES = ("evaluation/vendor100/gold.yaml", "evaluation/grounding_v1/holdout_questions.yaml",
             "evaluation/grounding_v2/contrast_questions.yaml")

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
