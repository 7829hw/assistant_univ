# -*- coding: utf-8 -*-
"""업체 v2 계약(get_billing_metrics 등)과 geoflow 층 사이의 정합성.

schema가 기준이다. IR 어휘, operator registry, 측정값 집계 의미(geoflow/measures.py),
provider, 로컬 계산, 답변, 평가 라벨이 schema와 같은 어휘를 쓰는지 본다. v2 전환 뒤
남은 불일치와 경계 동작(결과 형식, dimension_target, 상대 기간, mock gazetteer)을 고정한다.
"""

import os
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import mock_responses  # noqa: E402
import paraphrase_corpus as P  # noqa: E402
from geoflow import analysis_ops, conditions, measures, periods, providers, tims_contract  # noqa: E402
from geoflow.answer import ANSWER_SPECS, _METRIC_LABEL  # noqa: E402
from geoflow.compiler import compile_plan  # noqa: E402
from geoflow.composer import MacroComposer  # noqa: E402
from geoflow.errors import CompilerError, CompositionError, ExecutionError  # noqa: E402
from geoflow.grounding import parse_grounding  # noqa: E402
from geoflow.macros import MacroLibrary  # noqa: E402
from geoflow.operator_registry import OPERATORS  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline, Stage  # noqa: E402
from geoflow.types import CONCEPT_SUBTYPES, CoreConcept  # noqa: E402
from reference_provider import reference_handlers  # noqa: E402
from tests.test_geoflow import (  # noqa: E402
    ScriptedClient, event_concept, grounding_payload, measure_concept, place_concept,
    place_patch, planner_response,
)
from tests.test_geoflow_composition import (  # noqa: E402
    event, measure, new_tool_executor, payload, place,
)

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA = {entry["function"]["name"]: entry["function"] for entry in yaml.safe_load(
    (BASE_DIR / "schemas" / "tims.yaml").read_text(encoding="utf-8"))}
GAZETTEER = {entry["function"]["name"] for entry in yaml.safe_load(
    (BASE_DIR / "schemas" / "gazetteer.yaml").read_text(encoding="utf-8"))}
MEASURE_CONCEPTS = (CoreConcept.AMOUNT, CoreConcept.PROPORTION)
REF = date(2026, 9, 25)


def measure_subtypes():
    return {subtype for concept in MEASURE_CONCEPTS for subtype in CONCEPT_SUBTYPES[concept]}


class VocabularyAlignmentTest(unittest.TestCase):
    """schema metric enum ↔ operator output ↔ IR 어휘 ↔ 집계 의미 표 ↔ 답변 이름."""

    def test_metric_enum_equals_the_operator_outputs(self):
        for spec in OPERATORS.values():
            if "metric" not in spec.params:
                continue
            with self.subTest(operator=spec.name):
                enum = set(SCHEMA[spec.tool_name]["parameters"]["properties"]["metric"]["enum"])
                self.assertEqual({subtype for _, subtype in spec.output.allowed}, enum)

    def test_every_ir_measure_has_semantics_and_an_answer_name(self):
        produced = {subtype for spec in OPERATORS.values() if spec.output is not None
                    for concept, subtype in spec.output.allowed if concept in MEASURE_CONCEPTS}
        self.assertEqual(produced, measure_subtypes())
        self.assertEqual(set(measures.MEASURES), measure_subtypes())
        for concept in MEASURE_CONCEPTS:
            for subtype in CONCEPT_SUBTYPES[concept]:
                with self.subTest(subtype=subtype):
                    self.assertIn((concept, subtype), ANSWER_SPECS)
        for subtype in ("speed", "rpm", "fare", "vacant_ratio", "revenue",
                        "active_taxi_count", "active_taxi_ratio", "operating_days"):
            self.assertIn(subtype, _METRIC_LABEL)

    def test_retired_v1_metrics_are_gone_from_code_facing_vocabulary(self):
        prompt = (BASE_DIR / "prompts" / "geoflow_planner.yaml").read_text(encoding="utf-8")
        for name in ("hours", "operating_count", "operating_ratio", "get_operation_metrics"):
            with self.subTest(name=name):
                self.assertNotIn(name, prompt)
                self.assertNotIn(name, _METRIC_LABEL)
        for subtype in measure_subtypes():
            self.assertIn(subtype, prompt)

    def test_providers_expose_only_schema_tools(self):
        schema_tools = set(SCHEMA) | GAZETTEER
        self.assertEqual(set(mock_responses.MOCK_HANDLERS), schema_tools)
        self.assertLessEqual(set(reference_handlers()), schema_tools)
        self.assertEqual({spec.tool_name for spec in OPERATORS.values()}, schema_tools)

    def test_every_label_in_the_evaluation_files_uses_the_current_vocabulary(self):
        registry = yaml.safe_load((BASE_DIR / "evaluation" / "corpus_registry.yaml")
                                  .read_text(encoding="utf-8"))
        files = {"stub_query.yaml", "stub_query_boundary.yaml"}
        files |= {parent for entry in registry["corpora"] for parent in entry["parents"]}
        for name in sorted(files):
            for item in yaml.safe_load((BASE_DIR / name).read_text(encoding="utf-8")):
                for label in item.get("expected_concepts") or []:
                    concept, rest = label.split("/", 1)
                    subtype = rest.split(":", 1)[0]
                    with self.subTest(file=name, id=item["id"], label=label):
                        self.assertIn(subtype, CONCEPT_SUBTYPES[CoreConcept(concept)])
                for operator in item.get("expected_operators") or []:
                    self.assertIn(operator, OPERATORS, (name, item["id"]))


