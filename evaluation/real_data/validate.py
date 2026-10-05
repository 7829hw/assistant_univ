# -*- coding: utf-8 -*-
"""실제 질문 검증 기록(JSONL, 한 줄에 한 질문) 검사.

    python evaluation/real_data/validate.py RECORDS.jsonl

검사하는 것(형식과 내부 일관성):
- record_schema.json(JSON Schema).
- 단계: 판정(judgments)은 검토 완료(review.status=reviewed) 뒤에만 있다. 검토 완료면 의미·기대 동작·라벨 근거가 있다.
- 결정: decision_refs는 decisions.md의 항목이어야 한다. vendor_decision 근거는 `상태: 결정됨`인 항목만 인용할 수 있다.
- 연결: 판정의 run_id가 있고, 그 실행의 질문 원문·기준일이 question과 같다.
- 범위별 필요 자료(README 2절):
  - meaning은 GeoFlow 실행을 쓰고 값 판정을 하지 않는다.
  - provider_contract는 tims 호출과 응답이 필요하다.
  - response_interpretation은 tims 응답을 받은 GeoFlow 실행과 값 판정이 필요하다.
  - end_to_end는 GeoFlow CLI가 tims를 직접 호출한 실행이어야 한다. 업체 대행 실행은 end-to-end가 아니다.
- 값 판정: value_check=matches_tims면 그 실행에 실제 응답 기록이 있다.
- 분류 일관성: 기대 동작, 실제 결과(outcome), 판정 결과가 서로 맞는다. 정확한 거부는 실제 응답 없이 판정할 수 있지만
  멈춤 근거(기대 근거와 오류 코드)가 있어야 한다.
- 비교 조건: combination(T2PC·B)에 결과를 귀속하려면, 그 실행의 검증 표시가 그 조합과 비교됐어야 한다.
  다름은 그 범위가 허용하는 provider 항목뿐이고, 확인 안 함이 없어야 한다.
- 위치: evaluation/real_data/records/ 아래 파일에 테스트용 가짜 기록(record_id가 fake-로 시작)이 있으면 오류다.
검사하지 않는 것: 출처의 진위(source=real_user·provider=tims라고 적혀 있다고 실제인 것은 아니다), 라벨 의미의 타당성.
"""
import json
import re
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REAL_RECORDS_DIR = HERE / "records"

STOPS = {"needs_clarification", "unsupported"}
RESULTS = {
    "meaning": {"correct", "wrong_meaning", "correct_refusal", "wrong_refusal", "failure"},
    "provider_contract": {"conforms", "violates", "unclear"},
    "response_interpretation": {"correct", "wrong"},
    "end_to_end": {"correct", "silent_wrong", "correct_refusal", "wrong_refusal", "failure"},
}
#: 범위마다 허용하는 검증 표시의 "다름". 새 provider를 검증하는 범위에서는 provider 항목이 다른 것이 검증 대상이다.
#: 그 밖의 다름(model·digest·Ollama·prompt·code·생성 설정)은 비교 조건을 훼손한다.
PROVIDER_ITEMS = {"provider", "tims_execution"}


def allowed_differences(scope, provider_name):
    if scope == "meaning" and provider_name == "mock":
        return set()
    return set(PROVIDER_ITEMS)


def decision_states():
    """decisions.md의 결정 항목과 상태(미결정 / 결정됨)."""
    text = (HERE / "decisions.md").read_text(encoding="utf-8")
    states = {}
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        match = re.match(r"(D[0-9]+) ", block)
        if not match:
            continue
        status = re.search(r"^- 상태: (\S+)", block, flags=re.M)
        states[match.group(1)] = "decided" if status and status.group(1).startswith("결정됨") else "undecided"
    return states


