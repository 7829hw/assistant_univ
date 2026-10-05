"""Reuse production parsers, composition and all G1-G7 checks."""
import copy

from agent_graph import extract_scopes
from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError
from geoflow.grounding import drop_unsupported_regions, parse_grounding
from geoflow.validator import validate
from training.data.canonicalize import check_shape


def assess(payload, question, *, normalize=True, composer=None):
    result = dict(parse_ok=False, compose_ok=None, validation_ok=None,
                  validation_codes=[], error_code=None, outcome=None)
    try:
        check_shape(payload)
        if payload.get("unsupported"):
            # Production recognizes refusal before parse_grounding; no graph exists.
            result.update(parse_ok=True, outcome="unsupported")
            return result
        grounding = parse_grounding(copy.deepcopy(payload), question, normalize=normalize)
        if normalize:
            drop_unsupported_regions(grounding)
        result.update(parse_ok=True, compose_ok=False)
        plan = (composer or MacroComposer()).compose(grounding)
        result.update(compose_ok=True, validation_ok=False)
        report = validate(plan, user_scopes=set(extract_scopes(question)))
        result.update(validation_ok=report.ok, validation_codes=report.failed_rules(),
                      outcome="answered" if report.ok else "validation_failed")
        result["macros"] = list(plan.applied_macros)
        result["operators"] = [step.operator for step in plan.transformations]
    except (GeoFlowError, ValueError, TypeError) as error:
        result["error_code"] = getattr(error, "code", "INVALID_TRAINING_STRUCTURE")
        result["error_detail"] = str(error)
    return result


def chosen_ok(result):
    return result["parse_ok"] and (result["outcome"] == "unsupported" or result["validation_ok"] is True)


# -- T2PC 판정(조건 계층을 거치는 운영 경로) ---------------------------------------------------------------
# thor의 ``assess``는 parse_grounding → compose → validate만 본다(조건 계층 없음). 현재 운영 조합(T2PC)은 planner가
# 조건 계층(conditions.reconcile_payload)을 먼저 거친다. 아래 판정은 학습 target 문자열을 그대로 돌려주는 stub client로
# 운영 planner 경로를 지나게 하고(모델 호출 없음), compose → validate(mock Tool 목록) → compile(mock·legacy)을 기록한다.
# ``assess``는 비교용으로 그대로 둔다. compile 정지는 실행 계약의 한계이며 grounding 계약 판정(``t2pc_chosen_ok``)에 넣지 않는다.

from datetime import date as _date

#: 평가 harness의 고정 기준일(paraphrase_corpus.EVALUATION_REFERENCE_DATE, evaluate_vendor100.REFERENCE_DATE).
T2PC_REFERENCE_DATE = _date(2026, 9, 25)
_EXECUTOR = None


class _TargetClient:
    model = "training-target"

    def __init__(self, text):
        self.text = text

    def chat(self, messages, **kwargs):
        return {"message": {"content": self.text}, "done_reason": "stop"}


def _mock_executor():
    global _EXECUTOR
    if _EXECUTOR is None:
        from build import build
        from tool_executor import ToolExecutor
        from tool_handlers import get_tool_handlers
        tools, _ = build()
        _EXECUTOR = ToolExecutor(tools=tools, handlers=get_tool_handlers("mock"))
    return _EXECUTOR


def grounding_signature(grounding):
    """의미 비교 키: local id·text·순서를 무시하고 concept/subtype/role/source/value/attributes와 factor를 본다."""
    import json as _json
    concepts = sorted(_json.dumps({"concept": c.concept.value, "subtype": c.subtype, "role": c.role.value,
                                   "source": c.source.value, "value": c.value, "attributes": c.attributes},
                                  ensure_ascii=False, sort_keys=True) for c in grounding.concepts)
    return {"concepts": concepts, "factors": dict(sorted(grounding.factors.items()))}


def _planner_path(text, question, *, condition_check, reference_date):
    from geoflow import providers
    from geoflow.compiler import compile_plan
    from geoflow.planner import GeoFlowPlanner

    result = dict(parse_ok=False, compose_ok=None, validation_ok=None, validation_codes=[], error_code=None,
                  outcome=None, compile_ok=None, compile_error_code=None, condition_actions={}, signature=None)
    planner = GeoFlowPlanner(client=_TargetClient(text), condition_check=condition_check,
                             normalize_grounding=True, clock=lambda: reference_date)
    try:
        output = planner.plan(question)
    except GeoFlowError as error:
        result.update(error_code=getattr(error, "code", type(error).__name__), error_detail=str(error)[:300],
                      outcome="unsupported" if getattr(error, "code", None) == "UNSUPPORTED_QUESTION" else None,
                      parse_ok=getattr(error, "code", None) == "UNSUPPORTED_QUESTION")
        return result
    grounding = output.grounding
    audit = grounding.condition_audit or {}
    result["condition_actions"] = {key: {k: audit[key].get(k) for k in ("action", "basis", "llm_value", "value")}
                                   for key in ("date", "taxi_type", "taxi_status")
                                   if isinstance(audit.get(key), dict)
                                   and audit[key].get("action") not in (None, "none", "confirmed")}
    result.update(parse_ok=True, compose_ok=False, signature=grounding_signature(grounding))
    try:
        plan = MacroComposer().compose(grounding)
    except GeoFlowError as error:
        result.update(error_code=getattr(error, "code", type(error).__name__), error_detail=str(error)[:300])
        return result
    result.update(compose_ok=True, validation_ok=False)
    report = validate(plan, available_tools=_mock_executor().tool_names, user_scopes=set(extract_scopes(question)))
    result.update(validation_ok=report.ok, validation_codes=report.failed_rules(),
                  outcome="answered" if report.ok else "validation_failed",
                  operators=[step.operator for step in plan.transformations])
    if report.ok:
        profile = providers.profile_for()
        try:
            compile_plan(plan, reference_date=reference_date, contract=profile.contract,
                         date_policy=profile.date_policy, delegation=profile.delegation)
            result["compile_ok"] = True
        except GeoFlowError as error:
            result.update(compile_ok=False, compile_error_code=getattr(error, "code", type(error).__name__))
    return result


def assess_t2pc(payload, question, *, reference_date=T2PC_REFERENCE_DATE):
    """T2PC 운영 경로 판정. 조건 계층을 켠 결과와, 비교를 위해 끈 결과의 의미 차이를 함께 돌려준다."""
    import json as _json
    if isinstance(payload, dict) and payload.get("unsupported"):
        return dict(parse_ok=True, outcome="unsupported", compose_ok=None, validation_ok=None, validation_codes=[],
                    error_code=None, compile_ok=None, compile_error_code=None, condition_actions={},
                    condition_changed_meaning=False, signature=None)
    text = _json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
    on = _planner_path(text, question, condition_check=True, reference_date=reference_date)
    off = _planner_path(text, question, condition_check=False, reference_date=reference_date)
    on["condition_changed_meaning"] = (on["signature"] is not None and off["signature"] is not None
                                       and on["signature"] != off["signature"])
    on["condition_changed_outcome"] = ((on["error_code"], on["outcome"]) != (off["error_code"], off["outcome"]))
    return on


def t2pc_chosen_ok(result):
    """T2PC 경로에서 grounding 계약(parse·compose·validate)을 통과했는가. compile 정지는 따로 본다."""
    return result["parse_ok"] and (result["outcome"] == "unsupported" or result["validation_ok"] is True)