class MeasureAggregationTest(unittest.TestCase):
    """비율·속도·고유 대수에 뜻이 없는 집계는 합성 전에 거부한다."""

    @classmethod
    def setUpClass(cls):
        cls.composer = MacroComposer(MacroLibrary.from_directory())

    def compose(self, subtype, concept, ev, factors, places=()):
        concepts = [*places, event("e", ev), measure("m", concept, subtype)]
        return self.composer.compose(parse_grounding(payload(concepts, factors), "질문"))

    def test_sum_of_ratio_speed_and_distinct_count_is_rejected(self):
        cases = [
            ("vacant_ratio", "PROPORTION", "drive", {"aggregation": "sum"}, "aggregation"),
            ("active_taxi_ratio", "PROPORTION", "operation", {"aggregation": "sum"},
             "aggregation"),
            ("active_taxi_count", "AMOUNT", "operation", {"aggregation": "sum"}, "aggregation"),
            ("active_taxi_ratio", "PROPORTION", "operation",
             {"date": "last_month", "bucket": "week", "aggregation": "max", "rollup": "sum"},
             "rollup"),
            ("active_taxi_count", "AMOUNT", "operation",
             {"date": "last_month", "bucket": "week", "aggregation": "max", "rollup": "sum"},
             "rollup"),
        ]
        for subtype, concept, ev, factors, stage in cases:
            with self.subTest(subtype=subtype, factors=factors):
                with self.assertRaises(CompositionError) as caught:
                    self.compose(subtype, concept, ev, factors)
                self.assertEqual(caught.exception.code, "UNDEFINED_MEASURE_AGGREGATION")
                self.assertEqual(caught.exception.context["stage"], stage)
        with self.assertRaises(CompositionError) as caught:
            self.compose("speed", "AMOUNT", "passage", {"aggregation": "sum"},
                         places=[place("p", "동대구역")])
        self.assertEqual(caught.exception.code, "UNDEFINED_MEASURE_AGGREGATION")

    def test_additive_sums_are_kept(self):
        for subtype, ev in (("revenue", "operation"), ("operating_days", "operation"),
                            ("fare", "trip")):
            with self.subTest(subtype=subtype):
                plan = self.compose(subtype, "AMOUNT", ev, {"aggregation": "sum"})
                self.assertEqual(plan.transformations[-1].params["aggregation"], "sum")

    def test_the_refusal_is_an_unsupported_outcome(self):
        client = ScriptedClient([planner_response(grounding_payload([
            event_concept("op", "operation"),
            measure_concept("r", "PROPORTION", "active_taxi_ratio"),
        ], {"aggregation": "sum"}))])
        run = GeoFlowPipeline.create(client=client, tool_executor=new_tool_executor()).run(
            "가동률 합계는?")
        self.assertEqual(run.outcome, "unsupported")
        self.assertEqual(run.error["code"], "UNDEFINED_MEASURE_AGGREGATION")
        self.assertIn("가동률", run.error["user_message"])

    #: 기록이 하루에만 속한다고 가정한 계약(테스트 가정). 로컬 재계산의 수학 조건만 보려고 쓴다.
    DAY_RECORDS = tims_contract.DEFAULT_CONTRACT.assuming(**{
        f"day_records:{tool}": "하루 기록" for tool in (
            "get_billing_metrics", "get_drive_metrics", "get_trip_metrics")})

    def grouped(self, subtype, concept, ev, inner, places=(), **options):
        plan = self.compose(subtype, concept, ev,
                            {"date": "last_month", "bucket": "week", "aggregation": inner,
                             "rollup": "avg"}, places=places)
        return compile_plan(plan, reference_date=REF, **options)

    def test_daily_partition_follows_the_measure(self):
        """구간 안 집계를 하루 값으로 다시 만드는 분해는 측정값마다 성립 여부가 다르다.

        로컬 재계산만 보려고 위임을 끄고(delegation=False) 기록 계약을 가정한다. 수학 조건은
        계약과 무관하게 막는다.
        """
        local = {"contract": self.DAY_RECORDS, "delegation": False}
        allowed = [("revenue", "AMOUNT", "operation", "max"),
                   ("revenue", "AMOUNT", "operation", "sum"),
                   ("operating_days", "AMOUNT", "operation", "sum"),
                   ("vacant_ratio", "PROPORTION", "drive", "min"),
                   ("fare", "AMOUNT", "trip", "sum")]
        for subtype, concept, ev, inner in allowed:
            with self.subTest(subtype=subtype, inner=inner):
                execution = self.grouped(subtype, concept, ev, inner, **local)
                self.assertEqual(next(iter(execution.lowering.values()))["strategy"],
                                 "daily_partition")
        refused = [("active_taxi_count", "AMOUNT", "operation", "max"),
                   ("active_taxi_ratio", "PROPORTION", "operation", "max"),
                   ("operating_days", "AMOUNT", "operation", "max")]
        for subtype, concept, ev, inner in refused:
            with self.subTest(subtype=subtype, inner=inner):
                with self.assertRaises(CompilerError) as caught:
                    self.grouped(subtype, concept, ev, inner, **local)
                self.assertEqual(caught.exception.code, "UNVERIFIED_TIMS_CONTRACT")
                reasons = " ".join(item["reason"] for item in caught.exception.context["rejected"])
                self.assertIn(f"측정값 {subtype}", reasons)

    def test_local_math_does_not_block_delegation_and_vice_versa(self):
        """로컬로 다시 만들 수 없는 조합도 업체 bucket 호출로는 위임된다. 반대로 bucket을 받지
        않는 Tool은 위임할 수 없고, 로컬 근거(day_records)가 없으면 계산하지 않는다."""
        for subtype, concept in (("active_taxi_count", "AMOUNT"),
                                 ("active_taxi_ratio", "PROPORTION"),
                                 ("operating_days", "AMOUNT")):
            with self.subTest(subtype=subtype):
                execution = self.grouped(subtype, concept, "operation", "max")
                lowering = next(iter(execution.lowering.values()))
                self.assertEqual(lowering["path"], "provider_delegated")
        for subtype, concept, ev in (("fare", "AMOUNT", "trip"),
                                     ("vacant_ratio", "PROPORTION", "drive")):
            with self.subTest(subtype=subtype):
                with self.assertRaises(CompilerError) as caught:
                    self.grouped(subtype, concept, ev, "min")
                self.assertIn("day_records:", str(caught.exception))

    def test_single_stage_daily_composition_is_measure_aware(self):
        allowed = tims_contract.DEFAULT_CONTRACT.assuming(
            **{"day_records:get_billing_metrics": "택시·일 기록"})
        ok, _, _ = tims_contract.daily_composition("get_billing_metrics", "sum",
                                                   contract=allowed, measure="revenue")
        self.assertTrue(ok)
        ok, reason, _ = tims_contract.daily_composition(
            "get_billing_metrics", "sum", contract=allowed, measure="active_taxi_count")
        self.assertFalse(ok)
        self.assertIn("고유 대수", reason)


