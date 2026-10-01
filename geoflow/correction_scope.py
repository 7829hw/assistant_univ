# -*- coding: utf-8 -*-
"""factor 수정 재질의의 수정 범위, 적용 규칙, 결과 역할 기록.

한 계약 오류를 고치려고 결과 형태 전체를 다시 쓰게 하지 않는다. 수정 범위는 현재 factor의 계약 위반
(``factors.contract_issues``)과 factor 계약만으로 정한다. 질문의 뜻은 코드가 정하지 않는다.

코드가 하는 일은 세 종류로 나뉜다.

1. **계약상 같은 표현**(코드가 적용한다): ``answer=value``는 적지 않은 것과 같다(grounding 정규화와 같다). 정수 factor를
   숫자 문자열로 적은 것은 정수다. 뜻이 바뀌지 않는다.
2. **복구 후보**(모델이 고른다): 위반 factor 빼기, 빠진 짝 채우기, 역할을 다른 factor로 적기(``RECOVERY_CANDIDATES``),
   집계 값을 다른 단계로 옮기기, 답 대상에 맞게 구간 선택 방향 다시 고르기. 이것들은 계약이 보장하는 변환이 아니다.
   예를 들어 "주별 값 중 최대(rollup=max)"와 "가장 큰 지역(order=top)"은 같은 계산이 아니다. 코드는 후보를 열어 줄
   뿐이고, 어느 것이 질문에 맞는지는 모델이 정한다.
3. **코드가 확인할 수 있는 사실**(불변식): 범위 밖 조건이 그대로인가, 그룹이 사라지지 않았나, 수정 전에 적혀 있던
   순위 방향(order, rollup max/min)이 유지되나, 주·월 구간과 그룹의 충돌을 새로 만들지 않았나, 집계 값이 버려지지
   않았나, 새로 적은 집계 값마다 모델이 질문에서 옮겨 적은 표현이 실제로 질문에 있나(두 단계에 같은 값을 적었다면
   서로 겹치지 않는 두 자리에 있나). 마지막 것은 문자열이 있는지만 본다. 그 표현이 그 집계를 뜻하는지는 확인하지
   않는다. 그래서 통과해도 "모델이 근거를 댔고 문자열이 있다"일 뿐 의미가 증명된 것이 아니다.

확인할 수 없는 경우(새 집계 값에 근거 표현이 없거나 질문에서 찾을 수 없음)는 실행하지 않고, 확정하지 못한 집계
단계를 사용자에게 확인받는 상태로 끝낸다(``terminal``). 재질의 예산이 1회라 다시 물어 확인할 수 없기 때문이다.
"""

from dataclasses import dataclass, field

from geoflow.factors import (
    EXCLUSIVE_WITH_BUCKET,
    FACTOR_SPECS,
    RESULT_SHAPE_FACTORS,
    companions_for,
    contract_issues,
)

REMOVE = "remove"
CHANGE = "change"
ADD = "add"
#: 집계 값을 다른 단계로 옮긴다(aggregation ↔ rollup). 비운 단계에는 근거 표현이 있는 새 값만 적을 수 있다.
MOVE = "move"
#: 답 대상(answer=bucket)이 요구하는 구간 선택 방향(rollup max/min)을 다시 고른다. 원래 rollup 값은 aggregation으로
#: 옮겨 보존해야 하고, 새 방향 값에는 근거 표현이 필요하다.
RESELECT = "reselect"

STAGES = ("aggregation", "rollup")

#: 복구 후보: 한 factor가 맡은 결과 역할을 다른 factor로 적는 경우. 계약상 동치가 아니다(모델이 고른다).
#: 실측에서 모델이 자리를 혼동한 쌍만 둔다.
#: - bucket → dimension: 요일·지역 같은 그룹을 bucket에 적음(015, k36: bucket=dayofweek). bucket 값이 허용값이 아닐
#:   때만 연다. 성립하는 주·월 구간을 지역·요일 그룹으로 바꾸는 것은 계약 오류를 고치는 일이 아니다.
#: - rollup → order·limit: 그룹 가운데 가장 큰·작은 것을 고르는 순위를 rollup에 적음(c06a, g24, m17).
#: - answer → order·limit: 주·월이 아닌 그룹을 고르는 것을 answer=bucket으로 적음(k22, 065, m01).
RECOVERY_CANDIDATES = {
    "bucket": ("dimension",),
    "rollup": ("order", "limit"),
    "answer": ("order", "limit"),
}

