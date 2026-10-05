# -*- coding: utf-8 -*-
"""실제 질문 검증 기록 형식과 판정 규칙(evaluation/real_data). 여기의 기록은 모두 테스트용 가짜(record_id fake-)이며
실제 자료가 아니다. 모델·TIMS를 부르지 않는다."""

import copy
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("real_data_validate", ROOT / "evaluation" / "real_data" / "validate.py")
V = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(V)

TEXT = "(가짜) 지난달 가람구에서 출발한 운행은 몇 건이야?"
DAY = "2026-10-05"

COLLECTED = {"record_id": "fake-collected",
             "question": {"text": TEXT, "reference_date": DAY, "source": "real_user",
                          "provenance": {"provided_by_role": "서비스 담당자", "received_at": DAY}},
             "review": {"status": "unreviewed"}}

REVIEW = {"status": "reviewed", "reviewer_role": "서비스 담당자", "reviewed_at": DAY,
          "meaning": "가람구에서 출발한 지난달 trip 건수", "expected_behavior": "answer",
          "expected_call": "get_place_scope(name=가람구)\nget_trip_count(scope_pickup=$pickup.scope, date=last_month)",
          "label_basis": [{"kind": "question_explicit", "ref": "'지난달', '가람구에서 출발', '몇 건'"}]}

MATCHED = {"compared_to": "T2PC", "matched": ["model", "code"], "different": [], "unchecked": {}}


def run(run_id="r1", **changes):
    base = {"run_id": run_id, "kind": "geoflow_cli", "question_text": TEXT, "reference_date": DAY,
            "provider": {"name": "mock"}, "geoflow_verification": copy.deepcopy(MATCHED),
            "cli_record": "evaluation/runs/x/query_raw.json#fake", "outcome": "answered",
            "grounding": {"concepts": [], "factors": {"date": "last_month"}},
            "calls": [{"tool": "get_place_scope", "args": {"name": "가람구"}}]}
    base.update(changes)
    return base


def judgment(scope="meaning", run_id="r1", result="correct", **changes):
    base = {"scope": scope, "run_id": run_id, "result": result, "combination": "T2PC",
            "judged_by_role": "검토자", "judged_at": DAY, "evidence": ["grounding과 기대 호출 비교"],
            "value_check": "not_checked"}
    if scope == "meaning":
        base["basis"] = "calls"
    base.update(changes)
    return base


def record(review=None, runs=(), judgments=(), record_id="fake-1"):
    out = {"record_id": record_id, "question": copy.deepcopy(COLLECTED["question"]),
           "review": copy.deepcopy(review or REVIEW)}
    if runs:
        out["runs"] = list(runs)
    if judgments:
        out["judgments"] = list(judgments)
    return out


TIMS_DIRECT = {"name": "tims", "contract_version": "(가짜 계약 버전)", "mode": "direct"}
RESPONSES = [{"call_index": 0, "response_ref": "(가짜 응답 위치)", "data_source": "(가짜) TIMS 직접 호출",
              "received_at": DAY}]


class StageRecordsTest(unittest.TestCase):
    """단계별로 정상인 기록."""

    def ok(self, rec):
        self.assertEqual(V.validate_records([rec]), [])

    def test_collected_question_without_any_run(self):
        self.ok(COLLECTED)

    def test_reviewed_question_without_run(self):
        self.ok(record())

    def test_meaning_check_without_tims_on_grounding_only(self):
        self.ok(record(runs=[run(outcome="failed", error_code="PLACE_NOT_FOUND")],
                       judgments=[judgment(basis="grounding_only")]))

    def test_correct_refusal_needs_no_tims_response(self):
        review = dict(REVIEW, expected_behavior="clarify", expected_call=None, expected_stop_basis="연도 없는 날짜")
        self.ok(record(review=review, runs=[run(outcome="needs_clarification", error_code="DATE_AMBIGUOUS")],
                       judgments=[judgment(result="correct_refusal")]))

    def test_vendor_relay_provider_check(self):
        relay = run("r2", kind="vendor_relay", provider={"name": "tims", "contract_version": "(가짜)", "mode": "vendor_relay"},
                    source_run_id="r1", responses=RESPONSES, outcome=None)
        relay.pop("geoflow_verification"); relay.pop("outcome")
        self.ok(record(runs=[run(), relay],
                       judgments=[judgment("provider_contract", "r2", "conforms", combination="unverified")]))

    def test_end_to_end_direct_tims_with_expected_provider_difference(self):
        verification = dict(MATCHED, different=["provider", "tims_execution"])
        e2e = run(provider=TIMS_DIRECT, geoflow_verification=verification, responses=RESPONSES)
        self.ok(record(runs=[e2e], judgments=[judgment("end_to_end", result="correct", value_check="matches_tims")]))

    def test_decided_decision_can_be_cited(self):
        review = dict(REVIEW, label_basis=[{"kind": "vendor_decision", "ref": "decisions.md D1"}], decision_refs=["D1"])
        with mock.patch.object(V, "decision_states", return_value={"D1": "decided"}):
            self.ok(record(review=review))


