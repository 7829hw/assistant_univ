# -*- coding: utf-8 -*-
"""failure census 분석 코드의 판정을 못박는다."""

import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import failure_census as C

BASE_DIR = Path(__file__).resolve().parent.parent
#: 합성 전에 쓰이지 않는 코드(compile/IR 검사 등). census 대상 관측에서는 나지 않는다.
_NOT_OBSERVABLE = {
    "CYCLE", "EMPTY_REF", "EMPTY_REQUIRED_INPUT", "INVALID_FIELD_REFERENCE",
    "OUTPUT_ARITY", "UNEXPECTED_OUTPUT", "UNKNOWN_EXTRACTION", "UNKNOWN_OPERATOR",
    "UNKNOWN_PARAM", "UNKNOWN_PORT", "UNKNOWN_REFERENCE", "UNRESOLVED_FIELD",
    "UNRESOLVED_REF",
    # 구성 오류(Tool provider와 실행 프로필 불일치). 질문 관측에서는 나오지 않는다.
    "PROVIDER_PROFILE_MISMATCH",
}


def _item(concept, subtype, role, **extra):
    return {"concept": concept, "subtype": subtype, "role": role, **extra}


REVENUE = _item("AMOUNT", "revenue", "MEASURE")
OPERATION = _item("EVENT", "operation", "SUPPORT")


class StageTest(unittest.TestCase):
    def test_every_geoflow_error_code_has_a_stage(self):
        codes = set()
        for path in (BASE_DIR / "geoflow").glob("*.py"):
            codes.update(re.findall(r'code="([A-Z_]+)"', path.read_text(encoding="utf-8")))
        unclassified = {code for code in codes if C.stage_of(code) == "UNCLASSIFIED"}
        self.assertEqual(unclassified - _NOT_OBSERVABLE, set())

    def test_execution_and_success(self):
        self.assertEqual(C.stage_of("EXEC:NOT_FOUND"), "EXECUTION")
        self.assertIsNone(C.stage_of("OK"))
        self.assertEqual(C.stage_of("MISSING_REQUIRED_INPUT"), "OPERATOR_MAPPING")


class OutcomeTest(unittest.TestCase):
    def test_classes(self):
        none = {"expected_macros": ["NONE"]}
        cases = (
            ({**none, "validated": False}, C.SAFE_REJECTION),
            ({**none, "validated": True, "exec_status": "OK"}, C.SILENT_WRONG_PLAN),
            ({"validated": False}, C.SUPPORTED_REJECTION),
            ({"validated": True, "final_category": "correct", "exec_status": "OK"}, C.CORRECT),
            ({"validated": True, "final_category": "correct", "exec_status": "TOOL_ERROR",
              "exec_retryable": True}, C.RECOVERABLE_REJECTION),
            ({"validated": True, "final_category": "wrong_arguments", "exec_status": "OK",
              "arg_mismatches": [{"arg": "x"}], "expected_tool_args": {"x": 1}},
             C.SILENT_WRONG_PLAN),
            ({"validated": True, "final_category": "incorrect", "exec_status": "OK",
              "arg_mismatches": [], "expected_tool_args": {"x": 1}, "correct": False},
             C.EVALUATOR_ONLY),
        )
        for row, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(C.outcome_of(row), expected)


class FamilyTest(unittest.TestCase):
    GOLDEN_TWO_STAGE = {"concepts": [OPERATION, REVENUE],
                        "factors": {"bucket": "month", "aggregation": "sum", "rollup": "avg"}}

    def test_collapsed_two_stage_aggregation(self):
        payload = {"concepts": [OPERATION, REVENUE], "factors": {"bucket": "month", "rollup": "avg"}}
        self.assertEqual(C.structural_families(payload, self.GOLDEN_TWO_STAGE, []),
                         ["collapsed_two_stage_aggregation"])

    def test_group_word_read_as_place_is_flagged_for_review(self):
        golden = {"concepts": [OPERATION, _item("AMOUNT", "operating_count", "MEASURE")],
                  "factors": {"dimension": "sido"}}
        payload = {"concepts": [_item("LOCATION", "place", "SUBCOND", value={"name": "시도"}),
                                OPERATION, _item("AMOUNT", "operating_count", "MEASURE")],
                   "factors": {"dimension": "sigungu"}}
        self.assertEqual(C.structural_families(payload, golden, []),
                         ["group_word_as_place?", "wrong_dimension"])

    def test_od_role(self):
        place = {"name": "동성로동", "region": ""}
        golden = {"concepts": [_item("LOCATION", "place", "SUBCOND", value=place,
                                     attributes={"od_role": "pickup"}),
                               _item("AMOUNT", "trip_count", "MEASURE")], "factors": {}}
        missing = {"concepts": [_item("LOCATION", "place", "SUBCOND", value=place),
                                _item("AMOUNT", "trip_count", "MEASURE")], "factors": {}}
        wrong = {"concepts": [_item("LOCATION", "place", "SUBCOND", value=place,
                                    attributes={"od_role": "dropoff"}),
                              _item("AMOUNT", "trip_count", "MEASURE")], "factors": {}}
        self.assertEqual(C.structural_families(missing, golden, []), ["missing_od_role"])
        self.assertEqual(C.structural_families(wrong, golden, []), ["wrong_od_role"])

    def test_matching_grounding_has_no_tag(self):
        self.assertEqual(C.structural_families(self.GOLDEN_TWO_STAGE, self.GOLDEN_TWO_STAGE, []), [])

    def test_refusal_of_a_supported_intent(self):
        self.assertEqual(C.structural_families({"unsupported": True}, self.GOLDEN_TWO_STAGE, []),
                         ["model_refused_supported"])
        self.assertEqual(C.structural_families({"unsupported": True}, {"unsupported": True}, []), [])


