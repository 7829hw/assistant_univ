# -*- coding: utf-8 -*-
"""기간 조건과 그룹 기준과 집계 구간을 어휘가 구분하는지 못박는다.

"주말"(기간 조건), "요일별"(그룹 기준), "주 단위"(집계 구간)는 한국어로는
모두 '주'를 포함하지만 계약에서는 서로 다른 factor다. 값 공간이 겹치지
않아야 잘못 넣었을 때 조용히 통과하지 않는다.
"""

import os
import unittest

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError, PlannerError
from geoflow.factors import FACTOR_SPECS
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from geoflow.operator_registry import Operator, get_operator

SPEED = [
    {"id": "p", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
     "source": "user", "value": "대구"},
    {"id": "pa", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
     "source": "implicit"},
    {"id": "s", "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE",
     "source": "implicit"},
]
REVENUE = [
    {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
     "source": "implicit"},
    {"id": "r", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
     "source": "implicit"},
]


def ground(concepts, factors, question="질문"):
    return parse_grounding({"concepts": concepts, "factors": factors}, question)


class TimeVocabularyBoundaryTest(unittest.TestCase):
    def test_value_spaces_do_not_overlap(self):
        """세 factor의 값 공간이 겹치면 잘못 넣어도 걸리지 않는다."""
        dimension = FACTOR_SPECS["dimension"].values
        bucket = FACTOR_SPECS["bucket"].values
        self.assertFalse(dimension & bucket)
        for unit in ("week", "month"):
            self.assertIn(unit, bucket)
            self.assertNotIn(unit, dimension)

    def test_date_accepts_named_periods(self):
        pattern = FACTOR_SPECS["date"].pattern
        for value in ("weekend", "weekday", "holiday", "last_month", "20260530"):
            with self.subTest(value=value):
                self.assertTrue(pattern.match(value))
        for value in ("week", "dayofweek", "주말"):
            with self.subTest(value=value):
                self.assertIsNone(pattern.match(value))

    def test_dimension_meaning_says_it_groups_rather_than_filters(self):
        meaning = FACTOR_SPECS["dimension"].meaning
        self.assertTrue(meaning)
        self.assertIn("그룹", meaning)


class TimeExpressionGroundingTest(unittest.TestCase):
    """세 표현이 각각 제 factor로 들어가고 Tool 인자까지 간다."""

    def setUp(self):
        self.composer = MacroComposer(MacroLibrary.from_directory())

    def test_weekend_is_a_date_condition(self):
        grounding = ground(SPEED, {"date": "weekend", "aggregation": "avg"},
                           "주말 대구 지역의 평균 속도는?")
        self.assertEqual(grounding.factors["date"], "weekend")
        self.assertNotIn("dimension", grounding.factors)
        plan = self.composer.compose(grounding)
        self.assertEqual(plan.transformations[-1].params["date"], "weekend")

    def test_day_of_week_is_a_grouping_dimension(self):
        grounding = ground(REVENUE, {"dimension": "dayofweek"},
                           "요일별 택시 수입은?")
        plan = self.composer.compose(grounding)
        self.assertEqual(plan.transformations[-1].params["dimension"], "dayofweek")

    def test_week_unit_is_a_bucket_with_a_rollup(self):
        grounding = ground(REVENUE,
                           {"bucket": "week", "rollup": "avg", "aggregation": "avg"},
                           "주 단위로 집계한 택시 수입의 평균은?")
        params = self.composer.compose(grounding).transformations[-1].params
        self.assertEqual(params["bucket"], "week")
        self.assertEqual(params["rollup"], "avg")

    def test_month_unit_is_a_bucket_with_a_rollup(self):
        grounding = ground(REVENUE,
                           {"bucket": "month", "rollup": "max", "aggregation": "max"},
                           "월 단위로 집계한 수입의 최대값은?")
        params = self.composer.compose(grounding).transformations[-1].params
        self.assertEqual(params["bucket"], "month")
        self.assertEqual(params["rollup"], "max")


class TimeExpressionMisplacementIsRejectedTest(unittest.TestCase):
    def test_time_unit_as_dimension_is_rejected(self):
        """"주말"의 '주'를 그룹 기준으로 읽은 형태. 실측에서 나온 오답이다."""
        for value in ("week", "month"):
            with self.subTest(value=value):
                with self.assertRaises(PlannerError) as caught:
                    ground(SPEED, {"dimension": value})
                self.assertEqual(caught.exception.code, "INVALID_FACTOR")

    def test_named_period_as_dimension_is_rejected(self):
        with self.assertRaises(PlannerError) as caught:
            ground(SPEED, {"dimension": "weekend"})
        self.assertEqual(caught.exception.code, "INVALID_FACTOR")

    def test_named_period_as_bucket_is_rejected(self):
        with self.assertRaises(PlannerError) as caught:
            ground(REVENUE, {"bucket": "weekend", "rollup": "avg"})
        self.assertEqual(caught.exception.code, "INVALID_FACTOR")

    def test_grouping_key_as_bucket_is_rejected(self):
        with self.assertRaises(PlannerError) as caught:
            ground(REVENUE, {"bucket": "dayofweek", "rollup": "avg"})
        self.assertEqual(caught.exception.code, "INVALID_FACTOR")

    def test_bucket_without_rollup_is_still_caught(self):
        """짝 검사는 어휘가 아니라 합성 단계의 계약이다."""
        grounding = ground(REVENUE, {"bucket": "month", "aggregation": "max"})
        with self.assertRaises(GeoFlowError) as caught:
            MacroComposer(MacroLibrary.from_directory()).compose(grounding)
        self.assertEqual(caught.exception.code, "INVALID_FACTOR_COMBINATION")

    def test_operator_enum_agrees_with_the_factor_source(self):
        """값 범위가 두 곳에 적혀 있으므로 어긋나지 않는지 확인한다."""
        spec = get_operator(Operator.OPERATION_METRIC)
        self.assertEqual(sorted(spec.param_enums["bucket"]),
                         sorted(FACTOR_SPECS["bucket"].values))


if __name__ == "__main__":
    unittest.main()
