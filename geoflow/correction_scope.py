# -*- coding: utf-8 -*-
"""factor 수정 재질의의 수정 범위와 결과 역할 기록.

한 계약 오류를 고치려고 결과 형태 전체를 다시 쓰게 하지 않는다. 수정 범위는 현재 factor의 계약 위반(허용되지 않은
값, 빠진 짝, 답 대상)과 factor 계약만으로 정한다. 질문 문자열은 보지 않는다.

    위반 factor        → 빼거나(값 오류면 바꾸거나) 할 수 있다
    빠진 짝            → 새로 적을 수 있다. 단 함께 쓸 수 없는 factor가 남아 있으면 적을 수 없다
    뺄 수 있는 factor에 기대는 factor → 함께 뺄 수 있다(남으면 성립하지 않는다)
    뺄 수 있는 factor의 대체 표현     → 비어 있으면 새로 적을 수 있다(예: 요일 순위의 rollup → order·limit)
    새로 적는 factor의 짝             → 새로 적을 수 있다
    집계 단계 배치                    → 같은 값을 다른 단계로 옮기는 것만 된다(새 값을 만들지 않는다)

이 범위 밖의 factor는 수정안에서 빠져도 그대로 남는다. 범위 밖 factor를 다른 값으로 적거나 새로 적거나 null로
적으면 수정안 전체를 받지 않는다. 코드가 모델이 제안하지 않은 혼합 계획(일부만 적용)을 만들지 않기 위해서다.

적용 뒤에는 결과 역할(그룹, 순위 방향, 개수, 답 대상, 집계 단계)의 전후를 기록하고, 계약상 이유 없이 그룹이
사라지거나 순위 방향이 사라지거나 바뀌면 받지 않는다. 이것은 계약 수준의 보존 검사다. 질문의 뜻에 맞는지는
증명하지 않는다(예: 첫 grounding의 순위 방향이 이미 틀렸다면 그대로 남는다).
"""

from dataclasses import dataclass, field

from geoflow.errors import PlannerError
from geoflow.factors import (
    EXCLUSIVE_WITH_BUCKET,
    FACTOR_SPECS,
    RESULT_SHAPE_FACTORS,
    companions_for,
)

REMOVE = "remove"
CHANGE = "change"
ADD = "add"
#: 같은 값을 다른 집계 단계로 옮긴다(aggregation ↔ rollup). 새 값을 만들지 않는다.
MOVE = "move"

#: 한 factor가 맡은 결과 역할을 계약 안의 다른 factor로 적는 경우. 실측에서 모델이 자리를 혼동한 쌍만 둔다.
#: - bucket → dimension: 요일·지역 같은 그룹을 bucket에 적음(015, k36: bucket=dayofweek). bucket 값이 허용값이
#:   아닐 때만 연다. 성립하는 주·월 구간을 지역·요일 그룹으로 바꾸는 것은 계약 오류를 고치는 일이 아니다.
#: - rollup → order·limit: 그룹 가운데 가장 큰·작은 것을 고르는 순위를 rollup에 적음(c06a, g24, m17).
#: - answer → order·limit: 주·월이 아닌 그룹을 고르는 것을 answer=bucket으로 적음(k22, 065, m01).
ALTERNATIVES = {
    "bucket": ("dimension",),
    "rollup": ("order", "limit"),
    "answer": ("order", "limit"),
}

#: 수정안에서 값이 이것이면 적지 않은 것과 같다(grounding 정규화가 같게 다룬다).
NO_OP_VALUES = {"answer": "value"}

#: 결과 역할. 기록과 보존 검사에 쓴다.
_DIRECTION_OF_ROLLUP = {"max": "top", "min": "bottom"}


@dataclass
class CorrectionScope:
    """factor별 허용 동작과 그 근거."""

    issues: list[dict] = field(default_factory=list)
    permissions: dict[str, set] = field(default_factory=dict)
    reasons: dict[str, list] = field(default_factory=dict)
    #: 재질의로 고치지 않는 위반 factor(기록을 고르는 조건의 값 오류).
    unrepairable: list = field(default_factory=list)

    @property
    def repairable(self):
        return bool(self.permissions) and not self.unrepairable

    def allow(self, name, op, reason):
        ops = self.permissions.setdefault(name, set())
        if op in ops:
            return False
        ops.add(op)
        self.reasons.setdefault(name, []).append(reason)
        return True

    @property
    def editable(self):
        return tuple(name for name in RESULT_SHAPE_FACTORS + ("time",) if name in self.permissions)

    def to_dict(self):
        return {
            "issues": self.issues,
            "permissions": {name: sorted(ops) for name, ops in self.permissions.items()},
            "reasons": {name: list(items) for name, items in self.reasons.items()},
            "unrepairable": list(self.unrepairable),
        }


