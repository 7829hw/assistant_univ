# -*- coding: utf-8 -*-
"""operator-local 조건부 계약을 못박는다.

OPERATION_METRIC의 dimension은 vendor schema상 h3·sido·sigungu·emd·dayofweek를
받지만 "scope가 설정되지 않은 경우는 sido, dayofweek만 가능"하다. 전에는 enum을
{dayofweek, sido}로 좁혀 이 규칙을 대신했고, 그러면 지역이 있는 합법한 계획까지
막혔다. 이제 enum은 전체를 적고, 일부 값이 area input을 요구한다는 것을 따로
적는다. 합성과 Validator G4는 같은 규칙 하나를 쓴다.
"""

import copy
import dataclasses
import os
import unittest
from pathlib import Path

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from geoflow import validator as geoflow_validator
from geoflow.compiler import compile_plan
from geoflow.composer import MacroComposer
from geoflow.errors import CompositionError, PlannerError
from geoflow.executor import STATUS_OK, execute_plan
from geoflow.factors import FACTOR_CONSTRAINTS
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from geoflow.operator_mapping import DERIVED_PARAMS
from geoflow.operator_registry import (
    OPERATORS, PARAM_VALUE_REQUIRES_INPUT, Operator, OperatorContractViolation,
    ParamValueRequiresInput, check_input_constraints, get_operator,
)
from geoflow.types import ValueRef
from geoflow.validator import Rule
from tests.test_geoflow_composition import (
    event, measure, new_tool_executor, payload, place,
)

BASE_DIR = Path(__file__).resolve().parent.parent
AREA_DIMENSIONS = ("h3", "sigungu", "emd")
FREE_DIMENSIONS = ("sido", "dayofweek")


def _vendor_params():
    """(tool, param) -> vendor schema의 parameter 정의. $ref는 _common.yaml에서 푼다."""
    common = yaml.safe_load((BASE_DIR / "schemas" / "_common.yaml").read_text(encoding="utf-8"))
    definitions = common.get("$defs") or common
    params = {}
    for schema in ("tims.yaml", "gazetteer.yaml"):
        entries = yaml.safe_load((BASE_DIR / "schemas" / schema).read_text(encoding="utf-8"))
        for entry in entries:
            function = entry["function"]
            for param, spec in function["parameters"]["properties"].items():
                ref = spec.get("$ref", "")
                if ref:
                    spec = {**definitions.get(ref.rsplit("/", 1)[-1], {}), **spec}
                params[(function["name"], param)] = spec
    return params


VENDOR_PARAMS = _vendor_params()


def vendor_enum_for(tool, param):
    """vendor가 값을 목록으로 한정한 parameter면 그 목록, 아니면 None.

    pattern(date·time), 정수 범위(limit), 자유 문자열(name), boolean은 enum이
    아니므로 None이다. registry에 param_enums를 요구하는 대상은 enum뿐이다.
    """
    enum = VENDOR_PARAMS.get((tool, param), {}).get("enum")
    return frozenset(enum) if enum is not None else None


SCHEMA_ENUMS = {key: vendor_enum_for(*key) for key in VENDOR_PARAMS
                if vendor_enum_for(*key) is not None}


class ConstraintObjectTest(unittest.TestCase):
    RULE = ParamValueRequiresInput(param="dimension", values=frozenset({"sigungu"}),
                                   input_name="area", reason="지역이 필요합니다.")

    def test_violation_only_when_value_matches_and_input_is_missing(self):
        self.assertIsNone(self.RULE.violation("OP", {"dimension": "sido"}, frozenset()))
        self.assertIsNone(self.RULE.violation("OP", {}, frozenset()))
        self.assertIsNone(self.RULE.violation("OP", {"dimension": "sigungu"},
                                              frozenset({"area"})))
        violation = self.RULE.violation("OP", {"dimension": "sigungu"}, frozenset({"event"}))
        self.assertEqual(violation, OperatorContractViolation(
            kind=PARAM_VALUE_REQUIRES_INPUT, operator="OP", param="dimension",
            value="sigungu", required_input="area", bound_inputs=("event",),
            reason="지역이 필요합니다.",
        ))
        self.assertEqual(violation.context(), {
            "operator": "OP", "param": "dimension", "value": "sigungu",
            "required_input": "area", "bound_inputs": ["event"],
        })

    def test_registration_rejects_a_meaningless_constraint(self):
        spec = get_operator(Operator.OPERATION_METRIC)
        outside = dataclasses.replace(spec, input_constraints=(dataclasses.replace(
            self.RULE, values=frozenset({"hourofday"})),))
        with self.assertRaises(RuntimeError):
            check_input_constraints(outside)
        # 필수 port는 늘 채워져 있으므로 제약이 아무것도 막지 않는다.
        passage = get_operator(Operator.PASSAGE_COUNT)
        required = dataclasses.replace(passage, input_constraints=(self.RULE,))
        with self.assertRaises(RuntimeError):
            check_input_constraints(required)

    def test_only_operation_metric_carries_the_rule(self):
        carrying = {name for name in OPERATORS if get_operator(name).input_constraints}
        self.assertEqual(carrying, {Operator.OPERATION_METRIC})