#: 계약상 같은 표현: 수정안에서 값이 이것이면 적지 않은 것과 같다.
NO_OP_VALUES = {"answer": "value"}

#: 순위 방향 불변식. 수정 전 방향(order, 없으면 rollup max/min)이 수정 뒤에도 같아야 한다. 같은 계산이라는 뜻은 아니다.
_DIRECTION_OF_ROLLUP = {"max": "top", "min": "bottom"}

#: 확정하지 못한 집계 단계 → 사용자 확인 코드.
UNVERIFIED_INNER = "AMBIGUOUS_INNER_AGGREGATION"
UNVERIFIED_STAGE = "AMBIGUOUS_AGGREGATION_STAGE"


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

    def ops(self, name):
        return self.permissions.get(name, set())

    @property
    def editable(self):
        """바뀔 수 있는 factor. 집계 값을 옮길 수 있으면 받는 쪽 단계도 바뀐다(옮긴 값만 받는다)."""
        names = set(self.permissions)
        for stage, other in (("aggregation", "rollup"), ("rollup", "aggregation")):
            if MOVE in self.ops(stage):
                names.add(other)
        return tuple(name for name in RESULT_SHAPE_FACTORS + ("time",) if name in names)

    def to_dict(self):
        return {
            "issues": self.issues,
            "permissions": {name: sorted(ops) for name, ops in self.permissions.items()},
            "reasons": {name: list(items) for name, items in self.reasons.items()},
            "unrepairable": list(self.unrepairable),
        }


def dependents(name, factors):
    """``name``이 없으면 성립하지 않는, 지금 있는 factor."""
    return tuple(other for other in sorted(factors)
                 if other != name and name in companions_for(other))


def _addable(name, factors, scope):
    """새로 적어도 함께 쓸 수 없는 factor와 부딪치지 않는가. 남을 factor 기준이다."""
    if name in factors:
        return False
    staying = [other for other in factors if REMOVE not in scope.ops(other)]
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
            reason = "answer=bucket은 rollup이 max·min일 때만 성립합니다"
            scope.allow("answer", REMOVE, reason)
            # 구간을 고르는 질문이라면 선택 방향을 다시 고를 수 있다. 원래 rollup 값은 aggregation으로 옮겨 보존한다.
            if "aggregation" not in factors:
                scope.allow("rollup", RESELECT, reason + ". 지금 rollup 값은 aggregation으로 옮겨 남깁니다")
                scope.allow("rollup", MOVE, reason)
        elif issue["kind"] == "missing_companion":
            missing = ", ".join(issue["missing"])
            scope.allow(name, REMOVE, f"{name}는 {missing} 없이 성립하지 않습니다")
            wanted_additions += [(item, f"{name}의 짝입니다") for item in issue["missing"]]

    changed = True
    while changed:
        changed = False
        for name in list(scope.permissions):
            if REMOVE not in scope.ops(name):
                continue
            for other in dependents(name, factors):
                changed |= scope.allow(other, REMOVE, f"{name}를 빼면 {other}도 성립하지 않습니다")
            if name == "bucket" and "bucket" not in invalid:
                candidates = ()
            else:
                candidates = RECOVERY_CANDIDATES.get(name, ())
            for other in candidates:
                if other not in factors:
                    wanted_additions.append(
                        (other, f"{name}가 맡은 역할을 {other}로 적는 후보입니다(같은 계산이라는 뜻은 아닙니다)"))
        for other, reason in list(wanted_additions):
            if _addable(other, factors, scope) and scope.allow(other, ADD, reason):
                changed = True
                for companion in companions_for(other):
                    if companion not in factors:
                        wanted_additions.append((companion, f"{other}의 짝입니다"))

    # 집계 단계 배치 후보. 값은 그대로 두고 자리만 옮긴다.
    if "aggregation" in factors and ADD in scope.ops("rollup"):
        scope.allow("aggregation", MOVE,
                    "구간 안 집계로 적은 값이 구간별 결과의 집계라면 rollup으로 옮길 수 있습니다")
    if "aggregation" not in factors and REMOVE in scope.ops("rollup") and "rollup" in factors:
        scope.allow("rollup", MOVE, "rollup으로 적은 값이 그룹 안 집계라면 aggregation으로 옮길 수 있습니다")
    return scope


