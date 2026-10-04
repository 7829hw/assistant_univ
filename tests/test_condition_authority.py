# -*- coding: utf-8 -*-
"""조건 계층의 채움 권한: 질문 표현으로 조건을 채우는 것은 그 값이 측정값을 실제로 제한할 때다.

측정값 정의가 이미 고정한 값(operator 계약 ``inherent_conditions``)은 채우지 않는다. 실제 요구 조건(공차·대기영업,
Tool이 받지 않는 택시 유형)은 지금처럼 채워 보존하고 합성이 그 이유로 멈춘다. 모델이 적은 값은 지우지 않는다.
모델을 부르지 않는다(응답을 정해 둔 client).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from geoflow.conditions import fixed_by_measure  # noqa: E402
from geoflow.operator_registry import OPERATORS  # noqa: E402
from test_factor_correction import plan, run, tool_args  # noqa: E402


def place(name, region, role=None):
    concept = {"id": "p", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND", "source": "user",
               "value": {"name": name, "region": region}}
    if role:
        concept["attributes"] = {"od_role": role}
    return concept


TRIP = [{"id": "e", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT", "source": "implicit"},
        {"id": "m", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE", "source": "implicit"}]
PASSAGE = [{"id": "e", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT", "source": "implicit"},
           {"id": "m", "concept": "AMOUNT", "subtype": "passage_count", "role": "MEASURE", "source": "implicit"}]
FARE = [{"id": "e", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT", "source": "implicit"},
        {"id": "m", "concept": "AMOUNT", "subtype": "fare", "role": "MEASURE", "source": "implicit"}]


def actions(result):
    return result.to_dict()["condition_audit"]


class FillAuthorityTest(unittest.TestCase):
    def test_the_contract_declares_what_trip_fixes(self):
        fixed = {spec.tool_name: spec.inherent_conditions for spec in OPERATORS.values() if spec.inherent_conditions}
        self.assertEqual(fixed, {"get_trip_count": {"taxi_status": "occupied"},
                                 "get_trip_metrics": {"taxi_status": "occupied"}})
        self.assertEqual(fixed_by_measure(TRIP, "taxi_status"), "occupied")
        self.assertIsNone(fixed_by_measure(PASSAGE, "taxi_status"))
        self.assertIsNone(fixed_by_measure(TRIP, "taxi_type"))

    def test_restating_the_trip_definition_is_not_added_as_a_condition(self):
        # s27·s28 유형: 모델은 상태를 적지 않았다. "실차 택시"는 대상(손님을 태운 운행)을 다시 말한 것이다.
        result, _ = run("지난주 부산진구에서 실차 택시를 타고 출발한 운행은 몇 건이야?",
                        plan({"date": "last_week"}, [place("부산진구", "", "pickup"), *TRIP]))
        self.assertEqual(result.outcome, "answered")
        self.assertNotIn("taxi_status", tool_args(result))
        record = actions(result)["taxi_status"]
        self.assertEqual((record["action"], record["basis"]), ("not_filled", "value_fixed_by_measure_definition"))

    def test_a_real_status_requirement_on_trip_is_still_filled_and_stops(self):
        for question, where, date, value in (
                ("지난달 공차 택시가 대구 수성구에서 태운 손님은 몇 건이야?", ("수성구", "대구"), "last_month", "vacant"),
                ("어제 대기영업 택시가 동대구역에서 출발한 운행은 몇 건이야?", ("동대구역", ""), "20260924", "stationary")):
            with self.subTest(value=value):
                result, _ = run(question, plan({"date": date}, [place(*where, "pickup"), *TRIP]))
                self.assertEqual(result.outcome, "unsupported")
                error = result.to_dict()["error"]
                self.assertEqual(error["code"], "UNCONSUMED_CONDITION")
                self.assertIn("taxi_status", error["detail"])
                self.assertEqual(actions(result)["taxi_status"]["value"], value)

    def test_a_taxi_type_the_measure_does_not_take_is_still_filled_and_stops(self):
        result, _ = run("올해 법인택시가 받은 요금의 평균은?", plan({"date": "this_year", "aggregation": "avg"}, FARE))
        self.assertEqual(result.outcome, "unsupported")
        self.assertIn("taxi_type", result.to_dict()["error"]["detail"])

    def test_a_status_on_passage_count_is_still_filled(self):
        result, _ = run("어제 동성로를 지나간 실차 택시 통행량은?",
                        plan({"date": "20260924"}, [place("동성로", ""), *PASSAGE]))
        self.assertEqual(result.outcome, "answered")
        self.assertEqual(tool_args(result).get("taxi_status"), "occupied")

    def test_a_value_the_model_wrote_is_not_deleted(self):
        # 모델이 trip에 occupied를 적으면 지우지 않는다. 받는 변환이 없어 지금처럼 멈춘다.
        result, _ = run("지난달 대구 수성구에서 출발한 실차 건수는?",
                        plan({"date": "last_month", "taxi_status": "occupied"},
                             [place("수성구", "대구", "pickup"), *TRIP]))
        self.assertEqual(result.outcome, "unsupported")
        self.assertEqual(result.to_dict()["error"]["code"], "UNCONSUMED_CONDITION")


if __name__ == "__main__":
    unittest.main()