class AggregationPlanFamilyTest(unittest.TestCase):
    """raw aggregation_plan은 내려서 flat golden과 같은 층에서 비교한다."""

    GOLDEN = FamilyTest.GOLDEN_TWO_STAGE

    def _plan(self, plan, **others):
        return {"concepts": [OPERATION, REVENUE],
                "factors": {**others, "aggregation_plan": plan}}

    def test_a_correct_plan_has_no_tag(self):
        plan = {"bucket": {"unit": "month", "reducer": "sum"}, "result": {"reducer": "avg"}}
        self.assertEqual(C.structural_families(self._plan(plan), self.GOLDEN, []), [])

    def test_explicit_inner_left_unspecified(self):
        plan = {"bucket": {"unit": "month", "reducer": "unspecified"}, "result": {"reducer": "avg"}}
        tags = C.structural_families(self._plan(plan), self.GOLDEN, [])
        self.assertEqual(tags, ["collapsed_two_stage_aggregation"])
        self.assertIn("aggregation_stage", C.groups_of(tags))

    def test_stage_swap_in_either_representation(self):
        flat = {"concepts": [OPERATION, REVENUE],
                "factors": {"bucket": "month", "aggregation": "avg"}}
        self.assertIn("stage_swapped", C.structural_families(flat, self.GOLDEN, []))
        plan = {"bucket": {"unit": "month", "reducer": "avg"}, "result": {"reducer": "sum"}}
        self.assertIn("stage_swapped", C.structural_families(self._plan(plan), self.GOLDEN, []))

    def test_bucket_unit_written_in_another_factor(self):
        plan = {"bucket": {"unit": "month", "reducer": "sum"}, "result": {"reducer": "avg"}}
        tags = C.structural_families(self._plan(plan, dimension="month"), self.GOLDEN, [])
        self.assertIn("bucket_unit_in_other_factor", tags)
        self.assertEqual(C.groups_of(tags), ["bucket_unit_elsewhere"])

    def test_an_unreadable_plan_is_tagged(self):
        tags = C.structural_families(self._plan({"bucket": {"unit": "month"}}), self.GOLDEN, [])
        self.assertIn("invalid_aggregation_plan", tags)


class RecordedVariantTest(unittest.TestCase):
    def test_a_production_run_replays_under_its_recorded_contract(self):
        import evaluate_prompt_ab as A

        current = A.build_variant("PRODUCTION")
        arm = {"variant": "PRODUCTION", "prompt_sha256": current.sha256,
               "repair_contract_sha256": current.repair_sha256}
        self.assertEqual(A.recorded_variant(arm).sha256, current.sha256)
        # 422b952(되돌림)가 production이던 때의 run은 H2_AGG 계약으로 재생한다.
        arm = {"variant": "PRODUCTION", "prompt_sha256": A.PINNED_SHA256["H2_AGG"],
               "repair_contract_sha256": A.PINNED_REPAIR_SHA256["H2_AGG"]}
        variant = A.recorded_variant(arm)
        self.assertEqual(variant.name, "H2_AGG")
        self.assertEqual(variant.grounding_adapter, "aggregation_plan")
        with self.assertRaises(A.BenchmarkAborted):
            A.recorded_variant({"variant": "PRODUCTION", "prompt_sha256": "0" * 64,
                                "repair_contract_sha256": "0" * 64})


class ReplayTest(unittest.TestCase):
    def test_replay_client_refuses_to_invent_responses(self):
        client = C.ReplayClient(["{}"])
        self.assertEqual(client.chat([])["message"]["content"], "{}")
        with self.assertRaises(RuntimeError):
            client.chat([])


if __name__ == "__main__":
    unittest.main()
