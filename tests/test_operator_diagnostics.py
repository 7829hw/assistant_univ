# -*- coding: utf-8 -*-
"""operator를 고르지 못했을 때의 진단을 못박는다.

예전에는 후보 operator가 입력을 port에 배치하지 못한 이유가 모두 ``None``
하나로 사라져, "그런 operator가 없다"와 "operator는 있는데 필수 input이 질문에
없다"를 구분할 수 없었다. 이제 후보마다 실패 이유를 남기고, 필수 input이 정말
graph에 없을 때만 MISSING_REQUIRED_INPUT을 낸다. 나머지는 NO_OPERATOR다.

진단만 바뀌어야 한다. 어떤 operator가 선택되는지는 예전과 같아야 한다.
"""

import itertools
import json
import os
import unittest
from pathlib import Path

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_planner as E
from geoflow import operator_mapping
from geoflow.composer import MacroComposer
from geoflow.errors import CompositionError, GeoFlowError
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from geoflow.operator_mapping import BindFailureReason, CandidateFailure
from geoflow.operator_registry import OPERATORS, Operator, get_operator
from geoflow.planner import GeoFlowPlanner
from geoflow.repair import decide
from geoflow.types import ConceptNode, CoreConcept, FunctionalRole, NodeSource
from tests.test_geoflow_composition import (
    event, measure, new_tool_executor, payload, place,
)

BASE_DIR = Path(__file__).resolve().parent.parent
LOCATION_HINT = "지역을 함께 지정"


def _b18_item():
    items = yaml.safe_load(
        (BASE_DIR / "stub_query_boundary.yaml").read_text(encoding="utf-8"))
    return next(item for item in items if item["id"] == "b18_passage_count_ranking")


B18 = _b18_item()
B18_GOLDEN = payload(
    [event("e", "passage"), measure("m", "AMOUNT", "passage_count")],
    {"dimension": "sigungu", "order": "top", "limit": 3},
)


def _reference_bind_ports(spec, inputs):
    """d454988까지의 _bind_ports. 선택 결과가 그대로인지 비교하는 기준이다."""
    assigned = {}
    for port, port_spec in spec.inputs.items():
        matches = [node for node in inputs
                   if port_spec.binds(node.concept, node.subtype, node.attributes)]
        if len(matches) > 1:
            return None
        if not matches:
            if port_spec.required:
                return None
            continue
        assigned[port] = matches[0]
    consumed = {node.id for node in assigned.values()}
    if any(node.id not in consumed for node in inputs):
        return None
    return assigned


def _node(node_id, concept, subtype, **attributes):
    return ConceptNode(id=node_id, concept=concept, subtype=subtype,
                       role=FunctionalRole.COND, source=NodeSource.TOOL,
                       attributes=dict(attributes))


class _ComposeCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.composer = MacroComposer(MacroLibrary.from_directory())

    def _failure(self, concepts, factors=None, question="질문"):
        with self.assertRaises(CompositionError) as caught:
            self.composer.compose(parse_grounding(payload(concepts, factors), question))
        return caught.exception

    def _reasons(self, error):
        return {item["operator"]: item["reasons"]
                for item in error.context["candidate_failures"]}


class CandidateFailureTest(unittest.TestCase):
    def _failure(self, *problems):
        return CandidateFailure(operator="X", problems=tuple(problems))

    def test_only_a_single_missing_required_port_counts(self):
        missing = operator_mapping.BindProblem(
            BindFailureReason.REQUIRED_PORT_UNBOUND, port="area",
            expected_concept=CoreConcept.LOCATION, expected_subtypes=("scope",))
        leftover = operator_mapping.BindProblem(
            BindFailureReason.UNCONSUMED_INPUT, nodes=("e",))
        ambiguous = operator_mapping.BindProblem(
            BindFailureReason.AMBIGUOUS_PORT, port="event", nodes=("a", "b"))
        self.assertIs(self._failure(missing).sole_missing_port(), missing)
        self.assertIsNone(self._failure(missing, leftover).sole_missing_port())
        self.assertIsNone(self._failure(missing, missing).sole_missing_port())
        self.assertIsNone(self._failure(ambiguous).sole_missing_port())
        self.assertIsNone(self._failure(leftover).sole_missing_port())
        self.assertEqual(
            self._failure(leftover, missing).reasons,
            (BindFailureReason.REQUIRED_PORT_UNBOUND, BindFailureReason.UNCONSUMED_INPUT))

    def test_every_problem_of_a_candidate_is_kept(self):
        """passage_count에 trip 사건이 붙으면 area도 비고 trip도 남는다."""
        spec = get_operator(Operator.PASSAGE_COUNT)
        assigned, failure = operator_mapping._bind_ports(
            spec, [_node("t", CoreConcept.EVENT, "trip")])
        self.assertIsNone(assigned)
        self.assertEqual(failure.reasons, (BindFailureReason.REQUIRED_PORT_UNBOUND,
                                           BindFailureReason.UNCONSUMED_INPUT))


