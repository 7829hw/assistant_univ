# -*- coding: utf-8 -*-
"""모든 macro가 실패했을 때 보고하는 오류가 시도 순서와 무관한지 못박는다.

예전에는 "처음 본 구체적 오류, 없으면 처음 실패"를 보고해서, 후보 macro가 둘인
trip_count에서 macro 순서를 뒤집으면 오류 code가 47건 바뀌었다. 이제 실패를
모두 모은 뒤 composer.DIAGNOSTIC_PRECEDENCE로 하나를 고른다. 성공 경로는
그대로다.
"""

import itertools
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_planner as E
from geoflow import composer as composer_module
from geoflow.composer import (
    DIAGNOSTIC_PRECEDENCE, MacroComposer, MacroFailure, choose_diagnostic,
)
from geoflow.compiler import compile_plan
from geoflow.errors import CompositionError, GeoFlowError
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from tests.test_geoflow_composition import event, measure, payload, place

TWO_DROPOFFS = [place("a", "대구", od_role="dropoff"), place("b", "부산", od_role="dropoff"),
                measure("m", "AMOUNT", "trip_count")]
DAYOFWEEK = {"dimension": "dayofweek", "order": "top", "limit": 3}


def _reversed_macros():
    original = MacroLibrary.producing
    return mock.patch.object(MacroLibrary, "producing",
                             lambda self, c, s: tuple(reversed(original(self, c, s))))


class _Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.composer = MacroComposer(MacroLibrary.from_directory())

    def _error(self, concepts, factors=None):
        with self.assertRaises(CompositionError) as caught:
            self.composer.compose(parse_grounding(payload(concepts, factors), "질문"))
        return caught.exception

    def _result_of(self, concepts, factors=None):
        try:
            plan = self.composer.compose(parse_grounding(payload(concepts, factors), "질문"))
        except GeoFlowError as error:
            return (error.code, error.user_message,
                    json.dumps(error.context, ensure_ascii=False, sort_keys=True, default=str))
        return [(step.tool_name, sorted(step.arguments.items(), key=str))
                for step in compile_plan(plan).steps]


class PrecedenceTest(_Case):
    def test_an_event_the_operator_cannot_take_is_no_operator(self):
        """EVENT_TO_MEASURE는 passage를 받아 TRIP_COUNT에 넣으려다 타입이 맞지 않는다.
        OD_EVENT_TO_MEASURE는 passage를 보지도 않고 trip을 추론해 passage를 남긴다.
        원인은 앞쪽이다. 요금 + passage가 NO_OPERATOR인 것과도 같다.
        """
        for subtype in ("passage", "drive", "operation"):
            with self.subTest(event=subtype):
                concepts = [event("e", subtype), measure("m", "AMOUNT", "trip_count")]
                error = self._error(concepts)
                self.assertEqual(error.code, "NO_OPERATOR")
                self.assertEqual(
                    sorted((item["macro"], item["code"]) for item in error.context["macro_failures"]),
                    [("EVENT_TO_MEASURE", "NO_OPERATOR"), ("OD_EVENT_TO_MEASURE", "UNUSED_CONCEPT")])
                normal = self._result_of(concepts)
                with _reversed_macros():
                    self.assertEqual(self._result_of(concepts), normal)

    def test_an_ambiguous_port_comes_before_the_param_error_it_can_lead_to(self):
        """하차 장소 둘을 한 port에 둘 수 없다. OD 쪽은 그 port를 버리고 진행한 뒤에
        dimension=dayofweek에서 막힌다. port를 정하지 못한 것이 더 앞의 원인이다.
        """
        error = self._error(TWO_DROPOFFS, DAYOFWEEK)
        self.assertEqual(error.code, "AMBIGUOUS_PORT")
        self.assertEqual(
            sorted((item["macro"], item["code"]) for item in error.context["macro_failures"]),
            [("EVENT_TO_MEASURE", "INVALID_PARAM_VALUE"),
             ("OD_EVENT_TO_MEASURE", "INVALID_PARAM_VALUE"),
             ("PLACE_TO_SCOPE", "AMBIGUOUS_PORT")])
        with _reversed_macros():
            self.assertEqual(self._error(TWO_DROPOFFS, DAYOFWEEK).code, "AMBIGUOUS_PORT")

    def test_the_precedence_table_is_the_single_source(self):
        self.assertFalse(hasattr(composer_module, "SPECIFIC_FAILURES"))
        self.assertEqual(len(DIAGNOSTIC_PRECEDENCE), len(set(DIAGNOSTIC_PRECEDENCE)))

    def test_every_code_seen_inside_macro_attempts_is_ranked(self):
        seen = set()
        for concepts, factors in _grid():
            try:
                self.composer.compose(parse_grounding(payload(concepts, factors), "질문"))
            except GeoFlowError as error:
                seen.update(item["code"] for item in error.context.get("macro_failures", ()))
        self.assertTrue(seen)
        self.assertEqual(seen - set(DIAGNOSTIC_PRECEDENCE), set())