def _expected_results(scope, expected, outcome):
    """기대 동작과 실제 결과로 가능한 판정 결과."""
    answered_wrong = "wrong_meaning" if scope == "meaning" else "silent_wrong"
    if outcome == "failed":
        return {"failure"}
    if expected == "answer":
        return {"correct", answered_wrong} if outcome == "answered" else {"wrong_refusal"}
    return {answered_wrong} if outcome == "answered" else {"correct_refusal", "wrong_refusal"}


def _judgment_problems(record, judgment, runs):
    problems = []
    scope, result = judgment["scope"], judgment["result"]
    review = record.get("review") or {}
    question = record.get("question") or {}
    run = runs.get(judgment["run_id"])
    if review.get("status") != "reviewed":
        problems.append("판정은 검토 완료(review.status=reviewed) 뒤에만 적는다")
    if result not in RESULTS[scope]:
        problems.append(f"{scope} 판정에 쓸 수 없는 결과: {result}")
    if run is None:
        return problems + [f"run_id {judgment['run_id']}: 실행 기록이 없다"]
    if run["question_text"] != question.get("text"):
        problems.append("실행의 질문 원문이 question.text와 다르다(다른 사례를 연결함)")
    if run["reference_date"] != question.get("reference_date"):
        problems.append("실행의 기준일이 question.reference_date와 다르다")
    provider = run["provider"]
    responses = run.get("responses") or []
    value = judgment.get("value_check", "not_checked")

    if value == "matches_tims" and not (provider["name"] == "tims" and responses):
        problems.append("value_check=matches_tims인데 그 실행에 실제 TIMS 응답 기록이 없다")
    if scope == "meaning":
        if run["kind"] != "geoflow_cli":
            problems.append("meaning 판정은 GeoFlow 실행으로 한다")
        if value != "not_checked":
            problems.append("meaning 판정은 값을 판정하지 않는다(value_check는 not_checked)")
        if judgment.get("basis") is None:
            problems.append("meaning 판정에는 basis(calls·grounding_only)가 필요하다")
    elif judgment.get("basis") is not None:
        problems.append("basis는 meaning 판정에서만 쓴다")
    if scope in ("provider_contract", "response_interpretation", "end_to_end"):
        if provider["name"] != "tims":
            problems.append(f"{scope} 판정은 tims 실행으로만 한다(mock·reference는 실제 검증이 아니다)")
        if not provider.get("contract_version"):
            problems.append(f"{scope} 판정에는 provider.contract_version이 필요하다")
    if scope == "provider_contract":
        calls = run.get("calls") or []
        if not calls or not responses:
            problems.append("provider_contract 판정에는 보낸 호출과 받은 응답이 필요하다")
        if any(r["call_index"] >= len(calls) for r in responses):
            problems.append("응답의 call_index가 호출 목록 밖이다")
    if scope == "response_interpretation":
        if run["kind"] != "geoflow_cli" or not responses:
            problems.append("response_interpretation 판정은 실제 응답을 받은 GeoFlow 실행으로 한다")
        if value not in ("matches_tims", "differs"):
            problems.append("response_interpretation 판정에는 값 판정(matches_tims·differs)이 필요하다")
        if (result == "correct") != (value == "matches_tims"):
            problems.append("response_interpretation의 결과와 값 판정이 맞지 않는다")
    if scope == "end_to_end":
        if run["kind"] != "geoflow_cli" or provider.get("mode") != "direct":
            problems.append("end_to_end 판정은 GeoFlow CLI가 TIMS를 직접 호출한 실행만 쓴다(업체 대행 실행은 아니다)")
    if scope in ("meaning", "end_to_end") and not (scope == "meaning" and judgment.get("basis") == "grounding_only"):
        outcome = run.get("outcome")
        if outcome is None:
            problems.append(f"{scope} 판정에는 실행의 outcome이 필요하다")
        elif review.get("expected_behavior") and result not in _expected_results(scope, review["expected_behavior"], outcome):
            problems.append(f"기대 동작({review['expected_behavior']})·실제 결과({outcome})·판정({result})이 맞지 않는다")
        if result == "correct_refusal" and not (review.get("expected_stop_basis") and run.get("error_code")):
            problems.append("정확한 거부 판정에는 기대 멈춤 근거(review.expected_stop_basis)와 실제 오류 코드가 필요하다")
        if scope == "end_to_end" and result == "correct" and outcome == "answered" and value != "matches_tims":
            problems.append("답한 질문의 end_to_end 정상 판정에는 실제 응답과 맞는다는 값 판정이 필요하다")
    if scope == "meaning" and judgment.get("basis") == "grounding_only":
        if not run.get("grounding"):
            problems.append("grounding_only 판정에는 실행의 grounding 기록이 필요하다")
        if result not in ("correct", "wrong_meaning"):
            problems.append("grounding_only 판정의 결과는 correct·wrong_meaning뿐이다")

    combination = judgment["combination"]
    if combination != "unverified":
        source = run
        if run["kind"] == "vendor_relay":
            source = runs.get(run.get("source_run_id") or "")
            if source is None:
                return problems + ["업체 대행 실행을 조합에 귀속하려면 호출을 만든 GeoFlow 실행(source_run_id)이 필요하다"]
        verification = source.get("geoflow_verification")
        if not verification:
            problems.append(f"{combination}에 귀속하려면 실행의 geoflow_verification이 필요하다")
        else:
            if verification["compared_to"] != combination:
                problems.append(f"검증 표시의 비교 대상({verification['compared_to']})이 {combination}이 아니다")
            extra = set(verification["different"]) - allowed_differences(scope, source["provider"]["name"])
            if extra:
                problems.append(f"비교 조건을 훼손하는 다름: {', '.join(sorted(extra))} → combination=unverified로 적는다")
            if verification["unchecked"]:
                problems.append(f"확인 안 함 항목이 있다: {', '.join(sorted(verification['unchecked']))}")
    return problems