class SelectionUnchangedTest(unittest.TestCase):
    """진단을 얻으려고 operator 선택이 달라지면 안 된다."""

    NODES = (
        _node("p", CoreConcept.LOCATION, "place"),
        _node("s", CoreConcept.LOCATION, "scope"),
        _node("s2", CoreConcept.LOCATION, "scope"),
        _node("v", CoreConcept.LOCATION, "vicinity_scope"),
        _node("sp", CoreConcept.LOCATION, "scope", od_role="pickup"),
        _node("sd", CoreConcept.LOCATION, "scope", od_role="dropoff"),
        _node("ep", CoreConcept.EVENT, "passage"),
        _node("et", CoreConcept.EVENT, "trip"),
        _node("ed", CoreConcept.EVENT, "drive"),
        _node("eo", CoreConcept.EVENT, "operation"),
    )

    def test_binding_matches_the_previous_algorithm(self):
        checked = 0
        for spec in OPERATORS.values():
            for size in range(4):
                for inputs in itertools.combinations(self.NODES, size):
                    expected = _reference_bind_ports(spec, list(inputs))
                    assigned, failure = operator_mapping._bind_ports(spec, list(inputs))
                    self.assertEqual(assigned, expected, (spec.name, inputs))
                    self.assertEqual(failure is None, expected is not None)
                    checked += 1
        self.assertGreater(checked, 1000)


class MissingRequiredInputTest(_ComposeCase):
    def test_b18_golden_grounding(self):
        with self.assertRaises(CompositionError) as caught:
            self.composer.compose(parse_grounding(B18_GOLDEN, B18["question"]))
        error = caught.exception
        self.assertEqual(error.code, "MISSING_REQUIRED_INPUT")
        context = dict(error.context)
        failures = context.pop("candidate_failures")
        self.assertEqual(context, {
            "output": "AMOUNT/passage_count",
            "candidate_operator": Operator.PASSAGE_COUNT,
            "required_port": "area",
            "expected_concept": "LOCATION",
            "expected_subtypes": ["scope", "vicinity_scope"],
            "available_inputs": ["EVENT/passage"],
        })
        self.assertEqual(failures, [{
            "operator": Operator.PASSAGE_COUNT,
            "reasons": ["REQUIRED_PORT_UNBOUND"],
            "problems": [{
                "reason": "REQUIRED_PORT_UNBOUND", "port": "area",
                "expected_concept": "LOCATION",
                "expected_subtypes": ["scope", "vicinity_scope"], "nodes": [],
            }],
        }])
        self.assertIn(LOCATION_HINT, error.user_message)
        self.assertNotIn(Operator.PASSAGE_COUNT, error.user_message)
        self.assertNotIn("area", error.user_message)

    def test_b18_is_a_correct_refusal_without_tool_calls_or_repair(self):
        calls = []
        executor = new_tool_executor()
        original = executor.execute
        executor.execute = lambda name, arguments: (calls.append(name), original(name, arguments))[1]
        planner = GeoFlowPlanner(client=_Client(json.dumps(B18_GOLDEN, ensure_ascii=False)))
        record = E.evaluate_once(planner, self.composer, B18, execute=True,
                                 tool_executor=executor,
                                 available_tools=executor.tool_names)
        self.assertEqual(record["status"], "MISSING_REQUIRED_INPUT")
        self.assertFalse(record["validated"])
        self.assertTrue(record["refused"])
        self.assertTrue(record["correct"])
        self.assertEqual(record["macros"], [E.NO_TEMPLATE_LABEL])
        self.assertFalse(record["repair_attempted"])
        self.assertEqual(record["planner_calls"], 1)
        self.assertEqual(calls, [])

    def test_the_new_code_is_a_refusal_and_not_repairable(self):
        self.assertIn("MISSING_REQUIRED_INPUT", E.REFUSAL_CODES)
        with self.assertRaises(GeoFlowError) as caught:
            self.composer.compose(parse_grounding(B18_GOLDEN, B18["question"]))
        self.assertFalse(decide(caught.exception).repairable)
        self.assertFalse(decide(CompositionError(
            "테스트", code="MISSING_REQUIRED_INPUT", context={})).repairable)

    def test_speed_without_a_place_is_also_a_missing_input(self):
        """통행 통계 Tool은 모두 scope가 필수다."""
        error = self._failure([measure("m", "AMOUNT", "speed")], question="평균 속도는?")
        self.assertEqual(error.code, "MISSING_REQUIRED_INPUT")
        self.assertEqual(error.context["candidate_operator"], Operator.PASSAGE_METRIC)


