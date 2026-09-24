# -*- coding: utf-8 -*-
"""production grounding의 집계 계약(aggregation_plan)과 그 lowering.

측정한 H2 arm(04d7baed, evaluation/prompt_ab/20260924_032103_aggregation_holdout_h0_h2_r2)과
production이 같은 계약이라는 것을 여기서 못박는다. raw 표현만 바뀌고 실행 의미는
그대로라는 것도 corpus golden 전체로 확인한다.
"""

import copy
import dataclasses
import hashlib
import inspect
import json
import os
import unittest
from collections import Counter

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_plan as AP
import aggregation_prompt
import evaluate_prompt_ab as A
import paraphrase_corpus as P
from geoflow import aggregation as GA
from geoflow import factors as F
from geoflow import validator as geoflow_validator
from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError, PlannerError
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from geoflow.pipeline import Stage
from geoflow.planner import GeoFlowPlanner
from tests.test_geoflow_composition import new_tool_executor
from tests.test_geoflow_repair import event, measure, new_pipeline, payload

MEASURED_H2_SHA256 = "04d7baed2220c1d5dc748b2b9593b15e28921ef1c0ff2411feeb30ab307224bc"
REPAIR_SHA256 = "5af4c744a448f008fa9e1fa92848f4b08e24870bcd156852e4c71369e80e67c4"

REVENUE = [event("e", "operation"), measure("m", "AMOUNT", "revenue")]


class _Client:
    model = "x"


def _prompt():
    return GeoFlowPlanner(client=_Client()).system_prompt()


def _raise_code(test, raw, code):
    with test.assertRaises(PlannerError) as caught:
        GA.lower_raw_grounding(raw, raw_text="raw")
    test.assertEqual(caught.exception.code, code)
    test.assertEqual(caught.exception.context["raw_text"], "raw")
    return caught.exception


class ParserTest(unittest.TestCase):
    def test_no_bucket_plan(self):
        plan = GA.parse_aggregation_plan({"result": {"reducer": "avg"}})
        self.assertEqual(plan, GA.AggregationPlan(result_reducer="avg"))

    def test_bucket_with_a_specified_inner_reducer(self):
        plan = GA.parse_aggregation_plan(
            {"bucket": {"unit": "month", "reducer": "sum"}, "result": {"reducer": "avg"}})
        self.assertEqual(plan.bucket, GA.AggregationBucket(unit="month", reducer="sum"))
        self.assertEqual(plan.result_reducer, "avg")

    def test_bucket_with_an_unspecified_inner_reducer_keeps_the_marker(self):
        raw = {"bucket": {"unit": "week", "reducer": "unspecified"}, "result": {"reducer": "max"}}
        plan = GA.parse_aggregation_plan(raw)
        self.assertEqual(plan.bucket.reducer, GA.UNSPECIFIED)
        # unspecified는 avg로 합쳐지지 않는다. lowering 전까지 그대로 남는다.
        self.assertNotEqual(plan, GA.parse_aggregation_plan(
            {"bucket": {"unit": "week", "reducer": "avg"}, "result": {"reducer": "max"}}))
        self.assertEqual(plan.to_dict(), raw)

    def test_structural_errors_name_the_field(self):
        cases = (
            ({"bucket": {"unit": "month", "reducer": "sum"}}, "result"),
            ({"result": {}}, "result"),
            ({"bucket": {"unit": "month"}, "result": {"reducer": "avg"}}, "bucket"),
            ({"bucket": {"reducer": "sum"}, "result": {"reducer": "avg"}}, "bucket"),
            ({"result": {"reducer": "mean"}}, "result.reducer"),
            ({"result": {"reducer": "unspecified"}}, "result.reducer"),
            ({"result": {"reducer": ["avg"]}}, "result.reducer"),
            ({"bucket": {"unit": "month", "reducer": "mean"}, "result": {"reducer": "avg"}},
             "bucket.reducer"),
            ({"bucket": {"unit": "day", "reducer": "sum"}, "result": {"reducer": "avg"}},
             "bucket.unit"),
            ({"result": {"reducer": "avg"}, "stages": 2}, GA.PLAN_KEY),
            ("avg", GA.PLAN_KEY),
        )
        for plan, field in cases:
            with self.subTest(plan=plan):
                error = _raise_code(self, {"concepts": [], "factors": {GA.PLAN_KEY: plan}},
                                    GA.INVALID_AGGREGATION_PLAN)
                self.assertEqual(error.context["field"], field)
                self.assertIn(field, error.detail)

    def test_flat_aggregation_factors_are_not_raw_vocabulary(self):
        for flat in ({"bucket": "month"}, {"aggregation": "avg"}, {"rollup": "sum"},
                     {"aggregation": None}):
            with self.subTest(flat=flat):
                error = _raise_code(self, {"concepts": [], "factors": flat},
                                    GA.FLAT_AGGREGATION_FACTOR)
                self.assertEqual(error.context["flat_factors"], list(flat))

    def test_a_plan_and_flat_factors_are_two_sources(self):
        plan = {"result": {"reducer": "avg"}}
        for flat in ("bucket", "aggregation", "rollup"):
            with self.subTest(flat=flat):
                _raise_code(self, {"concepts": [], "factors": {GA.PLAN_KEY: plan, flat: "max"}},
                            GA.DUPLICATE_AGGREGATION_SOURCE)

    def test_evaluation_uses_the_production_codes(self):
        self.assertEqual(AP.DUPLICATE_AGGREGATION_SOURCE, GA.DUPLICATE_AGGREGATION_SOURCE)
        self.assertEqual(AP.FLAT_AGGREGATION_FACTOR, GA.FLAT_AGGREGATION_FACTOR)
        self.assertEqual(AP.LOWERING_ERROR, GA.INVALID_AGGREGATION_PLAN)

    def test_plan_errors_are_not_repairable(self):
        from geoflow.repair import decide

        for code in GA.AGGREGATION_PLAN_CODES:
            with self.subTest(code=code):
                self.assertFalse(decide(PlannerError("x", code=code)).repairable)