class InvalidRecordsTest(unittest.TestCase):
    """잘못된 완료 판정과 모순."""

    def bad(self, rec, fragment, **kwargs):
        problems = V.validate_records([rec], **kwargs)
        self.assertTrue(any(fragment in p for p in problems), problems)

    def test_reviewed_without_meaning_or_basis(self):
        self.bad(record(review=dict(REVIEW, meaning="")), "meaning")
        self.bad(record(review=dict(REVIEW, label_basis=[])), "label_basis")

    def test_undecided_decision_cited_as_vendor_decision(self):
        review = dict(REVIEW, label_basis=[{"kind": "vendor_decision", "ref": "decisions.md D1"}], decision_refs=["D1"])
        self.bad(record(review=review), "미결정")

    def test_value_match_without_tims_response(self):
        e2e = run(provider=TIMS_DIRECT, geoflow_verification=dict(MATCHED, different=["provider"]))
        self.bad(record(runs=[e2e], judgments=[judgment("end_to_end", result="correct", value_check="matches_tims")]),
                 "실제 TIMS 응답 기록이 없다")

    def test_expected_actual_and_result_disagree(self):
        self.bad(record(runs=[run(outcome="needs_clarification", error_code="X")], judgments=[judgment(result="correct")]),
                 "맞지 않는다")
        review = dict(REVIEW, expected_behavior="unsupported", expected_call=None, expected_stop_basis="시간대별 묶음")
        self.bad(record(review=review, runs=[run()], judgments=[judgment(result="correct")]), "맞지 않는다")

    def test_correct_refusal_without_stop_basis(self):
        review = dict(REVIEW, expected_behavior="clarify", expected_call=None)
        self.bad(record(review=review, runs=[run(outcome="needs_clarification", error_code="DATE_AMBIGUOUS")],
                        judgments=[judgment(result="correct_refusal")]), "멈춤 근거")

    def test_run_of_another_question_or_date(self):
        self.bad(record(runs=[run(question_text="다른 질문")], judgments=[judgment()]), "다른 사례")
        self.bad(record(runs=[run(reference_date="2026-09-25")], judgments=[judgment()]), "기준일")

    def test_judgment_before_review(self):
        self.bad(record(review={"status": "unreviewed"}, runs=[run()], judgments=[judgment()]), "검토 완료")

    def test_vendor_relay_is_not_end_to_end(self):
        relay = run(kind="vendor_relay", provider={"name": "tims", "contract_version": "v", "mode": "vendor_relay"},
                    responses=RESPONSES)
        self.bad(record(runs=[relay], judgments=[judgment("end_to_end", combination="unverified",
                                                          value_check="matches_tims")]), "직접 호출")

    def test_mock_cannot_back_provider_or_end_to_end(self):
        self.bad(record(runs=[run(responses=RESPONSES)],
                        judgments=[judgment("provider_contract", result="conforms", combination="unverified")]), "tims 실행")

    def test_comparability_is_broken_by_non_provider_differences(self):
        verification = dict(MATCHED, different=["provider", "model"])
        e2e = run(provider=TIMS_DIRECT, geoflow_verification=verification, responses=RESPONSES)
        self.bad(record(runs=[e2e], judgments=[judgment("end_to_end", value_check="matches_tims")]), "비교 조건을 훼손")
        unchecked = dict(MATCHED, unchecked={"model_digest": "응답 없음"})
        self.bad(record(runs=[run(geoflow_verification=unchecked)], judgments=[judgment()]), "확인 안 함")
        mock_diff = dict(MATCHED, different=["provider"])
        self.bad(record(runs=[run(geoflow_verification=mock_diff)], judgments=[judgment()]), "비교 조건을 훼손")

    def test_meaning_scope_does_not_claim_values(self):
        self.bad(record(runs=[run()], judgments=[judgment(value_check="matches_tims")]), "값을 판정하지 않는다")

    def test_fake_record_in_real_records_directory(self):
        location = V.REAL_RECORDS_DIR / "batch1.jsonl"
        self.bad(COLLECTED, "가짜 기록", location=location)

    def test_synthetic_source_and_duplicate_ids(self):
        rec = copy.deepcopy(COLLECTED)
        rec["question"]["source"] = "synthetic"
        self.assertTrue(V.validate_records([rec]))
        self.assertTrue(any("중복" in p for p in V.validate_records([COLLECTED, COLLECTED])))


class DecisionFileTest(unittest.TestCase):
    def test_all_decisions_are_listed_and_currently_undecided(self):
        self.assertEqual(V.decision_states(), {"D1": "undecided", "D2": "undecided", "D3": "undecided",
                                               "D4": "undecided"})


if __name__ == "__main__":
    unittest.main()
