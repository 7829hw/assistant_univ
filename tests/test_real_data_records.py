# -*- coding: utf-8 -*-
"""실제 질문 검증 기록 형식(evaluation/real_data). fixture는 형식 검사용이며 실제 자료가 아니다."""

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("real_data_validate", ROOT / "evaluation" / "real_data" / "validate.py")
V = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(V)

UNREVIEWED = {"record_id": "fmt-1",
              "question": {"text": "(형식 검사용 문장)", "reference_date": "2026-10-05", "source": "real_user"},
              "review": {"status": "unreviewed"}}

COMPARED = {
    "record_id": "fmt-2",
    "question": {"text": "(형식 검사용 문장)", "asked_at": "2026-10-05T10:00:00+09:00", "timezone": "Asia/Seoul",
                 "reference_date": "2026-10-05", "source": "service_staff", "anonymized": True},
    "review": {"status": "reviewed", "reviewer_role": "서비스 담당자", "reviewed_at": "2026-10-06",
               "meaning": "요일별 기간 총수입이 가장 큰 요일", "expected_behavior": "answer",
               "expected_call": "get_billing_metrics(metric=revenue, date=this_month, aggregation=sum, dimension=dayofweek, order=top, limit=1)",
               "label_basis": [{"kind": "question_explicit", "ref": "'이번 달', '요일'"},
                               {"kind": "vendor_decision", "ref": "decisions.md D1 (결정 기록 위치)"}],
               "decision_refs": ["D1"]},
    "provider": {"name": "tims", "contract_version": "(계약 버전)", "endpoint_version": None},
    "run": {"geoflow_verification": {"compared_to": "T2PC", "different": [], "unchecked": {}},
            "cli_record": "evaluation/runs/<run>/query_raw.json#fmt-2"},
    "actual": {"outcome": "answered", "calls": [], "tims_responses_ref": "(응답 원본 위치)", "answer_text": "(답변)"},
    "comparison": {"result": "correct", "unacceptable": [], "value_check": "matches_tims"},
}


class RecordFormatTest(unittest.TestCase):
    def test_minimal_unreviewed_record_is_valid(self):
        self.assertEqual(V.validate_records([UNREVIEWED]), [])

    def test_compared_record_with_full_chain_is_valid(self):
        self.assertEqual(V.validate_records([COMPARED]), [])

    def test_reviewed_record_needs_meaning_behavior_and_basis(self):
        record = copy.deepcopy(UNREVIEWED)
        record["review"]["status"] = "reviewed"
        problems = V.validate_records([record])
        for field in ("meaning", "expected_behavior", "label_basis", "reviewer_role"):
            self.assertTrue(any(field in p for p in problems), field)

    def test_comparison_needs_provider_run_actual_and_review(self):
        record = copy.deepcopy(COMPARED)
        del record["provider"]
        self.assertTrue(V.validate_records([record]))
        record = copy.deepcopy(COMPARED)
        record["review"] = {"status": "unreviewed"}
        self.assertTrue(V.validate_records([record]))

    def test_mock_or_reference_cannot_be_the_provider(self):
        record = copy.deepcopy(COMPARED)
        record["provider"]["name"] = "mock"
        self.assertTrue(V.validate_records([record]))

    def test_decision_refs_must_exist_and_back_vendor_decisions(self):
        record = copy.deepcopy(COMPARED)
        record["review"]["decision_refs"] = ["D99"]
        self.assertTrue(any("D99" in p for p in V.validate_records([record])))
        record["review"]["decision_refs"] = []
        self.assertTrue(any("vendor_decision" in p for p in V.validate_records([record])))

    def test_synthetic_source_is_not_accepted_and_ids_are_unique(self):
        record = copy.deepcopy(UNREVIEWED)
        record["question"]["source"] = "synthetic"
        self.assertTrue(V.validate_records([record]))
        self.assertTrue(any("중복" in p for p in V.validate_records([UNREVIEWED, UNREVIEWED])))

    def test_reference_date_must_be_a_date(self):
        record = copy.deepcopy(UNREVIEWED)
        record["question"]["reference_date"] = "어제"
        self.assertTrue(V.validate_records([record]))


if __name__ == "__main__":
    unittest.main()