class LoweringTest(unittest.TestCase):
    def _lower(self, plan, **others):
        return GA.lower_raw_grounding(
            {"concepts": [], "factors": {**others, GA.PLAN_KEY: plan}})["factors"]

    def test_the_three_shapes(self):
        self.assertEqual(self._lower({"result": {"reducer": "avg"}}), {"aggregation": "avg"})
        self.assertEqual(
            self._lower({"bucket": {"unit": "month", "reducer": "sum"},
                         "result": {"reducer": "avg"}}),
            {"bucket": "month", "rollup": "avg", "aggregation": "sum"})
        lowered = self._lower({"bucket": {"unit": "week", "reducer": "unspecified"},
                               "result": {"reducer": "max"}})
        self.assertEqual(lowered, {"bucket": "week", "rollup": "max"})
        self.assertNotIn(GA.UNSPECIFIED, lowered.values())

    def test_other_factors_survive_in_order(self):
        lowered = self._lower({"result": {"reducer": "avg"}}, date="last_month",
                              time="120000-130000", taxi_type="private", vicinity=True)
        self.assertEqual(list(lowered), ["date", "time", "taxi_type", "vicinity", "aggregation"])
        self.assertEqual(lowered["taxi_type"], "private")
        self.assertNotIn(GA.PLAN_KEY, lowered)

    def test_lowering_is_deterministic_and_does_not_mutate(self):
        raw = {"concepts": [{"id": "x"}], "factors": {
            "date": "last_week",
            GA.PLAN_KEY: {"bucket": {"unit": "month", "reducer": "sum"},
                          "result": {"reducer": "avg"}}}}
        before = copy.deepcopy(raw)
        first, second = GA.lower_raw_grounding(raw), GA.lower_raw_grounding(raw)
        self.assertEqual(first, second)
        self.assertEqual(raw, before)
        self.assertIs(first["concepts"], raw["concepts"])

    def test_lowered_payload_is_not_raw_again(self):
        """raw와 내부 어휘는 겹치지 않는다. 두 번 내리는 경로는 없고, 하면 거부된다."""
        lowered = GA.lower_raw_grounding(
            {"concepts": [], "factors": {GA.PLAN_KEY: {"result": {"reducer": "avg"}}}})
        _raise_code(self, lowered, GA.FLAT_AGGREGATION_FACTOR)

    def test_payloads_without_aggregation_pass_through(self):
        for raw in ({"concepts": [], "factors": {"date": "last_month"}},
                    {"concepts": []}, {"unsupported": True},
                    {"concepts": [], "factors": "oops"}):
            with self.subTest(raw=raw):
                self.assertIs(GA.lower_raw_grounding(raw), raw)


