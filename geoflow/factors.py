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
    r"|weekday|weekend|holiday|this_week|this_month|this_year)$"
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
                    context={"factor": self.name, "value": value},
                )
            return value
        if self.kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise PlannerError(
                    f"factor {self.name}은 정수여야 합니다. (받은 값: {value!r})",
                    code="INVALID_FACTOR",
                    context={"factor": self.name, "value": value},
                )
            return value
        if not isinstance(value, str) or not value.strip():
            raise PlannerError(
                f"factor {self.name}은 비어 있지 않은 문자열이어야 합니다. "
                f"(받은 값: {value!r})",
                code="INVALID_FACTOR",
                context={"factor": self.name, "value": value},
            )
        text = value.strip()
        if self.values and text not in self.values:
            raise PlannerError(
                f"factor {self.name}의 허용된 값이 아닙니다: {text!r} "
                f"(허용: {', '.join(sorted(self.values))})",
                code="INVALID_FACTOR",
                context={"factor": self.name, "value": value},
            )
        if self.pattern is not None and not self.pattern.fullmatch(text):
            raise PlannerError(
                f"factor {self.name}의 형식이 올바르지 않습니다: {text!r}",
                code="INVALID_FACTOR",
                context={"factor": self.name, "value": value},
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
            "answer", values=frozenset({"value", "bucket"}),
            meaning=(
                "구간(bucket)이 있는 질문에서 질문이 최종적으로 묻는 것. 값을 물으면 value(\"~ 중 가장 큰 값은?\", "
                "생략하면 value), 그 값을 가진 주·월을 물으면 bucket(\"~가 가장 큰 달은?\", \"어느 주\")이다. "
                "bucket은 rollup이 max나 min일 때만 뜻이 있다(가장 큰·작은 구간). bucket과 짝으로만 쓴다."
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
            "dimension_target", values=frozenset({"pickup", "dropoff", "both"}),
            meaning=(
                "실차 구간(trip)을 dimension으로 나눌 때 결과를 묶는 끝. "
                "pickup=승차 지역별, dropoff=하차 지역별, both=승차지-하차지 "
                "조합별. 생략하면 both로 묶인다. 장소의 od_role(장소가 제한하는 끝)과 독립이다."
            ),
        ),
        FactorSpec(
            "order", values=frozenset({"top", "bottom"}),
            meaning="그룹별 결과의 정렬 방향.",
        ),
        FactorSpec(
            "limit", kind="integer",
            meaning="그룹별 결과에서 보여 줄 개수. 순위(order)에는 늘 적는다. 하나만 묻는 순위는 1.",
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

- 질문에 "주별", "월별", "주 단위로" 같은 구간 표현이 있으면 집계어가 놓인 자리로 단계를 정한다.
  - 구간 표현과 측정값 사이의 집계어(각 구간 안에서 모으는 방법)는 aggregation이다.
  - 구간별 값들 가운데서 고르거나 합치는 집계어("~ 중 가장 큰 값", "~의 평균", "~의 중간값")는
    rollup이다.
  - "지난해 월별 평균 활성택시 대수 중 가장 작은 값은?" → bucket=month, aggregation=avg, rollup=min
  - "주별 수입 합계의 중간값은?" → bucket=week, aggregation=sum, rollup=med
  - 구간 안 집계어가 없으면 aggregation을 넣지 않는다.
    "월 단위로 나눈 수입의 합은?" → bucket=month, rollup=sum
- "총", "합계", "모두 더한"은 sum이다. "가장 큰 값", "최댓값"은 값을 묻는 집계(max)이다.
- 구간 표현이 없으면 집계어는 aggregation이다.
  - "평균 수입은?" → aggregation=avg (bucket과 rollup은 넣지 않는다)
- bucket이 있으면 answer로 질문이 묻는 것을 적는다. 값이면 value(생략해도 value), 그 값을 가진 주·월이면
  bucket이다.
  - "주별 운행 일수 평균 중 가장 작은 값은?" → bucket=week, aggregation=avg, rollup=min, answer=value
  - "주별 운행 일수 평균이 가장 작은 주는?"   → bucket=week, aggregation=avg, rollup=min, answer=bucket
  - 지역·요일을 고르는 순위("가장 많은 곳")는 bucket이 아니라 dimension·order·limit이다.
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
            "answer", ("bucket",),
            "답 대상(값/구간)은 구간을 나눌 때만 적습니다.",
        ),
        FactorConstraint(
            "rollup", ("bucket",),
            "1차 집계 결과를 합치려면 어떤 단위로 나눌지도 필요합니다.",
        ),
        FactorConstraint(
            "dimension_target", ("dimension",),
            "승차·하차 기준을 정하려면 무엇을 기준으로 나눌지도 필요합니다.",
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


def describe_constraints(exclude=()):
    """factor 공기 규칙을 Prompt에 넣을 문장으로 만든다.

    같은 규칙을 Prompt에 손으로 또 적어 두면 한쪽만 고쳐져 어긋난다.
    설명 문구까지 이 표에서 만들어 붙인다. ``exclude``의 factor가 걸린 규칙은 뺀다.
    """
    lines = []
    for item in sorted(FACTOR_CONSTRAINTS.values(), key=lambda item: item.factor):
        if item.factor in exclude or set(item.requires) & set(exclude):
            continue
        requires = ", ".join(item.requires)
        lines.append(f"- {item.factor}를 넣으면 {requires}도 함께 넣습니다. {item.reason}")
    for factor, (requires, reason) in sorted(CONTRACT_COMPANIONS.items()):
        if factor in exclude:
            continue
        lines.append(f"- {factor}를 넣으면 {', '.join(requires)}도 함께 넣습니다. {reason}")
    return "\n".join(lines)


#: 모델에게 전달하는 계약과 실행 계약을 맞춘다(grounding_v4). grounding 계약(parse·검증·합성·재질의)이 받는
#: 값은 모두 prompt에 안내한다. 빼 둘 factor가 생기면 여기에 적고 이유를 남긴다(현재 없음).
FLAT_PROMPT_EXCLUDED = frozenset()



#: Tool 계약이 요구하는 짝. factor 자체의 성립 조건(FACTOR_CONSTRAINTS)과 달리 업체 Tool 호출 규칙에서 온다.
#: prompt의 [짝을 이루는 factor]에 함께 적고(describe_constraints), 검증과 factor 재질의로 지킨다.
#: - order → limit: 업체 system prompt "top이나 bottom값만 필요하다면 limit를 1개로 제한", "3곳" → limit=3.
#:   정답 96문항이 모두 limit을 적는다. 빠지면 Tool 기본 개수로 다른 답이 된다.
CONTRACT_COMPANIONS = {
    "order": (("limit",), "순위를 매기려면 몇 개를 보일지(하나만 물으면 1)도 필요합니다."),
}


#: 값을 어떻게 나누고 모으고 줄 세우며 무엇을 답으로 돌려줄지 정하는 factor. 어떤 기록을 볼지 정하는 조건
#: (date·time·taxi_type·taxi_status·vicinity)과 구별한다. factor 계약 오류(짝 누락, 답 대상, 허용되지 않은 값)는
#: 이 묶음 안에서 서로 얽혀 생긴다. 예: 요일 순위에 answer=bucket을 붙이면 빠진 것은 bucket이지만 고칠 것은
#: answer다. 그래서 factor 수정 재질의는 이 묶음 안의 추가·변경·삭제를 받고, 기록을 고르는 조건과 개념은 바꾸지
#: 못한다.
RESULT_SHAPE_FACTORS = ("bucket", "aggregation", "rollup", "answer",
                        "dimension", "dimension_target", "order", "limit")

#: 주·월 구간(bucket)과 함께 쓸 수 없는 factor. 공간·요일 그룹과 시간 구간을 함께 나누는 계산은 schema가 정하지
#: 않았고 mock은 거절한다(합성 단계 UNSUPPORTED_AGGREGATION_COMBINATION). prompt의 dimension 설명에도 적혀 있다.
EXCLUSIVE_WITH_BUCKET = ("dimension", "order", "limit")


def companions_for(factor):
    """``factor``와 함께 있어야 하는 factor 이름(factor 성립 조건 + Tool 계약)."""
    constraint = FACTOR_CONSTRAINTS.get(factor)
    own = () if constraint is None else constraint.requires
    return own + CONTRACT_COMPANIONS.get(factor, ((), ""))[0]


def companion_reason(factor, missing):
    """빠진 짝에 대한 사용자 설명. Tool 계약 짝만 빠졌으면 그 설명을 쓴다."""
    constraint = FACTOR_CONSTRAINTS.get(factor)
    own = set(constraint.requires) if constraint else set()
    if not set(missing) & own and factor in CONTRACT_COMPANIONS:
        return CONTRACT_COMPANIONS[factor][1]
    return constraint.reason if constraint else CONTRACT_COMPANIONS[factor][1]


def missing_companions(factors, factor):
    """``factors`` 안에서 ``factor``에 빠진 동반 factor."""
    return tuple(name for name in companions_for(factor) if name not in factors)


#: answer=bucket이 고를 수 있는 구간 선택 방향.
ANSWER_SELECTIONS = (None, "max", "min")


def contract_issues(factors):
    """factor 계약 위반 전부: 허용되지 않은 값, 답 대상과 구간 선택이 맞지 않음, 빠진 짝.

    검증(``validate_factors``)과 factor 수정 재질의의 수정 범위(``correction_scope``)가 같은 정의를 쓴다. 검증은 첫
    위반에서 멈추지만 수정 범위는 얽힌 위반(예: 요일 순위에 answer=bucket과 rollup=min이 함께 bucket 없이 있음)을
    함께 본다. 이름 순서대로 돌려준다.
    """
    issues = []
    for name in sorted(factors):
        spec = FACTOR_SPECS.get(name)
        if spec is None:
            continue
        try:
            spec.coerce(factors[name])
        except PlannerError:
            issues.append({"kind": "invalid_value", "factor": name, "value": factors[name]})
    if factors.get("answer") == "bucket" and factors.get("rollup") not in ANSWER_SELECTIONS:
        issues.append({"kind": "answer_target", "factor": "answer", "rollup": factors.get("rollup")})
    for name in sorted(factors):
        if name not in FACTOR_SPECS:
            continue
        missing = list(missing_companions(factors, name))
        if missing:
            issues.append({"kind": "missing_companion", "factor": name, "missing": missing})
    return issues


def validate_factors(factors, *, raw_text=""):
    """grounding이 읽어 낸 조건이 그 자체로 성립하는지 확인한다.

    macro를 고르기 전에, Tool을 알기 전에 판정할 수 있는 검사다. 어떤
    operator가 이 조건을 소비할지와 무관하게 참이어야 하기 때문이다.
    Validator G4가 같은 종류의 검사를 operator 기준으로 한 번 더 수행하며,
    그쪽은 계획이 어떤 경로로 만들어졌든 적용되는 마지막 방어선이다.
    값 형식은 grounding 계약(``FactorSpec.coerce``)이 먼저 본다. 여기서는 답 대상과 짝을 본다.
    """
    for issue in contract_issues(factors):
        if issue["kind"] == "answer_target":
            raise PlannerError(
                "구간을 답으로 고르려면 rollup이 max(가장 큰 구간)나 min(가장 작은 구간)이어야 합니다.",
                user_message="어떤 구간을 고를지(가장 큰/작은) 질문에서 정하지 못했습니다.",
                code="INVALID_ANSWER_TARGET",
                context={"raw_text": raw_text, "present": sorted(factors), "factors": dict(factors)},
            )
    for issue in contract_issues(factors):
        if issue["kind"] != "missing_companion":
            continue
        name, missing = issue["factor"], tuple(issue["missing"])
        reason = companion_reason(name, missing)
        raise PlannerError(
            f"{name} 조건을 쓰려면 {', '.join(missing)} 조건도 함께 "
            f"필요합니다. {reason}",
            user_message=reason,
            code="INVALID_FACTOR_COMBINATION",
            context={
                "raw_text": raw_text,
                "factor": name,
                "missing": list(missing),
                "present": sorted(factors),
                # 수정 범위는 오류가 난 factor 전체에서 정한다(얽힌 위반을 함께 본다).
                "factors": dict(factors),
            },
        )
    return factors
