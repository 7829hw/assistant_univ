# -*- coding: utf-8 -*-
"""L1: H0 grounding 뒤에 집계 단계만 다시 묻는 국소 보정. 평가 전용.

전역 H2는 집계 표현을 바꾸려고 system prompt 전체를 바꿨고, 그 영향이 집계와 무관한
질의(날짜·dimension·taxi_type)까지 번졌다(20260925_011212_census_h2_production).
L1은 첫 grounding 호출을 production H0 그대로 두고, 그 결과의 **구조**가 구간 집계일
때만 두 번째 호출로 두 단계 reducer를 다시 정한다.

    H0 grounding (64bbceb4, 그대로)
        ↓ trigger: 읽어 낸 factor에 bucket이 있다 (질문 문자열은 보지 않는다)
    집계 전용 호출 → {"inner_reducer", "final_reducer"}
        ↓ AggregationStagePatch: aggregation·rollup만 바꾼다
    기존 flat factor → composer → operator → G1~G6 → compiler

trigger 조건에 rollup만 있는 경우를 넣지 않는다. bucket이 없으면 구간 안/구간별
단계가 없고, patch는 bucket을 만들 권한이 없으므로 고칠 수 있는 것이 없다.
그 경우는 H0 경로(기존 재질의 포함)를 그대로 탄다.
"""

import json
from dataclasses import dataclass

from geoflow.errors import PlannerError
from geoflow.factors import FACTOR_SPECS
from geoflow.grounding import Grounding

UNSPECIFIED = "unspecified"
#: patch가 바꿀 수 있는 factor. 이 밖은 전부 읽기 전용이다.
WRITABLE = ("aggregation", "rollup")
OUTPUT_KEYS = ("inner_reducer", "final_reducer")
#: 모델이 습관적으로 덧붙이는 설명 key. 값은 쓰지 않는다(Planner와 같은 목록).
IGNORABLE_KEYS = frozenset({"reason", "reasoning", "explanation", "note", "notes", "thought"})

# 보정 결과. 관측 기록과 분석이 이 이름을 쓴다.
NOT_TRIGGERED = "not_triggered"
APPLIED = "applied"
FALLBACK = "fallback"

# fallback 이유
REFINER_CALL_FAILED = "REFINER_CALL_FAILED"
REFINER_INVALID_JSON = "REFINER_INVALID_JSON"
REFINER_INVALID_OUTPUT = "REFINER_INVALID_OUTPUT"
PATCH_SCOPE_VIOLATION = "PATCH_SCOPE_VIOLATION"

#: 보정이 적용되면 그 관측의 재질의 1회 예산을 쓴 것으로 본다.
REPAIR_BUDGET_USED = "REPAIR_BUDGET_USED_BY_REFINEMENT"


def inner_reducers():
    return [*sorted(FACTOR_SPECS["aggregation"].values), UNSPECIFIED]


def final_reducers():
    return sorted(FACTOR_SPECS["rollup"].values)


def triggered(grounding):
    """H0 grounding의 구조만 본다. 구간 단위가 읽혔을 때만 보정한다."""
    return grounding is not None and "bucket" in grounding.factors


@dataclass(frozen=True)
class AggregationStagePatch:
    inner_reducer: str
    final_reducer: str

    def to_dict(self):
        return {"inner_reducer": self.inner_reducer, "final_reducer": self.final_reducer}


class RefinementError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def parse_patch(payload):
    if not isinstance(payload, dict):
        raise RefinementError(REFINER_INVALID_OUTPUT, "JSON 객체가 아니다")
    extra = sorted(set(payload) - set(OUTPUT_KEYS) - IGNORABLE_KEYS)
    missing = [key for key in OUTPUT_KEYS if key not in payload]
    if extra or missing:
        raise RefinementError(REFINER_INVALID_OUTPUT,
                              f"key가 맞지 않는다 (추가 {extra}, 누락 {missing})")
    inner, final = payload["inner_reducer"], payload["final_reducer"]
    if not isinstance(inner, str) or inner not in inner_reducers():
        raise RefinementError(REFINER_INVALID_OUTPUT, f"inner_reducer 값: {inner!r}")
    if not isinstance(final, str) or final not in final_reducers():
        raise RefinementError(REFINER_INVALID_OUTPUT, f"final_reducer 값: {final!r}")
    return AggregationStagePatch(inner_reducer=inner, final_reducer=final)


def apply_patch(grounding, patch):
    """aggregation·rollup만 바꾼 새 Grounding. 나머지는 같은 값·같은 순서로 둔다."""
    factors = dict(grounding.factors)
    if patch.inner_reducer == UNSPECIFIED:
        factors.pop("aggregation", None)
    else:
        factors["aggregation"] = FACTOR_SPECS["aggregation"].coerce(patch.inner_reducer)
    factors["rollup"] = FACTOR_SPECS["rollup"].coerce(patch.final_reducer)
    after = Grounding(question=grounding.question, concepts=list(grounding.concepts),
                      factors=factors)
    check_scope(grounding, after)
    return after


