# -*- coding: utf-8 -*-
"""Partial Grounding: 생략된 구조 필드(id, concept, role, source)를 parser가 ontology에서 채운다.

LLM을 부르지 않는다. 채운 결과가 같은 의미의 Full Grounding과 같은 실행 계획이 되는지, Full Grounding은
그대로 통과하는지 확인한다.
"""

import copy
import unittest
from datetime import date

from geoflow import providers
from geoflow.compiler import compile_plan
from geoflow.composer import MacroComposer
from geoflow.errors import CompositionError, PlannerError
from geoflow.grounding import complete_grounding_payload, parse_grounding
from geoflow.pipeline import GeoFlowPipeline
from tests.test_geoflow import ScriptedClient, new_tool_executor, planner_response

QUESTION = "지난달 동성로에서 평균 속도를 알려줘."
PARTIAL = {"concepts": [{"subtype": "place", "value": {"name": "동성로", "region": ""}},
                        {"subtype": "speed"}],
           "factors": {"date": "last_month", "aggregation": "avg"}}
FULL = {"concepts": [{"id": "place_1", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
                      "source": "user", "value": {"name": "동성로", "region": ""}},
                     {"id": "passage", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
                      "source": "implicit"},
                     {"id": "speed", "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE",
                      "source": "implicit"}],
        "factors": {"date": "last_month", "aggregation": "avg"}}


def shape(grounding):
    """id를 뺀 개념 구조와 factor."""
    concepts = sorted((item.concept.value, item.subtype, item.role.value, item.source.value,
                       repr(item.value), repr(sorted(item.attributes.items())))
                      for item in grounding.concepts)
    return concepts, grounding.factors


def steps(payload, question):
    plan = MacroComposer().compose(parse_grounding(copy.deepcopy(payload), question))
    return [(step.tool_name, {key: value for key, value in step.arguments.items()
                              if isinstance(value, (str, int, bool))})
            for step in compile_plan(plan).steps]


class CompletionTest(unittest.TestCase):
    def test_structural_fields_are_filled_from_ontology(self):
        grounding = parse_grounding(copy.deepcopy(PARTIAL), QUESTION)
        by_subtype = {item.subtype: item for item in grounding.concepts}
        place, speed = by_subtype["place"], by_subtype["speed"]
        self.assertEqual((place.concept.value, place.role.value, place.source.value, place.id),
                         ("LOCATION", "SUBCOND", "user", "place_1"))
        self.assertEqual((speed.concept.value, speed.role.value, speed.source.value, speed.id),
                         ("AMOUNT", "MEASURE", "implicit", "speed_1"))
        self.assertEqual(grounding.normalizations[0]["rule"], "partial_grounding_completed")

    def test_scope_and_valueless_place_roles(self):
        completed = complete_grounding_payload({"concepts": [
            {"subtype": "scope", "value": "scope:edge:1742"}, {"subtype": "place"},
            {"subtype": "trip"}]})["concepts"]
        self.assertEqual([(item["role"], item["source"]) for item in completed],
                         [("COND", "user"), ("MEASURE", "implicit"), ("SUPPORT", "implicit")])

    def test_full_payload_is_returned_unchanged(self):
        notes = []
        self.assertIs(complete_grounding_payload(FULL, notes), FULL)
        self.assertEqual(notes, [])

    def test_generated_ids_do_not_collide_with_given_ids(self):
        completed = complete_grounding_payload({"concepts": [
            {"id": "place_1", "subtype": "place", "value": {"name": "대구", "region": ""}},
            {"subtype": "place", "value": {"name": "부산", "region": ""}}, {"subtype": "trip_count"}]})
        self.assertEqual([item["id"] for item in completed["concepts"]],
                         ["place_1", "place_2", "trip_count_1"])

    def test_given_values_are_not_corrected(self):
        """적힌 값은 고치지 않는다. concept이 subtype과 어긋나면 기존 검사가 거부한다."""
        with self.assertRaises(PlannerError) as caught:
            parse_grounding({"concepts": [{"concept": "EVENT", "subtype": "speed"}]}, "속도")
        self.assertEqual(caught.exception.code, "INVALID_SUBTYPE")
        extent = parse_grounding({"concepts": [
            {"subtype": "place", "role": "EXTENT", "value": {"name": "대구", "region": ""}},
            {"subtype": "fare"}]}, "대구시의 평균 택시 요금은?")
        self.assertEqual(extent.concepts[0].role.value, "EXTENT")

    def test_unknown_subtype_is_not_guessed(self):
        with self.assertRaises(PlannerError) as caught:
            parse_grounding({"concepts": [{"subtype": "fuel"}]}, "연료 소비량")
        self.assertEqual(caught.exception.code, "INVALID_CONCEPT")

    def test_condition_written_as_concept_without_concept_moves_to_factor(self):
        """조건 값(private)은 어느 core concept의 subtype도 아니다. concept이 없어도 factor로 옮긴다."""
        for raw in ({"subtype": "private"}, {"subtype": "", "value": "corporate"}):
            with self.subTest(raw=raw):
                expected = "private" if raw["subtype"] else "corporate"
                factors = {} if raw["subtype"] else {"taxi_type": "corporate"}
                grounding = parse_grounding({"concepts": [raw, {"subtype": "revenue"}],
                                             "factors": factors}, "개인택시 수입")
                self.assertEqual(grounding.factors.get("taxi_type"), expected)
                self.assertEqual([item.subtype for item in grounding.concepts], ["revenue"])

    def test_partial_and_full_ground_to_the_same_structure(self):
        partial = parse_grounding(copy.deepcopy(PARTIAL), QUESTION)
        full = parse_grounding(copy.deepcopy({**FULL, "concepts": [
            item for item in FULL["concepts"] if item["concept"] != "EVENT"]}), QUESTION)
        self.assertEqual(shape(partial), shape(full))