class StaysNoOperatorTest(_ComposeCase):
    def test_true_type_mismatch(self):
        """요금은 trip에서만 나온다. 통행 사건은 어느 port에도 들어가지 않는다."""
        error = self._failure([event("e", "passage"), measure("m", "AMOUNT", "fare")])
        self.assertEqual(error.code, "NO_OPERATOR")
        self.assertEqual(self._reasons(error),
                         {Operator.TRIP_METRIC: ["UNCONSUMED_INPUT"]})
        self.assertEqual(error.context["output"], "AMOUNT/fare")
        self.assertEqual(error.context["inputs"], ["EVENT/passage"])

    def test_a_location_that_cannot_bind_is_not_reported_missing(self):
        """장소는 있는데 승차 한정이 붙어 area로 가지 못한다. "지역이 없다"가 아니다."""
        error = self._failure(
            [place("p", "대구", od_role="pickup"), event("e", "passage"),
             measure("m", "AMOUNT", "passage_count")],
            question="대구에서 승차한 통행량은?")
        self.assertEqual(error.code, "NO_OPERATOR")
        # 후보의 실패 이유만 보면 b18과 같다. 차이는 graph에 LOCATION이 있다는 것이다.
        self.assertEqual(self._reasons(error),
                         {Operator.PASSAGE_COUNT: ["REQUIRED_PORT_UNBOUND"]})
        self.assertNotIn(LOCATION_HINT, error.user_message)

    def test_a_candidate_with_several_problems(self):
        error = self._failure([event("e", "trip"), measure("m", "AMOUNT", "passage_count")])
        self.assertEqual(error.code, "NO_OPERATOR")
        self.assertEqual(self._reasons(error), {
            Operator.PASSAGE_COUNT: ["REQUIRED_PORT_UNBOUND", "UNCONSUMED_INPUT"]})

    def test_resolve_without_graph_nodes_stays_conservative(self):
        """graph를 모르면 필수 input이 없다고 단정하지 않는다."""
        output = _node("m", CoreConcept.AMOUNT, "passage_count")
        inputs = [_node("e", CoreConcept.EVENT, "passage")]
        with self.assertRaises(CompositionError) as caught:
            operator_mapping.resolve(inputs=inputs, output=output)
        self.assertEqual(caught.exception.code, "NO_OPERATOR")
        self.assertIn("candidate_failures", caught.exception.context)

    def test_any_node_of_the_expected_concept_blocks_the_new_code(self):
        output = _node("m", CoreConcept.AMOUNT, "passage_count")
        inputs = [_node("e", CoreConcept.EVENT, "passage")]
        for extra, code in (
            ([], "MISSING_REQUIRED_INPUT"),
            ([_node("p", CoreConcept.LOCATION, "place")], "NO_OPERATOR"),
            ([_node("s", CoreConcept.LOCATION, "scope", od_role="dropoff")], "NO_OPERATOR"),
            # 출력 node 자신은 입력 후보가 아니다.
            ([output], "MISSING_REQUIRED_INPUT"),
        ):
            with self.subTest(extra=[node.id for node in extra]):
                with self.assertRaises(CompositionError) as caught:
                    operator_mapping.resolve(inputs=inputs, output=output,
                                             available_nodes=inputs + extra)
                self.assertEqual(caught.exception.code, code)


class OtherDiagnosticsUnchangedTest(_ComposeCase):
    def test_existing_codes(self):
        cases = (
            ("MISSING_RELATION_QUALIFIER",
             [place("p", "동성로동"), event("e", "trip"), measure("m", "AMOUNT", "trip_count")], {}),
            ("AMBIGUOUS_LOCATION_RELATION",
             [place("a", "대구"), place("b", "부산"), measure("m", "AMOUNT", "speed")], {}),
            ("INVALID_PARAM_VALUE",
             [place("p", "대구"), event("e", "passage"), measure("m", "AMOUNT", "passage_count")],
             {"dimension": "dayofweek"}),
            ("PARAM_VALUE_REQUIRES_INPUT",
             [event("e", "operation"), measure("m", "AMOUNT", "operating_count")],
             {"dimension": "sigungu"}),
        )
        for code, concepts, factors in cases:
            with self.subTest(code=code):
                self.assertEqual(self._failure(concepts, factors).code, code)


class _Client:
    model = "fake"

    def __init__(self, content):
        self.content = content

    def chat(self, messages, tools=None):
        return {"message": {"content": self.content}}


if __name__ == "__main__":
    unittest.main()