def check_scope(before, after):
    """patch가 쓸 수 있는 곳 밖을 바꿨으면 거부한다. apply_patch의 두 번째 방어선이다."""
    if json.dumps([c.to_dict() for c in before.concepts], ensure_ascii=False, default=str) != \
            json.dumps([c.to_dict() for c in after.concepts], ensure_ascii=False, default=str):
        raise RefinementError(PATCH_SCOPE_VIOLATION, "개념이 바뀌었다")
    frozen_before = {k: v for k, v in before.factors.items() if k not in WRITABLE}
    frozen_after = {k: v for k, v in after.factors.items() if k not in WRITABLE}
    if frozen_before != frozen_after or list(frozen_before) != list(frozen_after):
        raise RefinementError(PATCH_SCOPE_VIOLATION,
                              f"읽기 전용 factor가 바뀌었다: {frozen_before} → {frozen_after}")
    if "bucket" not in after.factors:
        raise RefinementError(PATCH_SCOPE_VIOLATION, "bucket이 사라졌다")


# -- 집계 전용 호출 ---------------------------------------------------------

#: 한 번 쓰고 고정한다. 허용값 자리만 FACTOR_SPECS에서 채운다. 알려진 실패 질문을
#: 예시로 넣지 않고, 틀린 형태도 보여 주지 않는다.
_SYSTEM = """너는 질문 하나의 집계 단계만 정한다. 다른 것은 정하지 않는다.

질문은 분석 기간을 구간({units})으로 나눠 값을 구한다. 값은 두 단계로 모인다.

    원시 값 --inner_reducer--> 구간별 값 --final_reducer--> 최종 값

- inner_reducer: 각 구간 안의 원시 값을 하나로 모으는 방식이다. 질문이 구간 안에서
  값을 어떻게 모으는지 따로 말하지 않으면 unspecified로 적는다.
- final_reducer: 구간별 값들을 마지막에 하나로 합치는 방식이다. 질문이 최종적으로
  구하는 값이 이것이다.

허용값:
- inner_reducer: {inner}
- final_reducer: {final}

입력에는 질문과, 앞 단계가 읽은 구간 단위와 집계 값이 있다. 앞 단계의 집계 값은
참고일 뿐이다. 두 값은 질문에서 정한다.

출력은 JSON 객체 하나다.

    {"inner_reducer": "<inner_reducer>", "final_reducer": "<final_reducer>"}"""

_USER = """질문: {question}
구간 단위: {bucket}
앞 단계의 aggregation: {aggregation}
앞 단계의 rollup: {rollup}"""


def _fill(template, values):
    for name, value in values.items():
        template = template.replace("{" + name + "}", value)
    return template


def system_prompt():
    return _fill(_SYSTEM, {
        "units": ", ".join(sorted(FACTOR_SPECS["bucket"].values)),
        "inner": " | ".join(inner_reducers()),
        "final": " | ".join(final_reducers()),
    })


def user_message(question, grounding):
    factors = grounding.factors
    return _fill(_USER, {
        "question": question,
        "bucket": str(factors["bucket"]),
        "aggregation": str(factors.get("aggregation", "(없음)")),
        "rollup": str(factors.get("rollup", "(없음)")),
    })


def messages(question, grounding, prompt=None):
    return [{"role": "system", "content": prompt if prompt is not None else system_prompt()},
            {"role": "user", "content": user_message(question, grounding)}]


def refine(call, question, grounding, *, parse_json, prompt=None):
    """보정 한 번. 결과 dict와 (적용됐다면) 새 grounding을 돌려준다.

    ``call(messages) -> text``는 Planner의 호출 경로(재시도 규칙 포함)다. 실패하면
    예외를 밖으로 내지 않고 fallback으로 기록한다. 부서진 보정 때문에 H0보다
    나빠지지 않게 하기 위해서다.
    """
    result = {"outcome": FALLBACK, "reason": None, "patch": None, "raw_text": None,
              "factors_before": dict(grounding.factors), "factors_after": None}
    try:
        text = call(messages(question, grounding, prompt))
    except PlannerError as error:
        result["reason"] = REFINER_CALL_FAILED
        result["detail"] = error.code
        return result, None
    result["raw_text"] = text
    try:
        payload = parse_json(text)
    except PlannerError as error:
        result["reason"] = REFINER_INVALID_JSON
        result["detail"] = error.code
        return result, None
    try:
        patch = parse_patch(payload)
        after = apply_patch(grounding, patch)
    except RefinementError as error:
        result["reason"] = error.code
        result["detail"] = error.detail
        return result, None
    except PlannerError as error:
        result["reason"] = REFINER_INVALID_OUTPUT
        result["detail"] = error.detail
        return result, None
    result.update(outcome=APPLIED, patch=patch.to_dict(), factors_after=dict(after.factors))
    return result, after
