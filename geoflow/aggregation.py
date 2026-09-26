# -*- coding: utf-8 -*-
"""집계의 의미 표현(``AggregationSpec``).

집계를 Tool 인자(aggregation·bucket·rollup)가 아니라 계산 단계로 적는다.

    원시 값 --inner--> (구간별 값) --outer--> 최종 값
                                  --select--> 최종 구간(과 그 값)

- ``bucket``: 그룹 키. 시간 구간(week, month)이다. 없으면 한 단계 집계다.
- ``inner``: 원시 값에 적용하는 집계. bucket이 있으면 **각 구간 안에서** 적용된다.
- ``outer``: 구간별 값들을 하나의 값으로 합치는 집계.
- ``select``: 구간별 값 중 가장 큰(max)/작은(min) **구간**을 고른다. 답은 값이
  아니라 구간이다. "매출 합계가 가장 큰 주"가 여기에 해당한다.

같은 "지난달 매출"에서 네 질문이 서로 다른 spec이 된다.

    주별 합계의 평균       bucket=week, inner=sum, outer=avg
    주별 평균의 최댓값     bucket=week, inner=avg, outer=max
    전체 매출의 평균       inner=avg
    합계가 가장 큰 주      bucket=week, inner=sum, select=max

spec은 두 경로로 만들어진다.

1. production grounding(H0)의 flat factor에서 결정적으로 올린다(``from_flat``).
   flat 표현은 select를 표현할 수 없다.
2. 구조화 표기 ``factors.aggregation_plan``을 읽는다(``parse_plan``). H2 실험의
   형태에 ``result.select``를 더한 것이다. production prompt는 이 표기를 안내하지
   않는다. prompt를 바꾸려면 격리 측정이 먼저다(evaluation/design/
   aggregation_stage_grounding.md 8절).

bucket이 있는데 구간 안 집계가 질문에 없으면 ``UNSPECIFIED``다. 이것을 Tool 기본값
(avg)으로 내려 보내지 않는다. 합성 단계가 구조화된 실패로 바꾼다.
"""

from dataclasses import dataclass

from geoflow.errors import PlannerError
from geoflow.factors import FACTOR_SPECS

REDUCERS = FACTOR_SPECS["aggregation"].values
BUCKET_UNITS = FACTOR_SPECS["bucket"].values
SELECTIONS = frozenset({"max", "min"})
UNSPECIFIED = "unspecified"

#: 구조화 표기의 factor key.
PLAN_KEY = "aggregation_plan"
#: flat 표기의 집계 factor. 구조화 표기와 함께 쓰면 거부한다.
FLAT_KEYS = ("bucket", "aggregation", "rollup")

SOURCE_FLAT = "flat"
SOURCE_STRUCTURED = "structured"
SOURCE_BOTH = "structured+flat"

#: 사람이 읽는 이름. 답변이 쓴다.
REDUCER_LABELS = {
    "avg": "평균", "max": "최댓값", "min": "최솟값", "sum": "합계", "med": "중간값",
}
SELECT_LABELS = {"max": "가장 큰", "min": "가장 작은"}
BUCKET_LABELS = {"week": "주", "month": "월"}


@dataclass(frozen=True)
class AggregationSpec:
    """질문이 요구하는 집계 단계. Tool 인자와 무관하다."""

    bucket: str | None = None
    inner: str | None = None
    outer: str | None = None
    select: str | None = None
    source: str = SOURCE_FLAT

    @property
    def grouped(self):
        return self.bucket is not None

    @property
    def inner_specified(self):
        return self.inner not in (None, UNSPECIFIED)

    def to_dict(self):
        return {
            "bucket": self.bucket,
            "inner": self.inner,
            "outer": self.outer,
            "select": self.select,
            "source": self.source,
        }


def from_flat(factors):
    """H0 flat factor를 spec으로 올린다. LLM을 부르지 않는다.

    flat 표기에서 aggregation은 bucket 유무에 따라 다른 단계를 뜻한다.

        bucket 없음: aggregation = 최종 집계
        bucket 있음: aggregation = 구간 안 집계, rollup = 구간별 값의 집계

    bucket이 있고 aggregation이 없으면 구간 안 집계는 ``UNSPECIFIED``다. 짝 규칙
    (bucket↔rollup) 위반은 ``validate_factors``가 먼저 거부하므로 여기서 보지 않는다.
    """
    factors = factors or {}
    bucket = factors.get("bucket")
    if bucket is None:
        return AggregationSpec(inner=factors.get("aggregation"))
    return AggregationSpec(
        bucket=bucket,
        inner=factors.get("aggregation") or UNSPECIFIED,
        outer=factors.get("rollup"),
    )


def _plan_error(message, raw_text, **context):
    return PlannerError(
        f"aggregation_plan: {message}",
        user_message="질문의 집계 방식을 해석하지 못했습니다.",
        code="INVALID_AGGREGATION_PLAN",
        context={"raw_text": raw_text, **context},
    )