# -- 적용 -------------------------------------------------------------------


class ScopeViolation(ValueError):
    """수정안이 수정 범위를 벗어났거나 확인할 수 없다. ``record``에 제안·적용·막힌 변경을 남긴다."""

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


def _format(name, value):
    """계약상 같은 표현: 정수 factor를 숫자 문자열로 적은 것("1")은 정수다(k36 기록)."""
    spec = FACTOR_SPECS.get(name)
    if spec is not None and spec.kind == "integer" and isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


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


def _occurrences(text, span):
    found, start = [], text.find(span) if span else -1
    while start >= 0:
        found.append((start, start + len(span)))
        start = text.find(span, start + 1)
    return found


def check_stage_evidence(question, evidence, stages, *, disjoint):
    """새로 적은 집계 값마다 모델이 옮겨 적은 질문 표현이 질문에 있는지(문자열 사실만) 확인한다.

    ``disjoint``이면(같은 값을 두 단계에 적은 경우) 두 단계의 표현이 **같은 문자열**이고 질문의 서로 겹치지 않는
    두 자리에 있어야 한다. 서로 다른 문자열 두 개("월별", "가장 큰 값")는 같은 집계 표현이 두 번 있다는 사실이
    아니다(1b4a173 실측 t01c). 확인하지 못한 단계 목록을 돌려준다. 표현의 뜻은 보지 않는다.
    """
    evidence = evidence if isinstance(evidence, dict) else {}
    spans = {stage: (evidence.get(stage) or "").strip() if isinstance(evidence.get(stage), str) else ""
             for stage in stages}
    missing = [stage for stage, span in spans.items() if not _occurrences(question, span)]
    if missing or not disjoint or len(stages) < 2:
        return missing
    first, second = (spans[stage] for stage in stages)
    if first != second:
        return list(stages)
    for a_start, a_end in _occurrences(question, first):
        for b_start, b_end in _occurrences(question, second):
            if a_end <= b_start or b_end <= a_start:
                return []
    return list(stages)


