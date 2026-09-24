# -*- coding: utf-8 -*-
"""집계 단계의 grounding 표현(``aggregation_plan``)과 결정적 lowering.

Planner LLM은 집계를 flat factor 셋(``bucket``·``aggregation``·``rollup``)으로
적지 않고 ``aggregation_plan`` 하나로 적는다.

    "aggregation_plan": {
      "bucket": {"unit": "month", "reducer": "sum"},   # 구간 표현이 있을 때만
      "result": {"reducer": "avg"}
    }

flat 표현에서는 최종 집계를 적는 자리가 bucket 유무에 따라 바뀌었다(bucket이
없으면 aggregation, 있으면 rollup). 실측에서 모델은 bucket이 있을 때도 최종
집계를 aggregation에 적었다. 여기서는 최종 집계가 늘 ``result.reducer``이고,
구간 안 집계는 ``bucket.reducer``에 따로 적는다. 질문이 구간 안 집계를 말하지
않으면 ``unspecified``다. ``unspecified``는 avg가 아니다. 질문에 없다는 뜻이며,
lowering에서 aggregation을 생략해 Tool 기본값이 적용될 뿐이다.
근거: evaluation/prompt_ab/20260924_032103_aggregation_holdout_h0_h2_r2

이 표현은 grounding 경계에만 있다. ``lower_raw_grounding``이 LLM 호출 없이 flat
factor로 내리고, 그 뒤(``parse_grounding``, composer, operator, validator,
compiler, executor)는 flat factor만 본다. 재질의도 lowering된 flat factor를
대상으로 한다.

허용값은 ``FACTOR_SPECS``의 bucket·aggregation·rollup에서 읽는다. 여기에 값을
다시 적지 않는다.
"""

from dataclasses import dataclass

from geoflow.errors import PlannerError
from geoflow.factors import FACTOR_SPECS

PLAN_KEY = "aggregation_plan"

#: 질문이 구간 안 집계를 말하지 않았다는 표시. grounding에만 있고 Tool에는 가지 않는다.
UNSPECIFIED = "unspecified"

#: lowering이 만드는 내부 factor. raw grounding 어휘에는 없다.
LOWERED_FACTORS = ("bucket", "aggregation", "rollup")

#: aggregation_plan과 flat 집계 factor를 함께 적었다. 어느 쪽도 고르지 않는다.
DUPLICATE_AGGREGATION_SOURCE = "DUPLICATE_AGGREGATION_SOURCE"
#: flat 집계 factor만 적었다. raw grounding 계약에서는 쓸 수 없다.
FLAT_AGGREGATION_FACTOR = "FLAT_AGGREGATION_FACTOR"
#: aggregation_plan의 구조나 값이 올바르지 않다.
INVALID_AGGREGATION_PLAN = "INVALID_AGGREGATION_PLAN"

AGGREGATION_PLAN_CODES = frozenset({
    DUPLICATE_AGGREGATION_SOURCE, FLAT_AGGREGATION_FACTOR, INVALID_AGGREGATION_PLAN,
})


def bucket_units():
    return FACTOR_SPECS["bucket"].values


def bucket_reducers():
    """구간 안 집계. lowering하면 aggregation이 된다."""
    return FACTOR_SPECS["aggregation"].values | {UNSPECIFIED}


def result_reducers():
    """최종 집계. bucket이 없으면 aggregation, 있으면 rollup이 되므로 둘 다 받는 값."""
    return FACTOR_SPECS["aggregation"].values & FACTOR_SPECS["rollup"].values


@dataclass(frozen=True)
class AggregationBucket:
    unit: str
    #: ``UNSPECIFIED``일 수 있다.
    reducer: str

    def to_dict(self):
        return {"unit": self.unit, "reducer": self.reducer}


