# -*- coding: utf-8 -*-
"""검증 사슬(계획서 v2 5.2절, W5). 레코드마다 render_full과 render_partial이 같은 execution과 같은 mock 실행 결과를 내는가.

    semantics → render_full    → (planner: 정규화·조건 계층) → compose → validate → compile ─┐
    semantics → render_partial → completion → (같은 planner 경로) → compose → validate → compile ─┤ 같아야 함
                                                                                            └ mock execute(Tool 호출·결과)

1. 운영 경로 판정: ``training.data.validation.assess_t2pc``(T2PC, 기준일 2026-09-25)를 Full target과 "completion 뒤 Partial target"에 각각 부른다.
   ``PartialPlanner``는 completion 뒤 부모 검증을 그대로 거치므로, completion한 payload를 trunk 경로에 넣은 것과 같다.
   같아야 하는 것: parse·outcome·error_code·validation·operators·compile, grounding 서명(EVENT 노드를 뺀 것; Partial은 사건을 적지 않고 composer가 붙인다).
2. mock 실행: ``evaluate_vendor100``의 정답 planner pipeline(``cmd_gold``와 같은 경로)으로 두 payload를 실행해 Tool 호출 열(``_normalized``)과
   Tool 결과가 같은가.
3. execution 층과의 일치: 레코드에 vendor 형식 execution이 있으면 Full 실행이 그것과 같은 호출인가(업체 채점 ``score`` == match).
통과(``ok``, 지시 W5) = 1·2 모두 같고 3이 어긋나지 않는다(execution이 있을 때만). Full 경로가 mock에서 답하는지(``full_answered``: 판정·mock 모두
answered 또는 unsupported)는 따로 센다. mock gazetteer에 없는 장소 등으로 Full 경로도 답하지 못하는 레코드는 두 표현이 같아도 실행 확인이 약하다.
"""
import json

from grounding.completion import complete_grounding_payload
from grounding.full_renderer import render_full
from grounding.partial_renderer import render_partial

EXEC_KEYS = ("parse_ok", "outcome", "error_code", "validation_ok", "validation_codes", "operators", "compile_ok", "compile_error_code")


def _strip_events(signature):
    if not signature:
        return signature
    return {"concepts": [c for c in signature["concepts"] if json.loads(c).get("concept") != "EVENT"], "factors": signature["factors"]}


def _mock(payload, question):
    import evaluate_vendor100 as EV
    try:
        observed = EV.run_item(EV._pipeline(EV._GoldPlanner(payload)), question)
    except Exception as error:  # noqa: BLE001 - 기록하고 비교
        observed = EV._crashed(error)
    calls = [[c["tool"], EV._normalized(c["tool"], c["args"])] for c in observed["calls"]]
    results = [json.dumps(c.get("result"), ensure_ascii=False, sort_keys=True, default=str) for c in observed["calls"]]
    return observed, calls, results


def validate_semantics(semantics, question, execution=None):
    """검증 사슬 한 번. 결과 dict(``ok``와 단계별 비교)."""
    import evaluate_vendor100 as EV
    from training.data.validation import assess_t2pc
    full = render_full(semantics)
    partial = render_partial(semantics)
    completed = complete_grounding_payload(json.loads(json.dumps(partial)))
    a_full, a_part = assess_t2pc(full, question), assess_t2pc(completed, question)
    exec_same = {k: a_full.get(k) for k in EXEC_KEYS} == {k: a_part.get(k) for k in EXEC_KEYS}
    sig_same = _strip_events(a_full.get("signature")) == _strip_events(a_part.get("signature"))
    m_full, calls_full, res_full = _mock(full, question)
    m_part, calls_part, res_part = _mock(completed, question)
    mock_same = (m_full["outcome"], m_full["error_code"], calls_full, res_full) == (m_part["outcome"], m_part["error_code"], calls_part, res_part)
    execution_match = None
    if execution:
        category, _ = EV.score({"id": "-", "question": question, "gold": execution, "expected_outcome": "answered",
                                "vendor_verdict": "-"}, m_full)
        execution_match = category == "match"
    answered = a_full.get("outcome") in ("answered", "unsupported") and m_full["outcome"] in ("answered", "unsupported")
    ok = exec_same and sig_same and mock_same and execution_match is not False
    return {"ok": ok, "assess_same": exec_same, "signature_same(no EVENT)": sig_same, "mock_same": mock_same,
            "full_answered": answered, "execution_match": execution_match,
            "full": {k: a_full.get(k) for k in EXEC_KEYS}, "partial": {k: a_part.get(k) for k in EXEC_KEYS},
            "mock_full": {"outcome": m_full["outcome"], "error_code": m_full["error_code"], "calls": calls_full},
            **({} if mock_same else {"mock_partial": {"outcome": m_part["outcome"], "error_code": m_part["error_code"], "calls": calls_part}}),
            "condition_changed_meaning": a_full.get("condition_changed_meaning")}