def apply_correction(base, proposal, scope, *, question="", evidence=None):
    """수정안(고친 뒤의 결과 형태)을 범위 안에서만 적용한다. (결과 factor, 기록)을 돌려준다."""
    proposal = {name: _format(name, value) for name, value in dict(proposal or {}).items()}
    result = dict(base)
    shape = RESULT_SHAPE_FACTORS + ("time",)
    record = {"scope": scope.to_dict(), "applied": {"added": {}, "changed": {}, "removed": {}},
              "kept_omitted": [], "blocked": [],
              # 결과 형태의 전후와 모델 수정안. 전후 비교(어떤 순위·개수·그룹·답 대상·집계 단계가 바뀌었나)의 근거다.
              "before": {name: base[name] for name in shape if name in base},
              "proposed": {name: value for name, value in proposal.items() if name in shape},
              "evidence": evidence if isinstance(evidence, dict) else None}

    def block(name, why):
        record["blocked"].append({"factor": name, "reason": why,
                                  "base": base.get(name), "proposed": proposal.get(name)})

    def omitted_or_null(name):
        return name not in proposal or _absent(name, proposal[name])

    # 1. 집계 단계가 아닌 factor: 범위 안에서만 적용하고, 범위 밖은 빠져도 남긴다.
    for name, value in proposal.items():
        if name in STAGES:
            continue
        ops = scope.ops(name)
        present = name in base
        if _absent(name, value):
            if present and REMOVE not in ops:
                block(name, "뺄 수 없는 조건을 빼려 했습니다")
            continue
        if present and _same(name, value, base[name]):
            continue
        if not present:
            if ADD in ops:
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
        if name in STAGES or not omitted_or_null(name):
            continue
        if REMOVE in scope.ops(name):
            result.pop(name, None)
            record["applied"]["removed"][name] = base[name]
        elif name not in proposal and name in RESULT_SHAPE_FACTORS:
            # 수정 범위 밖 조건이 응답에서 빠진 것은 삭제가 아니다.
            record["kept_omitted"].append(name)

    # 2. 집계 단계(aggregation, rollup). 값마다 수정 전에서 이어진 값인지 새로 적은 값인지 가른다.
    def writable(stage):
        other = "rollup" if stage == "aggregation" else "aggregation"
        return bool(scope.ops(stage) & {ADD, MOVE, RESELECT, CHANGE}) or MOVE in scope.ops(other)

    staged = {}
    for stage in STAGES:
        ops = scope.ops(stage)
        if stage in proposal and not _absent(stage, proposal[stage]):
            value = proposal[stage]
            if stage in base and _same(stage, value, base[stage]):
                staged[stage] = base[stage]
            elif writable(stage):
                staged[stage] = value
            else:
                block(stage, "바꿀 수 없는 집계 단계의 값을 적었습니다" if stage in base
                      else "새로 적을 수 없는 집계 단계를 적었습니다")
                if stage in base:
                    staged[stage] = base[stage]
        elif stage in base:
            if ops & {REMOVE, MOVE, RESELECT, CHANGE}:
                continue                                # 뺐다(옮겼는지는 아래에서 본다)
            staged[stage] = base[stage]
            if stage not in proposal:
                record["kept_omitted"].append(stage)
            else:
                block(stage, "뺄 수 없는 집계 단계를 빼려 했습니다")
    # 수정 전 값이 수정 뒤 어디에 남았는지 맞춘다(같은 단계 우선). 남은 값은 "버린 값", 맞지 않은 값은 "새 값"이다.
    remaining = {stage: base[stage] for stage in STAGES if stage in base}
    carried, new = {}, []
    for stage in STAGES:
        if stage in staged and remaining.get(stage) == staged[stage]:
            carried[stage] = stage
            remaining.pop(stage)
    for stage in STAGES:
        if stage in staged and stage not in carried:
            source = next((other for other, value in remaining.items() if value == staged[stage]), None)
            if source is not None:
                carried[stage] = source
                remaining.pop(source)
            else:
                new.append(stage)
    for stage, value in remaining.items():
        if not scope.ops(stage) & {REMOVE, CHANGE}:
            block(stage, f"{stage}={value!r} 값을 다른 단계로 옮기지 않고 버렸습니다")
    for stage in STAGES:
        if staged.get(stage) != base.get(stage):
            if stage in staged:
                result[stage] = staged[stage]
                if stage in base:
                    record["applied"]["changed"][stage] = {"from": base[stage], "to": staged[stage]}
                else:
                    record["applied"]["added"][stage] = staged[stage]
            else:
                result.pop(stage, None)
                record["applied"]["removed"][stage] = base[stage]
    record["stage_values"] = {"carried": carried, "new": new}

    # 새로 적은 집계 값. 코드가 확인할 수 있는 것과 없는 것을 가른다.
    # - 구간 안 집계(aggregation)의 새 값: 받지 않는다. 계약이 요구하지 않고(미지정이 유효한 표현이다), 근거 문자열과 값의
    #   관계를 코드가 확인할 수 없으며, 모델이 지어내는 것이 관측된 경로다(g44; c2a0e2c 대조 셋 s01d는 "월별 수입"을
    #   근거로 sum을 지어냈다). 실행하지 않고 구간 안 집계를 확인받는다.
    # - 같은 값을 두 단계에 적음: 첫 grounding이 그 집계로 읽은 표현이 질문에 따로 두 번 있는지(문자열 사실)만 본다.
    # - rollup의 새 값(계약이 요구하는 짝): 근거 문자열이 질문에 있는지만 본다. 뜻은 확인하지 않는다.
    unverified = []
    if new:
        same_value = len(staged) == 2 and staged["aggregation"] == staged["rollup"]
        if "aggregation" in new and not same_value:
            unverified = ["aggregation"]
            record["evidence_check"] = {
                "needed": ["aggregation"], "unverified": unverified,
                "note": "구간 안 집계의 새 값은 재질의로 받지 않는다. 질문에서 확인할 방법이 없다."}
        else:
            needed = list(STAGES) if same_value else new
            unverified = check_stage_evidence(question, evidence, needed, disjoint=same_value)
            record["evidence_check"] = {"needed": needed, "unverified": unverified,
                                        "note": "문자열이 질문에 있는지만 확인했다. 그 표현의 뜻은 확인하지 않았다."}

    def exclusive(factors):
        # 허용값이 아닌 bucket(예: dayofweek)은 아직 구간이 아니다. 성립하는 구간과의 충돌만 센다.
        return (factors.get("bucket") in FACTOR_SPECS["bucket"].values
                and any(name in factors for name in EXCLUSIVE_WITH_BUCKET))

    if exclusive(result) and not exclusive(base):
        block("bucket", "주·월 구간과 함께 쓸 수 없는 그룹·순위가 남는 수정입니다")

    before, after = roles(base), roles(result)
    record["roles"] = {"before": before, "after": after}
    record["after"] = {name: result[name] for name in shape if name in result}
    if before["grouping"] and not after["grouping"]:
        block("grouping", "구간·그룹 기준이 모두 사라집니다")
    moved_into_aggregation = carried.get("aggregation") == "rollup"
    if before["direction"] and after["direction"] != before["direction"] and not moved_into_aggregation:
        block("direction", f"순위 방향이 {before['direction']}에서 {after['direction'] or '없음'}으로 바뀝니다")

    if record["blocked"]:
        raise ScopeViolation(
            "수정 범위를 벗어났습니다: "
            + "; ".join(f"{item['factor']}: {item['reason']}" for item in record["blocked"]),
            record,
        )
    if unverified:
        # 계약 안의 수정이지만 새 집계 값을 확인할 수 없다. 실행하지 않고 확정하지 못한 단계를 확인받는다.
        record["terminal"] = {
            "code": UNVERIFIED_INNER if unverified == ["aggregation"] else UNVERIFIED_STAGE,
            "unverified_stages": unverified,
            "reason": "재질의가 적은 집계 값의 근거 표현을 질문에서 확인하지 못했습니다",
        }
        raise ScopeViolation("새로 적은 집계 값의 근거를 질문에서 확인하지 못했습니다: "
                             + ", ".join(unverified), record)
    if result == base:
        raise ScopeViolation("바뀐 조건이 없습니다.", record)
    return result, record