@dataclass(frozen=True)
class AggregationPlan:
    """질문의 집계. 최종 집계는 bucket 유무와 관계없이 ``result_reducer``다."""

    result_reducer: str
    bucket: AggregationBucket | None = None

    def to_dict(self):
        """raw grounding 모양. ``unspecified``를 그대로 남긴다."""
        plan = {"result": {"reducer": self.result_reducer}}
        if self.bucket is not None:
            plan = {"bucket": self.bucket.to_dict(), **plan}
        return plan

    def lower(self):
        """내부 flat factor. ``unspecified``인 구간 안 집계는 적지 않는다."""
        if self.bucket is None:
            return {"aggregation": self.result_reducer}
        flat = {"bucket": self.bucket.unit, "rollup": self.result_reducer}
        if self.bucket.reducer != UNSPECIFIED:
            flat["aggregation"] = self.bucket.reducer
        return flat


def _invalid(field, problem, value, raw_text):
    return PlannerError(
        f"집계 계획을 읽을 수 없습니다: {field} {problem}",
        code=INVALID_AGGREGATION_PLAN,
        context={"raw_text": raw_text, "field": field, "problem": problem,
                 "value": value},
    )


def _choice(value, allowed):
    return isinstance(value, str) and value in allowed


def parse_aggregation_plan(raw, *, raw_text=""):
    """raw ``aggregation_plan``을 ``AggregationPlan``으로 읽는다. 질문 문자열은 보지 않는다."""
    if not isinstance(raw, dict):
        raise _invalid(PLAN_KEY, "은 객체여야 합니다", raw, raw_text)
    unknown = sorted(set(raw) - {"bucket", "result"})
    if unknown:
        raise _invalid(PLAN_KEY, f"에 모르는 key가 있습니다: {', '.join(unknown)}",
                       unknown, raw_text)
    result = raw.get("result")
    if not isinstance(result, dict) or set(result) != {"reducer"}:
        raise _invalid("result", "에는 reducer 하나만 적습니다", result, raw_text)
    if not _choice(result["reducer"], result_reducers()):
        raise _invalid("result.reducer",
                       f"는 {' | '.join(sorted(result_reducers()))} 중 하나입니다",
                       result["reducer"], raw_text)
    if "bucket" not in raw:
        return AggregationPlan(result_reducer=result["reducer"])
    bucket = raw["bucket"]
    if not isinstance(bucket, dict) or set(bucket) != {"unit", "reducer"}:
        raise _invalid("bucket", "에는 unit과 reducer를 모두 적습니다", bucket, raw_text)
    if not _choice(bucket["unit"], bucket_units()):
        raise _invalid("bucket.unit", f"는 {' | '.join(sorted(bucket_units()))} 중 하나입니다",
                       bucket["unit"], raw_text)
    if not _choice(bucket["reducer"], bucket_reducers()):
        raise _invalid("bucket.reducer",
                       f"는 {' | '.join(_bucket_reducer_choices())} 중 하나입니다",
                       bucket["reducer"], raw_text)
    return AggregationPlan(
        result_reducer=result["reducer"],
        bucket=AggregationBucket(unit=bucket["unit"], reducer=bucket["reducer"]),
    )


def lower_raw_grounding(payload, *, raw_text=""):
    """raw grounding payload의 ``aggregation_plan``을 flat factor로 내린다.

    원본은 건드리지 않는다. 다른 factor는 순서까지 그대로 두고 lowering한 factor를
    뒤에 붙인다. raw 어휘와 내부 어휘는 겹치지 않으므로, 이미 내린 payload를 다시
    넣으면 flat factor로 보고 거부한다(두 번 내리는 경로는 없다).

    ``aggregation_plan``만 집계의 출처다. flat 집계 factor가 있으면 어느 쪽을
    믿을지 정하지 않고 거부한다.
    """
    if not isinstance(payload, dict) or payload.get("unsupported"):
        return payload
    factors = payload.get("factors")
    if not isinstance(factors, dict):
        return payload
    flat = [key for key in LOWERED_FACTORS if key in factors]
    if flat and PLAN_KEY in factors:
        raise PlannerError(
            f"집계 계획을 읽을 수 없습니다: aggregation_plan과 {', '.join(flat)}을 "
            "함께 적었습니다",
            code=DUPLICATE_AGGREGATION_SOURCE,
            context={"raw_text": raw_text, "flat_factors": flat},
        )
    if flat:
        raise PlannerError(
            f"집계 계획을 읽을 수 없습니다: 집계는 aggregation_plan에 적습니다 "
            f"({', '.join(flat)})",
            code=FLAT_AGGREGATION_FACTOR,
            context={"raw_text": raw_text, "flat_factors": flat},
        )
    if PLAN_KEY not in factors:
        return payload
    plan = parse_aggregation_plan(factors[PLAN_KEY], raw_text=raw_text)
    lowered = {key: value for key, value in factors.items() if key != PLAN_KEY}
    lowered.update(plan.lower())
    return {**payload, "factors": lowered}