class ResultFormatTest(unittest.TestCase):
    """v2 결과 형식: {count} object, 지역명 목록, 단위를 붙인 문자열."""

    def test_scalar_parts(self):
        where = "t"
        self.assertEqual(analysis_ops.scalar_parts({"count": 12}, where=where), (12, ""))
        self.assertEqual(analysis_ops.scalar_parts("30km/h", where=where), (30, "km/h"))
        self.assertEqual(analysis_ops.scalar_parts("35%", where=where), (35, "%"))
        self.assertEqual(analysis_ops.scalar_parts("59.2%", where=where), (59.2, "%"))
        self.assertEqual(analysis_ops.scalar_parts(7, where=where), (7, ""))
        for bad in ("빠름", True, None, [1], {"count": 1, "x": 2}):
            with self.subTest(value=bad):
                with self.assertRaises(ExecutionError):
                    analysis_ops.scalar_parts(bad, where=where)

    def test_units_survive_local_combination_and_are_not_mixed(self):
        step = type("Step", (), {})()
        step.id, step.operator, step.inputs = "s", analysis_ops.COMBINE_DAYS, ["a", "b"]
        step.arguments = {"reducer": "max"}
        self.assertEqual(analysis_ops.run(step, {"a": "30km/h", "b": "42km/h"}), "42km/h")
        with self.assertRaises(ExecutionError) as caught:
            analysis_ops.run(step, {"a": "30km/h", "b": 42})
        self.assertEqual(caught.exception.code, "MIXED_UNITS")

    def run_pipeline(self, concepts, factors, question, *, clock=REF, profile=None):
        client = ScriptedClient([planner_response(grounding_payload(concepts, factors))])
        pipeline = GeoFlowPipeline.create(client=client, tool_executor=new_tool_executor(),
                                          clock=lambda: clock, execution_profile=profile)
        return pipeline.run(question)

    def test_grouped_unit_values_are_answered_with_their_unit(self):
        # bucket을 받지 않는 Tool의 구간별 값은 로컬 재계산으로만 만들 수 있다. 그 근거
        # (기록이 하루에만 속함)는 TIMS 계약에 없으므로 여기서는 테스트 가정으로 넣는다.
        contract = tims_contract.DEFAULT_CONTRACT.assuming(**{
            "day_records:get_passage_metrics": "하루 기록",
            "day_records:get_drive_metrics": "하루 기록"})
        local = replace(providers.profile_for(), contract=contract)
        speed = self.run_pipeline(
            [place_concept("p", "동대구역"), event_concept("e", "passage"),
             measure_concept("m", "AMOUNT", "speed")],
            {"date": "last_month", "bucket": "week", "aggregation": "max", "rollup": "avg"},
            "지난달 동대구역의 주별 최고 속도 평균은?", profile=local)
        self.assertEqual(speed.stage, Stage.DONE, speed.runtime_error)
        self.assertEqual(speed.execution["final_value"], "30km/h")
        self.assertIn("30km/h", speed.final_answer)
        refused = self.run_pipeline(
            [place_concept("p", "동대구역"), event_concept("e", "passage"),
             measure_concept("m", "AMOUNT", "speed")],
            {"date": "last_month", "bucket": "week", "aggregation": "max", "rollup": "avg"},
            "지난달 동대구역의 주별 최고 속도 평균은?")
        self.assertEqual(refused.error["code"], "UNVERIFIED_TIMS_CONTRACT")
        ratio = self.run_pipeline(
            [event_concept("e", "drive"), measure_concept("m", "PROPORTION", "vacant_ratio")],
            {"date": "last_month", "bucket": "week", "aggregation": "min", "rollup": "max"},
            "지난달 주별 최저 공차율 중 가장 큰 값은?", profile=local)
        self.assertEqual(ratio.stage, Stage.DONE, ratio.runtime_error)
        self.assertEqual(ratio.execution["final_value"], "35%")
        self.assertNotIn("%%", ratio.final_answer)

    def test_count_object_and_region_name_lists(self):
        count = self.run_pipeline(
            [place_concept("p", "동대구역"), event_concept("e", "passage"),
             measure_concept("m", "AMOUNT", "passage_count")], {}, "동대구역 통행량은?")
        self.assertIn("12,345건", count.final_answer)
        self.assertNotIn("count", count.final_answer)
        pickup = self.run_pipeline(
            [event_concept("e", "trip"), measure_concept("m", "AMOUNT", "trip_count")],
            {"dimension": "emd", "dimension_target": "pickup", "order": "bottom", "limit": 2},
            "승차가 가장 적은 읍면동 2곳은?")
        self.assertEqual(pickup.stage, Stage.DONE, pickup.runtime_error)
        self.assertIn("신천동: 281건", pickup.final_answer)
        self.assertIn("승차 지역 기준", pickup.final_answer)
        both = self.run_pipeline(
            [place_concept("p", "대구", od_role="pickup"), event_concept("e", "trip"),
             measure_concept("m", "AMOUNT", "trip_count")],
            {"dimension": "sigungu"}, "대구에서 출발한 실차 구간의 시군구별 건수는?")
        self.assertEqual(both.stage, Stage.DONE, both.runtime_error)
        self.assertIn("→", both.final_answer)
        sido = self.run_pipeline(
            [event_concept("e", "operation"),
             measure_concept("m", "PROPORTION", "active_taxi_ratio")],
            {"dimension": "sido"}, "시도별 가동률은?")
        self.assertIn("서울시: 59.2%", sido.final_answer)


class DimensionTargetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.composer = MacroComposer(MacroLibrary.from_directory())

    def args(self, factors, places=()):
        plan = self.composer.compose(parse_grounding(payload(
            [*places, event("e", "trip"), measure("m", "AMOUNT", "trip_count")], factors),
            "질문"))
        return compile_plan(plan).steps[-1].arguments

    def test_each_target_reaches_the_call_and_omission_keeps_the_default(self):
        for target in ("pickup", "dropoff", "both"):
            with self.subTest(target=target):
                args = self.args({"dimension": "emd", "dimension_target": target})
                self.assertEqual(args["dimension_target"], target)
        self.assertNotIn("dimension_target", self.args({"dimension": "emd"}))
        self.assertEqual(P.tool_defaults("get_trip_count"), {"dimension_target": "both"})

    def test_dimension_target_is_not_dropped_on_a_tool_that_does_not_take_it(self):
        with self.assertRaises(CompositionError) as caught:
            self.composer.compose(parse_grounding(payload(
                [place("p", "동대구역"), event("e", "passage"),
                 measure("m", "AMOUNT", "passage_count")],
                {"dimension": "emd", "dimension_target": "pickup"}), "질문"))
        self.assertEqual(caught.exception.code, "UNCONSUMED_CONDITION")


class CurrentPeriodPolicyTest(unittest.TestCase):
    """this_week·this_month·this_year를 푸는 규칙은 애플리케이션 정책이다."""

    def span(self, token, reference):
        start, end = periods.resolve_period(token, reference_date=reference)
        return periods.describe_period(start, end)

    def test_fixed_reference_dates_and_boundaries(self):
        cases = [
            # 2026-09-25(금). 주는 월요일에 시작한다.
            ("this_week", date(2026, 9, 25), "20260921-20260925"),
            ("this_week", date(2026, 9, 21), "20260921-20260921"),  # 월요일이면 하루
            ("this_week", date(2026, 9, 27), "20260921-20260927"),  # 일요일
            # 2026-01-01(목): 이번 주는 전년도 월요일에 시작한다.
            ("this_week", date(2026, 1, 1), "20251229-20260101"),
            ("this_month", date(2026, 9, 1), "20260901-20260901"),
            ("this_month", date(2024, 2, 29), "20240201-20240229"),
            ("this_year", date(2026, 1, 1), "20260101-20260101"),
            ("this_year", date(2026, 9, 25), "20260101-20260925"),
            ("last_week", date(2026, 1, 1), "20251222-20251228"),
        ]
        for token, reference, expected in cases:
            with self.subTest(token=token, reference=reference):
                self.assertEqual(self.span(token, reference), expected)
        for token in ("this_week", "this_month", "this_year"):
            with self.assertRaises(CompilerError):
                periods.resolve_period(token)

    def test_reference_date_is_the_seoul_calendar_day(self):
        # UTC 15:30은 서울 다음 날 00:30이다. 이번 달이 10월로 넘어간다.
        instant = datetime(2026, 9, 30, 15, 30, tzinfo=timezone.utc)
        reference = conditions.seoul_date(instant)
        self.assertEqual(reference, date(2026, 10, 1))
        self.assertEqual(self.span("this_month", reference), "20261001-20261001")

    def test_week_buckets_inside_this_month_are_clipped(self):
        start, end = periods.resolve_period("this_month", reference_date=REF)
        groups = periods.partition(start, end, "week")
        self.assertEqual(groups[0]["label"], "20260901-20260906")
        self.assertEqual(groups[-1]["label"], "20260921-20260925")
        self.assertFalse(groups[0]["complete"])
        self.assertFalse(groups[-1]["complete"])

    def test_policy_is_recorded_separately_from_the_tims_contract(self):
        self.assertEqual(tims_contract.ITEMS["relative_date_reference"].status,
                         tims_contract.UNKNOWN)
        composer = MacroComposer(MacroLibrary.from_directory())
        plan = composer.compose(parse_grounding(payload(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"date": "this_month", "aggregation": "sum"}), "이번 달 수입 합계는?"))
        record = next(iter(compile_plan(plan, reference_date=REF).date_semantics.values()))
        # legacy는 토큰을 그대로 보낸다. 해석 범위는 이 애플리케이션의 규칙이다.
        self.assertEqual(record["request"], ["this_month"])
        self.assertEqual(record["interpreted_range"], "20260901-20260925")
        self.assertEqual(record["interpretation"]["source"], "application_policy")
        self.assertEqual(record["provider"], tims_contract.SEMANTICS_UNVERIFIED)
        grouped = composer.compose(parse_grounding(payload(
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"date": "this_month", "bucket": "week", "aggregation": "sum", "rollup": "max"}),
            "이번 달 주별 수입 합계의 최댓값은?"))
        # 위임 호출: 토큰을 그대로 보내고 기간 경계는 제공자가 정한다.
        delegated = compile_plan(grouped, reference_date=REF)
        record = next(iter(delegated.date_semantics.values()))
        self.assertEqual((record["request"], record["responsibility"]),
                         (["this_month"], "provider"))
        lowering = next(iter(delegated.lowering.values()))
        self.assertEqual(lowering["semantics"]["relative_date"]["value"], "provider_defined")
        self.assertEqual(delegated.periods, {})
        # 로컬 재계산: 애플리케이션 정책으로 푼 기간과 그 출처가 남는다.
        local = compile_plan(grouped, reference_date=REF, delegation=False,
                             contract=tims_contract.DEFAULT_CONTRACT.assuming(
                                 **{"day_records:get_billing_metrics": "택시·일"}))
        detail = next(iter(local.periods.values()))
        self.assertEqual(detail["resolved"], "20260901-20260925")
        self.assertEqual(detail["interpretation"]["source"], "application_policy")
        self.assertEqual(next(iter(local.lowering.values()))["semantics"]["relative_date"]
                         ["source"], "application")