def validate_records(records, *, location=None):
    schema = json.loads((HERE / "record_schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    states = decision_states()
    in_real_dir = location is not None and REAL_RECORDS_DIR in Path(location).resolve().parents
    problems, seen = [], set()
    for index, record in enumerate(records, 1):
        where = f"{index}:{record.get('record_id', '?')}"
        schema_errors = list(validator.iter_errors(record))
        for error in schema_errors:
            path = "/".join(str(p) for p in error.absolute_path)
            problems.append(f"{where} {path}: {error.message}")
        if schema_errors:
            continue
        if record["record_id"] in seen:
            problems.append(f"{where} record_id 중복")
        seen.add(record["record_id"])
        if in_real_dir and record["record_id"].startswith("fake-"):
            problems.append(f"{where} 테스트용 가짜 기록이 실제 자료 위치에 있다")
        review = record["review"]
        refs = review.get("decision_refs") or []
        for ref in refs:
            if ref not in states:
                problems.append(f"{where} decision_refs {ref}: decisions.md에 없음")
        if any(b["kind"] == "vendor_decision" for b in review.get("label_basis") or []):
            if not refs:
                problems.append(f"{where} vendor_decision 근거인데 decision_refs가 없다")
            for ref in refs:
                if states.get(ref) == "undecided":
                    problems.append(f"{where} {ref}는 미결정인데 업체 결정(vendor_decision)으로 인용했다")
        runs = {}
        for run in record.get("runs") or []:
            if run["run_id"] in runs:
                problems.append(f"{where} run_id {run['run_id']} 중복")
            runs[run["run_id"]] = run
            if run["kind"] == "vendor_relay" and run["provider"].get("mode") != "vendor_relay":
                problems.append(f"{where} 업체 대행 실행의 provider.mode는 vendor_relay다")
        for judgment in record.get("judgments") or []:
            for problem in _judgment_problems(record, judgment, runs):
                problems.append(f"{where} [{judgment['scope']}:{judgment['run_id']}] {problem}")
    return problems


def main(path):
    records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    problems = validate_records(records, location=path)
    for problem in problems:
        print(problem)
    print(f"{len(records)} records, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
