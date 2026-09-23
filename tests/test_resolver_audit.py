# -*- coding: utf-8 -*-
"""실패한 후보 때문에 성공할 수 있는 후보를 놓치지 않는지 확인한다.

operator mapping은 후보를 모두 배치해 본 뒤, 배치된 후보가 하나일 때만 param
계약을 검사한다. 현재 registry에서는 output마다 후보 operator가 하나뿐이라
이 순서가 성공 가능한 후보를 가릴 수 없다. 두 번째 후보가 생기면 아래 불변식이
그 조합을 다시 따지게 만든다.

후보가 여럿인 곳은 macro 층의 AMOUNT/trip_count 하나다(EVENT_TO_MEASURE,
OD_EVENT_TO_MEASURE). composer는 실패한 macro를 건너뛰고 다음 macro를 시도하므로,
순서를 뒤집어도 성공과 실패가 바뀌지 않아야 한다.
"""

import itertools
import os
import unittest
from collections import defaultdict
from unittest import mock

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from geoflow import operator_mapping
from geoflow.composer import MacroComposer
from geoflow.compiler import compile_plan
from geoflow.errors import CompositionError, GeoFlowError
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from geoflow.operator_registry import OPERATORS
from geoflow.types import ConceptNode, CoreConcept, FunctionalRole, NodeSource
from tests.test_geoflow_composition import event, measure, payload, place
from tests.test_operator_diagnostics import SelectionUnchangedTest

FACTOR_SETS = (
    {},
    {"dimension": "sigungu"},
    {"dimension": "dayofweek", "order": "top", "limit": 3},
    {"dimension": "h3"},
    {"bucket": "week", "rollup": "avg"},
    {"aggregation": "avg"},
    {"taxi_type": "corporate"},
)


def _outputs():
    outputs = defaultdict(list)
    for spec in OPERATORS.values():
        if spec.output is None:
            continue
        for concept, subtype in spec.output.allowed:
            outputs[(concept, subtype)].append(spec.name)
    return outputs


def _evaluate_alone(spec, inputs, output, factors):
    """후보 하나를 다른 후보와 무관하게 평가한다. 성립하면 (inputs, params)."""
    assigned, failure = operator_mapping._bind_ports(spec, inputs)
    if failure is not None:
        return None
    try:
        params, _ = operator_mapping._resolve_params(
            spec, output, dict(factors), bound_inputs=assigned)
    except CompositionError:
        return None
    return {port: node.id for port, node in assigned.items()}, params


class CandidateMultiplicityTest(unittest.TestCase):
    def test_every_output_has_a_single_operator_candidate(self):
        """늘어나면 아래 viability 불변식과 AMBIGUOUS_OPERATOR 순서를 다시 본다.

        resolve()는 배치된 후보가 둘 이상이면 param을 보기 전에
        AMBIGUOUS_OPERATOR로 멈춘다. 후보가 하나뿐인 지금은 문제가 되지 않는다.
        """
        multi = {key: names for key, names in _outputs().items() if len(names) > 1}
        self.assertEqual(multi, {})

    def test_only_trip_count_has_two_producing_macros(self):
        library = MacroLibrary.from_directory()
        multi = {}
        for key in _outputs():
            names = [macro.name for macro in library.producing(*key)]
            if len(names) > 1:
                multi[(key[0].value, key[1])] = names
        self.assertEqual(multi, {
            ("AMOUNT", "trip_count"): ["EVENT_TO_MEASURE", "OD_EVENT_TO_MEASURE"],
        })


class ResolverViabilityTest(unittest.TestCase):
    """resolve()와 후보별 독립 평가가 어긋나지 않는다."""

    def _check(self, candidates_order=None):
        checked = 0
        for (concept, subtype), _ in sorted(_outputs().items(),
                                           key=lambda item: (item[0][0].value, item[0][1])):
            output = ConceptNode(id="out", concept=concept, subtype=subtype,
                                 role=FunctionalRole.MEASURE, source=NodeSource.TOOL)
            candidates = operator_mapping.candidates_for(concept, subtype)
            for size in range(3):
                for inputs in itertools.combinations(SelectionUnchangedTest.NODES, size):
                    for factors in FACTOR_SETS:
                        viable = {
                            spec.name: result for spec in candidates
                            if (result := _evaluate_alone(spec, list(inputs), output, factors))
                        }
                        try:
                            binding = operator_mapping.resolve(
                                inputs=list(inputs), output=output, factors=factors)
                        except CompositionError as error:
                            self.assertNotEqual(len(viable), 1,
                                                (subtype, inputs, factors, error.code))
                            checked += 1
                            continue
                        # 선택된 후보는 스스로 성립하고, 같은 binding과 param을 쓴다.
                        self.assertIn(binding.operator, viable)
                        ports, params = viable[binding.operator]
                        self.assertEqual({p: ref.node_id for p, ref in binding.inputs.items()}, ports)
                        self.assertEqual(binding.params, params)
                        checked += 1
        return checked

    def test_resolve_matches_independent_candidate_evaluation(self):
        self.assertGreater(self._check(), 5000)

    def test_reversed_candidate_order_gives_the_same_result(self):
        original = operator_mapping.candidates_for
        with mock.patch.object(operator_mapping, "candidates_for",
                               lambda c, s: tuple(reversed(original(c, s)))):
            self.assertGreater(self._check(), 5000)


class MacroOrderTest(unittest.TestCase):
    """trip_count의 두 macro 순서를 뒤집어도 성공과 실패, Tool 호출이 같다."""

    @classmethod
    def setUpClass(cls):
        cls.composer = MacroComposer(MacroLibrary.from_directory())

    def _outcomes(self):
        outcomes = {}
        subtypes = sorted({(c.value, s) for c, s in _outputs() if c.value in ("AMOUNT", "PROPORTION")})
        places = (None, "plain", "pickup", "dropoff")
        for (concept, subtype), ev, first, second, factors in itertools.product(
                subtypes, (None, "passage", "trip", "operation"), places, (None, "dropoff"),
                FACTOR_SETS[:3]):
            concepts = [measure("m", concept, subtype)]
            if ev:
                concepts.insert(0, event("e", ev))
            if first:
                concepts.insert(0, place("p", "대구", od_role=None if first == "plain" else first))
            if second:
                concepts.insert(0, place("d", "부산", od_role=second))
            key = (subtype, ev, first, second, tuple(sorted(factors)))
            try:
                plan = self.composer.compose(parse_grounding(payload(concepts, factors), "질문"))
            except GeoFlowError:
                outcomes[key] = None
                continue
            outcomes[key] = [(s.tool_name, sorted(s.arguments.items(), key=str))
                             for s in compile_plan(plan).steps]
        return outcomes

    def test_reversed_macro_order_does_not_change_success_or_tool_calls(self):
        baseline = self._outcomes()
        original = MacroLibrary.producing
        with mock.patch.object(MacroLibrary, "producing",
                               lambda self, c, s: tuple(reversed(original(self, c, s)))):
            reversed_order = self._outcomes()
        self.assertEqual(reversed_order.keys(), baseline.keys())
        for key, calls in baseline.items():
            with self.subTest(key=key):
                self.assertEqual(reversed_order[key], calls)
        self.assertGreater(sum(calls is not None for calls in baseline.values()), 80)
        # 두 macro가 모두 관여하는 trip_count 계획이 비교 대상에 들어 있다.
        self.assertGreater(sum(calls is not None for key, calls in baseline.items()
                               if key[0] == "trip_count"), 10)


if __name__ == "__main__":
    unittest.main()
