# -*- coding: utf-8 -*-
"""조건 평가 채점기 v2. 질문 해석 / 요청 인자 / provider 계약 / mock 정답을 따로 센다.

v1(``structured_grounding_eval.score``)과 다른 점
- 조건 판정을 최종 grounding의 글자 대신 **의미**로 한다. 기간은 gold가 받아들이는 표현
  목록(``accept``)으로 비교하므로 "지난달"을 ``last_month``로 적든 손으로 센 절대 범위로
  적든 같은 점수다. taxi_type ``all``과 생략은 실행 의미가 같다(schema pt_taxi_type
  "all=조건 미적용"). 단, 사용자가 "전체 택시"라고 말했는지(``taxi_stated``)는 따로 남긴다.
- grounding이 거부된 관측은 조건 판정 불가(``not_judgeable``)로 두고 누락으로 세지 않는다.
- 요청 인자(실제로 나간 호출)와 provider 의미(그 인자를 TIMS 계약상 같은 기간으로
  읽는가)를 나눈다. provider 판정은 이 파일 안의 정규식으로 한다(제품 코드를 쓰지 않음).
  계약상 확인되는 것: 단일 날짜 ``YYYYMMDD``, 인자 없음(질문에 기간이 없을 때), taxi_type
  enum 값. 범위·상대 토큰·요일 토큰은 확인되지 않는다(tims_contract 표).
- mock 정답은 "gold 요청 인자와 같은 인자로 호출했다"는 뜻이다. mock은 인자를 해석하지
  않으므로(인자 hash) 하루 단위로 나눈 호출은 비교할 수 없다(``mock_not_comparable``).
- 실제 데이터 기준 정답은 측정하지 않는다(``real_data: not_measured``).
- 조건 상태가 검증 불가(보류)인 값은 맞더라도 ``verified_ok``로 세지 않는다.

    python condition_scoring.py RUN_DIR --analysis-id ID [--addendum FILE]
        [--corrects PATH ... --reason TEXT]
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from evaluation_records import write_analysis

SCORER_NAME = "condition_scoring"
SCORER_VERSION = "v2.7"
# v2.7: 집계 의미를 칸별로 따로 센다(bucket, inner, outer, 결과 종류 value/group). gold에
#       retrieval_tags가 있으면 붙인 예시 중 그 의미 구분을 설명하는 예시가 있었는지(검색 포함률)를
#       센다. system prompt 글자 수와 입력 token(prompt_eval_count), 지연을 요약에 더한다.
#       이전 판의 판정(plan_ok, correct_answer 등)은 바꾸지 않는다.
# v2.6: 구간마다 부른 범위 호출(range_partition)이 gold 기간을 빈틈과 겹침 없이 덮으면 요청
#       인자 보존으로 인정한다. v2.5까지는 범위 호출이 여러 개면 보존 실패로 셌다.
# v2.5: gold에 answer가 있으면 계산 값(와 선택 구간)을 비교한다(reference provider용).
#       관측의 실행 프로필이 reference이면 provider 의미는 reference 계약(단일 날짜·양 끝 포함
#       범위 확인)으로 판정하고 mock 정답은 해당 없음으로 둔다.
# v2.4: 결과 형태 구조(group key=dimension, order, limit)를 판정한다. gold에 structure가 없으면
#       셋 다 "없음"이 기대값이다. 이전 판(v2.3)은 이를 보지 않아, 목록 질의가 된 답(cond_v2
#       d35: dimension=emd, order=bottom)을 정답으로 셌다. 값 반환/구간 선택(select)과 구간
#       단위(bucket)·구간 안/밖 reducer는 이전부터 plan 비교에 들어 있다.
# v2.3: 계약상 실행 가능한 질문에서의 정답 수(correct_contract_executable)를 요약에 더한다.
# v2.2: 여러 날짜 호출을 합친 답(하루 단위 합성)은 기록이 하루에만 속한다는 계약이 TIMS에
#       없으므로 provider 의미 미확인으로 센다(날짜 하나하나가 단일 날짜여도).
# v2.1: 계약 코드로 멈췄어도 집계 계획이 틀렸으면(없는 bucket을 지어냄 등) 집계 원인으로 센다.

_SINGLE = re.compile(r"\d{8}")
#: provider 계약 한계로 멈춘 결과. 답할 수 있는 질문이어도 부당한 거부로 세지 않고 따로 센다.
CONTRACT_CODES = frozenset({"DATE_EXECUTION_UNVERIFIED", "UNVERIFIED_TIMS_CONTRACT"})
CONDITION_CODES = frozenset({
    "DATE_EXPRESSION_UNSUPPORTED", "DATE_AMBIGUOUS", "DATE_CONFLICT",
    "DATE_MULTIPLE_UNSUPPORTED", "TAXI_TYPE_EXPRESSION_UNSUPPORTED", "PLACE_NOT_IN_QUESTION",
    "CONDITION_LOST", "INVALID_FACTOR",
})
AGGREGATION_CODES = frozenset({
    "AMBIGUOUS_INNER_AGGREGATION", "UNSUPPORTED_AGGREGATION", "UNSUPPORTED_GROUPED_MEASURE",
    "UNSUPPORTED_AGGREGATION_COMBINATION", "AGGREGATION_SOURCE_CONFLICT",
    "MISSING_OUTER_AGGREGATION", "INVALID_AGGREGATION_PLAN", "UNSUPPORTED_PARTITION_SIZE",
    "UNSUPPORTED_PERIOD_FOR_GROUPING", "UNRESOLVED_PERIOD",
})
VERIFIED_STATUSES = frozenset({"interpreted", "conflict", "absent"})
#: 결과의 형태를 바꾸는 factor. 값 하나인지, 어떤 key로 나눈 목록인지, 몇 개를 어떤 순서로인지.
STRUCTURE_KEYS = ("dimension", "order", "limit")


# -- gold ------------------------------------------------------------------


def load_gold(questions_path, addendum_path=None):
    """{id: 정규화한 기대값}. v1 gold(pt_date 글자)와 v2 gold(accept 목록)를 같은 모양으로.

    addendum은 v1 gold에 손으로 적은 동치 표현(예: last_month = 20260801-20260831)을 더한다.
    원래 gold 파일은 바꾸지 않는다.
    """
    document = yaml.safe_load(Path(questions_path).read_text(encoding="utf-8"))
    extra = {}
    if addendum_path:
        extra = yaml.safe_load(Path(addendum_path).read_text(encoding="utf-8")).get(
            "date_equivalents") or {}
    gold = {}
    for item in document["questions"]:
        expected = dict(item["expected"])
        conditions = dict(expected.get("conditions") or {})
        date = conditions.get("date")
        if isinstance(date, dict):
            accept = [str(value) for value in date.get("accept") or []]
            request = date.get("request", accept[0] if accept else None)
        elif date is None:
            accept, request = [], None
        else:
            accept = [str(date)] + [str(v) for v in extra.get(str(date), [])]
            request = str(date)
        places = conditions.get("place")
        if places is not None and not isinstance(places, list):
            places = [places]
        taxi = conditions.get("taxi_type")
        gold[item["id"]] = {
            "question": item["question"],
            "outcome": expected["outcome"],
            "plan": expected.get("plan"),
            "date_accept": accept,
            "date_request": request,
            "taxi_type": None if taxi == "all" else taxi,
            "taxi_stated": conditions.get("taxi_stated"),
            "place": sorted(places) if places else [],
            "od": conditions.get("od"),
            "contract_executable": expected.get(
                "contract_executable",
                expected["outcome"] == "answered" and (date is None or (
                    isinstance(date, str) and bool(_SINGLE.fullmatch(date))))),
            "family": item.get("family") or item.get("class"),
            "structure": {key: (expected.get("structure") or {}).get(key)
                          for key in STRUCTURE_KEYS},
            "answer": expected.get("answer"),
            "retrieval_tags": list(item.get("retrieval_tags") or []),
            "ambiguity": item.get("ambiguity"),
        }
    return document, gold


# -- 관측 하나 ---------------------------------------------------------------


def _norm_taxi(value):
    return None if value in (None, "all") else value


def _date_ok(value, gold):
    return (value is None and not gold["date_accept"]) or (
        value is not None and str(value) in gold["date_accept"])


def grounding_plan(grounding):
    if not grounding:
        return "NO_GROUNDING"
    spec = grounding.get("aggregation") or {}
    if spec.get("bucket") is None:
        return None if spec.get("inner") is None else {"final": spec["inner"]}
    plan = {"bucket": spec["bucket"], "inner": spec.get("inner") or "unspecified"}
    if spec.get("select"):
        plan["select"] = spec["select"]
    else:
        plan["final"] = spec.get("outer")
    return plan


def _grounding_places(grounding):
    return sorted(
        (item.get("value") or {}).get("name") if isinstance(item.get("value"), dict)
        else item.get("value")
        for item in grounding.get("concepts") or []
        if item.get("concept") == "LOCATION" and item.get("role") != "MEASURE"
        and item.get("value"))


def _grounding_od(grounding):
    roles = {}
    for item in grounding.get("concepts") or []:
        role = (item.get("attributes") or {}).get("od_role")
        if role and isinstance(item.get("value"), dict):
            roles[role] = item["value"].get("name")
    return roles


def interpretation(record, gold):
    """최종 grounding의 조건이 질문 의미와 같은가. 조건마다 ok/missing/added/changed."""
    grounding = record.get("grounding")
    if not grounding:
        return {"judgeable": False, "status": {k: "not_judgeable"
                                               for k in ("date", "taxi_type", "place", "od")},
                "ok": None}
    factors = grounding.get("factors") or {}
    status = {}
    date = factors.get("date")
    if _date_ok(date, gold):
        status["date"] = "ok"
    elif date is None:
        status["date"] = "missing"
    elif not gold["date_accept"]:
        status["date"] = "added"
    else:
        status["date"] = "changed"
    taxi, want = _norm_taxi(factors.get("taxi_type")), gold["taxi_type"]
    status["taxi_type"] = ("ok" if taxi == want else "missing" if taxi is None
                           else "added" if want is None else "changed")
    places = _grounding_places(grounding)
    status["place"] = ("ok" if places == gold["place"] else
                       "missing" if set(places) < set(gold["place"]) else
                       "added" if set(places) > set(gold["place"]) else "changed")
    status["od"] = ("ok" if gold["od"] is None or _grounding_od(grounding) == gold["od"]
                    else "changed")
    return {"judgeable": True, "status": status,
            "ok": all(value == "ok" for value in status.values())}


def request_level(record, gold):
    """실제로 나간 측정 호출의 인자가 질문 의미를 옮겼는가. 기록이 없으면 None."""
    executed = record.get("executed")
    if executed is None:
        return {"recorded": False}
    if not executed.get("measure_calls"):
        return {"recorded": True, "called": False}
    dates = executed.get("dates") or []
    daily = len(dates) > 1 and all(_SINGLE.fullmatch(d) for d in dates)
    tiled = len(dates) > 1 and all(_RANGE.fullmatch(d) for d in dates)
    if tiled:
        ranges = [a for a in gold["date_accept"] if _RANGE.fullmatch(a)]
        date_ok = any(_tiles(dates, item) for item in ranges)
    elif daily:
        # 하루 단위 합성: 호출 날짜가 gold의 범위를 빈틈없이 덮어야 한다.
        ranges = [a for a in gold["date_accept"] if re.fullmatch(r"\d{8}-\d{8}", a)]
        date_ok = any(_covers(dates, item) for item in ranges)
    elif not dates:
        date_ok = not gold["date_accept"]
    else:
        date_ok = len(dates) == 1 and dates[0] in gold["date_accept"]
    taxis = {_norm_taxi(value) for value in executed.get("taxi_types") or []} or {None}
    taxi_ok = taxis == {gold["taxi_type"]}
    places_ok = sorted(executed.get("place_lookups") or []) == gold["place"]
    return {"recorded": True, "called": True, "daily": daily, "date_ok": date_ok,
            "taxi_ok": taxi_ok, "place_ok": places_ok,
            "ok": date_ok and taxi_ok and places_ok}


def _tiles(spans, span):
    """범위 목록이 span을 빈틈·겹침 없이 덮는가."""
    days = []
    for item in spans:
        days += _days(item)
    return days == _days(span)


def _days(span):
    from datetime import date, timedelta
    head, _, tail = span.partition("-")
    start = date(int(head[:4]), int(head[4:6]), int(head[6:]))
    end = date(int(tail[:4]), int(tail[4:6]), int(tail[6:])) if tail else start
    out = []
    while start <= end:
        out.append(start.strftime("%Y%m%d"))
        start += timedelta(days=1)
    return out


def _covers(dates, span):
    from datetime import date, timedelta
    head, tail = span.split("-")
    start = date(int(head[:4]), int(head[4:6]), int(head[6:]))
    end = date(int(tail[:4]), int(tail[4:6]), int(tail[6:]))
    days = []
    while start <= end:
        days.append(start.strftime("%Y%m%d"))
        start += timedelta(days=1)
    return sorted(dates) == days


_RANGE = re.compile(r"\d{8}-\d{8}")


def _provider_of(record):
    return (record.get("execution_profile") or {}).get("provider") or "mock"


def provider_level(record):
    """나간 측정 호출의 기간 인자가 그 provider의 계약상 확인된 의미인가(장소는 판정하지 않음).

    mock은 TIMS 계약(단일 날짜만 확인), reference는 reference 계약(단일 날짜·양 끝 포함 범위,
    기록이 하루에만 속하므로 하루 합성도 확인)으로 본다.
    """
    executed = record.get("executed")
    if executed is None:
        return {"recorded": False}
    if not executed.get("measure_calls"):
        return {"recorded": True, "called": False}
    dates = executed.get("dates") or []
    if _provider_of(record) == "reference":
        confirmed = all(_SINGLE.fullmatch(v) or _RANGE.fullmatch(v) for v in dates)
        return {"recorded": True, "called": True, "date_confirmed": confirmed,
                "composition_unverified": False, "contract": "reference",
                "unverified_arguments": [v for v in dates
                                         if not (_SINGLE.fullmatch(v) or _RANGE.fullmatch(v))]}
    single = all(_SINGLE.fullmatch(value) for value in dates)
    composed = len(dates) > 1
    return {"recorded": True, "called": True, "date_confirmed": single and not composed,
            "composition_unverified": composed,
            "unverified_arguments": [value for value in dates if not _SINGLE.fullmatch(value)]}


def mock_level(record, gold, plan_ok, request):
    """mock 기준 정답: gold 요청 인자와 같은 인자로 계산했는가."""
    if _provider_of(record) != "mock":
        return "not_applicable"
    if record.get("outcome") != "answered" or not request.get("recorded"):
        return None
    if request.get("daily"):
        return "mock_not_comparable"
    executed = record.get("executed") or {}
    dates = executed.get("dates") or []
    same_date = (dates == [gold["date_request"]]) if gold["date_request"] else not dates
    return bool(plan_ok and same_date and request.get("taxi_ok") and request.get("place_ok"))


def corrections(record, gold):
    """보정 하나하나가 맞았는지: good | bad | unnecessary(같은 의미로 바꿈) | wrong_to_wrong."""
    counts = Counter()
    for item in (record.get("condition_audit") or {}).get("corrections") or []:
        key = item["condition"]
        if key == "date":
            before, after = _date_ok(item.get("from"), gold), _date_ok(item.get("to"), gold)
        else:
            before = _norm_taxi(item.get("from")) == gold["taxi_type"]
            after = _norm_taxi(item.get("to")) == gold["taxi_type"]
        counts["unnecessary" if before and after else "good" if after
               else "bad" if before else "wrong_to_wrong"] += 1
    return dict(counts)


def verified_claims(record, interp):
    """조건 계층이 검증했다고 적은 조건과 실제 정오. 보류(unverifiable)는 검증으로 세지 않는다."""
    audit = record.get("condition_audit")
    if not audit:
        return None
    result = {}
    for key in ("date", "taxi_type"):
        status = (audit.get(key) or {}).get("status") or _legacy_status(audit.get(key) or {})
        verified = status in VERIFIED_STATUSES
        correct = interp["judgeable"] and interp["status"][key] == "ok"
        result[key] = {"status": status, "verified_ok": verified and correct,
                       "verified_wrong": verified and interp["judgeable"] and not correct,
                       "unverified": not verified}
    return result


def _legacy_status(record):
    """status 필드가 없던 기록(v1 조건 계층)의 action을 상태로 옮긴다. 근거를 새로 만들지 않는다."""
    action = record.get("action")
    return {"confirmed": "interpreted", "filled": "interpreted", "corrected": "conflict",
            "removed_no_evidence": "absent", "none": "absent",
            "unverified": "unverifiable"}.get(action, "unknown")


def block_cause(record, plan_ok=True):
    code = (record.get("error") or {}).get("code")
    if record.get("outcome") == "answered" or code is None:
        return None
    if code in CONTRACT_CODES:
        return "contract" if plan_ok else "aggregation"
    if code in CONDITION_CODES:
        return "condition"
    if code in AGGREGATION_CODES:
        return "aggregation"
    return "other"


def structure_level(record, gold):
    """dimension·order·limit이 질문 의미와 같은가. grounding이 없으면 판정 불가(None)."""
    grounding = record.get("grounding")
    if not grounding:
        return {"judgeable": False, "ok": None}
    factors = grounding.get("factors") or {}
    got = {key: factors.get(key) for key in STRUCTURE_KEYS}
    want = gold.get("structure") or {key: None for key in STRUCTURE_KEYS}
    wrong = [key for key in STRUCTURE_KEYS if got.get(key) != want.get(key)]
    return {"judgeable": True, "ok": not wrong, "wrong": wrong, "got": got}


def answer_level(record, gold):
    """gold answer와 계산 결과 비교. gold에 answer가 없으면 None."""
    want = gold.get("answer")
    if not want:
        return None
    if record.get("outcome") != "answered":
        return False
    value = record.get("final_value")
    if isinstance(value, dict) and "groups" in value:
        labels = [group.get("label") for group in value.get("groups") or []]
        return bool(labels == [str(g) for g in want.get("groups") or []]
                    and _close(value.get("value"), want.get("value")))
    return not want.get("groups") and _close(value, want.get("value"))


def _close(a, b):
    return isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) < 1e-6


def returns_kind(plan):
    """값을 돌려주는가, 구간을 골라 돌려주는가."""
    if isinstance(plan, dict) and plan.get("select"):
        return "group"
    return "value"


def _spec(plan):
    """plan(grounding_plan 모양)을 칸별 값으로. 집계가 없으면 모두 None."""
    if not isinstance(plan, dict):
        return {"bucket": None, "inner": None, "outer": None, "select": None}
    if plan.get("bucket") is None:
        return {"bucket": None, "inner": plan.get("final"), "outer": None, "select": None}
    return {"bucket": plan["bucket"], "inner": plan.get("inner"),
            "outer": plan.get("final"), "select": plan.get("select")}


def slot_level(record, gold):
    """집계 의미 칸별 판정. 답할 수 있거나 확인이 필요한 질문에서 grounding이 있을 때만."""
    plan = grounding_plan(record.get("grounding"))
    if gold["outcome"] not in ("answered", "needs_clarification") or plan == "NO_GROUNDING":
        return None
    got, want = _spec(plan), _spec(gold["plan"])
    return {"bucket": got["bucket"] == want["bucket"], "inner": got["inner"] == want["inner"],
            "outer": got["outer"] == want["outer"],
            "result_kind": returns_kind(plan) == returns_kind(gold["plan"]),
            "got": got}


def retrieval_coverage(record, gold):
    """붙인 예시 가운데 gold가 적은 의미 구분(retrieval_tags)을 설명하는 예시가 있었나."""
    retrieval = record.get("retrieval")
    if not retrieval or not gold.get("retrieval_tags"):
        return None
    from geoflow.examples import load_store
    store = load_store()
    tags = set()
    for example_id in retrieval.get("included") or []:
        try:
            tags.update(store.get(example_id).tags)
        except KeyError:
            continue
    return bool(tags & set(gold["retrieval_tags"]))


def judge(record, gold):
    plan = grounding_plan(record.get("grounding"))
    structure = structure_level(record, gold)
    plan_ok = plan == gold["plan"] and structure["ok"] is not False
    interp = interpretation(record, gold)
    request = request_level(record, gold)
    provider = provider_level(record)
    outcome = record.get("outcome")
    answered = outcome == "answered"
    if answered and request.get("recorded"):
        semantic_ok = plan_ok and bool(request.get("ok")) and interp["status"]["od"] == "ok"
        semantic_source = "request"
    else:
        semantic_ok = plan_ok and bool(interp["ok"])
        semantic_source = "grounding"
    want = gold["outcome"]
    cause = block_cause(record, plan_ok)
    refused = want == "answered" and not answered
    contract_refusal = refused and not gold["contract_executable"] and cause == "contract"
    return {
        "outcome": outcome, "code": (record.get("error") or {}).get("code"),
        "plan": plan, "plan_ok": plan_ok, "structure": structure,
        "returns": returns_kind(plan), "returns_ok": returns_kind(plan) == returns_kind(
            gold["plan"]),
        "interpretation": interp, "request": request, "provider": provider,
        "mock_correct": mock_level(record, gold, plan_ok, request),
        "answer_correct": answer_level(record, gold),
        "real_data_correct": "not_measured",
        "semantic_source": semantic_source,
        "correct_answer": answered and want == "answered" and semantic_ok,
        "silent_semantic_error": answered and not (want == "answered" and semantic_ok),
        "answered_provider_unverified": bool(
            answered and want == "answered" and semantic_ok
            and provider.get("recorded") and provider.get("called")
            and not provider.get("date_confirmed")),
        "contract_refusal": contract_refusal,
        "unjust_refusal": refused and not contract_refusal,
        "outcome_ok": outcome == want,
        "clarification_ok": want == "needs_clarification" and outcome == "needs_clarification",
        "block_cause": cause,
        "corrections": corrections(record, gold),
        "verified_claims": verified_claims(record, interp),
        "taxi_stated": gold["taxi_stated"],
        "slots": slot_level(record, gold),
        "retrieval_covered": retrieval_coverage(record, gold),
    }


# -- 요약 ------------------------------------------------------------------


def summarize(judged, arms):
    summary = {}
    for arm in arms:
        mine = [row for row in judged if row["arm"] == arm and row.get("valid", True)]
        answerable = [r for r in mine if r["gold_outcome"] == "answered"]
        executable = [r for r in answerable if r["contract_executable"]]
        judgeable = [r for r in mine if r["interpretation"]["judgeable"]]
        requested = [r for r in mine if r["request"].get("called")]
        corrections_total = Counter()
        for row in mine:
            corrections_total.update(row["corrections"])
        claims = [row["verified_claims"] for row in mine if row["verified_claims"]]
        summary[arm] = {
            "observations": len(mine),
            "answerable": len(answerable),
            "answerable_contract_executable": len(executable),
            # 1. 질문 의미에 맞는 조건 해석(최종 grounding, 판정 가능한 관측만)
            "interpretation_ok": sum(bool(r["interpretation"]["ok"]) for r in judgeable),
            "interpretation_judgeable": len(judgeable),
            "not_judgeable": len(mine) - len(judgeable),
            "interpretation_status": {
                key: dict(Counter(r["interpretation"]["status"][key] for r in judgeable))
                for key in ("date", "taxi_type", "place", "od")},
            # 2. 조건이 실행 요청에 보존됨(측정 호출이 나간 관측만)
            "request_ok": sum(bool(r["request"].get("ok")) for r in requested),
            "request_called": len(requested),
            "request_not_recorded": sum(not r["request"].get("recorded") for r in mine),
            # 3. provider 계약상 기간 의미가 확인됨
            "provider_date_confirmed": sum(bool(r["provider"].get("date_confirmed"))
                                           for r in requested),
            # 4. mock 기준 계산 정답
            "mock_correct": sum(r["mock_correct"] is True for r in mine),
            "mock_not_comparable": sum(r["mock_correct"] == "mock_not_comparable" for r in mine),
            # 5. 실제 데이터 기준 정답
            "real_data_correct": "not_measured",
            "correct_answer": sum(r["correct_answer"] for r in mine),
            "correct_contract_executable": sum(r["correct_answer"] for r in executable),
            # 6. 조용한 의미 오류와, 의미는 맞지만 provider 의미가 확인되지 않은 답
            "silent_semantic_error": sum(r["silent_semantic_error"] for r in mine),
            "answered_provider_unverified": sum(r["answered_provider_unverified"] for r in mine),
            # 7. 답할 수 있는 질문의 부당한 거부 / 계약 한계로 멈춤
            "unjust_refusal": sum(r["unjust_refusal"] for r in answerable),
            "unjust_refusal_contract_executable": sum(r["unjust_refusal"] for r in executable),
            "contract_refusal": sum(r["contract_refusal"] for r in answerable),
            "clarification_ok": sum(r["clarification_ok"] for r in mine),
            "outcome_ok": sum(r["outcome_ok"] for r in mine),
            # 8. 보정
            "corrections": dict(corrections_total),
            "block_cause": dict(Counter(r["block_cause"] for r in mine if r["block_cause"])),
            "verified_ok": sum(c[k]["verified_ok"] for c in claims for k in c),
            "verified_wrong": sum(c[k]["verified_wrong"] for c in claims for k in c),
            "unverified_conditions": sum(c[k]["unverified"] for c in claims for k in c),
            "structure_wrong": sum(r["structure"]["ok"] is False for r in mine),
            "answer_correct": sum(r["answer_correct"] is True for r in mine),
            "answer_judged": sum(r["answer_correct"] is not None for r in mine),
            "returns_wrong": sum(not r["returns_ok"] for r in mine
                                 if r["interpretation"]["judgeable"]),
            "outcomes": dict(Counter(r["outcome"] for r in mine)),
            "tool_calls_total": sum(r.get("tool_calls") or 0 for r in mine),
            "llm_calls_total": sum(r.get("llm_calls") or 0 for r in mine),
            # v2.7
            "slots_judged": sum(r["slots"] is not None for r in mine),
            "slot_ok": {key: sum(bool(r["slots"] and r["slots"][key]) for r in mine)
                        for key in ("bucket", "inner", "outer", "result_kind")},
            "plan_ok": sum(r["plan_ok"] for r in mine),
            "retrieval_covered": sum(r["retrieval_covered"] is True for r in mine),
            "retrieval_judged": sum(r["retrieval_covered"] is not None for r in mine),
            "system_prompt_chars_median": _median([r.get("system_prompt_chars") for r in mine]),
            "prompt_tokens_median": _median([r.get("prompt_tokens") for r in mine]),
            "elapsed_ms_median": _median([r.get("elapsed_ms") for r in mine]),
            "by_ambiguity": dict(Counter(f"{r.get('ambiguity') or 'clear'}:{category(r)}"
                                         for r in mine)),
        }
    return summary


def _median(values):
    values = sorted(value for value in values if value is not None)
    return values[len(values) // 2] if values else None


def category(row):
    if row["correct_answer"]:
        return "correct"
    if row["silent_semantic_error"]:
        return "silent_wrong"
    if row["outcome_ok"]:
        return "correct_refusal"
    if row["contract_refusal"]:
        return "contract_refusal"
    if row["unjust_refusal"]:
        return "unjust_refusal"
    return "other"


def transitions(judged, before, after):
    by = {}
    for row in judged:
        by.setdefault((row["id"], row.get("repetition", 0)), {})[row["arm"]] = row
    counts, examples = Counter(), {}
    for key, arms in sorted(by.items()):
        if before not in arms or after not in arms:
            continue
        change = f"{category(arms[before])}->{category(arms[after])}"
        counts[change] += 1
        examples.setdefault(change, []).append(key[0])
    return {"counts": dict(counts), "ids": examples}


def _prompt_tokens(record):
    calls = record.get("llm_calls")
    if not isinstance(calls, list):
        return None
    counts = [call.get("prompt_eval_count") for call in calls if isinstance(call, dict)]
    return sum(counts) if counts and None not in counts else None


def score_records(records, gold, arms):
    judged = []
    for record in records:
        expected = gold[record["id"]]
        valid = record.get("measurement", "valid") == "valid"
        row = {"id": record["id"], "arm": record["arm"],
               "repetition": record.get("repetition", 0), "valid": valid,
               "gold_outcome": expected["outcome"],
               "contract_executable": expected["contract_executable"],
               "tool_calls": record.get("tool_calls"),
               "llm_calls": len(record.get("llm_calls") or []) if isinstance(
                   record.get("llm_calls"), list) else record.get("llm_calls"),
               "system_prompt_chars": record.get("system_prompt_chars"),
               "prompt_tokens": _prompt_tokens(record), "elapsed_ms": record.get("elapsed_ms"),
               "ambiguity": expected.get("ambiguity")}
        if valid:
            row.update(judge(record, expected))
        judged.append(row)
    invalid = {row["id"] for row in judged if not row["valid"]}
    for row in judged:
        if row["id"] in invalid:
            row["valid"] = False
    usable = [row for row in judged if row["valid"]]
    summary = {"invalid_questions": sorted(invalid), "arms": summarize(usable, arms)}
    if len(arms) >= 2:
        summary["transitions"] = {
            f"{arms[i]}->{arms[j]}": transitions(usable, arms[i], arms[j])
            for i in range(len(arms)) for j in range(len(arms))
            if i < j and arms[j] in (arms[i] + "+cc", arms[i] + "+rx", arms[i] + "+fx")}
    return summary, judged


def score_run(run_dir, *, analysis_id, addendum=None, corrects=None, reason=None):
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    _document, gold = load_gold(meta["questions_file"], addendum)
    records = [json.loads(line) for line in open(run_dir / "observations.jsonl",
                                                 encoding="utf-8")]
    arms = list(meta.get("arms") or sorted({r["arm"] for r in records}))
    summary, judged = score_records(records, gold, arms)
    inputs = [run_dir / "observations.jsonl", meta["questions_file"]]
    if addendum:
        inputs.append(addendum)
    target = write_analysis(
        run_dir, analysis_id=analysis_id,
        outputs={"summary.json": summary, "judged.json": judged},
        scorer={"name": SCORER_NAME, "version": SCORER_VERSION, "source": __file__},
        config={"addendum": str(addendum) if addendum else None, "arms": arms},
        inputs=inputs,
        corrects=None if not corrects else {"previous": [str(p) for p in corrects],
                                            "reason": reason},
    )
    return target, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    parser.add_argument("--analysis-id", required=True)
    parser.add_argument("--addendum")
    parser.add_argument("--corrects", nargs="*")
    parser.add_argument("--reason")
    args = parser.parse_args(argv)
    if args.corrects and not args.reason:
        parser.error("--corrects에는 --reason이 필요합니다.")
    target, summary = score_run(args.run_dir, analysis_id=args.analysis_id,
                                addendum=args.addendum, corrects=args.corrects,
                                reason=args.reason)
    print(target)
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