class SelectorTest(unittest.TestCase):
    def _failure(self, macro, code, **context):
        return MacroFailure(macro, CompositionError("t", code=code, context=context))

    def test_tie_break_does_not_depend_on_attempt_order(self):
        items = [self._failure("B", "NO_OPERATOR", inputs=["EVENT/trip"]),
                 self._failure("A", "NO_OPERATOR", inputs=["EVENT/passage"]),
                 self._failure("C", "UNUSED_CONCEPT", unused=["e"])]
        chosen = {choose_diagnostic(list(order)).context["inputs"][0]
                  for order in itertools.permutations(items)}
        self.assertEqual(chosen, {"EVENT/passage"})

    def test_macro_name_is_only_the_last_tie_break(self):
        items = [self._failure("A", "NO_OPERATOR", inputs=["EVENT/trip"]),
                 self._failure("B", "NO_OPERATOR", inputs=["EVENT/passage"])]
        # 이름으로는 A가 앞이지만 context가 먼저 비교된다.
        self.assertEqual(choose_diagnostic(items).context["inputs"], ["EVENT/passage"])

    def test_unknown_codes_come_after_every_ranked_code(self):
        items = [self._failure("A", "SOMETHING_NEW"), self._failure("B", "UNUSED_CONCEPT")]
        self.assertEqual(choose_diagnostic(items).code, "UNUSED_CONCEPT")

    def test_macro_failures_summarise_every_distinct_failure(self):
        items = [self._failure("B", "UNUSED_CONCEPT", unused=["e"]),
                 self._failure("A", "NO_OPERATOR", inputs=["EVENT/passage"]),
                 self._failure("A", "NO_OPERATOR", inputs=["EVENT/passage"])]
        summary = choose_diagnostic(items).context["macro_failures"]
        self.assertEqual(sorted((item["macro"], item["code"]) for item in summary),
                         [("A", "NO_OPERATOR"), ("B", "UNUSED_CONCEPT")])
        self.assertTrue(all("macro_failures" not in item["context"] for item in summary))

    def test_failures_before_a_successful_branch_are_forgotten(self):
        build = composer_module._Build()
        build.note_failure("OUTER", CompositionError("t", code="NO_OPERATOR"))
        mark = build.failure_mark()
        build.note_failure("INNER", CompositionError("t", code="AMBIGUOUS_PORT"))
        build.forget_failures_since(mark)
        self.assertEqual([item.macro for item in build.failures], ["OUTER"])
        # snapshot/restore는 진단 기록을 되돌리지 않는다.
        state = build.snapshot()
        build.note_failure("LATER", CompositionError("t", code="NO_OPERATOR"))
        build.restore(state)
        self.assertEqual(len(build.failures), 2)


def _grid():
    places = (None, "plain", "pickup", "dropoff")
    for (concept, subtype), ev, first, second, factors in itertools.product(
            (("AMOUNT", "trip_count"), ("AMOUNT", "passage_count"), ("AMOUNT", "fare"),
             ("AMOUNT", "hours"), ("AMOUNT", "speed")),
            (None, "passage", "trip", "operation"), places, (None, "dropoff"),
            ({}, DAYOFWEEK, {"dimension": "sigungu"})):
        concepts = [measure("m", concept, subtype)]
        if ev:
            concepts.insert(0, event("e", ev))
        if first:
            concepts.insert(0, place("p", "대구", od_role=None if first == "plain" else first))
        if second:
            concepts.insert(0, place("d", "부산", od_role=second))
        yield concepts, factors


class OrderIndependenceTest(_Case):
    def test_reversed_macro_order_gives_the_same_outcome(self):
        """성공이면 Tool 호출까지, 실패면 code·사용자 메시지·context까지 같다."""
        grid = list(_grid())
        normal = [self._result_of(c, f) for c, f in grid]
        with _reversed_macros():
            reversed_order = [self._result_of(c, f) for c, f in grid]
        failures = sum(isinstance(outcome, tuple) for outcome in normal)
        self.assertGreater(failures, 400)
        # 조건을 받지 않는 Tool 조합은 UNCONSUMED_CONDITION으로 거부되므로 성공
        # 수가 줄었다(예전 40개 초과 → 40개).
        self.assertGreater(len(normal) - failures, 35)
        for (concepts, factors), a, b in zip(grid, normal, reversed_order):
            with self.subTest(concepts=[c["id"] + ":" + c["subtype"] for c in concepts],
                              factors=factors):
                self.assertEqual(a, b)


class RefusalTest(_Case):
    def test_both_sides_of_the_45_are_refusals(self):
        """NO_OPERATOR와 UNUSED_CONCEPT는 둘 다 거부로 채점된다."""
        self.assertIn("NO_OPERATOR", E.REFUSAL_CODES)
        self.assertIn("UNUSED_CONCEPT", E.REFUSAL_CODES)
        self.assertIn("AMBIGUOUS_PORT", E.REFUSAL_CODES)


if __name__ == "__main__":
    unittest.main()