class SchemaEnumTest(unittest.TestCase):
    def test_operation_metric_dimension_is_the_full_vendor_enum(self):
        spec = get_operator(Operator.OPERATION_METRIC)
        self.assertEqual(spec.allowed_values("dimension"),
                         SCHEMA_ENUMS[("get_operation_metrics", "dimension")])
        rule, = spec.input_constraints
        self.assertEqual(rule.values, frozenset(AREA_DIMENSIONS))
        self.assertEqual(rule.input_name, "area")
        self.assertEqual(spec.inputs["area"].arg_name, "scope")

    def test_every_declared_enum_matches_the_vendor_schema(self):
        """registry가 적은 값 범위가 vendor schema와 다시 어긋나지 않게 한다."""
        for name in OPERATORS:
            spec = get_operator(name)
            for param, values in spec.param_enums.items():
                with self.subTest(operator=name, param=param):
                    self.assertEqual(values, SCHEMA_ENUMS[(spec.tool_name, param)])

    def test_every_exposed_param_exists_in_the_vendor_schema(self):
        for name in OPERATORS:
            spec = get_operator(name)
            for param in spec.params:
                with self.subTest(operator=name, param=param):
                    self.assertIn((spec.tool_name, param), VENDOR_PARAMS)

    def test_every_vendor_enum_has_a_registry_enum(self):
        """선언이 아예 빠진 enum도 잡는다.

        위 검사는 registry가 적은 enum만 비교해서, TRIP_COUNT.dimension처럼 선언
        자체가 없으면 지나갔다. 이번에는 operator가 노출하는 param 쪽에서 출발한다.
        registry가 output에서 값을 정하는 param(metric 등)은 사용자 값이 들어오지
        않으므로 제외한다.
        """
        missing = set()
        for name in OPERATORS:
            spec = get_operator(name)
            for param in spec.params - set(DERIVED_PARAMS):
                if vendor_enum_for(spec.tool_name, param) is not None \
                        and spec.allowed_values(param) is None:
                    missing.add((name, param))
        self.assertEqual(missing, set())

    def test_non_enum_params_are_not_forced_into_an_enum(self):
        """pattern·범위·자유 문자열 param에는 enum을 억지로 적지 않는다."""
        for name in OPERATORS:
            spec = get_operator(name)
            for param in spec.param_enums:
                with self.subTest(operator=name, param=param):
                    self.assertIsNotNone(vendor_enum_for(spec.tool_name, param))


class _ContractCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.composer = MacroComposer(MacroLibrary.from_directory())
        cls.tool_executor = new_tool_executor()

    def _compose(self, dimension, *, area):
        concepts = [event("e", "operation"), measure("m", "AMOUNT", "operating_count")]
        if area:
            concepts.insert(0, place("p", "대구"))
        question = ("대구 " if area else "") + f"{dimension} 기준 영업 횟수는?"
        return self.composer.compose(
            parse_grounding(payload(concepts, {"dimension": dimension}), question))

    def _validate(self, plan):
        return geoflow_validator.validate(plan, available_tools=self.tool_executor.tool_names)


