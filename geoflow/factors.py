# -*- coding: utf-8 -*-
"""Factor 어휘와 factor 불변식.

Factor는 개념이 아니라 분석을 한정하는 조건이다. 날짜, 시간, 집계 방식,
그룹화 기준 같은 것들이다.

이 모듈은 두 가지를 갖는다.

1. **어휘**(``FACTOR_SPECS``) — 어떤 factor 이름이 있고 각 값이 어떤 형식인가
2. **불변식**(``FACTOR_CONSTRAINTS``) — 어떤 factor가 다른 factor 없이는
   성립하지 않는가

둘 다 특정 Tool이나 질문 유형에 속하지 않는다. "주 단위로 1차 집계한다"는
말은 합치는 방법이 있어야 뜻이 통하고, "가장 많은 3곳"은 무엇으로 나눈
3곳인지가 있어야 뜻이 통한다. 어떤 operator가 그 조건을 소비하든 참이다.
그래서 예전처럼 template YAML의 ``slot_requires``나 operator마다 중복
선언하지 않고 여기 한 곳에만 둔다.

반면 "dimension에 어떤 값을 넣을 수 있는가"는 Tool마다 다르므로
``OperatorSpec.param_enums``가 갖는다. 이 모듈은 값의 형식만 보고,
그 Tool이 그 값을 받는지는 보지 않는다.

이 모듈은 ``geoflow.errors``와 표준 라이브러리 외에는 의존하지 않는다.
grounding과 operator registry가 모두 여기에 기대기 때문이다.
"""

import re
from dataclasses import dataclass
from typing import Any

from geoflow.errors import PlannerError

_AGGREGATIONS = frozenset({"max", "min", "sum", "avg", "med"})
_DATE_PATTERN = re.compile(
    r"^(\d{8}(-\d{8})?|last_week|last_month|last_year"
    r"|weekday|weekend|holiday)$"
)
_TIME_PATTERN = re.compile(r"^\d{6}-\d{6}$")


@dataclass(frozen=True)
class FactorSpec:
    """factor 하나의 형식.

    Tool별로 어떤 factor를 받는지는 operator registry가 정한다. 여기서는
    "이 값이 그 factor로 말이 되는가"만 본다.
    """

    name: str
    kind: str = "text"
    values: frozenset[str] = frozenset()
    pattern: Any = None
    #: 이 조건이 무엇을 정하는지. Prompt 설명의 단일 기준이다. 같은 설명을
    #: Prompt에 손으로 적어 두면 어휘가 바뀔 때 조용히 어긋난다.
    meaning: str = ""

    def coerce(self, value):
        if self.kind == "boolean":
            if not isinstance(value, bool):
                raise PlannerError(
                    f"factor {self.name}은 true/false여야 합니다. "
                    f"(받은 값: {value!r})",
                    code="INVALID_FACTOR",
                )
            return value
        if self.kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise PlannerError(
                    f"factor {self.name}은 정수여야 합니다. (받은 값: {value!r})",
                    code="INVALID_FACTOR",
                )
            return value
        if not isinstance(value, str) or not value.strip():
            raise PlannerError(
                f"factor {self.name}은 비어 있지 않은 문자열이어야 합니다. "
                f"(받은 값: {value!r})",
                code="INVALID_FACTOR",
            )
        text = value.strip()
        if self.values and text not in self.values:
            raise PlannerError(
                f"factor {self.name}의 허용된 값이 아닙니다: {text!r} "
                f"(허용: {', '.join(sorted(self.values))})",
                code="INVALID_FACTOR",
            )
        if self.pattern is not None and not self.pattern.fullmatch(text):
            raise PlannerError(
                f"factor {self.name}의 형식이 올바르지 않습니다: {text!r}",
                code="INVALID_FACTOR",
            )
        return text


