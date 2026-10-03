# -*- coding: utf-8 -*-
"""축별 채점(evaluate_vendor100.score_semantic·execution_path)이 실패한 조회를 구분하되 잘못된 장소·조건을
통과시키지 않는지 본다. 모델을 부르지 않는다. 장소 scope는 mock 제공자 gazetteer 값이다."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluate_vendor100 import execution_path, parse_calls, score, score_semantic  # noqa: E402

SUSEONG = "scope:district:2726000000"     # 대구 수성구
JUNG_DAEGU = "scope:district:2723000000"  # 대구 중구
BUSANJIN = "scope:district:2623000000"    # 부산 부산진구
NOT_FOUND = {"status": "ERROR", "error_code": "NOT_FOUND", "message": "없음"}


def item(gold_text, question="q"):
    return {"id": "t", "question": question, "expected_outcome": "answered",
            "gold": parse_calls(gold_text)}


def lookup(name, result, region=None, vicinity=False):
    args = {"name": name, "include_vicinity": vicinity, **({"region": region} if region else {})}
    return {"tool": "get_place_scope", "args": args, "result": result}


def observed(calls, answer):
    return {"outcome": "answered", "calls": calls, "final_answer": answer}


FARE = item("get_place_scope(name=부산진구)\n"
            "get_trip_metrics(scope=$place.scope, metric=fare, aggregation=min, date=this_year)")


def fare_call(scope, value=12000):
    return {"tool": "get_trip_metrics", "result": value,
            "args": {"scope": scope, "metric": "fare", "aggregation": "min", "date": "this_year"}}


class SemanticAxisTest(unittest.TestCase):
    def test_failed_lookup_discarded_before_a_correct_final_call(self):
        # m31 유형: 첫 조회가 실패했고, 고친 조회의 scope로 맞는 호출을 했다.
        obs = observed([lookup("진구", NOT_FOUND, "부산"), lookup("부산진구", BUSANJIN),
                        fare_call(BUSANJIN)], "최소 요금: 12,000")
        self.assertEqual(score(FARE, obs)[0], "answered_mismatch")   # v3는 실패 조회를 센다
        self.assertEqual(score_semantic(FARE, obs)[0], "match")
        path = execution_path(FARE, obs)
        self.assertEqual(path["lookup_kinds"], ["failed:NOT_FOUND", "used"])
        self.assertFalse(path["clean"])

    def test_wrong_place_used_in_analysis_is_wrong_even_if_the_number_matches(self):
        # 잘못된 장소(대구 중구)의 scope를 분석에 썼다. mock 값이 같아 답변 숫자는 같다.
        obs = observed([lookup("중구", JUNG_DAEGU, "대구"), fare_call(JUNG_DAEGU)], "최소 요금: 12,000")
        category, checks = score_semantic(FARE, obs)
        self.assertEqual(category, "answered_mismatch")
        self.assertEqual(checks["arg_mismatches"], [["scope", BUSANJIN, JUNG_DAEGU]])

    def test_wrong_place_looked_up_but_discarded_stays_on_the_path_axis(self):
        obs = observed([lookup("중구", JUNG_DAEGU, "대구"), lookup("부산진구", BUSANJIN),
                        fare_call(BUSANJIN)], "최소 요금: 12,000")
        self.assertEqual(score_semantic(FARE, obs)[0], "match")
        self.assertEqual(execution_path(FARE, obs)["lookup_kinds"], ["discarded", "used"])

    def test_same_place_with_a_different_region_spelling_is_the_same_place(self):
        # m10 유형: 질문에 없는 상위 지역을 붙였지만 제공자가 같은 scope로 푼다.
        obs = observed([lookup("부산진구", BUSANJIN, "부산"), fare_call(BUSANJIN)], "최소 요금: 12,000")
        self.assertEqual(score(FARE, obs)[0], "answered_mismatch")
        self.assertEqual(score_semantic(FARE, obs)[0], "match")

    def test_vicinity_is_compared_although_the_scope_value_is_the_same(self):
        gold = item("get_place_scope(name=수성구, region=대구, include_vicinity=true)\n"
                    "get_trip_metrics(scope=$place.scope, metric=fare, aggregation=min, date=this_year)")
        obs = observed([lookup("수성구", SUSEONG, "대구", vicinity=False), fare_call(SUSEONG)],
                       "최소 요금: 12,000")
        category, checks = score_semantic(gold, obs)
        self.assertEqual(category, "answered_mismatch")
        self.assertFalse(checks["vicinity_ok"])

    def test_a_scope_that_no_lookup_produced_is_not_accepted(self):
        obs = observed([lookup("진구", NOT_FOUND, "부산"), fare_call(BUSANJIN)], "최소 요금: 12,000")
        category, checks = score_semantic(FARE, obs)
        self.assertEqual(category, "answered_mismatch")
        self.assertFalse(checks["scope_from_lookup"])

    def test_wrong_condition_with_the_same_number_is_wrong(self):
        call = fare_call(BUSANJIN)
        call["args"]["aggregation"] = "max"
        obs = observed([lookup("부산진구", BUSANJIN), call], "최대 요금: 12,000")
        self.assertEqual(score_semantic(FARE, obs)[0], "answered_mismatch")

    def test_user_literal_scope_needs_no_lookup(self):
        gold = item(f"get_trip_metrics(scope={BUSANJIN}, metric=fare, aggregation=min, date=this_year)")
        obs = observed([fare_call(BUSANJIN)], "최소 요금: 12,000")
        self.assertEqual(score_semantic(gold, obs)[0], "match")
        self.assertTrue(execution_path(gold, obs)["clean"])

    def test_od_ends_are_compared_by_scope(self):
        gold = item("get_place_scope(name=부산진구)\nget_place_scope(name=중구, region=대구)\n"
                    "get_trip_count(scope_pickup=$pickup.scope, scope_dropoff=$dropoff.scope, date=last_month)")
        swapped = {"tool": "get_trip_count", "result": {"count": 20},
                   "args": {"scope_pickup": JUNG_DAEGU, "scope_dropoff": BUSANJIN, "date": "last_month"}}
        obs = observed([lookup("부산진구", BUSANJIN), lookup("중구", JUNG_DAEGU, "대구"), swapped], "20건")
        self.assertEqual(score_semantic(gold, obs)[0], "answered_mismatch")


if __name__ == "__main__":
    unittest.main()