def contract_issues(factors):
    """현재 factor의 계약 위반 전부. 검증은 첫 위반에서 멈추지만, 수정 범위는 얽힌 위반을 함께 봐야 한다.

    예: 요일 순위에 answer=bucket과 rollup=min이 함께 있으면 둘 다 bucket이 없어 성립하지 않는다.
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
    if factors.get("answer") == "bucket" and factors.get("rollup") not in (None, "max", "min"):
        issues.append({"kind": "answer_target", "factor": "answer", "rollup": factors.get("rollup")})
    for name in sorted(factors):
        if name not in FACTOR_SPECS:
            continue
        missing = [item for item in companions_for(name) if item not in factors]
        if missing:
            issues.append({"kind": "missing_companion", "factor": name, "missing": missing})
    return issues


def dependents(name, factors):
    """``name``이 없으면 성립하지 않는, 지금 있는 factor."""
    return tuple(other for other in sorted(factors)
                 if other != name and name in companions_for(other))


def _addable(name, factors, scope):
    """새로 적어도 함께 쓸 수 없는 factor와 부딪치지 않는가. 남을 factor 기준이다."""
    if name in factors:
        return False
    staying = [other for other in factors if REMOVE not in scope.permissions.get(other, ())]
    if name == "bucket":
        return not any(other in EXCLUSIVE_WITH_BUCKET for other in staying)
    if name in EXCLUSIVE_WITH_BUCKET:
        return "bucket" not in staying
    return True


def correction_scope(factors):
    """현재 factor에서 계약 위반을 찾고, 그것을 고치는 데 필요한 범위만 연다."""
    scope = CorrectionScope(issues=contract_issues(factors))
    wanted_additions = []
    invalid = {issue["factor"] for issue in scope.issues if issue["kind"] == "invalid_value"}
    for issue in scope.issues:
        name = issue["factor"]
        if issue["kind"] == "invalid_value":
            if name not in RESULT_SHAPE_FACTORS and name != "time":
                # 날짜·택시 유형·운행 상태는 조건 계층이 질문 근거로 다룬다. 재질의로 다시 정하지 않는다.
                scope.unrepairable.append(name)
                continue
            scope.allow(name, CHANGE, f"{name}={issue['value']!r}는 허용값이 아닙니다")
            if name != "time":
                scope.allow(name, REMOVE, f"{name}={issue['value']!r}는 허용값이 아닙니다")
        elif issue["kind"] == "answer_target":
            scope.allow("answer", REMOVE, "answer=bucket은 rollup이 max·min일 때만 성립합니다")
            scope.allow("answer", CHANGE, "answer=bucket은 rollup이 max·min일 때만 성립합니다")
            scope.allow("rollup", CHANGE, "answer=bucket은 rollup이 max·min일 때만 성립합니다")
        elif issue["kind"] == "missing_companion":
            missing = ", ".join(issue["missing"])
            scope.allow(name, REMOVE, f"{name}는 {missing} 없이 성립하지 않습니다")
            wanted_additions += [(item, f"{name}의 짝입니다") for item in issue["missing"]]

    changed = True
    while changed:
        changed = False
        for name in list(scope.permissions):
            if REMOVE not in scope.permissions[name]:
                continue
            for other in dependents(name, factors):
                changed |= scope.allow(other, REMOVE, f"{name}를 빼면 {other}도 성립하지 않습니다")
            if name == "bucket" and "bucket" not in invalid:
                alternatives = ()
            else:
                alternatives = ALTERNATIVES.get(name, ())
            for other in alternatives:
                if other not in factors:
                    wanted_additions.append((other, f"{name}가 맡은 역할을 {other}로 적을 수 있습니다"))
        for other, reason in list(wanted_additions):
            if _addable(other, factors, scope) and scope.allow(other, ADD, reason):
                changed = True
                for companion in companions_for(other):
                    if companion not in factors:
                        wanted_additions.append((companion, f"{other}의 짝입니다"))

    # 집계 단계 배치. 값은 그대로 두고 자리만 옮긴다.
    if "aggregation" in factors and ADD in scope.permissions.get("rollup", ()):
        scope.allow("aggregation", MOVE, "구간 안 집계로 적은 값이 구간별 결과의 집계라면 rollup으로 옮길 수 있습니다")
    if "aggregation" not in factors and REMOVE in scope.permissions.get("rollup", ()) and "rollup" in factors:
        scope.allow("rollup", MOVE, "rollup으로 적은 값이 그룹 안 집계라면 aggregation으로 옮길 수 있습니다")
    return scope


# -- 적용 -------------------------------------------------------------------


class ScopeViolation(ValueError):
    """수정안이 수정 범위를 벗어났다. ``record``에 무엇을 제안했고 무엇이 막혔는지 남긴다."""

    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


def _same(name, value, current):
    if value == current:
        return True
    spec = FACTOR_SPECS.get(name)
    if spec is None:
        return False
    try:
        return spec.coerce(value) == current
    except Exception:  # noqa: BLE001 - 형식이 틀린 값은 다른 값이다
        return False


def _absent(name, value):
    return value is None or value == "" or NO_OP_VALUES.get(name) == value


def roles(factors):
    """결과 역할 요약(계약 수준). 순위 방향은 order, 없으면 rollup max/min에서 읽는다."""
    direction = factors.get("order") or _DIRECTION_OF_ROLLUP.get(factors.get("rollup"))
    return {
        "grouping": factors.get("bucket") or factors.get("dimension"),
        "grouping_field": "bucket" if "bucket" in factors else "dimension" if "dimension" in factors else None,
        "direction": direction,
        "limit": factors.get("limit"),
        "answer": factors.get("answer") or "value",
        "aggregation": factors.get("aggregation"),
        "rollup": factors.get("rollup"),
    }


def _format(name, value):
    """의미를 바꾸지 않는 형식 맞춤. 정수 factor를 숫자 문자열로 적은 것("1")만 정수로 읽는다(k36 기록)."""
    spec = FACTOR_SPECS.get(name)
    if spec is not None and spec.kind == "integer" and isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


def apply_correction(base, proposal, scope):
    """수정안(고친 뒤의 결과 형태 전체)을 범위 안에서만 적용한다. (결과 factor, 기록)을 돌려준다."""
    proposal = {name: _format(name, value) for name, value in dict(proposal or {}).items()}
    result = dict(base)
    shape = RESULT_SHAPE_FACTORS + ("time",)
    record = {"scope": scope.to_dict(), "applied": {"added": {}, "changed": {}, "removed": {}},
              "kept_omitted": [], "blocked": [],
              # 결과 형태의 전후와 모델 수정안. 전후 비교(어떤 순위·개수·그룹·답 대상·집계 단계가 바뀌었나)의 근거다.
              "before": {name: base[name] for name in shape if name in base},
              "proposed": {name: value for name, value in proposal.items() if name in shape}}

    def block(name, why):
        record["blocked"].append({"factor": name, "reason": why,
                                  "base": base.get(name), "proposed": proposal.get(name)})

    for name, value in proposal.items():
        ops = scope.permissions.get(name, set())
        present = name in base
        if _absent(name, value):
            if present and REMOVE not in ops and MOVE not in ops:
                block(name, "뺄 수 없는 조건을 빼려 했습니다")
            continue
        if present and _same(name, value, base[name]):
            continue
        if not present:
            if ADD in ops:
                result[name] = value
                record["applied"]["added"][name] = value
            elif name == "aggregation" and MOVE in scope.permissions.get("rollup", ()):
                result[name] = value
                record["applied"]["added"][name] = value
            else:
                block(name, "새로 적을 수 없는 조건을 적었습니다")
        elif CHANGE in ops:
            result[name] = value
            record["applied"]["changed"][name] = {"from": base[name], "to": value}
        else:
            block(name, "바꿀 수 없는 조건의 값을 바꿨습니다")

    for name in sorted(base):
        if name in proposal and not _absent(name, proposal[name]):
            continue
        ops = scope.permissions.get(name, set())
        if REMOVE in ops or MOVE in ops:
            result.pop(name, None)
            record["applied"]["removed"][name] = base[name]
        elif name not in proposal:
            # 수정 범위 밖 조건이 응답에서 빠진 것은 삭제가 아니다.
            if name in RESULT_SHAPE_FACTORS:
                record["kept_omitted"].append(name)

    removed = record["applied"]["removed"]
    added = record["applied"]["added"]
    # 집계 단계를 옮겼다면 값이 같아야 한다. 그렇지 않으면 집계를 버리거나 새로 만든 것이다.
    if "aggregation" in removed and REMOVE not in scope.permissions.get("aggregation", ()):
        if result.get("rollup") != removed["aggregation"]:
            block("aggregation", "구간 안 집계 값을 rollup으로 옮기지 않고 버렸습니다")
    if "aggregation" in added and ADD not in scope.permissions.get("aggregation", ()):
        if removed.get("rollup") != added["aggregation"]:
            block("aggregation", "rollup에서 옮긴 값이 아닌 집계를 새로 적었습니다")
    if "rollup" in removed and REMOVE not in scope.permissions.get("rollup", ()):
        if result.get("aggregation") != removed["rollup"]:
            block("rollup", "rollup 값을 aggregation으로 옮기지 않고 버렸습니다")
    if ("rollup" in added and "aggregation" in base and result.get("aggregation") == base["aggregation"]
            and added["rollup"] == base["aggregation"]):
        # 빠진 단계를 채우면서 남아 있는 단계의 값을 그대로 복사했다. 한 집계 표현을 두 단계에 쓴 것이다(c08b·g44).
        # 그 값이 구간별 결과의 집계라면 옮기기(aggregation을 빼고 rollup에 적기)로 적는다.
        block("rollup", "구간 안 집계 값을 rollup에 복사했습니다(한 집계 표현을 두 단계에 씀)")

    def exclusive(factors):
        # 허용값이 아닌 bucket(예: dayofweek)은 아직 구간이 아니다. 성립하는 구간과의 충돌만 센다.
        return (factors.get("bucket") in FACTOR_SPECS["bucket"].values
                and any(name in factors for name in EXCLUSIVE_WITH_BUCKET))

    if exclusive(result) and not exclusive(base):
        # 계약 위반을 고치면서 다른 계약 충돌(주·월 구간 + 지역·요일 그룹)을 새로 만들었다.
        block("bucket", "주·월 구간과 함께 쓸 수 없는 그룹·순위가 남는 수정입니다")

    before, after = roles(base), roles(result)
    record["roles"] = {"before": before, "after": after}
    record["after"] = {name: result[name] for name in shape if name in result}
    if before["grouping"] and not after["grouping"]:
        block("grouping", "구간·그룹 기준이 모두 사라집니다")
    moved_into_aggregation = ("rollup" in removed and added.get("aggregation") == removed["rollup"])
    if before["direction"] and after["direction"] != before["direction"] and not moved_into_aggregation:
        block("direction", f"순위 방향이 {before['direction']}에서 {after['direction'] or '없음'}으로 바뀝니다")

    if record["blocked"]:
        raise ScopeViolation(
            "수정 범위를 벗어났습니다: "
            + "; ".join(f"{item['factor']}: {item['reason']}" for item in record["blocked"]),
            record,
        )
    if result == base:
        raise ScopeViolation("바뀐 조건이 없습니다.", record)
    return result, record


def describe_scope(scope, factors):
    """재질의 문구의 수정 범위 설명. 허용 동작과 근거를 factor마다 적는다."""
    labels = {REMOVE: "뺄 수 있음", CHANGE: "값을 바꿀 수 있음", ADD: "새로 적을 수 있음",
              MOVE: "같은 값을 다른 집계 단계로 옮길 수 있음"}
    lines = []
    for name in scope.editable:
        ops = scope.permissions[name]
        current = f"지금 {factors[name]!r}" if name in factors else "지금 없음"
        how = ", ".join(labels[op] for op in (REMOVE, CHANGE, ADD, MOVE) if op in ops)
        why = "; ".join(dict.fromkeys(scope.reasons.get(name, ())))
        lines.append(f"- {name} ({current}): {how}. {why}")
    return "\n".join(lines)


def kept_factors(scope, factors):
    """수정 범위 밖이라 그대로 남는 결과 형태 factor."""
    return {name: factors[name] for name in RESULT_SHAPE_FACTORS
            if name in factors and name not in scope.permissions}

