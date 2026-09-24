# -*- coding: utf-8 -*-
"""두 단계 집계: 의미 golden과 채점. 평가 전용.

H2 표현의 parser와 lowering은 production(``geoflow.aggregation``)이 갖고, 여기서는
그것을 그대로 부른다. 평가와 제품이 같은 코드로 내린다.

이전 grounding 계약(H0)은 flat factor 셋으로 집계를 적었다.

    bucket 없음: aggregation = 최종 집계
    bucket 있음: aggregation = 구간 안 집계, rollup = 최종 집계

최종 집계를 적는 자리가 bucket 유무에 따라 바뀐다. H2는 최종 집계를 늘
``result.reducer``에 적고, 구간 안 집계는 ``bucket.reducer``에 따로 적는다.
질문이 구간 안 집계를 말하지 않으면 ``unspecified``다.

    "aggregation_plan": {
      "bucket": {"unit": "month", "reducer": "sum"},   # 구간 표현이 있을 때만
      "result": {"reducer": "avg"}
    }

H2는 grounding 층의 표현이다. ``lower_payload``가 LLM을 부르지 않고 flat factor로
바꾸고, 그 뒤는 제품 경로(parse_grounding → composer → operator → G1~G6 → compiler
→ executor)를 그대로 탄다.

corpus의 의미 golden은 한 곳에만 적는다.

    aggregation: {final: avg}
    aggregation: {bucket: month, inner: sum, final: avg}
    aggregation: {bucket: month, inner: unspecified, final: sum}

H0 golden, H2 golden, 기대 Tool 인자는 모두 여기서 유도한다.
"""

from geoflow import aggregation as GA
from geoflow.errors import PlannerError

REDUCERS = tuple(sorted(GA.result_reducers()))
UNSPECIFIED = GA.UNSPECIFIED
UNITS = tuple(sorted(GA.bucket_units()))
FLAT_KEYS = GA.LOWERED_FACTORS
PLAN_KEY = GA.PLAN_KEY

#: grounding을 거부하는 이유. 제품 code와 같다.
DUPLICATE_AGGREGATION_SOURCE = GA.DUPLICATE_AGGREGATION_SOURCE
FLAT_AGGREGATION_FACTOR = GA.FLAT_AGGREGATION_FACTOR
#: H2 측정(c8ef8ab) 때 이름은 LOWERING_ERROR였다. 그 run에는 이 code가 없다.
LOWERING_ERROR = GA.INVALID_AGGREGATION_PLAN


class PlanError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


# -- 의미 golden -----------------------------------------------------------


def semantic_problems(semantic):
    """의미 golden 하나가 올바른지. 없으면(None) 집계가 없는 질의다."""
    if semantic is None:
        return []
    if not isinstance(semantic, dict):
        return ["aggregation은 mapping이어야 한다"]
    problems = []
    unknown = set(semantic) - {"bucket", "inner", "final"}
    if unknown:
        problems.append(f"모르는 key {sorted(unknown)}")
    if semantic.get("final") not in REDUCERS:
        problems.append(f"final은 {REDUCERS} 중 하나여야 한다")
    if "bucket" in semantic:
        if semantic["bucket"] not in UNITS:
            problems.append(f"bucket은 {UNITS} 중 하나여야 한다")
        if semantic.get("inner") not in (*REDUCERS, UNSPECIFIED):
            problems.append("bucket이 있으면 inner를 적는다 (질문에 없으면 unspecified)")
    elif "inner" in semantic:
        problems.append("bucket이 없으면 inner를 적지 않는다")
    return problems


def semantic_to_flat(semantic):
    """H0 grounding의 flat factor."""
    if semantic is None:
        return {}
    if "bucket" not in semantic:
        return {"aggregation": semantic["final"]}
    flat = {"bucket": semantic["bucket"], "rollup": semantic["final"]}
    if semantic["inner"] != UNSPECIFIED:
        flat["aggregation"] = semantic["inner"]
    return flat


def semantic_to_plan(semantic):
    """H2 grounding의 aggregation_plan."""
    if semantic is None:
        return None
    plan = {"result": {"reducer": semantic["final"]}}
    if "bucket" in semantic:
        plan = {"bucket": {"unit": semantic["bucket"], "reducer": semantic["inner"]}, **plan}
    return plan


def expected_tool_args(semantic):
    """집계 관련 기대 Tool 인자. None은 "없어야 한다(또는 schema 기본값)"다.

    구간 안 집계가 unspecified면 aggregation을 기대하지 않는다. Tool 기본값(avg)과
    같은 값은 채점에서 생략과 같게 본다.
    """
    if semantic is None:
        return {"bucket": None, "rollup": None}
    if "bucket" not in semantic:
        return {"aggregation": semantic["final"], "bucket": None, "rollup": None}
    inner = semantic["inner"]
    return {"bucket": semantic["bucket"],
            "aggregation": None if inner == UNSPECIFIED else inner,
            "rollup": semantic["final"]}