def parse_plan(raw, *, raw_text=""):
    """구조화 표기를 spec으로 읽는다.

        {"result": {"reducer": "avg"}}
        {"bucket": {"unit": "week", "reducer": "sum"}, "result": {"reducer": "avg"}}
        {"bucket": {"unit": "week", "reducer": "sum"}, "result": {"select": "max"}}

    bucket이 없으면 result.reducer가 곧 원시 값의 집계다. bucket이 있으면
    bucket.reducer(질문에 없으면 "unspecified")가 구간 안 집계이고, result는
    reducer와 select 중 정확히 하나다.
    """
    if not isinstance(raw, dict):
        raise _plan_error("object여야 합니다.", raw_text)
    unknown = sorted(set(raw) - {"bucket", "result"})
    if unknown:
        raise _plan_error(f"허용되지 않은 key: {', '.join(unknown)}", raw_text)
    result = raw.get("result")
    if not isinstance(result, dict):
        raise _plan_error("result object가 필요합니다.", raw_text)
    unknown = sorted(set(result) - {"reducer", "select"})
    if unknown:
        raise _plan_error(
            f"result에 허용되지 않은 key: {', '.join(unknown)}", raw_text,
        )
    reducer = result.get("reducer")
    select = result.get("select")
    if reducer is not None and reducer not in REDUCERS:
        raise _plan_error(f"result.reducer가 올바르지 않습니다: {reducer!r}",
                          raw_text)
    if select is not None and select not in SELECTIONS:
        raise _plan_error(f"result.select가 올바르지 않습니다: {select!r}",
                          raw_text)
    if (reducer is None) == (select is None):
        raise _plan_error("result에는 reducer와 select 중 하나만 적습니다.",
                          raw_text)

    bucket = raw.get("bucket")
    if bucket is None:
        if select is not None:
            # 구간이 없으면 고를 구간도 없다.
            raise _plan_error("select는 bucket과 함께만 쓸 수 있습니다.", raw_text)
        return AggregationSpec(inner=reducer, source=SOURCE_STRUCTURED)

    if not isinstance(bucket, dict):
        raise _plan_error("bucket은 object여야 합니다.", raw_text)
    unknown = sorted(set(bucket) - {"unit", "reducer"})
    if unknown:
        raise _plan_error(
            f"bucket에 허용되지 않은 key: {', '.join(unknown)}", raw_text,
        )
    unit = bucket.get("unit")
    if unit not in BUCKET_UNITS:
        raise _plan_error(f"bucket.unit이 올바르지 않습니다: {unit!r}", raw_text)
    inner = bucket.get("reducer")
    if inner not in (*REDUCERS, UNSPECIFIED):
        raise _plan_error(
            f"bucket.reducer는 {', '.join(sorted(REDUCERS))} 또는 "
            f"{UNSPECIFIED}여야 합니다. (받은 값: {inner!r})",
            raw_text,
        )
    return AggregationSpec(
        bucket=unit, inner=inner, outer=reducer, select=select,
        source=SOURCE_STRUCTURED,
    )


def split_plan(raw_factors, *, raw_text=""):
    """factor 원문에서 구조화 표기를 떼어 낸다. ``(나머지 factor, spec 또는 None)``.

    flat 집계 factor가 함께 오면 두 표현의 뜻이 같은지 본다. 같으면 받아들이고
    (source="structured+flat"), 다르면 어느 쪽이 질문의 뜻인지 고르지 않고 거부한다.
    flat 쪽 값은 나머지 factor에 그대로 남겨 기록과 재질의가 읽을 수 있게 한다.
    """
    if not isinstance(raw_factors, dict) or PLAN_KEY not in raw_factors:
        return raw_factors, None
    rest = {key: value for key, value in raw_factors.items() if key != PLAN_KEY}
    structured = parse_plan(raw_factors[PLAN_KEY], raw_text=raw_text)
    flat_keys = [key for key in FLAT_KEYS if rest.get(key) not in (None, "")]
    if not flat_keys:
        return rest, structured
    flat = from_flat({key: rest[key] for key in flat_keys})
    if not _same_meaning(structured, flat):
        raise PlannerError(
            "aggregation_plan과 flat 집계 factor의 뜻이 다릅니다: "
            f"구조화={structured.to_dict()}, flat={flat.to_dict()}",
            user_message="질문의 집계 방식을 해석하지 못했습니다.",
            code="AGGREGATION_SOURCE_CONFLICT",
            context={"raw_text": raw_text, "structured": structured.to_dict(),
                     "flat": flat.to_dict(), "flat_keys": flat_keys},
        )
    return rest, AggregationSpec(
        bucket=structured.bucket, inner=structured.inner, outer=structured.outer,
        select=structured.select, source=SOURCE_BOTH,
    )


def _same_meaning(structured, flat):
    """두 표현이 같은 계산을 뜻하는가. flat은 구간 선택(select)을 표현할 수 없다."""
    if structured.select is not None:
        return False
    return (structured.bucket, structured.inner, structured.outer) == (
        flat.bucket, flat.inner, flat.outer)
