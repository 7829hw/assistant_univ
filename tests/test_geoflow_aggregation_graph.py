# -*- coding: utf-8 -*-
"""두 단계 집계의 의미 graph → 실행 계획 → 실행 → 답변을 정답 grounding으로 검증한다.

LLM을 부르지 않는다. grounding은 질문의 뜻을 사람이 적은 것이고, 그 뒤의 합성·검증·
lowering·실행·답변이 질문과 같은 계산을 하는지만 본다.

고정 자료는 구간마다 표본 수와 값이 다르게 골랐다. 서로 다른 계산이 우연히 같은
답을 내지 않게 하기 위해서다. 기대값은 아래 표에서 손으로 계산해 상수로 적었다.
구현 코드로 계산하지 않는다.

2026년 8월(기준일 2026-09-25의 "지난달"). 8/1은 토요일이다. 대구·개인 택시는 매일
10짜리 기록이 하나 있고, 며칠에 기록이 더 있다(8/3 +300, 8/10~13 각 +80, 8/17 +190,
8/31 +30). 월요일 시작, 기간 경계에서 자르는 주(의미 graph의 정의)로 나누면

    주  기간                 기록 수  합계  평균(기록 단위)  최댓값
    W1  20260801-20260802    2       20    10              10     (부분 주)
    W2  20260803-20260809    8       370   46.25           300
    W3  20260810-20260816    11      390   35.4545…        80
    W4  20260817-20260823    8       260   32.5            190
    W5  20260824-20260830    7       70    10              10
    W6  20260831-20260831    2       40    20              30     (부분 주)
                             38      1150

    주별 합계의 평균     = 1150 / 6 = 191.666…
    주별 합계의 최댓값   = 390 (W3)
    주별 합계가 가장 큰 주 = W3
    주별 평균의 최댓값   = 46.25 (W2)   ← 평균이 가장 큰 주는 W2로, 합계 기준(W3)과 다르다
    주별 최댓값의 평균   = (10+300+80+190+10+30) / 6 = 620 / 6 = 103.333…
    전체 평균            = 1150 / 38 = 30.263…
    부분 주를 버리는 bucket의 합계 평균 = (370+390+260+70) / 4 = 272.5

조건을 잃으면 값이 달라지도록 섞인 자료를 둔다.

    대구·법인 8/5 5000   → taxi_type을 잃으면 W2 합계 5370
    부산·개인 8/12 7000  → 부산은 이날만 자료가 있다(빈 날 검사에도 쓴다)
    대구·개인 7/31 9999, 9/1 8888 → 기간을 잃으면 값이 바뀐다
"""

import contextlib
import io
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
from geoflow.tims_contract import (  # noqa: E402
    CONFIRMED,
    DEFAULT_CONTRACT,
    UNKNOWN,
)
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
AUGUST_DAYS = [f"202608{day:02d}" for day in range(1, 32)]


def _revenue_rows():
    rows = [(f"202608{day:02d}", "private", DAEGU, 10) for day in range(1, 32)]
    extra = [("20260803", 300), ("20260810", 80), ("20260811", 80), ("20260812", 80),
             ("20260813", 80), ("20260817", 190), ("20260831", 30)]
    rows += [(day, "private", DAEGU, value) for day, value in extra]
    rows += [("20260805", "corporate", DAEGU, 5000), ("20260812", "private", BUSAN, 7000),
             ("20260731", "private", DAEGU, 9999), ("20260901", "private", DAEGU, 8888)]
    return rows


REVENUE = _revenue_rows()