#: grounding이 쓸 수 있는 factor 전체. 여기 없는 이름은 거부한다.
#: "근처/주변"은 질문 유형이 아니라 vicinity factor로 표현한다.
FACTOR_SPECS: dict[str, FactorSpec] = {
    spec.name: spec for spec in (
        FactorSpec(
            "date", pattern=_DATE_PATTERN,
            meaning="분석 대상 날짜 또는 기간.",
        ),
        FactorSpec(
            "time", pattern=_TIME_PATTERN,
            meaning="분석 대상 시간대.",
        ),
        FactorSpec(
            "aggregation", values=_AGGREGATIONS,
            meaning=(
                "원시 값을 하나로 모으는 1차 집계 방식. bucket이 있으면 각 "
                "구간 안에서 적용되고, 없으면 전체에 적용된다. 질문에 집계 "
                "표현이 없으면 넣지 않는다."
            ),
        ),
        FactorSpec(
            "rollup", values=_AGGREGATIONS,
            meaning=(
                "bucket별로 나온 값들을 하나로 합치는 2차 집계 방식. "
                "집계 **방식**이지 시간 단위가 아니다. bucket과 짝으로만 쓴다."
            ),
        ),
        FactorSpec(
            "bucket", values=frozenset({"week", "month"}),
            meaning=(
                "분석 기간을 나누는 시간 구간. 지정하면 구간마다 값을 먼저 "
                "구한 뒤 rollup으로 합친다. 자료가 일 단위이므로 day는 없다."
            ),
        ),
        FactorSpec(
            "taxi_type", values=frozenset({"private", "corporate", "all"}),
            # 설명을 덧붙이지 않는다. "개념이 아니라 조건" 문구와 그 변형들은
            # 모델 상태를 비운 paraphrase 측정에서 이 짧은 정의를 넘지 못했고,
            # 틀린 형태(OBJECT/…)를 보여 준 문구는 오히려 그 형태를 만들게 했다.
            # 근거: evaluation/prompt_ab/20260923_162440_selection_taxi_wording,
            #       evaluation/prompt_ab/20260923_172436_holdout_dpre_t2
            meaning="택시 유형 조건.",
        ),
        FactorSpec(
            "taxi_status",
            values=frozenset({"occupied", "vacant", "stationary", "all"}),
            meaning="운행 상태 조건.",
        ),
        FactorSpec(
            "dimension",
            values=frozenset({"h3", "sido", "sigungu", "emd", "dayofweek"}),
            meaning=(
                "결과를 나눌 그룹 기준. 지정하면 단일 값이 아니라 그룹별 "
                "분포를 얻는다. bucket과 함께 쓸 수 없다."
            ),
        ),
        FactorSpec(
            "order", values=frozenset({"top", "bottom"}),
            meaning="그룹별 결과의 정렬 방향.",
        ),
        FactorSpec(
            "limit", kind="integer",
            meaning="그룹별 결과에서 보여 줄 개수.",
        ),
        FactorSpec(
            "vicinity", kind="boolean",
            meaning="장소의 주변 영역을 포함할지 여부.",
        ),
    )
}

#: 구조를 정하는 factor. Tool 인자가 아니라 어떤 subtype을 만들지를 정한다.
STRUCTURAL_FACTORS = frozenset({"vicinity"})

#: 시간 구간을 나눌 때 집계가 두 단계로 나뉜다는 사실. 어느 factor 하나에
#: 속하는 설명이 아니라 셋의 관계이므로 따로 둔다.
#:
#: 실측에서 모델이 반복해 틀린 지점이다. 질문의 집계어("평균", "최대값")를
#: aggregation에 넣어 버리고 rollup에는 시간 단위("week", "month")를 복사했다.
#: 집계어가 어디에 속하는지는 시간 구간 표현의 유무가 정한다.
FACTOR_STAGE_NOTE = """구간을 나누는 질문에서는 집계가 두 단계다.

    원시 값 --aggregation--> 구간별 값 --rollup--> 최종 값

- 질문에 "주 단위로", "월 단위로" 같은 구간 표현이 있으면, 함께 나온 집계어는
  구간별 값들을 합치는 rollup이다.
  - "월 단위로 나눈 영업시간의 합은?" → bucket=month, rollup=sum
- 구간 표현이 없으면 집계어는 aggregation이다.
  - "평균 영업시간은?" → aggregation=avg (bucket과 rollup은 넣지 않는다)
- rollup에 week나 month 같은 시간 단위를 넣지 않는다. rollup은 합치는
  방식이다."""


@dataclass(frozen=True)
class FactorConstraint:
    """factor 하나가 성립하기 위해 함께 있어야 하는 factor.

    ``reason``은 사용자에게 보여 줄 설명이다. operator 이름이 아니라 조건의
    의미로 말한다. 사용자는 semantic operator를 본 적이 없기 때문이다.
    """

    factor: str
    requires: tuple[str, ...]
    reason: str


