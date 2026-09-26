# -*- coding: utf-8 -*-
"""두 단계 집계의 의미 graph → 실행 계획 → 실행 → 답변을 정답 grounding으로 검증한다.

LLM을 부르지 않는다. grounding은 질문의 뜻을 사람이 적은 것이고, 그 뒤의 합성·검증·
lowering·실행·답변이 질문과 같은 계산을 하는지만 본다.

고정 자료는 구간마다 표본 수와 값이 다르게 골랐다. 서로 다른 계산이 우연히 같은
답을 내지 않게 하기 위해서다. 기대값은 아래 표에서 손으로 계산해 상수로 적었다.
구현 코드로 계산하지 않는다.

2026년 8월(기준일 2026-09-25의 "지난달"). 8/1은 토요일이다. 월요일 시작 주로 나누면

    주  기간                 대구·개인 수입            n  합계  평균
    W1  20260801-20260802   100, 50                 2   150   75    (부분 주)
    W2  20260803-20260809   300                     1   300   300
    W3  20260810-20260816   90, 90, 90, 90          4   360   90
    W4  20260817-20260823   200, 20                 2   220   110
    W5  20260824-20260830   10, 10, 10              3   30    10
    W6  20260831-20260831   40                      1   40    40    (부분 주)
                                                    13  1100

    주별 합계의 평균   = 1100 / 6        = 183.333…
    주별 합계의 최댓값 = 360 (W3)
    주별 평균의 최댓값 = 300 (W2)       ← 합계가 가장 큰 주(W3)와 다르다
    주별 평균의 평균   = 625 / 6        = 104.1666…
    전체 평균          = 1100 / 13      = 84.615…  ← 평균의 평균과 다르다

조건이 빠지면 값이 달라지도록 섞인 자료를 둔다.

    대구·법인 8/5 5000, 8/25 700   → taxi_type을 잃으면 W2 합계가 5300
    부산·개인 8/12 7000            → scope를 잃으면 W3 합계가 7360
    대구·개인 7/31 9999, 9/1 8888  → 기간을 잃으면 값이 바뀐다
"""

import json
import os
import unittest
from datetime import date, timedelta

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from agent_graph import extract_scopes  # noqa: E402

from geoflow import validator as geoflow_validator  # noqa: E402
from geoflow.answer import format_answer  # noqa: E402
from geoflow.compiler import compile_plan, verify_lowering  # noqa: E402
from geoflow.composer import MacroComposer  # noqa: E402
from geoflow.errors import (  # noqa: E402
    CompilerError,
    CompositionError,
    GeoFlowError,
    PlannerError,
)
from geoflow.executor import STATUS_OK, execute_plan  # noqa: E402
from geoflow.grounding import parse_grounding  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline, Stage  # noqa: E402
from geoflow.planner import PlannerOutput  # noqa: E402
from geoflow.repair import decide as decide_repair  # noqa: E402
from geoflow.types import (  # noqa: E402
    ConceptNode,
    CoreConcept,
    FunctionalRole,
    GeoFlowPlan,
    NodeSource,
    Transformation,
    ValueRef,
)
from geoflow.validator import Rule  # noqa: E402

REFERENCE = date(2026, 9, 25)
DAEGU = "scope:district:2700000000"
BUSAN = "scope:district:2600000000"

W1, W2, W3 = "20260801-20260802", "20260803-20260809", "20260810-20260816"
W4, W5, W6 = "20260817-20260823", "20260824-20260830", "20260831-20260831"
AUGUST_WEEKS = [W1, W2, W3, W4, W5, W6]

#: (날짜, taxi_type, scope, 수입)
REVENUE = [
    ("20260801", "private", DAEGU, 100), ("20260802", "private", DAEGU, 50),
    ("20260803", "private", DAEGU, 300),
    ("20260810", "private", DAEGU, 90), ("20260811", "private", DAEGU, 90),
    ("20260812", "private", DAEGU, 90), ("20260813", "private", DAEGU, 90),
    ("20260817", "private", DAEGU, 200), ("20260818", "private", DAEGU, 20),
    ("20260824", "private", DAEGU, 10), ("20260825", "private", DAEGU, 10),
    ("20260826", "private", DAEGU, 10),
    ("20260831", "private", DAEGU, 40),
    # 조건을 잃으면 섞여 들어오는 자료
    ("20260805", "corporate", DAEGU, 5000), ("20260825", "corporate", DAEGU, 700),
    ("20260812", "private", BUSAN, 7000),
    ("20260731", "private", DAEGU, 9999), ("20260901", "private", DAEGU, 8888),
]

#: (날짜, scope, 속도). get_passage_metrics는 bucket을 받지 않는다.
#:   W1 30 | W2 40, 20 → 30 | W3 50 | W4 10, 30 → 20 | W5 25 | W6 60
#:   주별 평균의 최댓값 = 60 (W6, 부분 주), 전체 평균 = 265 / 8 = 33.125
SPEED = [
    ("20260801", DAEGU, 30), ("20260803", DAEGU, 40), ("20260804", DAEGU, 20),
    ("20260812", DAEGU, 50), ("20260820", DAEGU, 10), ("20260821", DAEGU, 30),
    ("20260825", DAEGU, 25), ("20260831", DAEGU, 60),
    ("20260812", BUSAN, 999),
]


def _day(text):
    return date(int(text[:4]), int(text[4:6]), int(text[6:]))