# -- Prompt ----------------------------------------------------------------

PLAN_HEADING = "[집계 계획]"
#: [사용 가능한 factor]와 [조건이 뜻하는 것]에서 aggregation_plan의 값 형식 자리.
PLAN_SHAPE = f"아래 {PLAN_HEADING}의 형식"

#: 문구는 H2 측정(04d7baed) 그대로다. 허용값 자리만 FACTOR_SPECS에서 채운다.
_PLAN_MEANING = "질문의 집계 방식. 구간 단위는 {units}이며, 자료가 일 단위이므로 day는 없다."

_PLAN_CONTRACT = '''{heading}
집계 방식은 factors의 {key} 하나에 적는다.

    "{key}": {
      "bucket": {"unit": "<{units}>", "reducer": "<{bucket_reducers}>"},
      "result": {"reducer": "<{result_reducers}>"}
    }

    원시 값 --bucket.reducer--> 구간별 값 --result.reducer--> 최종 값   (구간이 있을 때)
    원시 값 --result.reducer--> 최종 값                                  (구간이 없을 때)

- result.reducer는 질문이 최종적으로 구하는 값의 집계 방식이다. 구간이 있든
  없든 최종 집계는 늘 result.reducer에 적는다.
- bucket은 질문에 "주 단위로", "월 단위로" 같은 구간 표현이 있을 때 넣는다.
  - unit은 구간 단위다.
  - reducer는 각 구간 안의 값을 먼저 하나로 모으는 방식이다. 질문이 구간
    안의 집계를 따로 말하지 않으면 {unspecified}로 적는다.
  - bucket을 넣으면 result도 함께 넣는다.
- 질문에 집계 표현이 없으면 {key}을 넣지 않는다.
  - "월 단위로 나눈 영업시간의 합은?" → bucket.unit=month, bucket.reducer={unspecified}, result.reducer=sum
  - "평균 영업시간은?" → result.reducer=avg (bucket은 넣지 않는다)'''

#: raw 어휘에서 내부 factor를 부르는 이름. FactorSpec.meaning의 {factor} 참조를 채운다.
GROUNDING_REFERENCES = {"bucket": f"{PLAN_KEY}의 bucket"}


def _bucket_reducer_choices():
    return [*sorted(bucket_reducers() - {UNSPECIFIED}), UNSPECIFIED]


def _fill(template, values):
    # JSON 예시의 중괄호가 있어 str.format을 쓰지 않는다.
    for name, value in values.items():
        template = template.replace("{" + name + "}", value)
    return template


def _values():
    return {
        "heading": PLAN_HEADING,
        "key": PLAN_KEY,
        "units": " | ".join(sorted(bucket_units())),
        "bucket_reducers": " | ".join(_bucket_reducer_choices()),
        "result_reducers": " | ".join(sorted(result_reducers())),
        "unspecified": UNSPECIFIED,
    }


def describe_plan_meaning():
    return _fill(_PLAN_MEANING, _values())


def describe_aggregation_contract():
    """system prompt의 [집계 계획] 절."""
    return _fill(_PLAN_CONTRACT, _values())


def grounding_factor_names():
    """LLM이 factors에 적을 수 있는 이름. 내부 집계 factor 대신 aggregation_plan이 있다."""
    return sorted((set(FACTOR_SPECS) - set(LOWERED_FACTORS)) | {PLAN_KEY})