class PipelineTest(unittest.TestCase):
    """raw H2 → lowering → 합성 → operator → G1~G6 → 컴파일 → Mock 실행."""

    CASES = (
        ("f01", "월 단위로 합산한 택시 수입의 평균은?",
         {"bucket": {"unit": "month", "reducer": "sum"}, "result": {"reducer": "avg"}},
         {"bucket": "month", "aggregation": "sum", "rollup": "avg"}),
        ("f03", "월 단위 택시 수입의 합계는?",
         {"bucket": {"unit": "month", "reducer": "unspecified"}, "result": {"reducer": "sum"}},
         {"bucket": "month", "aggregation": None, "rollup": "sum"}),
        ("avg_inner", "주 단위 평균 수입의 최대값은?",
         {"bucket": {"unit": "week", "reducer": "avg"}, "result": {"reducer": "max"}},
         {"bucket": "week", "aggregation": "avg", "rollup": "max"}),
        ("no_bucket", "택시 수입의 평균은?",
         {"result": {"reducer": "avg"}},
         {"bucket": None, "aggregation": "avg", "rollup": None}),
    )

    def test_each_shape_runs_to_the_tool(self):
        for name, question, plan, expected in self.CASES:
            with self.subTest(case=name):
                pipeline, client = new_pipeline([payload(REVENUE, {GA.PLAN_KEY: plan})])
                run = pipeline.run(question)
                self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(run.validation["status"], "OK")
                self.assertEqual(len(run.validation["checked_rules"]), 6)
                self.assertEqual(run.repair_count, 0)
                self.assertEqual([entry["tool"] for entry in run.hop_log][:1],
                                 ["get_operation_metrics"])
                arguments = run.hop_log[0]["arguments"]
                for key, value in expected.items():
                    self.assertEqual(arguments.get(key), value, key)
                self.assertNotIn(GA.PLAN_KEY, json.dumps(run.execution_plan, default=str))
                self.assertNotIn(GA.UNSPECIFIED, json.dumps(arguments, default=str))

    def test_the_plan_does_not_reach_geoflow(self):
        planner = GeoFlowPlanner(client=_ScriptedText(json.dumps(payload(REVENUE, {
            GA.PLAN_KEY: {"bucket": {"unit": "month", "reducer": "unspecified"},
                          "result": {"reducer": "sum"}}}))))
        grounding = planner.plan("월 단위 택시 수입의 합계는?").grounding
        self.assertEqual(grounding.factors, {"bucket": "month", "rollup": "sum"})
        plan = MacroComposer(MacroLibrary.from_directory()).compose(grounding)
        text = json.dumps([dataclasses.asdict(t) for t in plan.transformations], default=str)
        self.assertNotIn(GA.PLAN_KEY, text)
        self.assertNotIn(GA.UNSPECIFIED, text)

    def test_downstream_modules_do_not_know_the_plan(self):
        from geoflow import compiler, composer, executor, macros, operator_mapping
        from geoflow import operator_registry, validator

        for module in (compiler, composer, executor, macros, operator_mapping,
                       operator_registry, validator):
            with self.subTest(module=module.__name__):
                self.assertNotIn(GA.PLAN_KEY, inspect.getsource(module))

    def test_the_bucket_rollup_invariant_still_guards_lowered_factors(self):
        """lowering을 거치지 않은 경로로 bucket만 내려와도 기존 불변식이 막는다."""
        grounding = parse_grounding(payload(REVENUE, {"bucket": "month"}), "q")
        with self.assertRaises(GeoFlowError) as caught:
            MacroComposer(MacroLibrary.from_directory()).compose(grounding)
        self.assertEqual(caught.exception.code, "INVALID_FACTOR_COMBINATION")
        self.assertIn("bucket", F.FACTOR_CONSTRAINTS)
        self.assertIn("rollup", F.FACTOR_CONSTRAINTS)


class _ScriptedText:
    model = "x"

    def __init__(self, text):
        self.text = text

    def chat(self, messages, tools=None):
        return {"message": {"content": self.text}}


class SemanticEquivalenceTest(unittest.TestCase):
    """corpus golden 전체: flat golden의 Tool 호출 == H2로 적고 내린 Tool 호출."""

    REGISTRY = yaml.safe_load((P.BASE_DIR / "evaluation" / "corpus_registry.yaml")
                              .read_text(encoding="utf-8"))

    def test_every_aggregation_golden(self):
        composer = MacroComposer(MacroLibrary.from_directory())
        tools = new_tool_executor().tool_names
        checked = Counter()
        for entry in self.REGISTRY["corpora"]:
            path = P.BASE_DIR / entry["path"]
            parents = P.corpus_parents(path)
            for intent in P.load_corpus(path, parents):
                golden = intent.get("golden") or {}
                factors = golden.get("factors") or {}
                if not any(key in factors for key in AP.FLAT_KEYS):
                    continue
                question = parents[intent["intent"]]["question"]
                raw = AP.raw_grounding(golden)
                self.assertIn(GA.PLAN_KEY, raw["factors"])
                planner = GeoFlowPlanner(client=_ScriptedText(json.dumps(raw, ensure_ascii=False)))
                calls = []
                for grounding in (parse_grounding(golden, question),
                                  planner.plan(question).grounding):
                    plan = composer.compose(grounding)
                    self.assertTrue(geoflow_validator.validate(plan, available_tools=tools).ok)
                    calls.append(P.final_tool_call(plan))
                with self.subTest(corpus=path.name, intent=intent["intent"]):
                    self.assertEqual(calls[0], calls[1])
                checked[path.name] += 1
        # 네 corpus 모두에 집계 golden이 있다.
        self.assertEqual(len(checked), len(self.REGISTRY["corpora"]))
        self.assertGreaterEqual(sum(checked.values()), 38)