class ConditionalContractTest(_ContractCase):
    def test_without_area_only_sido_and_dayofweek_pass(self):
        for dimension in FREE_DIMENSIONS:
            with self.subTest(dimension=dimension):
                plan = self._compose(dimension, area=False)
                self.assertTrue(self._validate(plan).ok)
                step = compile_plan(plan).steps[-1]
                self.assertEqual(step.arguments["dimension"], dimension)
                self.assertNotIn("scope", step.arguments)
        for dimension in AREA_DIMENSIONS:
            with self.subTest(dimension=dimension):
                with self.assertRaises(CompositionError) as caught:
                    self._compose(dimension, area=False)
                error = caught.exception
                self.assertEqual(error.code, PARAM_VALUE_REQUIRES_INPUT)
                self.assertEqual(error.context["param"], "dimension")
                self.assertEqual(error.context["value"], dimension)
                self.assertEqual(error.context["required_input"], "area")
                self.assertEqual(error.context["operator"], Operator.OPERATION_METRIC)
                self.assertNotIn("area", error.context["bound_inputs"])
                # 사용자에게 보이는 말에는 내부 operator 이름이 없다.
                self.assertNotIn("OPERATION_METRIC", error.user_message)
                self.assertIn("지역", error.user_message)

    def test_with_area_every_dimension_passes(self):
        for dimension in FREE_DIMENSIONS + AREA_DIMENSIONS:
            with self.subTest(dimension=dimension):
                plan = self._compose(dimension, area=True)
                self.assertEqual([t.operator for t in plan.transformations],
                                 ["RESOLVE_PLACE_SCOPE", "OPERATION_METRIC"])
                self.assertTrue(self._validate(plan).ok, self._validate(plan).errors)
                steps = compile_plan(plan).steps
                self.assertEqual([s.tool_name for s in steps],
                                 ["get_place_scope", "get_operation_metrics"])
                self.assertEqual(steps[-1].arguments["dimension"], dimension)
                self.assertIsInstance(steps[-1].arguments["scope"], ValueRef)

    def test_scoped_grouping_runs_end_to_end(self):
        """전에는 지역이 있어도 막히던 계획. 이제 합성·검증·컴파일·실행까지 간다."""
        grounding = parse_grounding(payload(
            [place("p", "대구"), event("e", "operation"),
             measure("m", "AMOUNT", "operating_count")],
            {"dimension": "sigungu", "order": "top", "limit": 3},
        ), "대구에서 영업 횟수가 가장 많은 시군구 3곳은?")
        plan = self.composer.compose(grounding)
        self.assertTrue(self._validate(plan).ok)
        result = execute_plan(compile_plan(plan), self.tool_executor)
        self.assertEqual(result.status, STATUS_OK, result.error)

    def test_nationwide_sigungu_is_rejected_before_any_tool_call(self):
        with self.assertRaises(CompositionError) as caught:
            self.composer.compose(parse_grounding(payload(
                [event("e", "operation"), measure("m", "AMOUNT", "operating_count")],
                {"dimension": "sigungu", "order": "top", "limit": 3},
            ), "전국에서 영업 횟수가 가장 많은 시군구 3곳은?"))
        self.assertEqual(caught.exception.code, PARAM_VALUE_REQUIRES_INPUT)


class SharedEvaluatorTest(_ContractCase):
    """합성을 거치지 않은 계획도 G4가 같은 규칙으로 막는다."""

    def _g4(self, plan):
        report = self._validate(plan)
        return [e for e in report.errors
                if e["rule"] == Rule.EXECUTABILITY
                and e["context"].get("code") == PARAM_VALUE_REQUIRES_INPUT]

    def _metric_step(self, plan):
        return next(t for t in plan.transformations if t.operator == "OPERATION_METRIC")

    def test_g4_rejects_a_hand_edited_plan(self):
        plan = copy.deepcopy(self._compose("dayofweek", area=False))
        self._metric_step(plan).params["dimension"] = "sigungu"
        violations = self._g4(plan)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["context"]["value"], "sigungu")
        self.assertEqual(violations[0]["context"]["required_input"], "area")

    def test_g4_rejects_a_plan_whose_area_was_removed(self):
        plan = copy.deepcopy(self._compose("emd", area=True))
        del self._metric_step(plan).inputs["area"]
        self.assertEqual(len(self._g4(plan)), 1)

    def test_g4_passes_the_same_edit_when_it_is_legal(self):
        plan = copy.deepcopy(self._compose("dayofweek", area=False))
        self._metric_step(plan).params["dimension"] = "sido"
        self.assertEqual(self._g4(plan), [])
        self.assertTrue(self._validate(plan).ok)

    def test_mapping_and_g4_report_the_same_violation(self):
        with self.assertRaises(CompositionError) as caught:
            self._compose("h3", area=False)
        plan = copy.deepcopy(self._compose("sido", area=False))
        self._metric_step(plan).params["dimension"] = "h3"
        context = dict(self._g4(plan)[0]["context"])
        context.pop("code")
        context.pop("transformation")
        self.assertEqual(context, caught.exception.context)


TRIP_DIMENSIONS = ("h3", "sido", "sigungu", "emd")


