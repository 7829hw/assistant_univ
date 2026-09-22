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
        FactorSpec("date", pattern=_DATE_PATTERN),
        FactorSpec("time", pattern=_TIME_PATTERN),
        FactorSpec("aggregation", values=_AGGREGATIONS),
        FactorSpec("rollup", values=_AGGREGATIONS),
        FactorSpec("bucket", values=frozenset({"week", "month"})),
        FactorSpec(
            "taxi_type", values=frozenset({"private", "corporate", "all"}),
        ),
        FactorSpec(
            "taxi_status",
            values=frozenset({"occupied", "vacant", "stationary", "all"}),
        ),
        FactorSpec(
            "dimension",
            values=frozenset({"h3", "sido", "sigungu", "emd", "dayofweek"}),
        ),
        FactorSpec("order", values=frozenset({"top", "bottom"})),
        FactorSpec("limit", kind="integer"),
        FactorSpec("vicinity", kind="boolean"),
    )
}

#: 구조를 정하는 factor. Tool 인자가 아니라 어떤 subtype을 만들지를 정한다.
STRUCTURAL_FACTORS = frozenset({"vicinity"})


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