class SamePlanTest(unittest.TestCase):
    """support EVENT는 parser가 아니라 composer가 이미 만든다. partial도 같은 Tool 호출이 된다."""

    def test_speed(self):
        self.assertEqual(steps(PARTIAL, QUESTION), steps(FULL, QUESTION))

    def test_od_trip_count(self):
        question = "동대구역에서 출발해 동성로에 도착한 실차 건수는?"
        places = [{"subtype": "place", "value": {"name": "동대구역", "region": ""},
                   "attributes": {"od_role": "pickup"}},
                  {"subtype": "place", "value": {"name": "동성로", "region": ""},
                   "attributes": {"od_role": "dropoff"}}]
        full = {"concepts": [{"id": f"p{index}", "concept": "LOCATION", "role": "SUBCOND",
                              "source": "user", **item} for index, item in enumerate(places)]
                + [{"id": "trip", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT"},
                   {"id": "m", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE"}]}
        partial = {"concepts": places + [{"subtype": "trip_count"}]}
        self.assertEqual(steps(partial, question), steps(full, question))
        self.assertEqual([tool for tool, _ in steps(partial, question)],
                         ["get_place_scope", "get_place_scope", "get_trip_count"])


class EventRefusalRegressionTest(unittest.TestCase):
    """evaluation/partial_grounding/regression_event_refusal.yaml: 잘못된 EVENT가 거부를 만들던 답해야 할 문항.

    full에서 모델이 고른 사건(fare+operation)은 operator가 없어 거부된다. partial은 사건을 적지 않으므로
    측정값에서 정해지는 사건으로 답한다. 이 질문은 거부되어야 할 이유가 없다(gold expected_outcome answered).
    """

    QUESTION = "지난해 부산 소속 택시의 요금 중간값은?"
    PLACE = {"subtype": "place", "value": {"name": "부산", "region": ""}}
    FACTORS = {"date": "last_year", "aggregation": "med"}

    def test_wrong_event_in_full_output_is_what_refused(self):
        full = {"concepts": [{**self.PLACE, "id": "p", "concept": "LOCATION", "role": "SUBCOND", "source": "user"},
                             {"id": "e", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT"},
                             {"id": "m", "concept": "AMOUNT", "subtype": "fare", "role": "MEASURE"}],
                "factors": self.FACTORS}
        with self.assertRaises(CompositionError) as caught:
            steps(full, self.QUESTION)
        self.assertEqual(caught.exception.code, "NO_OPERATOR")

    def test_partial_output_answers_with_the_measure_event(self):
        partial = {"concepts": [self.PLACE, {"subtype": "fare"}], "factors": self.FACTORS}
        self.assertEqual(steps(partial, self.QUESTION)[-1],
                         ("get_trip_metrics", {"aggregation": "med", "date": "last_year", "metric": "fare"}))


class PlannerPathTest(unittest.TestCase):
    """조건 대조(condition_check)는 parse 전에 concept·role·source를 읽는다. partial도 같은 답이 된다."""

    def run_payload(self, payload):
        pipeline = GeoFlowPipeline.create(
            client=ScriptedClient([planner_response(payload)]), tool_executor=new_tool_executor(),
            clock=lambda: date(2026, 9, 25), condition_check=True, condition_notes=False,
            execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY))
        run = pipeline.run(QUESTION).to_dict()
        trace = (run.get("execution") or {}).get("trace") or []
        return run["outcome"], [(hop["tool"], hop["arguments"]) for hop in trace
                                if hop.get("phase") == "tool"]

    def test_partial_output_answers_like_full_output(self):
        full = self.run_payload(FULL)
        self.assertEqual(full[0], "answered")
        self.assertEqual([tool for tool, _ in full[1]], ["get_place_scope", "get_passage_metrics"])
        self.assertEqual(self.run_payload(PARTIAL), full)


if __name__ == "__main__":
    unittest.main()