#: (날짜, scope, 속도). get_passage_metrics는 bucket을 받지 않는다.
#: 대구는 매일 20, 8/12만 20과 50 두 기록이다.
#:   하루 최댓값의 주별 최댓값: W3 50, 나머지 20 → 최댓값 50
SPEED = [(f"202608{day:02d}", DAEGU, 20) for day in range(1, 32)] + [
    ("20260812", DAEGU, 50), ("20260812", BUSAN, 999),
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

    bucket의 경계는 schema에 없다. 이 fake는 경계를 설정으로 받는다. 병합 경로가
    TIMS의 정의에 따라 다른 값을 낼 수 있음을 보이기 위해서다. 날짜 범위는 양 끝을
    포함한다(이것도 이 fake의 선택이다).
    """

    TOOLS = {
        "get_place_scope": {"name", "region", "include_vicinity"},
        "get_operation_metrics": {"metric", "scope", "date", "taxi_type", "aggregation",
                                  "bucket", "rollup", "dimension", "order", "limit"},
        "get_passage_metrics": {"metric", "scope", "date", "time", "aggregation"},
        "get_passage_count": {"scope", "date", "time", "taxi_type", "taxi_status",
                              "dimension", "order", "limit"},
    }

    def __init__(self, *, tools=None, fail_on_date=None, drop_partial_buckets=False):
        self.calls = []
        self._tools = set(self.TOOLS) if tools is None else set(tools)
        self.fail_on_date = fail_on_date
        self.drop_partial_buckets = drop_partial_buckets

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
            natural_start = cursor - timedelta(days=cursor.weekday())
            stop = min(natural_start + timedelta(days=6), end)
            complete = cursor == natural_start and stop == natural_start + timedelta(days=6)
            if complete or not self.drop_partial_buckets:
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


#: 호출 하나로 합치는 것이 의미 graph와 같은 계산이 되는 가상의 계약.
#: 실제 계약이 아니다. 병합 경로의 동작을 검증할 때만 쓴다.
MATCHING_BUCKET_CONTRACT = DEFAULT_CONTRACT.assuming(
    bucket_week_start="monday", bucket_partial="clip_to_period",
    bucket_empty="undefined", relative_date_reference="Asia/Seoul calendar",
)
#: 날짜 범위의 양 끝 포함이 확인되었다고 가정한 계약.
RANGE_CONTRACT = DEFAULT_CONTRACT.assuming(range_inclusive="inclusive")


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


def grouped(inner, **result):
    return plan_of({"bucket": {"unit": "week", "reducer": inner}, "result": result})


BASE = {"date": "last_month", "taxi_type": "private"}
SUM_THEN_AVG = {**BASE, **grouped("sum", reducer="avg")}
SUM_THEN_MAX = {**BASE, **grouped("sum", reducer="max")}
AVG_THEN_MAX = {**BASE, **grouped("avg", reducer="max")}
MAX_THEN_AVG = {**BASE, **grouped("max", reducer="avg")}
OVERALL_AVG = {**BASE, **plan_of({"result": {"reducer": "avg"}})}
WEEK_WITH_MAX_SUM = {**BASE, **grouped("sum", select="max")}
WEEK_WITH_MAX_AVG = {**BASE, **grouped("avg", select="max")}

Q_SUM_THEN_AVG = "지난달 대구 개인택시 주별 매출 합계의 평균은?"
Q_SUM_THEN_MAX = "지난달 대구 개인택시 주별 매출 합계의 최댓값은?"
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
        if "concepts" not in payload:
            payload = revenue_grounding(payload)
        return self.composer.compose(self.ground(payload, question))

    def run_golden(self, payload, question, *, reference=REFERENCE,
                   contract=DEFAULT_CONTRACT):
        """pipeline._prepare/_finish와 같은 순서. Planner만 정답 grounding으로 바꾼다."""
        plan = self.compose(payload, question)
        scopes = set(extract_scopes(question))
        geoflow_validator.validate(
            plan, available_tools=self.tims.tool_names, user_scopes=scopes,
        ).raise_if_failed()
        execution = compile_plan(plan, reference_date=reference, contract=contract)
        result = execute_plan(execution, self.tims, known_scopes=scopes)
        answer = (format_answer(plan, result, execution_plan=execution)
                  if result.status == STATUS_OK else None)
        return plan, execution, result, answer

    def metric_calls(self):
        return [args for name, args in self.tims.calls if name == "get_operation_metrics"]


# -- 계약 표 ---------------------------------------------------------------------


class ContractTableTest(unittest.TestCase):
    def test_statuses_are_recorded_with_evidence(self):
        table = {row["key"]: row for row in DEFAULT_CONTRACT.table()}
        for key in ("inner_is_aggregation", "rollup_unweighted", "aggregation_default",
                    "single_date"):
            self.assertEqual(table[key]["status"], CONFIRMED, key)
        for key in ("bucket_week_start", "bucket_partial", "bucket_empty", "null_result",
                    "relative_date_reference"):
            self.assertEqual(table[key]["status"], UNKNOWN, key)
        self.assertEqual(table["range_inclusive"]["status"], "observed")
        self.assertTrue(all(row["evidence"] for row in table.values()))

    def test_confirmed_items_cite_a_quote_that_exists(self):
        from geoflow.tims_contract import evidence_problems
        self.assertEqual(evidence_problems(), [])

    def test_confirming_without_evidence_is_caught(self):
        from dataclasses import replace

        from geoflow.tims_contract import ITEMS, TimsContract, evidence_problems
        items = dict(ITEMS)
        items["bucket_week_start"] = replace(items["bucket_week_start"], status=CONFIRMED,
                                             value="monday")
        problems = evidence_problems(TimsContract(items))
        self.assertTrue(any("bucket_week_start" in p for p in problems))
        items["bucket_week_start"] = replace(items["bucket_week_start"],
                                             source="schemas/tims.yaml", quote="월요일에 시작")
        self.assertTrue(evidence_problems(TimsContract(items)))

    def test_assumptions_are_marked_and_only_count_in_assumed_contracts(self):
        from geoflow.tims_contract import ASSUMED, RANGE_PARTITION, TimsContract
        self.assertEqual(RANGE_CONTRACT.status("range_inclusive"), ASSUMED)
        self.assertTrue(RANGE_CONTRACT.allows(RANGE_PARTITION))
        leaked = TimsContract(dict(RANGE_CONTRACT.items))  # allow_assumptions=False
        self.assertFalse(leaked.allows(RANGE_PARTITION))
        self.assertNotIn(ASSUMED, {item.status for item in DEFAULT_CONTRACT.items.values()})

    def test_mock_is_not_cited_as_evidence(self):
        for row in DEFAULT_CONTRACT.table():
            self.assertNotIn("mock", row["evidence"].lower())


# -- 1~4. 네 질문은 서로 다른 의미 graph와 계산이 된다 --------------------------------


class SemanticGraphTest(Case):
    def signature(self, plan):
        groups = [node.attributes.get("group_by") for node in plan.concepts
                  if node.attributes.get("group_by")]
        return (
            tuple(plan.applied_macros),
            tuple((item.operator, tuple(sorted(item.params.items())))
                  for item in plan.transformations if item.operator != "RESOLVE_PLACE_SCOPE"),
            tuple(json.dumps(item, sort_keys=True) for item in groups),
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
        self.assertEqual(produce.operator, "OPERATION_METRIC")
        self.assertEqual(produce.params, {"aggregation": "sum", "date": "last_month",
                                          "metric": "revenue", "taxi_type": "private"})
        self.assertEqual(produce.inputs["area"].node_id, resolve.outputs[0])
        self.assertEqual((groups.concept, groups.subtype), (CoreConcept.AMOUNT, "revenue"))
        self.assertEqual(groups.attributes["group_by"], {"bucket": "week"})
        self.assertEqual(groups.role, FunctionalRole.SUPPORT)
        self.assertEqual((combine.operator, combine.params), ("REDUCE_GROUPS", {"reducer": "avg"}))
        self.assertEqual(combine.inputs["groups"].node_id, groups.id)
        self.assertEqual(combine.outputs, [plan.final_node])

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
        flat = {**BASE, "bucket": "week", "aggregation": "sum", "rollup": "avg"}
        structured = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        lifted = self.composer.compose(parse_grounding(revenue_grounding(flat), Q_SUM_THEN_AVG))
        self.assertEqual(self.signature(lifted), self.signature(structured))

    def test_every_graph_passes_all_rules(self):
        for payload, question in ((SUM_THEN_AVG, Q_SUM_THEN_AVG), (AVG_THEN_MAX, Q_AVG_THEN_MAX),
                                  (OVERALL_AVG, Q_OVERALL_AVG),
                                  (WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)):
            with self.subTest(question=question):
                report = geoflow_validator.validate(self.compose(payload, question),
                                                    available_tools=self.tims.tool_names)
                self.assertTrue(report.ok, report.errors)


# -- lowering: 계약이 정한 경로 --------------------------------------------------


class LoweringStrategyTest(Case):
    def test_unconfirmed_bucket_contract_is_never_fused(self):
        plan = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        execution = compile_plan(plan, reference_date=REFERENCE)
        lowering = execution.lowering["measure_groups"]
        self.assertEqual(lowering["strategy"], "daily_partition")
        rejected = {item["strategy"]: item["reason"] for item in lowering["rejected"]}
        for key in ("bucket_week_start", "bucket_partial", "bucket_empty"):
            self.assertIn(key, rejected["fused_bucket_rollup"])
        self.assertIn("range_inclusive", rejected["range_partition"])
        for step in execution.tool_steps:
            self.assertNotIn("bucket", step.arguments)
            self.assertNotIn("rollup", step.arguments)

    def test_daily_calls_cover_the_period_one_day_each(self):
        plan = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        execution = compile_plan(plan, reference_date=REFERENCE)
        calls = [step for step in execution.tool_steps if step.group is not None]
        self.assertEqual([step.arguments["date"] for step in calls], AUGUST_DAYS)
        self.assertTrue(all(step.assumptions == ["single_date"] for step in calls))
        collect = next(s for s in execution.steps if s.operator == "COLLECT_GROUPS")
        self.assertEqual([len(keys) for keys in collect.arguments["members"]],
                         [2, 7, 7, 7, 7, 1])
        self.assertEqual(collect.arguments["reducer"], "sum")

    def test_inner_average_needs_a_range_contract(self):
        """평균은 하루 평균들로 다시 만들 수 없다(표본 수가 없다). 범위 계약도 없다."""
        plan = self.compose(AVG_THEN_MAX, Q_AVG_THEN_MAX)
        with self.assertRaises(CompilerError) as caught:
            compile_plan(plan, reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "UNVERIFIED_TIMS_CONTRACT")
        reasons = {item["strategy"]: item["reason"]
                   for item in caught.exception.context["rejected"]}
        self.assertIn("avg", reasons["daily_partition"])

    def test_confirmed_range_contract_allows_range_calls(self):
        plan = self.compose(AVG_THEN_MAX, Q_AVG_THEN_MAX)
        execution = compile_plan(plan, reference_date=REFERENCE, contract=RANGE_CONTRACT)
        self.assertEqual(execution.lowering["measure_groups"]["strategy"], "range_partition")
        self.assertEqual([s.arguments["date"] for s in execution.tool_steps[1:]], AUGUST_WEEKS)

    def test_matching_bucket_contract_allows_one_call(self):
        plan = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        execution = compile_plan(plan, reference_date=REFERENCE,
                                 contract=MATCHING_BUCKET_CONTRACT)
        (step,) = execution.tool_steps[1:]
        self.assertEqual((step.arguments["bucket"], step.arguments["aggregation"],
                          step.arguments["rollup"]), ("week", "sum", "avg"))
        self.assertEqual(step.covers, ["measure_groups", "combine_groups"])
        self.assertEqual(step.argument_sources["rollup"], "combine_groups.params.reducer")

    def test_confirmed_but_different_bucket_definition_is_not_fused(self):
        contract = DEFAULT_CONTRACT.assuming(
            bucket_week_start="sunday", bucket_partial="clip_to_period",
            bucket_empty="undefined", relative_date_reference="Asia/Seoul calendar",
        )
        execution = compile_plan(self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG),
                                 reference_date=REFERENCE, contract=contract)
        lowering = execution.lowering["measure_groups"]
        self.assertEqual(lowering["strategy"], "daily_partition")
        self.assertIn("bucket_week_start", lowering["rejected"][0]["reason"])

    def test_select_is_never_fused(self):
        execution = compile_plan(self.compose(WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM),
                                 reference_date=REFERENCE, contract=MATCHING_BUCKET_CONTRACT)
        self.assertNotEqual(execution.lowering["measure_groups"]["strategy"],
                            "fused_bucket_rollup")

    def test_too_many_daily_calls_are_refused(self):
        payload = {**SUM_THEN_AVG, "date": "20260101-20260630"}
        with self.assertRaises(CompilerError) as caught:
            compile_plan(self.compose(payload, "상반기 주별 매출 합계의 평균은?"),
                         reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_PARTITION_SIZE")

    def test_lowering_rejects_a_strategy_the_contract_does_not_allow(self):
        plan = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        execution = compile_plan(plan, reference_date=REFERENCE,
                                 contract=MATCHING_BUCKET_CONTRACT)
        with self.assertRaises(CompilerError) as caught:
            verify_lowering(plan, execution, reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "LOWERING_MISMATCH")


# -- 실행: 두 경로와 fake bucket의 차이 --------------------------------------------


class ExecutionTest(Case):
    def test_1_sum_then_avg(self):
        _plan, _execution, result, answer = self.run_golden(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        self.assertEqual(result.status, STATUS_OK, result.error)
        self.assertAlmostEqual(result.final_value, 1150 / 6)
        self.assertEqual(len(self.metric_calls()), 31)
        self.assertIn("주별 합계의 평균: 191.667", answer)
        self.assertIn("하루마다 합계를 조회하고", answer)

    def test_2_avg_then_max_under_a_range_contract(self):
        _plan, _execution, result, answer = self.run_golden(
            AVG_THEN_MAX, Q_AVG_THEN_MAX, contract=RANGE_CONTRACT)
        self.assertEqual(result.final_value, 46.25)
        self.assertEqual([call["date"] for call in self.metric_calls()], AUGUST_WEEKS)
        self.assertIn("주별 평균의 최댓값: 46.25", answer)

    def test_3_overall_average_differs_from_average_of_group_averages(self):
        _plan, _execution, overall, answer = self.run_golden(OVERALL_AVG, Q_OVERALL_AVG)
        self.assertAlmostEqual(overall.final_value, 1150 / 38)
        (call,) = self.metric_calls()
        self.assertEqual(call, {"metric": "revenue", "scope": DAEGU, "date": "last_month",
                                "taxi_type": "private", "aggregation": "avg"})
        self.assertIn("개인 택시 평균 영업 수익: 30.263", answer)
        self.tims.calls.clear()
        avg_of_avgs = {**BASE, **grouped("avg", reducer="avg")}
        _plan, _execution, grouped_result, _ = self.run_golden(
            avg_of_avgs, "지난달 대구 개인택시 주별 매출 평균의 평균은?", contract=RANGE_CONTRACT)
        self.assertAlmostEqual(grouped_result.final_value,
                               (10 + 46.25 + 390 / 11 + 32.5 + 10 + 20) / 6)
        self.assertNotAlmostEqual(overall.final_value, grouped_result.final_value)

    def test_4_max_value_versus_the_week_with_the_max(self):
        _plan, _execution, value, value_answer = self.run_golden(SUM_THEN_MAX, Q_SUM_THEN_MAX)
        self.assertEqual(value.final_value, 390)
        self.assertIn("주별 합계의 최댓값: 390", value_answer)
        self.tims.calls.clear()
        _plan, _execution, week, week_answer = self.run_golden(WEEK_WITH_MAX_SUM,
                                                               Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(week.final_value["value"], 390)
        self.assertEqual([g["label"] for g in week.final_value["groups"]], [W3])
        self.assertIn("주별 합계가 가장 큰 주: 20260810-20260816", week_answer)

    def test_argmax_of_sums_is_not_argmax_of_averages(self):
        _plan, _execution, result, _answer = self.run_golden(
            WEEK_WITH_MAX_AVG, "지난달 대구 개인택시 매출 평균이 가장 큰 주는?",
            contract=RANGE_CONTRACT)
        self.assertEqual([g["label"] for g in result.final_value["groups"]], [W2])
        self.assertEqual(result.final_value["value"], 46.25)

    def test_inner_max_is_rebuilt_from_daily_maxima(self):
        _plan, _execution, result, _answer = self.run_golden(
            MAX_THEN_AVG, "지난달 대구 개인택시 주별 매출 최댓값의 평균은?")
        self.assertAlmostEqual(result.final_value, 620 / 6)
        rows = result.state["revenue_groups"]
        self.assertEqual([row["value"] for row in rows], [10, 300, 80, 190, 10, 30])
        self.assertEqual(rows[0]["parts"], [10, 10])
        self.assertEqual(rows[0]["parts_reducer"], "max")

    def test_partial_weeks_at_the_month_boundary(self):
        _plan, _execution, week, answer = self.run_golden(WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)
        rows = week.state["revenue_groups"]
        self.assertEqual([row["group"]["label"] for row in rows], AUGUST_WEEKS)
        self.assertEqual([row["value"] for row in rows], [20, 370, 390, 260, 70, 40])
        self.assertEqual([row["group"]["complete"] for row in rows],
                         [False, True, True, True, True, False])
        self.assertIn("20260801-20260802(부분 구간): 20", answer)

    def test_a_bucket_that_drops_partial_weeks_would_answer_differently(self):
        """병합을 막는 이유. TIMS가 부분 주를 버린다면 같은 인자로 다른 값이 나온다."""
        tims = FakeTims(drop_partial_buckets=True)
        fused = tims.execute("get_operation_metrics", {
            "metric": "revenue", "scope": DAEGU, "date": "last_month", "taxi_type": "private",
            "aggregation": "sum", "bucket": "week", "rollup": "avg"})
        self.assertEqual(fused, 272.5)
        tims.calls.clear()
        self.tims = tims
        _plan, _execution, result, _answer = self.run_golden(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        # 기본 계약에서는 병합하지 않으므로 의미 graph의 정의대로 계산된다.
        self.assertAlmostEqual(result.final_value, 1150 / 6)
        self.assertTrue(all("bucket" not in call for call in self.metric_calls()))

    def test_fused_path_agrees_only_when_the_contract_matches(self):
        _plan, _execution, fused, _ = self.run_golden(
            SUM_THEN_AVG, Q_SUM_THEN_AVG, contract=MATCHING_BUCKET_CONTRACT)
        _plan, _execution, daily, _ = self.run_golden(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        self.assertAlmostEqual(fused.final_value, daily.final_value)

    def test_local_reduction_when_the_tool_has_no_bucket(self):
        payload = {"concepts": [place("place", "대구"), event("passage"), measure("speed")],
                   "factors": {"date": "last_month", **grouped("max", reducer="max")}}
        _plan, _execution, result, _answer = self.run_golden(
            payload, "지난달 대구 주별 최고 속도의 최댓값은?")
        self.assertEqual(result.status, STATUS_OK, result.error)
        self.assertEqual(result.final_value, 50)
        speed = [a for n, a in self.tims.calls if n == "get_passage_metrics"]
        self.assertEqual([call["date"] for call in speed], AUGUST_DAYS)


# -- 5. 조건 보존 --------------------------------------------------------------------


class ConditionPreservationTest(Case):
    def test_every_partition_call_keeps_every_condition(self):
        self.run_golden(WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)
        calls = self.metric_calls()
        self.assertEqual(len(calls), 31)
        for call in calls:
            self.assertEqual((call["taxi_type"], call["scope"], call["aggregation"]),
                             ("private", DAEGU, "sum"))
            self.assertIn(call["date"], AUGUST_DAYS)

    def test_lost_conditions_would_change_the_answer(self):
        no_taxi = {"date": "last_month", **grouped("sum", select="max")}
        _plan, _execution, result, _answer = self.run_golden(
            no_taxi, "지난달 대구 매출 합계가 가장 큰 주는?")
        self.assertEqual([g["label"] for g in result.final_value["groups"]], [W2])
        self.assertEqual(result.final_value["value"], 5370)

    def test_lowering_that_drops_a_condition_is_rejected(self):
        plan = self.compose(WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)
        execution = compile_plan(plan, reference_date=REFERENCE)
        next(s for s in execution.steps if s.group is not None).arguments.pop("taxi_type")
        with self.assertRaises(CompilerError) as caught:
            verify_lowering(plan, execution, reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "LOWERING_MISMATCH")

    def test_lowering_with_a_missing_day_is_rejected(self):
        plan = self.compose(WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)
        execution = compile_plan(plan, reference_date=REFERENCE)
        dropped = next(s for s in execution.steps if s.group is not None)
        execution.steps.remove(dropped)
        for ids in execution.semantic_map.values():
            if dropped.id in ids:
                ids.remove(dropped.id)
        with self.assertRaises(CompilerError) as caught:
            verify_lowering(plan, execution, reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "LOWERING_MISMATCH")

    def test_lowering_with_a_wrong_collect_reducer_is_rejected(self):
        plan = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        execution = compile_plan(plan, reference_date=REFERENCE)
        next(s for s in execution.steps if s.operator == "COLLECT_GROUPS").arguments[
            "reducer"] = "max"
        with self.assertRaises(CompilerError):
            verify_lowering(plan, execution, reference_date=REFERENCE)

    def test_lowering_with_swapped_fused_stages_is_rejected(self):
        plan = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        execution = compile_plan(plan, reference_date=REFERENCE,
                                 contract=MATCHING_BUCKET_CONTRACT)
        fused = execution.tool_steps[-1]
        fused.arguments["aggregation"], fused.arguments["rollup"] = "avg", "sum"
        with self.assertRaises(CompilerError):
            verify_lowering(plan, execution, reference_date=REFERENCE,
                            contract=MATCHING_BUCKET_CONTRACT)

    def test_condition_the_tool_cannot_take_is_refused(self):
        payload = {"concepts": [place("place", "대구"), event("passage"), measure("speed")],
                   "factors": {"date": "last_month", "taxi_type": "private",
                               **grouped("max", reducer="max")}}
        with self.assertRaises(CompositionError) as caught:
            self.compose(payload, "지난달 대구 개인택시 주별 최고 속도의 최댓값은?")
        self.assertEqual(caught.exception.code, "UNCONSUMED_CONDITION")

    def test_count_tool_consumes_only_its_inherent_sum(self):
        def payload(how):
            return {"concepts": [
                {"id": "area", "concept": "LOCATION", "subtype": "scope", "role": "COND",
                 "source": "user", "value": "scope:edge:19384"},
                event("passage"), measure("passage_count")],
                "factors": {"date": "20260530", "aggregation": how}}
        question = "2026년 5월 30일 scope:edge:19384 지점을 통과하는 차량 대수는?"
        plan = self.composer.compose(parse_grounding(payload("sum"), question))
        self.assertNotIn("aggregation", plan.transformations[-1].params)
        with self.assertRaises(CompositionError) as caught:
            self.composer.compose(parse_grounding(payload("avg"), question))
        self.assertEqual(caught.exception.code, "UNCONSUMED_CONDITION")

    def test_answer_shows_period_scope_taxi_type_and_semantics(self):
        *_rest, answer = self.run_golden(WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM)
        for text in ("대구", "지난달(20260801-20260831)", "개인 택시", "주별 합계가 가장 큰 주",
                     "월요일 시작 7일", "- 계산:"):
            self.assertIn(text, answer)

    def test_trace_links_every_step_to_a_semantic_step(self):
        plan, execution, result, _answer = self.run_golden(WEEK_WITH_MAX_SUM,
                                                           Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(set(execution.semantic_map), {t.id for t in plan.transformations})
        self.assertTrue(all(entry["covers"] for entry in result.trace))
        local = [entry for entry in result.trace if entry["phase"] == "local"]
        self.assertEqual([entry["operator"] for entry in local],
                         ["COLLECT_GROUPS", "SELECT_GROUP"])
        self.assertEqual(local[0]["result"][2]["value"], 390)


# -- 6. 자료·계약이 없으면 명시적으로 거부 -----------------------------------------


class RefusalTest(Case):
    def test_relative_period_without_reference_date(self):
        with self.assertRaises(CompilerError) as caught:
            compile_plan(self.compose(WEEK_WITH_MAX_SUM, Q_WEEK_WITH_MAX_SUM))
        self.assertEqual(caught.exception.code, "UNRESOLVED_PERIOD")

    def test_no_period_to_partition(self):
        payload = {k: v for k, v in WEEK_WITH_MAX_SUM.items() if k != "date"}
        with self.assertRaises(CompilerError) as caught:
            compile_plan(self.compose(payload, "대구 개인택시 매출 합계가 가장 큰 주는?"),
                         reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "UNRESOLVED_PERIOD")

    def test_non_contiguous_period_is_not_partitioned(self):
        payload = {**WEEK_WITH_MAX_SUM, "date": "weekend"}
        with self.assertRaises(CompilerError) as caught:
            compile_plan(self.compose(payload, "주말 매출 합계가 가장 큰 주는?"),
                         reference_date=REFERENCE)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_PERIOD_FOR_GROUPING")

    def test_explicit_range_needs_no_reference_date(self):
        payload = {**WEEK_WITH_MAX_SUM, "date": "20260803-20260816"}
        execution = compile_plan(self.compose(payload, "그 기간 매출 합계가 가장 큰 주는?"))
        self.assertEqual(len([s for s in execution.tool_steps if s.group]), 14)

    def test_count_measure_cannot_be_grouped(self):
        payload = {"concepts": [place("place", "대구"), event("passage"),
                                measure("passage_count")],
                   "factors": {"date": "last_month", **grouped("sum", reducer="avg")}}
        with self.assertRaises(CompositionError) as caught:
            self.compose(payload, "지난달 대구 주별 통행량 합계의 평균은?")
        self.assertEqual(caught.exception.code, "UNSUPPORTED_GROUPED_MEASURE")

    def test_grouping_with_dimension_is_not_assumed_supported(self):
        with self.assertRaises(CompositionError) as caught:
            self.compose({**SUM_THEN_AVG, "dimension": "sigungu"},
                         "대구 시군구별 주별 매출 합계의 평균은?")
        self.assertEqual(caught.exception.code, "UNSUPPORTED_AGGREGATION_COMBINATION")

    def test_missing_tool_fails_validation(self):
        report = geoflow_validator.validate(self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG),
                                            available_tools=["get_place_scope"])
        self.assertIn(Rule.EXECUTABILITY, report.failed_rules())

    def test_day_without_data_is_not_counted_as_zero(self):
        """부산은 8/12에만 자료가 있다. 빈 날의 반환값(null)의 뜻은 계약에 없다."""
        _plan, _execution, result, answer = self.run_golden(
            revenue_grounding(WEEK_WITH_MAX_SUM, where="부산"),
            "지난달 부산 개인택시 매출 합계가 가장 큰 주는?")
        self.assertEqual(result.error["code"], "EMPTY_GROUP_VALUE")
        self.assertIsNone(answer)

    def test_tool_error_in_one_partition_stops_the_plan(self):
        self.tims = FakeTims(fail_on_date="20260804")
        _plan, _execution, result, answer = self.run_golden(WEEK_WITH_MAX_SUM,
                                                            Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(result.status, "TOOL_ERROR")
        self.assertIsNone(answer)
        self.assertEqual(self.metric_calls()[-1]["date"], "20260804")

    def test_malformed_structured_plans(self):
        for bad in ({"result": {"select": "max"}},
                    {"bucket": {"unit": "week", "reducer": "sum"}, "result": {}},
                    {"bucket": {"unit": "day", "reducer": "sum"}, "result": {"reducer": "avg"}},
                    {"bucket": {"unit": "week", "reducer": "sum"},
                     "result": {"reducer": "avg", "select": "max"}}):
            with self.subTest(plan=bad):
                with self.assertRaises(PlannerError) as caught:
                    self.ground(revenue_grounding({**BASE, **plan_of(bad)}), "질문")
                self.assertEqual(caught.exception.code, "INVALID_AGGREGATION_PLAN")

    def test_flat_contract_does_not_read_the_structured_plan(self):
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(revenue_grounding(SUM_THEN_AVG), Q_SUM_THEN_AVG)
        self.assertEqual(caught.exception.code, "UNKNOWN_FACTOR")


# -- flat·구조화 표현이 함께 올 때 ----------------------------------------------------


class SourceAgreementTest(Case):
    def test_agreeing_flat_and_structured_are_accepted(self):
        payload = revenue_grounding({**SUM_THEN_AVG, "bucket": "week", "aggregation": "sum",
                                     "rollup": "avg"})
        grounding = self.ground(payload, Q_SUM_THEN_AVG)
        self.assertEqual(grounding.aggregation.inner, "sum")
        self.assertEqual(grounding.aggregation.source, "structured+flat")

    def test_conflicting_flat_and_structured_are_rejected(self):
        for flat in ({"bucket": "week", "aggregation": "avg", "rollup": "avg"},
                     {"bucket": "week", "rollup": "avg"},
                     {"bucket": "month", "aggregation": "sum", "rollup": "avg"},
                     {"aggregation": "avg"}):
            with self.subTest(flat=flat):
                with self.assertRaises(PlannerError) as caught:
                    self.ground(revenue_grounding({**SUM_THEN_AVG, **flat}), Q_SUM_THEN_AVG)
                self.assertEqual(caught.exception.code, "AGGREGATION_SOURCE_CONFLICT")

    def test_select_cannot_agree_with_a_flat_rollup(self):
        payload = revenue_grounding({**WEEK_WITH_MAX_SUM, "bucket": "week",
                                     "aggregation": "sum", "rollup": "max"})
        with self.assertRaises(PlannerError) as caught:
            self.ground(payload, Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(caught.exception.code, "AGGREGATION_SOURCE_CONFLICT")


# -- 7. 모호한 구간 안 집계 --------------------------------------------------------


class AmbiguousInnerAggregationTest(Case):
    def test_flat_and_structured_unspecified_inner_ask_for_confirmation(self):
        for grounding in (
            parse_grounding(revenue_grounding({**BASE, "bucket": "week", "rollup": "avg"}),
                            "지난달 주별 매출의 평균은?"),
            self.ground(revenue_grounding({**BASE, **grouped("unspecified", reducer="avg")}),
                        "지난달 주별 매출의 평균은?"),
        ):
            with self.subTest(source=grounding.aggregation.source):
                with self.assertRaises(CompositionError) as caught:
                    self.composer.compose(grounding)
                self.assertEqual(caught.exception.code, "AMBIGUOUS_INNER_AGGREGATION")
                self.assertTrue(caught.exception.context["needs_clarification"])
                self.assertEqual(caught.exception.context["clarify"], "inner_reducer")
                self.assertFalse(decide_repair(caught.exception).repairable)

    def test_single_stage_without_aggregation_keeps_the_existing_behavior(self):
        payload = revenue_grounding({"date": "last_month"})
        *_rest, answer = self.run_golden(payload, "지난달 대구 매출은?")
        self.assertIn("TIMS 기본값(평균)이 적용되었습니다", answer)


# -- G7 구조 검사 --------------------------------------------------------------


class AggregationRuleTest(Case):
    def test_compressed_bucket_param_is_rejected(self):
        plan = self.composer.compose(parse_grounding(
            revenue_grounding({"date": "last_month", "aggregation": "sum"}), "질문"))
        plan.transformations[-1].params.update({"bucket": "week", "rollup": "avg"})
        self.assertIn(Rule.AGGREGATION_SEMANTICS,
                      geoflow_validator.validate(plan).failed_rules())

    def test_grouped_node_cannot_be_final(self):
        plan = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        combine = plan.transformations.pop()
        plan.concepts = [node for node in plan.concepts if node.id != combine.outputs[0]]
        plan.final_node = combine.inputs["groups"].node_id
        self.assertIn(Rule.AGGREGATION_SEMANTICS,
                      geoflow_validator.validate(plan).failed_rules())

    def test_reduce_groups_needs_a_grouped_input(self):
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
        self.assertIn(Rule.AGGREGATION_SEMANTICS,
                      geoflow_validator.validate(plan).failed_rules())

    def test_validator_rejects_a_grouped_node_without_inner_aggregation(self):
        plan = self.compose(SUM_THEN_AVG, Q_SUM_THEN_AVG)
        del next(t for t in plan.transformations if t.id == "measure_groups").params[
            "aggregation"]
        self.assertIn(Rule.AGGREGATION_SEMANTICS,
                      geoflow_validator.validate(plan).failed_rules())


# -- 8. 회귀: pipeline과 scope provenance --------------------------------------


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
        self.assertEqual(run.execution_plan["lowering"]["measure_groups"]["strategy"],
                         "daily_partition")

    def test_pipeline_reports_ambiguity_as_needs_clarification(self):
        flat = revenue_grounding({**BASE, "bucket": "week", "rollup": "avg"})
        run = self.pipeline(flat, structured=False).run("지난달 주별 매출의 평균은?")
        self.assertEqual(run.error["code"], "AMBIGUOUS_INNER_AGGREGATION")
        self.assertEqual(run.outcome, "needs_clarification")
        self.assertEqual(self.tims.calls, [])

    def test_pipeline_reports_unverified_contract_as_unsupported(self):
        run = self.pipeline(revenue_grounding(AVG_THEN_MAX)).run(Q_AVG_THEN_MAX)
        self.assertEqual(run.error["code"], "UNVERIFIED_TIMS_CONTRACT")
        self.assertEqual(run.outcome, "unsupported")
        self.assertEqual(self.tims.calls, [])

    def test_user_scope_in_a_grouped_plan_is_accepted(self):
        payload = {"concepts": [
            {"id": "area", "concept": "LOCATION", "subtype": "scope", "role": "COND",
             "source": "user", "value": DAEGU},
            event("operation"), measure("revenue")], "factors": SUM_THEN_AVG}
        _plan, _execution, result, _answer = self.run_golden(
            payload, f"지난달 {DAEGU}의 개인택시 주별 매출 합계의 평균은?")
        self.assertAlmostEqual(result.final_value, 1150 / 6)

    def test_fabricated_scope_in_a_grouped_plan_is_rejected(self):
        payload = {"concepts": [
            {"id": "area", "concept": "LOCATION", "subtype": "scope", "role": "COND",
             "source": "user", "value": DAEGU},
            event("operation"), measure("revenue")], "factors": SUM_THEN_AVG}
        with self.assertRaises(GeoFlowError) as caught:
            self.run_golden(payload, "지난달 대구 개인택시 주별 매출 합계의 평균은?")
        self.assertEqual(caught.exception.code, "UNGROUNDED_SCOPE")


class CliRepairEventTest(unittest.TestCase):
    """계획 단계 재질의 사건을 CLI가 받아도 멈추지 않는다."""

    def test_planning_repair_event_is_printed(self):
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


if __name__ == "__main__":
    unittest.main()


# -- 구조화 grounding 경로(설정으로 선택) ---------------------------------------


class _ScriptedClient:
    model = "scripted"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, tools=None, **kwargs):
        self.calls.append(messages)
        return {"message": {"content": json.dumps(self.responses.pop(0),
                                                  ensure_ascii=False)}}


class StructuredGroundingPathTest(unittest.TestCase):
    def planner(self, mode, responses=()):
        from geoflow.planner import GeoFlowPlanner
        return GeoFlowPlanner(client=_ScriptedClient(responses), aggregation_grounding=mode)

    def test_flat_prompt_is_unchanged_and_structured_prompt_is_separate(self):
        import hashlib
        flat = self.planner("flat").system_prompt()
        structured = self.planner("structured").system_prompt()
        self.assertEqual(hashlib.sha256(flat.encode()).hexdigest()[:8], "64bbceb4")
        self.assertIn("[집계 계획]", structured)
        self.assertIn('"select"', structured)
        self.assertNotIn("- bucket: month | week", structured)
        self.assertNotIn("- rollup:", structured)
        self.assertNotIn("[집계 계획]", flat)

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            self.planner("auto")

    def test_structured_pipeline_runs_from_llm_output_to_answer(self):
        from geoflow.planner import GeoFlowPlanner
        client = _ScriptedClient([revenue_grounding(WEEK_WITH_MAX_SUM)])
        tims = FakeTims()
        pipeline = GeoFlowPipeline(
            planner=GeoFlowPlanner(client=client, aggregation_grounding="structured"),
            composer=MacroComposer(), tool_executor=tims, clock=lambda: REFERENCE)
        run = pipeline.run(Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(run.outcome, "answered", run.runtime_error)
        self.assertIn("주별 합계가 가장 큰 주: 20260810-20260816", run.final_answer)
        self.assertEqual(run.grounding["aggregation"]["select"], "max")
        self.assertIn("[집계 계획]", client.calls[0][0]["content"])

    def test_flat_pipeline_rejects_the_structured_output(self):
        from geoflow.planner import GeoFlowPlanner
        pipeline = GeoFlowPipeline(
            planner=GeoFlowPlanner(client=_ScriptedClient(
                [revenue_grounding(WEEK_WITH_MAX_SUM)] * 2)),
            composer=MacroComposer(), tool_executor=FakeTims(), clock=lambda: REFERENCE)
        run = pipeline.run(Q_WEEK_WITH_MAX_SUM)
        self.assertEqual(run.error["code"], "UNKNOWN_FACTOR")

    def test_structured_ambiguity_is_a_clarification_not_a_failure(self):
        from geoflow.planner import GeoFlowPlanner
        payload = revenue_grounding({**BASE, **grouped("unspecified", reducer="avg")})
        pipeline = GeoFlowPipeline(
            planner=GeoFlowPlanner(client=_ScriptedClient([payload]),
                                   aggregation_grounding="structured"),
            composer=MacroComposer(), tool_executor=FakeTims(), clock=lambda: REFERENCE)
        run = pipeline.run("지난달 대구 개인택시 주별 매출의 평균은?")
        self.assertEqual(run.outcome, "needs_clarification")
        self.assertTrue(run.runtime_error.startswith("확인 필요:"))
        self.assertEqual(run.error["context"]["choices"], ["avg", "max", "med", "min", "sum"])

    def test_place_repair_keeps_the_structured_aggregation(self):
        from geoflow.repair import PlaceValuePatch, apply_patch
        grounding = parse_grounding(revenue_grounding(WEEK_WITH_MAX_SUM), Q_WEEK_WITH_MAX_SUM,
                                    structured_aggregation=True)
        repaired = apply_patch(grounding, PlaceValuePatch("place", "대구", ""))
        self.assertEqual(repaired.aggregation, grounding.aggregation)
        self.assertEqual(repaired.aggregation.select, "max")

    def test_cli_shows_clarification_separately_from_errors(self):
        import assistant_cli

        text = assistant_cli._format_outcome(None, "확인 필요: 각 구간 안에서 ...")
        self.assertIn("NEEDS_CLARIFICATION", text)
        self.assertNotIn("ERROR", text)
        self.assertIn("ERROR", assistant_cli._format_outcome(None, "planner 단계 실패: x"))

    def test_cli_accepts_the_grounding_option(self):
        import assistant_cli

        parser_help = io.StringIO()
        with contextlib.redirect_stdout(parser_help), self.assertRaises(SystemExit):
            assistant_cli.main(["--help"])
        self.assertIn("--aggregation-grounding", parser_help.getvalue())