class TripCountEnumTest(_ContractCase):
    """TRIP_COUNT.dimension은 vendor enum으로 한정한다. 조건부 계약은 없다."""

    def _trip_grounding(self, dimension, *, pickup):
        concepts = [event("e", "trip"), measure("m", "AMOUNT", "trip_count")]
        if pickup:
            concepts.insert(0, place("p", "대구", od_role="pickup"))
        return parse_grounding(payload(concepts, {"dimension": dimension}),
                               ("대구에서 출발한 " if pickup else "") + "실차 구간 건수는?")

    def _trip_step(self, plan):
        return next(t for t in plan.transformations if t.operator == Operator.TRIP_COUNT)

    def test_vendor_dimensions_pass_every_stage(self):
        for dimension in TRIP_DIMENSIONS:
            for pickup in (True, False):
                with self.subTest(dimension=dimension, pickup=pickup):
                    plan = self.composer.compose(self._trip_grounding(dimension, pickup=pickup))
                    report = self._validate(plan)
                    self.assertTrue(report.ok, report.errors)
                    compiled = compile_plan(plan)
                    self.assertEqual(compiled.steps[-1].tool_name, "get_trip_count")
                    self.assertEqual(compiled.steps[-1].arguments["dimension"], dimension)
                    result = execute_plan(compiled, self.tool_executor)
                    self.assertEqual(result.status, STATUS_OK, result.error)

    def test_dayofweek_is_rejected_at_mapping(self):
        """factor로는 합법이지만 이 Tool은 받지 않는 값. Tool 호출 전에 막는다."""
        with self.assertRaises(CompositionError) as caught:
            self.composer.compose(self._trip_grounding("dayofweek", pickup=True))
        self.assertEqual(caught.exception.code, "INVALID_PARAM_VALUE")
        self.assertEqual(caught.exception.context,
                         {"operator": Operator.TRIP_COUNT, "param": "dimension"})

    def test_values_outside_every_enum_are_rejected_at_mapping(self):
        """grounding parse를 거치지 않고 들어온 값도 operator enum이 막는다."""
        for value in ("week", "banana"):
            with self.subTest(value=value):
                grounding = self._trip_grounding("sigungu", pickup=True)
                grounding.factors["dimension"] = value
                with self.assertRaises(CompositionError) as caught:
                    self.composer.compose(grounding)
                self.assertEqual(caught.exception.code, "INVALID_PARAM_VALUE")

    def test_grounding_parse_rejects_values_outside_the_factor_range_first(self):
        for value in ("week", "banana"):
            with self.subTest(value=value):
                with self.assertRaises(PlannerError) as caught:
                    self._trip_grounding(value, pickup=True)
                self.assertEqual(caught.exception.code, "INVALID_FACTOR")

    def test_g4_rejects_hand_edited_values(self):
        for value in ("dayofweek", "week", "banana"):
            with self.subTest(value=value):
                plan = copy.deepcopy(self.composer.compose(
                    self._trip_grounding("sigungu", pickup=True)))
                self._trip_step(plan).params["dimension"] = value
                errors = [e for e in self._validate(plan).errors
                          if e["rule"] == Rule.EXECUTABILITY
                          and e["context"].get("param") == "dimension"]
                self.assertEqual(len(errors), 1)

    def test_static_enum_and_conditional_contract_stay_separate(self):
        trip = get_operator(Operator.TRIP_COUNT)
        self.assertEqual(trip.input_constraints, ())
        self.assertEqual(trip.contract_violations({"dimension": "h3"}, ()), ())
        metric = get_operator(Operator.OPERATION_METRIC)
        # OPERATION_METRIC의 dayofweek는 enum 안이고 area도 필요 없다.
        self.assertIn("dayofweek", metric.allowed_values("dimension"))
        self.assertEqual(metric.contract_violations({"dimension": "dayofweek"}, ()), ())
        # TRIP_COUNT의 dayofweek는 enum 밖이다. 조건부 계약이 아니라 enum이 막는다.
        self.assertNotIn("dayofweek", trip.allowed_values("dimension"))


class RegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.composer = MacroComposer(MacroLibrary.from_directory())

    def test_passage_count_spatial_dimensions_are_unchanged(self):
        """PASSAGE_COUNT는 area가 필수 port라 규칙과 무관하다."""
        for dimension in AREA_DIMENSIONS + ("sido",):
            with self.subTest(dimension=dimension):
                plan = self.composer.compose(parse_grounding(payload(
                    [place("p", "대구"), event("e", "passage"),
                     measure("m", "AMOUNT", "passage_count")],
                    {"dimension": dimension},
                ), f"대구 {dimension}별 통행량은?"))
                self.assertEqual(compile_plan(plan).steps[-1].arguments["dimension"], dimension)

    def test_trip_count_grouping_is_unchanged(self):
        plan = self.composer.compose(parse_grounding(payload(
            [place("p", "동성로동", od_role="pickup"), event("e", "trip"),
             measure("m", "AMOUNT", "trip_count")],
            {"dimension": "sigungu"},
        ), "동성로동에서 출발한 실차 구간의 시군구별 건수는?"))
        self.assertEqual(compile_plan(plan).steps[-1].arguments["dimension"], "sigungu")

    def test_dimension_with_bucket_is_not_blocked(self):
        """vendor 근거가 없는 mock 전용 제약은 operator 계약으로 올리지 않는다."""
        spec = get_operator(Operator.OPERATION_METRIC)
        self.assertEqual(spec.contract_violations(
            {"dimension": "sido", "bucket": "week", "rollup": "avg"}, ()), ())
        self.assertFalse(any("dimension" in c.requires for c in FACTOR_CONSTRAINTS.values()
                             if c.factor == "bucket"))
        self.assertNotIn("dimension", FACTOR_CONSTRAINTS)


if __name__ == "__main__":
    unittest.main()