def describe_scope(scope, factors):
    """재질의 문구의 수정 범위 설명. 허용 동작과 근거를 factor마다 적는다."""
    labels = {REMOVE: "뺄 수 있음", CHANGE: "값을 바꿀 수 있음", ADD: "새로 적을 수 있음",
              MOVE: "같은 값을 다른 집계 단계로 옮길 수 있음",
              RESELECT: "구간을 고르는 방향(max·min)으로 다시 고를 수 있음"}
    lines = []
    for name in scope.editable:
        ops = scope.ops(name)
        current = f"지금 {factors[name]!r}" if name in factors else "지금 없음"
        how = ", ".join(labels[op] for op in (REMOVE, CHANGE, ADD, MOVE, RESELECT) if op in ops)
        why = "; ".join(dict.fromkeys(scope.reasons.get(name, ())))
        if not ops:
            how, why = "다른 집계 단계에서 옮긴 값만 받을 수 있음", "새 값을 만들지 않습니다"
        lines.append(f"- {name} ({current}): {how}. {why}")
    return "\n".join(lines)


def opens_stage_values(scope):
    """수정 범위가 집계 단계에 값을 적거나 옮기는 것을 여는가. 재질의 문구의 집계 단계 지침을 이때만 보인다."""
    return bool(scope.ops("rollup") & {ADD, MOVE, RESELECT} or scope.ops("aggregation") & {MOVE, ADD})


STAGE_GUIDANCE = """- 구간 안 집계(aggregation)와 구간별 결과의 집계(rollup)는 질문에서 따로 읽습니다. 질문의 집계 표현
  하나는 한 단계에만 해당합니다. 두 단계에 같은 집계가 필요하면 질문에 같은 표현이 따로 두 번 있습니다.
- aggregation에는 새 값을 적지 않습니다. 지금 값을 그대로 두거나 rollup으로 옮기기만 합니다. 구간 안 집계가
  질문에 있는데 빠졌다면 비워 두세요. 사용자에게 확인합니다.
- rollup에 새 값을 적거나 같은 값을 두 단계에 적으면, 그 값이 나온 질문 표현을 evidence에 질문 그대로 옮겨
  적습니다. 두 단계에 같은 값을 적으면 단계마다 같은 표현을 적습니다.
  예: {"factors": {...}, "evidence": {"rollup": "<질문 표현>"}}"""


def stage_guidance(scope):
    return STAGE_GUIDANCE if opens_stage_values(scope) else ""


def kept_factors(scope, factors):
    """수정 범위 밖이라 그대로 남는 결과 형태 factor."""
    return {name: factors[name] for name in RESULT_SHAPE_FACTORS
            if name in factors and name not in scope.permissions}