#: factor 공기(co-occurrence) 불변식의 단일 기준.
#:
#: 예전에는 같은 규칙이 template YAML의 slot_requires와 operator 3개의
#: param_requires에 흩어져 있었다. 한쪽만 고쳐져 조용히 어긋나는 것을 막기
#: 위해 여기 한 곳에 둔다. operator는 자기가 받는 parameter로 걸러 쓴다.
FACTOR_CONSTRAINTS: dict[str, FactorConstraint] = {
    item.factor: item for item in (
        FactorConstraint(
            "bucket", ("rollup",),
            "주·월 단위로 1차 집계하려면 그 결과를 합치는 방법도 필요합니다.",
        ),
        FactorConstraint(
            "rollup", ("bucket",),
            "1차 집계 결과를 합치려면 어떤 단위로 나눌지도 필요합니다.",
        ),
        FactorConstraint(
            "order", ("dimension",),
            "순위를 매기려면 무엇을 기준으로 나눌지도 필요합니다.",
        ),
        FactorConstraint(
            "limit", ("dimension",),
            "개수를 제한하려면 무엇을 기준으로 나눌지도 필요합니다.",
        ),
    )
}


def describe_factor(name):
    """factor 하나가 받는 값을 사람이 읽을 수 있게 설명한다.

    재질의 요청문이 허용값을 알려 줄 때 쓴다. 같은 목록을 Prompt에 손으로
    적어 두면 어휘가 바뀔 때 어긋나므로 정의에서 만든다.
    """
    spec = FACTOR_SPECS.get(name)
    if spec is None:
        return name
    if spec.values:
        return f"{name}: {' | '.join(sorted(spec.values))} 중 하나"
    if spec.kind == "boolean":
        return f"{name}: true | false"
    if spec.kind == "integer":
        return f"{name}: 정수"
    if spec.pattern is not None:
        return f"{name}: {spec.pattern.pattern} 형식"
    return f"{name}: 문자열"


def describe_factor_semantics(names=None):
    """factor가 무엇을 정하는지 설명하는 Prompt 조각을 만든다.

    허용값만 보여 주는 것으로는 부족했다. 실측에서 모델이 rollup의 허용값을
    보고도 시간 단위를 넣었다. 값의 범위가 아니라 역할을 알려야 한다.
    """
    names = sorted(FACTOR_SPECS) if names is None else list(names)
    lines = []
    for name in names:
        spec = FACTOR_SPECS.get(name)
        if spec is None or not spec.meaning:
            continue
        lines.append(f"- {describe_factor(name)}")
        lines.append(f"    {spec.meaning}")
    return "\n".join(lines)


def describe_constraints():
    """factor 공기 규칙을 Prompt에 넣을 문장으로 만든다.

    같은 규칙을 Prompt에 손으로 또 적어 두면 한쪽만 고쳐져 어긋난다.
    설명 문구까지 이 표에서 만들어 붙인다.
    """
    return "\n".join(
        f"- {item.factor}를 넣으면 {', '.join(item.requires)}도 함께 "
        f"넣습니다. {item.reason}"
        for item in sorted(
            FACTOR_CONSTRAINTS.values(), key=lambda item: item.factor
        )
    )


def companions_for(factor):
    """``factor``와 함께 있어야 하는 factor 이름."""
    constraint = FACTOR_CONSTRAINTS.get(factor)
    return () if constraint is None else constraint.requires


def missing_companions(factors, factor):
    """``factors`` 안에서 ``factor``에 빠진 동반 factor."""
    return tuple(name for name in companions_for(factor) if name not in factors)


def validate_factors(factors, *, raw_text=""):
    """grounding이 읽어 낸 조건이 그 자체로 성립하는지 확인한다.

    macro를 고르기 전에, Tool을 알기 전에 판정할 수 있는 검사다. 어떤
    operator가 이 조건을 소비할지와 무관하게 참이어야 하기 때문이다.
    Validator G4가 같은 종류의 검사를 operator 기준으로 한 번 더 수행하며,
    그쪽은 계획이 어떤 경로로 만들어졌든 적용되는 마지막 방어선이다.
    """
    for name in sorted(factors):
        missing = missing_companions(factors, name)
        if not missing:
            continue
        constraint = FACTOR_CONSTRAINTS[name]
        raise PlannerError(
            f"{name} 조건을 쓰려면 {', '.join(missing)} 조건도 함께 "
            f"필요합니다. {constraint.reason}",
            user_message=constraint.reason,
            code="INVALID_FACTOR_COMBINATION",
            context={
                "raw_text": raw_text,
                "factor": name,
                "missing": list(missing),
                "present": sorted(factors),
            },
        )
    return factors