class PromptContractTest(unittest.TestCase):
    """measured H2와 production prompt가 byte 단위로 같다."""

    def test_production_prompt_is_the_measured_h2_prompt(self):
        production = _prompt()
        measured = aggregation_prompt.h2_prompt(A._h0_prompt())
        self.assertEqual(production, measured)
        self.assertEqual(hashlib.sha256(production.encode("utf-8")).hexdigest(),
                         MEASURED_H2_SHA256)

    def test_production_variant_keeps_the_repair_contract(self):
        variant = A.build_variant("PRODUCTION")
        self.assertEqual(variant.sha256, MEASURED_H2_SHA256)
        self.assertEqual(variant.repair_sha256, REPAIR_SHA256)
        self.assertEqual(variant.aggregation_contract, "plan")
        self.assertEqual(A.build_variant("H2_AGG").sha256, MEASURED_H2_SHA256)

    def test_the_frozen_h0_prompt_is_the_previous_production(self):
        self.assertEqual(hashlib.sha256(A._h0_prompt().encode("utf-8")).hexdigest(),
                         A.PINNED_SHA256["H0_AGG"])

    def test_raw_vocabulary_hides_the_lowered_factors(self):
        from geoflow.planner import describe_factors

        names = [line.split(":")[0][2:] for line in describe_factors().splitlines()]
        self.assertIn(GA.PLAN_KEY, names)
        for name in GA.LOWERED_FACTORS:
            self.assertNotIn(name, names)
        prompt = _prompt()
        self.assertNotIn("- bucket를 넣으면", prompt)
        self.assertNotIn("- rollup를 넣으면", prompt)
        self.assertIn("- order를 넣으면 dimension도", prompt)

    def test_reducer_values_come_from_the_factor_specs(self):
        """FactorSpec 값이 바뀌면 [집계 계획]과 parser가 함께 바뀐다."""
        original = dict(F.FACTOR_SPECS)
        extended = original["aggregation"].values | {"p90"}
        try:
            for name in ("aggregation", "rollup"):
                F.FACTOR_SPECS[name] = dataclasses.replace(original[name], values=extended)
            F.FACTOR_SPECS["bucket"] = dataclasses.replace(
                original["bucket"], values=original["bucket"].values | {"quarter"})
            contract = GA.describe_aggregation_contract()
            self.assertIn("<avg | max | med | min | p90 | sum | unspecified>", contract)
            self.assertIn('"result": {"reducer": "<avg | max | med | min | p90 | sum>"}', contract)
            self.assertIn("<month | quarter | week>", contract)
            self.assertIn("month | quarter | week", GA.describe_plan_meaning())
            self.assertEqual(GA.parse_aggregation_plan(
                {"bucket": {"unit": "quarter", "reducer": "p90"},
                 "result": {"reducer": "p90"}}).lower(),
                {"bucket": "quarter", "rollup": "p90", "aggregation": "p90"})
        finally:
            F.FACTOR_SPECS.clear()
            F.FACTOR_SPECS.update(original)
        self.assertEqual(hashlib.sha256(_prompt().encode("utf-8")).hexdigest(),
                         MEASURED_H2_SHA256)

    def test_no_enum_is_written_by_hand(self):
        source = inspect.getsource(GA)
        self.assertNotIn("avg | max", source)
        self.assertNotIn('"month", "week"', source)
        self.assertNotIn("month | week", source)

    def test_repair_keeps_the_lowered_vocabulary(self):
        """재질의는 lowering된 grounding을 다루므로 flat factor 이름으로 설명한다."""
        self.assertIn("bucket과 함께 쓸 수 없다", F.describe_factor_semantics(["dimension"]))
        self.assertIn("aggregation_plan의 bucket과 함께 쓸 수 없다", _prompt())


if __name__ == "__main__":
    unittest.main()