class MockGazetteerHierarchyTest(unittest.TestCase):
    """"대구 동성로동" NOT_FOUND는 v2 mock 계층 데이터의 결함이다."""

    def test_region_check_fails_because_the_parent_chain_does_not_reach_daegu(self):
        dongseongro_dong = mock_responses.DISTRICT_FIXTURES["동성로동"]["scope"]
        self.assertEqual(mock_responses.mock_get_place_scope({"name": "동성로동"}),
                         dongseongro_dong)
        parent = mock_responses.PARENT_BY_SCOPE[dongseongro_dong]
        # 부모 scope(2711000000)가 districts에 없어 대구까지 이어지지 않는다.
        self.assertEqual(parent, "scope:district:2711000000")
        self.assertNotIn(parent, mock_responses.PARENT_BY_SCOPE)
        failed = mock_responses.mock_get_place_scope({"name": "동성로동", "region": "대구"})
        self.assertEqual(failed["error_code"], "NOT_FOUND")
        # 같은 mock에서 중구 소속 장소는 대구로 이어진다.
        self.assertEqual(mock_responses.mock_get_place_scope({"name": "동인동", "region": "대구"}),
                         mock_responses.DISTRICT_FIXTURES["동인동"]["scope"])

    def test_repair_to_the_street_changes_the_place_and_is_not_the_intended_argument(self):
        question = "대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는?"
        grounding = grounding_payload([
            place_concept("origin", "동성로동", "대구", od_role="pickup"),
            place_concept("destination", "신천동", od_role="dropoff"),
            event_concept("trip", "trip"), measure_concept("m", "AMOUNT", "trip_count")])
        client = ScriptedClient([planner_response(grounding),
                                 planner_response(place_patch("origin", "동성로", "대구"))])
        run = GeoFlowPipeline.create(client=client, tool_executor=new_tool_executor()).run(
            question)
        # 실행은 성공하지만 출발지가 동성로동(행정동)이 아니라 동성로(도로 edge)로 바뀌었다.
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        call = next(hop for hop in run.hop_log if hop["tool"] == "get_trip_count")
        self.assertEqual(call["arguments"]["scope_pickup"], "scope:edge:1742")
        self.assertNotEqual(call["arguments"]["scope_pickup"],
                            mock_responses.DISTRICT_FIXTURES["동성로동"]["scope"])
        self.assertEqual(run.slots["origin"]["name"], "동성로")


if __name__ == "__main__":
    unittest.main()