def _reduce(values, how):
    """fake TIMS의 집계. 제품 코드와 따로 적는다."""
    if not values:
        return None
    if how == "sum":
        return sum(values)
    if how == "avg":
        return sum(values) / len(values)
    if how == "max":
        return max(values)
    if how == "min":
        return min(values)
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


class FakeTims:
    """고정 자료 위의 TIMS. 인자 이름을 엄격히 검사하고 호출을 기록한다.

    bucket=week의 경계는 schema에 없다. 이 fake는 월요일 시작, 기간 경계에서 자르는
    것으로 정했다. 호출 하나로 합친 계획과 로컬 분해 계획을 같은 자료에서 비교하려면
    fake가 하나의 정의를 가져야 하기 때문이다.
    """

    TOOLS = {
        "get_place_scope": {"name", "region", "include_vicinity"},
        "get_operation_metrics": {"metric", "scope", "date", "taxi_type", "aggregation",
                                  "bucket", "rollup", "dimension", "order", "limit"},
        "get_passage_metrics": {"metric", "scope", "date", "time", "aggregation"},
        "get_passage_count": {"scope", "date", "time", "taxi_type", "taxi_status",
                              "dimension", "order", "limit"},
    }

    def __init__(self, *, tools=None, fail_on_date=None):
        self.calls = []
        self._tools = set(self.TOOLS) if tools is None else set(tools)
        self.fail_on_date = fail_on_date

    @property
    def tool_names(self):
        return sorted(self._tools)

    def execute(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        unknown = set(arguments) - self.TOOLS[name]
        if unknown:
            raise AssertionError(f"{name}이 받지 않는 인자: {sorted(unknown)}")
        if self.fail_on_date is not None and arguments.get("date") == self.fail_on_date:
            return {"status": "ERROR", "error_code": "UPSTREAM_TIMEOUT",
                    "message": "TIMS 응답 지연", "retryable": False}
        if name == "get_place_scope":
            return {"scope": {"대구": DAEGU, "부산": BUSAN}[arguments["name"]]}
        if name == "get_operation_metrics":
            return self._operation(arguments)
        if name == "get_passage_metrics":
            return self._speed(arguments)
        raise AssertionError(f"이 테스트에서 부르지 않는 Tool: {name}")

    @staticmethod
    def _period(value):
        if value == "last_month":
            return date(2026, 8, 1), date(2026, 8, 31)
        head, _, tail = value.partition("-")
        return _day(head), _day(tail or head)

    def _within(self, arguments, day, scope):
        start, end = self._period(arguments["date"])
        return start <= _day(day) <= end and scope == arguments.get("scope", scope)

    def _weeks(self, start, end):
        weeks, cursor = [], start
        while cursor <= end:
            stop = min(cursor + timedelta(days=6 - cursor.weekday()), end)
            weeks.append((cursor, stop))
            cursor = stop + timedelta(days=1)
        return weeks

    def _operation(self, arguments):
        assert arguments["metric"] == "revenue"
        taxi = arguments.get("taxi_type", "all")
        rows = [(day, value) for day, kind, scope, value in REVENUE
                if self._within(arguments, day, scope) and taxi in ("all", kind)]
        how = arguments.get("aggregation", "avg")
        if "bucket" not in arguments:
            return _reduce([value for _, value in rows], how)
        assert arguments["bucket"] == "week"
        start, end = self._period(arguments["date"])
        per_week = [
            _reduce([value for day, value in rows if lo <= _day(day) <= hi], how)
            for lo, hi in self._weeks(start, end)
        ]
        return _reduce([value for value in per_week if value is not None],
                       arguments["rollup"])

    def _speed(self, arguments):
        assert arguments["metric"] == "speed"
        values = [value for day, scope, value in SPEED
                  if self._within(arguments, day, scope)]
        return _reduce(values, arguments.get("aggregation", "avg"))


def place(node_id, name):
    return {"id": node_id, "concept": "LOCATION", "subtype": "place",
            "role": "SUBCOND", "source": "user", "value": {"name": name}}


def event(subtype):
    return {"id": subtype, "concept": "EVENT", "subtype": subtype,
            "role": "SUPPORT", "source": "implicit"}


def measure(subtype, concept="AMOUNT"):
    return {"id": subtype, "concept": concept, "subtype": subtype,
            "role": "MEASURE", "source": "implicit"}


def revenue_grounding(factors, *, where="대구"):
    concepts = [event("operation"), measure("revenue")]
    if where:
        concepts.insert(0, place("place", where))
    return {"concepts": concepts, "factors": factors}


def plan_of(aggregation):
    return {"aggregation_plan": aggregation}


#: 네 질문의 정답 grounding. 기간·지역·택시 유형은 같고 집계 뜻만 다르다.
BASE = {"date": "last_month", "taxi_type": "private"}
SUM_THEN_AVG = {**BASE, **plan_of({"bucket": {"unit": "week", "reducer": "sum"},
                                   "result": {"reducer": "avg"}})}
AVG_THEN_MAX = {**BASE, **plan_of({"bucket": {"unit": "week", "reducer": "avg"},
                                   "result": {"reducer": "max"}})}
OVERALL_AVG = {**BASE, **plan_of({"result": {"reducer": "avg"}})}
WEEK_WITH_MAX_SUM = {**BASE, **plan_of({"bucket": {"unit": "week", "reducer": "sum"},
                                        "result": {"select": "max"}})}
SUM_THEN_MAX = {**BASE, **plan_of({"bucket": {"unit": "week", "reducer": "sum"},
                                   "result": {"reducer": "max"}})}

Q_SUM_THEN_AVG = "지난달 대구 개인택시 주별 매출 합계의 평균은?"
Q_AVG_THEN_MAX = "지난달 대구 개인택시 주별 매출 평균의 최댓값은?"
Q_OVERALL_AVG = "지난달 대구 개인택시 전체 매출의 평균은?"
Q_WEEK_WITH_MAX_SUM = "지난달 대구 개인택시 매출 합계가 가장 큰 주는?"


class Case(unittest.TestCase):
    def setUp(self):
        self.composer = MacroComposer()
        self.tims = FakeTims()

    def ground(self, payload, question):
        return parse_grounding(payload, question, structured_aggregation=True)

    def compose(self, payload, question):
        return self.composer.compose(self.ground(payload, question))

    def run_golden(self, payload, question, *, reference=REFERENCE):
        """pipeline._prepare/_finish와 같은 순서. Planner만 정답 grounding으로 바꾼다."""
        plan = self.compose(payload, question)
        scopes = set(extract_scopes(question))
        geoflow_validator.validate(
            plan, available_tools=self.tims.tool_names, user_scopes=scopes,
        ).raise_if_failed()
        execution = compile_plan(plan, reference_date=reference)
        result = execute_plan(execution, self.tims, known_scopes=scopes)
        answer = (format_answer(plan, result, execution_plan=execution)
                  if result.status == STATUS_OK else None)
        return plan, execution, result, answer

    def metric_calls(self):
        return [args for name, args in self.tims.calls if name == "get_operation_metrics"]


# -- 1~4. 네 질문은 서로 다른 의미 graph와 계산이 된다 --------------------------------


class SemanticGraphTest(Case):
    def signature(self, plan):
        grouped = [node.attributes.get("group_by") for node in plan.concepts
                   if node.attributes.get("group_by")]
        return (
            tuple(plan.applied_macros),
            tuple((item.operator, tuple(sorted(item.params.items())))
                  for item in plan.transformations if item.operator != "RESOLVE_PLACE_SCOPE"),
            tuple(json.dumps(item, sort_keys=True) for item in grouped),
        )

    def test_four_questions_have_four_graphs(self):
        cases = [(SUM_THEN_AVG, Q_SUM_THEN_AVG), (AVG_THEN_MAX, Q_AVG_THEN_MAX),
                 (OVERALL_AVG, Q_OVERALL_AVG), (WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)]
        signatures = [self.signature(self.compose(*case)) for case in cases]
        self.assertEqual(len(set(signatures)), 4, signatures)

    def test_sum_then_avg_preserves_the_dependency_chain(self):
        """기간·대상 제한 → 주별 그룹 → 각 주의 합계 → 주별 합계들의 평균."""
        plan = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        self.assertEqual(plan.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_GROUPED_MEASURE"])
        resolve, produce, combine = plan.transformations
        groups = plan.node(produce.outputs[0])
        # 제한 조건은 구간 안 집계 변환이 모두 받는다.
        self.assertEqual(produce.operator, "OPERATION_METRIC")
        self.assertEqual(produce.params, {"aggregation": "sum", "date": "last_month",
                                          "metric": "revenue", "taxi_type": "private"})
        self.assertEqual(produce.inputs["area"].node_id, resolve.outputs[0])
        # 중간 결과: 매출과 같은 개념이고 주별로 나뉘어 있다. 새 core concept가 아니다.
        self.assertEqual((groups.concept, groups.subtype), (CoreConcept.AMOUNT, "revenue"))
        self.assertEqual(groups.attributes["group_by"], {"bucket": "week"})
        self.assertEqual(groups.role, FunctionalRole.SUPPORT)
        # 바깥 집계
        self.assertEqual(combine.operator, "REDUCE_GROUPS")
        self.assertEqual(combine.params, {"reducer": "avg"})
        self.assertEqual(combine.inputs["groups"].node_id, groups.id)
        self.assertEqual(combine.outputs, [plan.final_node])
        self.assertEqual(plan.node(plan.final_node).role, FunctionalRole.MEASURE)

    def test_overall_average_has_no_group(self):
        plan = self.compose(OVERALL_AVG, Q_OVERALL_AVG)
        self.assertEqual(plan.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"])
        self.assertFalse(any(node.attributes.get("group_by") for node in plan.concepts))
        self.assertEqual(plan.transformations[-1].params["aggregation"], "avg")

    def test_selecting_a_group_returns_the_group(self):
        plan = self.compose(WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)
        combine = plan.transformations[-1]
        self.assertEqual((combine.operator, combine.params), ("SELECT_GROUP", {"select": "max"}))
        self.assertEqual(plan.node(plan.final_node).attributes["returns"], "group")

    def test_flat_h0_factors_lift_to_the_same_graph(self):
        """production(H0) flat factor가 구조화 표기와 같은 graph가 된다."""
        flat = {**BASE, "bucket": "week", "aggregation": "sum", "rollup": "avg"}
        structured = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        lifted = self.composer.compose(parse_grounding(revenue_grounding(flat),
                                                       Q_SUM_THEN_AVG))
        self.assertEqual(self.signature(lifted), self.signature(structured))

    def test_every_graph_passes_all_rules(self):
        for payload, question in ((SUM_THEN_AVG, Q_SUM_THEN_AVG),
                                  (AVG_THEN_MAX, Q_AVG_THEN_MAX),
                                  (OVERALL_AVG, Q_OVERALL_AVG),
                                  (WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)):
            with self.subTest(question=question):
                report = geoflow_validator.validate(
                    self.compose(revenue_grounding(payload), question),
                    available_tools=self.tims.tool_names)
                self.assertTrue(report.ok, report.errors)
                self.assertIn(Rule.AGGREGATION_SEMANTICS, report.checked_rules)

    def compose(self, payload, question):
        if "concepts" not in payload:
            payload = revenue_grounding(payload)
        return super().compose(payload, question)


class ExecutionTest(Case):
    def run_golden(self, payload, question, **kwargs):
        return super().run_golden(revenue_grounding(payload), question, **kwargs)

    def test_1_sum_then_avg(self):
        _plan, execution, result, answer = self.run_golden(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        self.assertEqual(result.status, STATUS_OK, result.error)
        self.assertAlmostEqual(result.final_value, 1100 / 6)
        # TIMS가 bucket/rollup을 받으므로 두 의미 단계가 호출 하나로 합쳐진다.
        (call,) = self.metric_calls()
        self.assertEqual(call, {"metric": "revenue", "scope": DAEGU, "date": "last_month",
                                "taxi_type": "private", "aggregation": "sum",
                                "bucket": "week", "rollup": "avg"})
        (step,) = execution.tool_steps[1:]
        self.assertEqual(step.covers, ["measure_groups", "combine_groups"])
        self.assertEqual(step.argument_sources["rollup"], "combine_groups.params.reducer")
        self.assertEqual(step.argument_sources["aggregation"],
                         "measure_groups.params.aggregation")
        self.assertIn("revenue_groups", execution.unobserved)
        self.assertIn("주별 합계의 평균: 183.333", answer)

    def test_2_avg_then_max(self):
        _plan, _execution, result, answer = self.run_golden(AVG_THEN_MAX, Q_AVG_THEN_MAX)
        self.assertEqual(result.final_value, 300)
        (call,) = self.metric_calls()
        self.assertEqual((call["aggregation"], call["bucket"], call["rollup"]),
                         ("avg", "week", "max"))
        self.assertIn("주별 평균의 최댓값: 300", answer)

    def test_3_overall_average_differs_from_average_of_group_averages(self):
        _plan, _execution, overall, answer = self.run_golden(OVERALL_AVG, Q_OVERALL_AVG)
        self.assertAlmostEqual(overall.final_value, 1100 / 13)
        (call,) = self.metric_calls()
        self.assertEqual(call, {"metric": "revenue", "scope": DAEGU, "date": "last_month",
                                "taxi_type": "private", "aggregation": "avg"})
        self.tims.calls.clear()
        avg_of_avgs = {**BASE, **plan_of({"bucket": {"unit": "week", "reducer": "avg"},
                                          "result": {"reducer": "avg"}})}
        _plan, _execution, grouped, _answer = self.run_golden(
            avg_of_avgs, "지난달 대구 개인택시 주별 매출 평균의 평균은?")
        self.assertAlmostEqual(grouped.final_value, 625 / 6)
        self.assertNotAlmostEqual(overall.final_value, grouped.final_value)
        self.assertIn("개인 택시 평균 영업 수익: 84.615", answer)
        self.assertNotIn("TIMS 기본값", answer)

    def test_4_max_value_versus_the_week_with_the_max(self):
        _plan, _execution, value, value_answer = self.run_golden(SUM_THEN_MAX,
                                                                 "지난달 주별 매출 합계의 최댓값은?")
        self.assertEqual(value.final_value, 360)
        self.assertIn("주별 합계의 최댓값: 360", value_answer)

        self.tims.calls.clear()
        plan, execution, week, week_answer = self.run_golden(WEEK_WITH_MAX_SUM,
                                                             Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(week.status, STATUS_OK, week.error)
        self.assertEqual(week.final_value["value"], 360)
        self.assertEqual([group["label"] for group in week.final_value["groups"]], [W3])
        # TIMS rollup은 구간을 돌려주지 않는다. 기간을 명시 구간으로 나눠 부른다.
        calls = self.metric_calls()
        self.assertEqual([call["date"] for call in calls], AUGUST_WEEKS)
        for call in calls:
            self.assertEqual({key: call[key] for key in ("metric", "scope", "taxi_type",
                                                          "aggregation")},
                             {"metric": "revenue", "scope": DAEGU, "taxi_type": "private",
                              "aggregation": "sum"})
            self.assertNotIn("bucket", call)
            self.assertNotIn("rollup", call)
        rows = week.state["revenue_groups"]
        self.assertEqual([row["value"] for row in rows], [150, 300, 360, 220, 30, 40])
        self.assertEqual([row["group"]["complete"] for row in rows],
                         [False, True, True, True, True, False])
        self.assertEqual(execution.periods["measure_groups"]["resolved"],
                         "20260801-20260831")
        self.assertIn("주별 합계가 가장 큰 주: 20260810-20260816", week_answer)
        self.assertIn("지난달(20260801-20260831)", week_answer)
        self.assertIn("20260801-20260802(부분 구간): 150", week_answer)

    def test_argmax_of_sums_is_not_argmax_of_averages(self):
        by_avg = {**BASE, **plan_of({"bucket": {"unit": "week", "reducer": "avg"},
                                     "result": {"select": "max"}})}
        _plan, _execution, result, _answer = self.run_golden(
            by_avg, "지난달 대구 개인택시 매출 평균이 가장 큰 주는?")
        self.assertEqual([group["label"] for group in result.final_value["groups"]], [W2])
        self.assertEqual(result.final_value["value"], 300)

    def test_local_reduction_when_the_tool_has_no_bucket(self):
        """get_passage_metrics는 bucket을 받지 않는다. 구간별 값을 받아 로컬에서 합친다."""
        payload = {"concepts": [place("place", "대구"), event("passage"), measure("speed")],
                   "factors": {"date": "last_month",
                               **plan_of({"bucket": {"unit": "week", "reducer": "avg"},
                                          "result": {"reducer": "max"}})}}
        _plan, execution, result, answer = super().run_golden(
            payload, "지난달 대구 주별 평균 속도의 최댓값은?")
        self.assertEqual(result.status, STATUS_OK, result.error)
        self.assertEqual(result.final_value, 60)
        speed_calls = [args for name, args in self.tims.calls if name == "get_passage_metrics"]
        self.assertEqual([call["date"] for call in speed_calls], AUGUST_WEEKS)
        self.assertTrue(all(call["aggregation"] == "avg" for call in speed_calls))
        self.assertEqual([step.operator for step in execution.steps if step.is_local],
                         ["COLLECT_GROUPS", "REDUCE_GROUPS"])
        self.assertIn("로컬에서 구간별 값의 최댓값을 계산했습니다", answer)

    def test_fused_and_local_paths_agree_under_the_same_week_definition(self):
        """같은 뜻을 두 경로로 계산한다. fake의 bucket 경계가 local과 같을 때만 성립한다."""
        _plan, _execution, fused, _ = self.run_golden(SUM_THEN_MAX, "지난달 주별 매출 합계의 최댓값은?")
        _plan, _execution, local, _ = self.run_golden(WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(fused.final_value, local.final_value["value"])


# -- 5. 공간·시간·택시 유형 조건 보존 -------------------------------------------------


class ConditionPreservationTest(Case):
    def test_every_partition_call_keeps_every_condition(self):
        self.run_golden(revenue_grounding(WEEK_WITH_MAX_SUM), Q_WEEK_WITH_MAX_SUM)
        for call in self.metric_calls():
            self.assertEqual(call["taxi_type"], "private")
            self.assertEqual(call["scope"], DAEGU)
            self.assertIn(call["date"], AUGUST_WEEKS)

    def test_lost_conditions_would_change_the_answer(self):
        """자료가 조건을 구분하는지 확인한다. 조건 하나를 빼면 다른 주가 뽑힌다."""
        no_taxi = {"date": "last_month", **{k: v for k, v in WEEK_WITH_MAX_SUM.items()
                                            if k not in BASE}}
        _plan, _execution, result, _answer = self.run_golden(
            revenue_grounding(no_taxi), "지난달 대구 매출 합계가 가장 큰 주는?")
        self.assertEqual([g["label"] for g in result.final_value["groups"]], [W2])
        self.assertEqual(result.final_value["value"], 5300)

    def test_lowering_that_drops_a_condition_is_rejected(self):
        plan = self.compose(revenue_grounding(WEEK_WITH_MAX_SUM), Q_WEEK_WITH_MAX_SUM)
        execution = compile_plan(plan, reference_date=REFERENCE)
        partition = next(step for step in execution.steps if step.group is not None)
        del partition.arguments["taxi_type"]
        with self.assertRaises(CompilerError) as caught:
            verify_lowering(plan, execution, reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "LOWERING_MISMATCH")

    def test_lowering_with_a_missing_week_is_rejected(self):
        plan = self.compose(revenue_grounding(WEEK_WITH_MAX_SUM), Q_WEEK_WITH_MAX_SUM)
        execution = compile_plan(plan, reference_date=REFERENCE)
        dropped = next(step for step in execution.steps if step.group is not None)
        execution.steps.remove(dropped)
        for ids in execution.semantic_map.values():
            if dropped.id in ids:
                ids.remove(dropped.id)
        with self.assertRaises(CompilerError) as caught:
            verify_lowering(plan, execution, reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "LOWERING_MISMATCH")

    def test_lowering_with_swapped_stages_is_rejected(self):
        plan = self.compose(revenue_grounding(SUM_THEN_AVG), Q_SUM_THEN_AVG)
        execution = compile_plan(plan, reference_date=REFERENCE)
        fused = execution.tool_steps[-1]
        fused.arguments["aggregation"], fused.arguments["rollup"] = "avg", "sum"
        with self.assertRaises(CompilerError) as caught:
            verify_lowering(plan, execution, reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "LOWERING_MISMATCH")

    def test_condition_the_tool_cannot_take_is_refused(self):
        """get_passage_metrics는 taxi_type을 받지 않는다. 버리지 않고 거부한다."""
        payload = {"concepts": [place("place", "대구"), event("passage"), measure("speed")],
                   "factors": {"date": "last_month", "taxi_type": "private",
                               **plan_of({"bucket": {"unit": "week", "reducer": "avg"},
                                          "result": {"reducer": "max"}})}}
        with self.assertRaises(CompositionError) as caught:
            self.compose(payload, "지난달 대구 개인택시 주별 평균 속도의 최댓값은?")
        self.assertEqual(caught.exception.code, "UNCONSUMED_CONDITION")
        self.assertEqual(caught.exception.context["unconsumed"], ["taxi_type"])

    def test_count_tool_consumes_only_its_inherent_sum(self):
        """개수 Tool은 사건 수(=합)를 돌려준다. sum은 조건 손실이 아니고 avg는 손실이다."""
        def payload(how):
            return {"concepts": [
                {"id": "area", "concept": "LOCATION", "subtype": "scope", "role": "COND",
                 "source": "user", "value": "scope:edge:19384"},
                event("passage"), measure("passage_count")],
                "factors": {"date": "20260530", "aggregation": how}}
        question = "2026년 5월 30일 scope:edge:19384 지점을 통과하는 차량 대수는?"
        plan = self.composer.compose(parse_grounding(payload("sum"), question))
        self.assertEqual(plan.transformations[-1].operator, "PASSAGE_COUNT")
        self.assertNotIn("aggregation", plan.transformations[-1].params)
        with self.assertRaises(CompositionError) as caught:
            self.composer.compose(parse_grounding(payload("avg"), question))
        self.assertEqual(caught.exception.code, "UNCONSUMED_CONDITION")
        self.assertEqual(caught.exception.context["unconsumed"], ["aggregation"])

    def test_answer_shows_period_scope_taxi_type_and_semantics(self):
        *_rest, answer = self.run_golden(revenue_grounding(WEEK_WITH_MAX_SUM),
                                         Q_WEEK_WITH_MAX_SUM)
        for text in ("대구", "지난달(20260801-20260831)", "개인 택시",
                     "주별 합계가 가장 큰 주", "월요일 시작 7일", "- 계산:"):
            self.assertIn(text, answer)
        *_rest, fused = self.run_golden(revenue_grounding(SUM_THEN_AVG), Q_SUM_THEN_AVG)
        for text in ("대구", "지난달", "개인 택시", "주별 합계의 평균",
                     "bucket=week, aggregation=sum, rollup=avg", "TIMS 정의"):
            self.assertIn(text, fused)

    def test_trace_links_every_step_to_a_semantic_step(self):
        plan, execution, result, _answer = self.run_golden(
            revenue_grounding(WEEK_WITH_MAX_SUM), Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(set(execution.semantic_map),
                         {item.id for item in plan.transformations})
        for entry in result.trace:
            self.assertTrue(entry["covers"], entry)
        partitions = [entry for entry in result.trace if entry.get("group")]
        self.assertEqual([entry["group"]["label"] for entry in partitions], AUGUST_WEEKS)
        local = [entry for entry in result.trace if entry["phase"] == "local"]
        self.assertEqual([entry["operator"] for entry in local],
                         ["COLLECT_GROUPS", "SELECT_GROUP"])
        self.assertEqual(local[-1]["covers"], ["combine_groups"])
        self.assertEqual(local[0]["result"][2]["value"], 360)


# -- 6. 필요한 자료·기능이 없으면 명시적으로 거부 ---------------------------------------


class RefusalTest(Case):
    def test_relative_period_without_reference_date(self):
        plan = self.compose(revenue_grounding(WEEK_WITH_MAX_SUM), Q_WEEK_WITH_MAX_SUM)
        with self.assertRaises(CompilerError) as caught:
            compile_plan(plan)
        self.assertEqual(caught.exception.code, "UNRESOLVED_PERIOD")

    def test_no_period_to_partition(self):
        payload = {k: v for k, v in WEEK_WITH_MAX_SUM.items() if k != "date"}
        plan = self.compose(revenue_grounding(payload), "대구 개인택시 매출 합계가 가장 큰 주는?")
        with self.assertRaises(CompilerError) as caught:
            compile_plan(plan, reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "UNRESOLVED_PERIOD")

    def test_non_contiguous_period_is_not_partitioned(self):
        payload = {**WEEK_WITH_MAX_SUM, "date": "weekend"}
        plan = self.compose(revenue_grounding(payload), "주말 매출 합계가 가장 큰 주는?")
        with self.assertRaises(CompilerError) as caught:
            compile_plan(plan, reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_PERIOD_FOR_GROUPING")

    def test_explicit_range_needs_no_reference_date(self):
        payload = {**WEEK_WITH_MAX_SUM, "date": "20260803-20260816"}
        plan = self.compose(revenue_grounding(payload), "그 기간 매출 합계가 가장 큰 주는?")
        execution = compile_plan(plan)
        self.assertEqual([step.arguments["date"] for step in execution.tool_steps[1:]],
                         [W2, W3])

    def test_count_measure_cannot_be_grouped(self):
        payload = {"concepts": [place("place", "대구"), event("passage"),
                                measure("passage_count")],
                   "factors": {"date": "last_month",
                               **plan_of({"bucket": {"unit": "week", "reducer": "sum"},
                                          "result": {"reducer": "avg"}})}}
        with self.assertRaises(CompositionError) as caught:
            self.compose(payload, "지난달 대구 주별 통행량 합계의 평균은?")
        self.assertEqual(caught.exception.code, "UNSUPPORTED_GROUPED_MEASURE")

    def test_grouping_with_dimension_is_not_assumed_supported(self):
        payload = {**SUM_THEN_AVG, "dimension": "sigungu"}
        with self.assertRaises(CompositionError) as caught:
            self.compose(revenue_grounding(payload), "대구 시군구별 주별 매출 합계의 평균은?")
        self.assertEqual(caught.exception.code, "UNSUPPORTED_AGGREGATION_COMBINATION")

    def test_missing_tool_fails_validation(self):
        plan = self.compose(revenue_grounding(SUM_THEN_AVG), Q_SUM_THEN_AVG)
        report = geoflow_validator.validate(plan, available_tools=["get_place_scope"])
        self.assertFalse(report.ok)
        self.assertIn(Rule.EXECUTABILITY, report.failed_rules())

    def test_week_without_data_is_not_counted_as_zero(self):
        """부산은 W3에만 자료가 있다. 빈 주를 0으로 채워 고르지 않는다."""
        payload = revenue_grounding(WEEK_WITH_MAX_SUM, where="부산")
        _plan, _execution, result, answer = self.run_golden(
            payload, "지난달 부산 개인택시 매출 합계가 가장 큰 주는?")
        self.assertNotEqual(result.status, STATUS_OK)
        self.assertEqual(result.error["code"], "EMPTY_GROUP_VALUE")
        self.assertIsNone(answer)

    def test_tool_error_in_one_partition_stops_the_plan(self):
        self.tims = FakeTims(fail_on_date=W4)
        _plan, _execution, result, answer = self.run_golden(
            revenue_grounding(WEEK_WITH_MAX_SUM), Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(result.status, "TOOL_ERROR")
        self.assertIsNone(answer)
        self.assertEqual([args["date"] for args in self.metric_calls()], [W1, W2, W3, W4])

    def test_structured_and_flat_aggregation_cannot_be_mixed(self):
        payload = revenue_grounding({**SUM_THEN_AVG, "rollup": "avg"})
        with self.assertRaises(PlannerError) as caught:
            self.ground(payload, Q_SUM_THEN_AVG)
        self.assertEqual(caught.exception.code, "DUPLICATE_AGGREGATION_SOURCE")

    def test_malformed_structured_plans(self):
        for bad in ({"result": {"select": "max"}},
                    {"bucket": {"unit": "week", "reducer": "sum"}, "result": {}},
                    {"bucket": {"unit": "day", "reducer": "sum"},
                     "result": {"reducer": "avg"}},
                    {"bucket": {"unit": "week", "reducer": "sum"},
                     "result": {"reducer": "avg", "select": "max"}}):
            with self.subTest(plan=bad):
                with self.assertRaises(PlannerError) as caught:
                    self.ground(revenue_grounding({**BASE, **plan_of(bad)}), "질문")
                self.assertEqual(caught.exception.code, "INVALID_AGGREGATION_PLAN")

    def test_production_grounding_does_not_read_the_structured_plan(self):
        """production planner의 계약(H0)은 그대로다. 모르는 factor로 거부한다."""
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(revenue_grounding(SUM_THEN_AVG), Q_SUM_THEN_AVG)
        self.assertEqual(caught.exception.code, "UNKNOWN_FACTOR")


# -- 7. 모호한 구간 안 집계를 채우지 않는다 ------------------------------------------


class AmbiguousInnerAggregationTest(Case):
    def test_flat_and_structured_unspecified_inner_are_refused(self):
        for grounding in (
            parse_grounding(revenue_grounding({**BASE, "bucket": "week", "rollup": "avg"}),
                            "지난달 주별 매출의 평균은?"),
            self.ground(revenue_grounding({**BASE, **plan_of(
                {"bucket": {"unit": "week", "reducer": "unspecified"},
                 "result": {"reducer": "avg"}})}), "지난달 주별 매출의 평균은?"),
        ):
            with self.subTest(source=grounding.aggregation.source):
                with self.assertRaises(CompositionError) as caught:
                    self.composer.compose(grounding)
                self.assertEqual(caught.exception.code, "AMBIGUOUS_INNER_AGGREGATION")
                # 재질의로 채우지 않는다. 국소 보정(L1)은 구간 안 집계를 지어냈다.
                self.assertFalse(decide_repair(caught.exception).repairable)

    def test_single_stage_without_aggregation_keeps_the_existing_behavior(self):
        """구간이 없는 질문은 기존대로 Tool 기본값을 쓴다(호환). 답변이 이를 밝힌다."""
        payload = revenue_grounding({"date": "last_month"})
        plan = self.composer.compose(parse_grounding(payload, "지난달 대구 매출은?"))
        self.assertNotIn("aggregation", plan.transformations[-1].params)
        *_rest, answer = self.run_golden(payload, "지난달 대구 매출은?")
        self.assertIn("TIMS 기본값(평균)이 적용되었습니다", answer)

    def test_validator_rejects_a_grouped_node_without_inner_aggregation(self):
        plan = self.compose(revenue_grounding(SUM_THEN_AVG), Q_SUM_THEN_AVG)
        produce = next(item for item in plan.transformations if item.id == "measure_groups")
        del produce.params["aggregation"]
        report = geoflow_validator.validate(plan)
        self.assertIn(Rule.AGGREGATION_SEMANTICS, report.failed_rules())


# -- G7 구조 검사 -----------------------------------------------------------------


class AggregationRuleTest(Case):
    def plan(self):
        return self.compose(revenue_grounding(SUM_THEN_AVG), Q_SUM_THEN_AVG)

    def test_compressed_bucket_param_is_rejected(self):
        """두 단계를 Tool 인자로 압축한 예전 모양은 의미 graph로 인정하지 않는다."""
        plan = self.composer.compose(parse_grounding(
            revenue_grounding({"date": "last_month", "aggregation": "sum"}), "질문"))
        plan.transformations[-1].params.update({"bucket": "week", "rollup": "avg"})
        report = geoflow_validator.validate(plan)
        self.assertIn(Rule.AGGREGATION_SEMANTICS, report.failed_rules())

    def test_grouped_node_cannot_be_final(self):
        plan = self.plan()
        combine = plan.transformations.pop()
        plan.concepts = [node for node in plan.concepts if node.id != combine.outputs[0]]
        plan.final_node = combine.inputs["groups"].node_id
        report = geoflow_validator.validate(plan)
        self.assertIn(Rule.AGGREGATION_SEMANTICS, report.failed_rules())

    def test_reduce_groups_needs_a_grouped_input(self):
        """원시 값에서 "구간별 값의 평균"을 만들어 내는 graph는 성립하지 않는다."""
        nodes = [
            ConceptNode("operation", CoreConcept.EVENT, "operation", FunctionalRole.SUPPORT,
                        NodeSource.IMPLICIT, value="operation"),
            ConceptNode("total", CoreConcept.AMOUNT, "revenue", FunctionalRole.SUPPORT,
                        NodeSource.TOOL),
            ConceptNode("revenue", CoreConcept.AMOUNT, "revenue", FunctionalRole.MEASURE,
                        NodeSource.DERIVED),
        ]
        plan = GeoFlowPlan(
            version="1.0", question="질문", template="x", concepts=nodes, final_node="revenue",
            transformations=[
                Transformation("t1", "OPERATION_METRIC", {"event": ValueRef("operation")},
                               ["total"], {"metric": "revenue", "aggregation": "avg"}),
                Transformation("t2", "REDUCE_GROUPS", {"groups": ValueRef("total")},
                               ["revenue"], {"reducer": "avg"}),
            ],
        )
        report = geoflow_validator.validate(plan)
        self.assertIn(Rule.AGGREGATION_SEMANTICS, report.failed_rules())

    def test_select_group_must_return_a_group(self):
        plan = self.compose(revenue_grounding(WEEK_WITH_MAX_SUM), Q_WEEK_WITH_MAX_SUM)
        plan.node(plan.final_node).attributes.pop("returns")
        self.assertIn(Rule.AGGREGATION_SEMANTICS,
                      geoflow_validator.validate(plan).failed_rules())


# -- 8. 회귀: scope provenance와 실제 pipeline -----------------------------------


class _StubPlanner:
    """정답 grounding을 돌려주는 planner. LLM을 부르지 않는다."""

    def __init__(self, payload, *, structured=True):
        self.payload = payload
        self.structured = structured

    def plan(self, question):
        grounding = parse_grounding(self.payload, question,
                                    structured_aggregation=self.structured)
        return PlannerOutput(grounding=grounding, raw_text=json.dumps(self.payload))

    def repair_planning_error(self, *args, **kwargs):
        raise AssertionError("재질의하지 않아야 한다")


class RegressionTest(Case):
    def pipeline(self, payload, **kwargs):
        return GeoFlowPipeline(planner=_StubPlanner(payload, **kwargs),
                               composer=self.composer, tool_executor=self.tims,
                               clock=lambda: REFERENCE)

    def test_pipeline_runs_the_local_path_with_the_injected_clock(self):
        run = self.pipeline(revenue_grounding(WEEK_WITH_MAX_SUM)).run(Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertIn("20260810-20260816", run.final_answer)
        self.assertEqual(run.execution_plan["periods"]["measure_groups"]["reference_date"],
                         "20260925")
        self.assertEqual([hop["phase"] for hop in run.hop_log].count("local"), 2)

    def test_pipeline_refuses_ambiguous_inner_without_calling_tools(self):
        flat = revenue_grounding({**BASE, "bucket": "week", "rollup": "avg"})
        run = self.pipeline(flat, structured=False).run("지난달 주별 매출의 평균은?")
        self.assertEqual(run.error["code"], "AMBIGUOUS_INNER_AGGREGATION")
        self.assertEqual(self.tims.calls, [])

    def test_user_scope_in_a_grouped_plan_is_accepted(self):
        payload = {"concepts": [
            {"id": "area", "concept": "LOCATION", "subtype": "scope", "role": "COND",
             "source": "user", "value": DAEGU},
            event("operation"), measure("revenue")], "factors": SUM_THEN_AVG}
        question = f"지난달 {DAEGU}의 개인택시 주별 매출 합계의 평균은?"
        _plan, _execution, result, _answer = self.run_golden(payload, question)
        self.assertAlmostEqual(result.final_value, 1100 / 6)

    def test_fabricated_scope_in_a_grouped_plan_is_rejected(self):
        payload = {"concepts": [
            {"id": "area", "concept": "LOCATION", "subtype": "scope", "role": "COND",
             "source": "user", "value": DAEGU},
            event("operation"), measure("revenue")], "factors": SUM_THEN_AVG}
        with self.assertRaises(GeoFlowError) as caught:
            self.run_golden(payload, "지난달 대구 개인택시 주별 매출 합계의 평균은?")
        self.assertEqual(caught.exception.code, "UNGROUNDED_SCOPE")


if __name__ == "__main__":
    unittest.main()


class CliRepairEventTest(unittest.TestCase):
    """계획 단계 재질의 사건을 CLI가 받아도 멈추지 않는다.

    예전 처리기는 장소 조회 실패 payload(concept, name)만 가정해 KeyError로
    끝났다. "지난달 매출 합계가 가장 큰 주" live 실행에서 드러났다.
    """

    def test_planning_repair_event_is_printed(self):
        import contextlib
        import io

        import assistant_cli

        handle = assistant_cli._make_graph_event_handler()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            handle("geoflow_repair", {"attempt": 1, "failure": {
                "stage": "planner", "code": "INVALID_FACTOR_COMBINATION",
                "kind": "factor_completion", "message": "..."}})
            handle("geoflow_repair", {"attempt": 1, "failure": {
                "concept": "place", "name": "대구시", "region": "",
                "message": "", "step_id": "resolve_scope"}})
        self.assertIn("INVALID_FACTOR_COMBINATION", out.getvalue())
        self.assertIn("concept=place", out.getvalue())