# -- H2 lowering (제품 코드) -----------------------------------------------


def lower_plan(plan):
    """aggregation_plan → flat factor. 형식이 어긋나면 PlanError."""
    try:
        return GA.parse_aggregation_plan(plan).lower()
    except PlannerError as error:
        raise PlanError(error.code, error.detail) from error


def lower_payload(payload):
    """H2 grounding payload를 flat factor 모양으로 바꾼다. 원본은 건드리지 않는다."""
    try:
        return GA.lower_raw_grounding(payload)
    except PlannerError as error:
        raise PlanError(error.code, error.detail) from error


def raw_grounding(payload):
    """flat 집계로 적은 내부 grounding(corpus golden)을 raw grounding 모양으로 바꾼다.

    golden을 모델 응답으로 흉내 낼 때 쓴다. lowering하면 원래 golden으로 돌아온다.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("factors"), dict):
        return payload
    factors = payload["factors"]
    if not any(key in factors for key in FLAT_KEYS):
        return payload
    raw = {key: value for key, value in factors.items() if key not in FLAT_KEYS}
    raw[PLAN_KEY] = semantic_to_plan(flat_to_semantic(factors))
    return {**payload, "factors": raw}


# -- 채점 ------------------------------------------------------------------


def flat_to_semantic(factors):
    """H0 출력을 의미 표현으로 읽는다. 채점에만 쓴다."""
    factors = factors or {}
    if "bucket" in factors:
        return {"bucket": factors["bucket"],
                "inner": factors.get("aggregation", UNSPECIFIED),
                "final": factors.get("rollup")}
    if "aggregation" in factors or "rollup" in factors:
        return {"final": factors.get("aggregation"), "orphan_rollup": factors.get("rollup")}
    return None


def plan_to_semantic(plan):
    """H2 출력을 의미 표현으로 읽는다. 형식이 틀려도 읽을 수 있는 만큼 읽는다."""
    if not isinstance(plan, dict):
        return None
    result = plan.get("result") if isinstance(plan.get("result"), dict) else {}
    semantic = {"final": result.get("reducer")}
    bucket = plan.get("bucket")
    if isinstance(bucket, dict):
        semantic.update(bucket=bucket.get("unit"), inner=bucket.get("reducer", UNSPECIFIED))
    return semantic


INNER_REDUCER_OMITTED = "INNER_REDUCER_OMITTED_OR_UNSPECIFIED"
INNER_REDUCER_INVENTED = "INNER_REDUCER_INVENTED"
INNER_REDUCER_WRONG = "INNER_REDUCER_WRONG"
FINAL_REDUCER_WRONG = "FINAL_REDUCER_WRONG"
STAGE_SWAPPED = "STAGE_SWAPPED"
BUCKET_WRONG = "BUCKET_WRONG"


def aggregation_errors(predicted, golden):
    """예측한 집계 의미가 golden과 어떻게 다른지. 같으면 빈 목록이다.

    구간 안 집계가 unspecified인데 avg를 적은 것은 실행 의미가 같다(Tool 기본값).
    """
    errors = []
    gold_bucket = (golden or {}).get("bucket")
    pred_bucket = (predicted or {}).get("bucket")
    if gold_bucket != pred_bucket:
        errors.append(BUCKET_WRONG)
    gold_final = (golden or {}).get("final")
    pred_final = (predicted or {}).get("final")
    if gold_bucket and pred_bucket:
        gold_inner, pred_inner = golden["inner"], predicted.get("inner", UNSPECIFIED)
        swapped = (pred_final != gold_final and pred_inner == gold_final
                   and gold_inner != gold_final)
        if swapped:
            errors.append(STAGE_SWAPPED)
        elif gold_inner == UNSPECIFIED:
            if pred_inner not in (UNSPECIFIED, "avg"):
                errors.append(INNER_REDUCER_INVENTED)
        elif pred_inner == UNSPECIFIED:
            if gold_inner != "avg":
                errors.append(INNER_REDUCER_OMITTED)
        elif pred_inner != gold_inner:
            errors.append(INNER_REDUCER_WRONG)
        if pred_final != gold_final and not swapped:
            errors.append(FINAL_REDUCER_WRONG)
    elif pred_final != gold_final and not (gold_final is None and pred_final is None):
        errors.append(FINAL_REDUCER_WRONG)
    return errors


def explicit_inner_left_unspecified(predicted, golden):
    """질문이 구간 안 집계를 말했는데 unspecified로 둔 경우. avg여도 센다."""
    return bool(golden and golden.get("bucket") and golden["inner"] != UNSPECIFIED
                and predicted and predicted.get("bucket")
                and predicted.get("inner", UNSPECIFIED) == UNSPECIFIED)
