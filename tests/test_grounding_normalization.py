# -*- coding: utf-8 -*-
"""질문 해석 보강: 운행 상태 조건 읽기, 조건 읽기의 빈틈, 장소 값의 자리 바로잡기.

LLM을 부르지 않는다. 각 규칙은 뜻이 하나로 정해지는 경우만 다루고, 그 밖은 LLM 값을 그대로 둔다.
"""

import unittest
from datetime import date

from geoflow import conditions
from geoflow.errors import PlannerError
from geoflow.grounding import normalize_place_concepts, parse_grounding

REF = date(2026, 9, 25)


def place(name, region="", **extra):
    return {"id": "p", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
            "source": "user", "value": {"name": name, "region": region}, **extra}


class TaxiStatusTest(unittest.TestCase):
    def status(self, question, llm=None):
        factors = {} if llm is None else {"taxi_status": llm}
        record = conditions.reconcile_taxi_status(factors, question)
        return factors.get("taxi_status"), record["action"]

    def test_status_words_before_taxi_or_passage_are_conditions(self):
        self.assertEqual(self.status("광안리 주변의 공차 법인택시 통행량은?"), ("vacant", "filled"))
        self.assertEqual(self.status("법인 실차 택시 통행량"), ("occupied", "filled"))
        self.assertEqual(self.status("개인 대기영업 택시 통행량"), ("stationary", "filled"))
        self.assertEqual(self.status("동성로의 실차 통행량은?"), ("occupied", "filled"))
        self.assertEqual(self.status("빈차 택시 통행량", "occupied"), ("vacant", "corrected"))

    def test_entity_and_measure_words_are_not_conditions(self):
        for question in ("대구 수성구에서 출발한 실차 구간 건수는?", "서울 소속 택시의 최대 공차율은?",
                         "대구에서 출발해 부산에 도착한 실차 중 승차 읍면동 상위 2곳은?",
                         "대구에 도착한 실차의 하차 읍면동"):
            with self.subTest(question=question):
                self.assertEqual(self.status(question), (None, "none"))

    def test_value_without_any_status_word_is_held_unless_no_tool_takes_it(self):
        passage = [{"id": "m", "concept": "AMOUNT", "subtype": "passage_count", "role": "MEASURE"}]
        trip = [{"id": "m", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE"}]
        for concepts, expected in ((passage, ("vacant", "held")), (trip, (None, "removed_no_evidence"))):
            factors = {"taxi_status": "vacant"}
            record = conditions.reconcile_taxi_status(factors, "대구의 택시 통행량은?",
                                                      concepts=concepts)
            self.assertEqual((factors.get("taxi_status"), record["action"]), expected)
        self.assertEqual(self.status("실차 구간 건수는?", "occupied"), ("occupied", "held"))

    def test_multiple_statuses_are_not_guessed(self):
        with self.assertRaises(PlannerError) as caught:
            self.status("공차 택시 통행량과 실차 택시 통행량")
        self.assertEqual(caught.exception.code, "TAXI_STATUS_EXPRESSION_UNSUPPORTED")


class ConditionReaderGapTest(unittest.TestCase):
    def test_scope_literal_digits_are_not_date_cues(self):
        factors = {}
        record = conditions.reconcile_date(
            factors, "휴일 자정부터 오전 4시까지 scope:district:2726000000의 통행량은?", REF)
        self.assertEqual((factors.get("date"), record["action"]), ("holiday", "filled"))

    def test_taxi_type_with_a_status_word_in_between(self):
        for question, value in (("법인 실차 택시 통행량", "corporate"),
                                ("개인 대기영업 택시 통행량", "private")):
            factors = {}
            conditions.reconcile_taxi_type(factors, question)
            self.assertEqual(factors.get("taxi_type"), value)

    def test_payload_reconciliation_touches_only_owned_factors(self):
        payload = {"concepts": [], "factors": {"date": "202310", "dimension": "emd"}}
        fixed, audit = conditions.reconcile_payload(
            payload, "이번 달 법인 실차 택시 통행량", reference_date=REF)
        self.assertEqual(fixed["factors"], {"date": "this_month", "dimension": "emd",
                                            "taxi_type": "corporate", "taxi_status": "occupied"})
        self.assertEqual({c["condition"] for c in audit["corrections"]},
                         {"date", "taxi_type", "taxi_status"})


class DriftGuardTest(unittest.TestCase):
    """prompt 변경 뒤 새로 관측된 형태(개발셋 063·064·066·089)."""

    MEASURE = {"id": "m", "concept": "AMOUNT", "subtype": "operating_days", "role": "MEASURE",
               "source": "implicit"}
    EVENT = {"id": "e", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
             "source": "implicit"}

    def test_redundant_condition_concept_without_subtype_is_dropped(self):
        extra = {"id": "o", "concept": "OBJECT", "subtype": "", "role": "COND", "source": "user",
                 "value": "private"}
        grounding = parse_grounding({"concepts": [extra, self.EVENT, self.MEASURE],
                                     "factors": {"taxi_type": "private"}}, "개인택시 운행 일수")
        self.assertEqual(grounding.factors["taxi_type"], "private")
        with self.assertRaises(PlannerError):   # factor가 없으면 되풀이가 아니므로 거부
            parse_grounding({"concepts": [extra, self.EVENT, self.MEASURE], "factors": {}},
                            "개인택시 운행 일수")

    def test_date_token_written_as_a_factor_name(self):
        grounding = parse_grounding({"concepts": [self.EVENT, self.MEASURE],
                                     "factors": {"holiday": True}}, "휴일 운행 일수")
        self.assertEqual(grounding.factors["date"], "holiday")
        with self.assertRaises(PlannerError) as caught:
            parse_grounding({"concepts": [self.EVENT, self.MEASURE],
                             "factors": {"holiday": True, "date": "weekend"}}, "질문")
        self.assertEqual(caught.exception.code, "UNKNOWN_FACTOR")

class PlaceNormalizationTest(unittest.TestCase):
    def test_empty_name_takes_the_region(self):
        (concept,), notes = normalize_place_concepts([place("", "대구")])
        self.assertEqual(concept["value"], {"name": "대구", "region": ""})
        (concept,), _ = normalize_place_concepts([place("", "부산 초읍동")])
        self.assertEqual(concept["value"], {"name": "초읍동", "region": "부산"})
        self.assertEqual(notes[0]["rule"], "empty_name_region_is_place")

    def test_region_equal_to_name_is_dropped(self):
        (concept,), notes = normalize_place_concepts([place("대구", "대구")])
        self.assertEqual(concept["value"], {"name": "대구", "region": ""})

    def test_grouping_unit_words_are_not_places(self):
        grouped = {"dimension": "emd"}
        concepts, notes = normalize_place_concepts(
            [place("읍면동", attributes={"od_role": "pickup"}), place("전국")], grouped)
        self.assertEqual(concepts, [])
        self.assertEqual([n["rule"] for n in notes], ["non_place_word_dropped"] * 2)
        # 그룹 기준(dimension)이 어디에도 없으면 단위 말 장소를 빼지 않는다. 빼면 "읍면동별
        # 통행량"이 전체 값 하나로 조용히 바뀐다. "전국"은 장소 조건 없음이라 뺀다(grounding_v2).
        concepts, notes = normalize_place_concepts(
            [place("읍면동", attributes={"od_role": "pickup"}), place("전국")])
        self.assertEqual([c["value"]["name"] for c in concepts], ["읍면동"])
        self.assertEqual([n["rule"] for n in notes],
                         ["unit_word_place_kept_no_dimension", "non_place_word_dropped"])
        # 값 없는 장소의 text가 단위 말이면 그룹 기준을 되풀이한 것이다(개발셋 078).
        valueless = {"id": "o", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
                     "source": "implicit", "text": "시군구"}
        self.assertEqual(normalize_place_concepts([valueless], {"dimension": "sigungu"})[0], [])
        self.assertEqual(normalize_place_concepts([valueless])[0], [valueless])
        (concept,), notes = normalize_place_concepts(
            [place("읍면동", "부산", attributes={"od_role": "dropoff"})])
        self.assertEqual(concept["value"], {"name": "부산", "region": ""})
        self.assertEqual(concept["attributes"], {"od_role": "dropoff"})

    def test_ordinary_places_are_untouched(self):
        concepts = [place("어린이대공원", "부산 초읍동"), place("동성로")]
        self.assertEqual(normalize_place_concepts(concepts), (concepts, []))

    def test_records_survive_parsing_and_can_be_turned_off(self):
        payload = {"concepts": [place("", "대구"),
                                {"id": "e", "concept": "EVENT", "subtype": "operation",
                                 "role": "SUPPORT", "source": "implicit"},
                                {"id": "m", "concept": "AMOUNT", "subtype": "revenue",
                                 "role": "MEASURE", "source": "implicit"}],
                   "factors": {}}
        grounding = parse_grounding(payload, "대구 소속 택시 수입")
        self.assertEqual(grounding.to_dict()["normalizations"][0]["rule"],
                         "empty_name_region_is_place")
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(payload, "대구 소속 택시 수입", normalize=False)
        self.assertEqual(caught.exception.code, "INVALID_PLACE")


class ConditionConceptTest(unittest.TestCase):
    def payload(self, concept, factors=None):
        return {"concepts": [
            {"id": "e", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
             "source": "implicit"},
            {"id": "m", "concept": "PROPORTION", "subtype": "active_taxi_ratio",
             "role": "MEASURE", "source": "implicit"}, concept], "factors": factors or {}}

    def test_taxi_type_written_as_object_becomes_a_factor(self):
        concept = {"id": "t", "concept": "OBJECT", "subtype": "private", "role": "COND",
                   "source": "user"}
        grounding = parse_grounding(self.payload(concept), "지난 주 개인택시의 평균 가동률은?")
        self.assertEqual(grounding.factors["taxi_type"], "private")
        self.assertEqual(grounding.normalizations[0]["rule"], "condition_concept_to_factor")

    def test_condition_name_as_subtype(self):
        valued = {"id": "t", "concept": "LOCATION", "subtype": "taxi_type", "role": "COND",
                  "source": "user", "value": "private"}
        self.assertEqual(parse_grounding(self.payload(valued), "개인택시 가동률").factors,
                         {"taxi_type": "private"})
        empty = {"id": "t", "concept": "OBJECT", "subtype": "taxi_type", "role": "COND",
                 "source": "user"}
        grounding = parse_grounding(self.payload(empty, {"taxi_type": "corporate"}), "법인택시 가동률")
        self.assertEqual(grounding.factors["taxi_type"], "corporate")
        self.assertEqual(grounding.normalizations[0]["rule"], "redundant_condition_concept_dropped")
        with self.assertRaises(PlannerError):   # 값이 어디에도 없으면 조건을 잃지 않도록 거부
            parse_grounding(self.payload(empty), "법인택시 가동률")

    def test_conflicting_values_are_not_chosen(self):
        concept = {"id": "t", "concept": "OBJECT", "subtype": "private", "role": "COND",
                   "source": "user"}
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(self.payload(concept, {"taxi_type": "corporate"}), "질문")
        self.assertEqual(caught.exception.code, "INVALID_SUBTYPE")


if __name__ == "__main__":
    unittest.main()
