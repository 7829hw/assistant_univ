# -*- coding: utf-8 -*-
"""운행 상태(taxi_status) 계약 설명이 실행 계약과 같은지, 요구된 상태가 버려지지 않고 그 이유로 멈추는지 본다.

모델을 부르지 않는다. 설명(prompt·factor 의미)은 "taxi_status를 받는 측정값은 통행량뿐"이라고 말한다. 그 사실이
operator registry와 어긋나면 이 테스트가 깨진다.
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluate_vendor100 import REFERENCE_DATE, _GoldPlanner, _executor  # noqa: E402
from geoflow.factors import FACTOR_SPECS  # noqa: E402
from geoflow.operator_registry import OPERATORS  # noqa: E402
from geoflow.planner import GeoFlowPlanner  # noqa: E402


def _measures(spec):
    return {subtype for _, subtype in spec.output.allowed} if spec.output else set()


def _run(payload, question):
    from geoflow.composer import MacroComposer
    from geoflow.pipeline import GeoFlowPipeline

    pipeline = GeoFlowPipeline(planner=_GoldPlanner(payload), composer=MacroComposer(),
                               tool_executor=_executor(), clock=lambda: REFERENCE_DATE)
    return pipeline.run(question)


def _trip(factors, place=("수성구", "대구", "pickup")):
    name, region, role = place
    return {"concepts": [
        {"id": "p", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND", "source": "user",
         "value": {"name": name, "region": region}, "attributes": {"od_role": role}},
        {"id": "e", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT", "source": "implicit"},
        {"id": "m", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE", "source": "implicit"}],
        "factors": factors}


class StatusContractTest(unittest.TestCase):
    def test_only_passage_count_consumes_taxi_status(self):
        consuming = set().union(*(_measures(spec) for spec in OPERATORS.values() if "taxi_status" in spec.params))
        self.assertEqual(consuming, {"passage_count"})

    def test_the_description_leaves_executability_to_the_program(self):
        """요구된 상태는 측정값과 관계없이 적고, 계산 가능 여부는 프로그램이 판단한다고 말한다.

        어느 측정값이 받는지(실행 가능성)는 모델에게 판단 근거로 주지 않는다. T1에서 그 문장을 보고 모델이
        grounding 대신 unsupported를 냈다(evaluation/grounding_v10).
        """
        meaning = FACTOR_SPECS["taxi_status"].meaning
        self.assertIn("측정값과 관계없이 적는다", meaning)
        self.assertNotIn("뿐", meaning)
        self.assertNotIn("지원 불가", meaning)
        prompt = GeoFlowPlanner(client=None).system_prompt()
        self.assertIn("계산할\n  수 있는지와 멈출 이유는 프로그램이 판단합니다", prompt)
        self.assertIn("조건을 빼거나 바꾸지 않습니다", prompt)
        self.assertNotIn('"실차 구간 건수"만 AMOUNT/trip_count', prompt)
        self.assertNotIn("bucket과 함께 쓸 수 없다", prompt)

    def test_a_required_status_on_trip_stops_with_that_reason(self):
        for status in ("vacant", "stationary", "occupied"):
            with self.subTest(status=status):
                run = _run(_trip({"date": "last_month", "taxi_status": status}), "q")
                self.assertEqual(run.outcome, "unsupported")
                record = run.to_dict()["error"]
                self.assertEqual(record["code"], "UNCONSUMED_CONDITION")
                self.assertIn("taxi_status", json.dumps(record, ensure_ascii=False))

    def test_trip_without_a_status_is_answered(self):
        run = _run(_trip({"date": "last_month"}), "q")
        self.assertEqual(run.outcome, "answered")

    def test_a_status_on_passage_count_reaches_the_call(self):
        payload = {"concepts": [
            {"id": "p", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND", "source": "user",
             "value": {"name": "동성로", "region": ""}},
            {"id": "e", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT", "source": "implicit"},
            {"id": "m", "concept": "AMOUNT", "subtype": "passage_count", "role": "MEASURE", "source": "implicit"}],
            "factors": {"date": "20260924", "taxi_status": "vacant"}}
        run = _run(payload, "q")
        self.assertEqual(run.outcome, "answered")
        calls = [hop for hop in run.hop_log if hop.get("phase") == "tool" and hop["tool"] == "get_passage_count"]
        self.assertEqual(calls[-1]["arguments"].get("taxi_status"), "vacant")


if __name__ == "__main__":
    unittest.main()
