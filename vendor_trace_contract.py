# -*- coding: utf-8 -*-
"""업체 gold trace contract 로딩과 실행 trace 판정.

업체 자료의 "정답 Tool" 설명은 default argument까지 나열한 strict specification이
아니므로 exact equality로 비교하지 않는다. 대신 필수 argument, 허용 argument,
금지 argument, 결과 의존성(binding)을 각각 판정한다.

평가 로직에 질문별 분기를 두지 않는다. 판정 기준은 전부 gold YAML에서 온다.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_GOLD_FILE = (
    Path(__file__).resolve().parent / "evaluation" / "vendor"
    / "vendor_trace_gold.yaml"
)


class Failure:
    """업체가 지적한 오류 유형과 대응되는 실패 분류."""

    TOOL_SEQUENCE_MISMATCH = "TOOL_SEQUENCE_MISMATCH"
    MISSING_REQUIRED_ARGUMENT = "MISSING_REQUIRED_ARGUMENT"
    WRONG_ARGUMENT_VALUE = "WRONG_ARGUMENT_VALUE"
    FORBIDDEN_ARGUMENT = "FORBIDDEN_ARGUMENT"
    UNGROUNDED_ARGUMENT = "UNGROUNDED_ARGUMENT"
    DEPENDENCY_BINDING_MISMATCH = "DEPENDENCY_BINDING_MISMATCH"
    SCOPE_PROVENANCE_VIOLATION = "SCOPE_PROVENANCE_VIOLATION"
    UNEXPECTED_RETRY = "UNEXPECTED_RETRY"
    EXECUTION_ERROR = "EXECUTION_ERROR"


_SCOPE_PATTERN = re.compile(r"scope:[A-Za-z0-9_:.-]+")
_TIME_TEXT = re.compile(r"^(\d{2}):?(\d{2})(?::?(\d{2}))?$")


def normalize_value(value):
    """업체 표기와 Tool canonical 표기의 차이를 흡수한다.

    예: "12:00~13:00" → "120000-130000", "edge:1742" → "scope:edge:1742".
    scope 값을 새로 만들어내지는 않고 표기만 canonical로 맞춘다.
    """
    if isinstance(value, bool) or not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return text
    if text.startswith("edge:") or text.startswith("district:") or text.startswith("h3:"):
        return f"scope:{text}"
    if "~" in text or "-" in text:
        parts = re.split(r"[~-]", text)
        if len(parts) == 2:
            converted = [_normalize_clock(part) for part in parts]
            if all(converted):
                return f"{converted[0]}-{converted[1]}"
    return text


def _normalize_clock(text):
    matched = _TIME_TEXT.fullmatch(text.strip())
    if not matched:
        return None
    hour, minute, second = matched.group(1), matched.group(2), matched.group(3)
    return f"{hour}{minute}{second or '00'}"


@dataclass
class StepContract:
    """gold trace의 Tool 호출 한 단계."""

    tool: str
    id: str | None = None
    required_args: dict[str, Any] = field(default_factory=dict)
    optional_args: tuple[str, ...] = ()
    forbidden_args: tuple[str, ...] = ()
    required_bindings: dict[str, dict] = field(default_factory=dict)
    must_succeed: bool = True
    allow_retry: bool = False

    @property
    def allowed_args(self):
        return set(self.required_args) | set(self.optional_args) | set(
            self.required_bindings
        )


@dataclass
class CaseContract:
    """질문 하나의 acceptance contract."""

    id: str
    steps: list[StepContract]
    vendor_verdict: str = ""
    note: str = ""
    forbidden_args: tuple[str, ...] = ()
    grounded_args: tuple[str, ...] = ()
    max_failed_calls: int = 0

    @property
    def tool_sequence(self):
        return [step.tool for step in self.steps]


def load_gold(path=DEFAULT_GOLD_FILE):
    """gold YAML을 읽고 구조 계약을 검증한다."""
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path}: cases가 비어 있습니다.")

    loaded: dict[str, CaseContract] = {}
    for entry in cases:
        steps = []
        seen_ids = set()
        for index, raw in enumerate(entry.get("steps") or []):
            if "tool" not in raw:
                raise ValueError(f"{entry['id']}.steps[{index}]: tool이 없습니다.")
            step_id = raw.get("id")
            if step_id is not None:
                if step_id in seen_ids:
                    raise ValueError(
                        f"{entry['id']}: step id가 중복되었습니다: {step_id}"
                    )
                seen_ids.add(step_id)
            steps.append(StepContract(
                tool=raw["tool"],
                id=step_id,
                required_args=dict(raw.get("required_args") or {}),
                optional_args=tuple(raw.get("optional_args") or ()),
                forbidden_args=tuple(raw.get("forbidden_args") or ()),
                required_bindings=dict(raw.get("required_bindings") or {}),
                must_succeed=bool(raw.get("must_succeed", True)),
                allow_retry=bool(raw.get("allow_retry", False)),
            ))
        if not steps:
            raise ValueError(f"{entry['id']}: steps가 비어 있습니다.")

        for step in steps:
            for argument, binding in step.required_bindings.items():
                source = binding.get("from_step")
                if source not in seen_ids:
                    raise ValueError(
                        f"{entry['id']}.{step.tool}.{argument}: 알 수 없는 "
                        f"from_step입니다: {source}"
                    )

        loaded[entry["id"]] = CaseContract(
            id=entry["id"],
            steps=steps,
            vendor_verdict=str(entry.get("vendor_verdict", "")),
            note=str(entry.get("note", "")).strip(),
            forbidden_args=tuple(entry.get("forbidden_args") or ()),
            grounded_args=tuple(entry.get("grounded_args") or ()),
            max_failed_calls=int(entry.get("max_failed_calls", 0)),
        )
    return loaded


def _is_error(result):
    return isinstance(result, dict) and result.get("status") == "ERROR"


def analysis_calls(hop_log):
    """표시용 labeling 호출을 제외한 분석 단계 Tool 호출만 추린다."""
    return [
        entry for entry in (hop_log or [])
        if entry.get("phase") != "labeling"
    ]


def _value_matches(expected, actual, question):
    """gold 값 표기와 실제 argument 값을 semantic하게 비교한다."""
    actual_norm = normalize_value(actual)
    if isinstance(expected, dict):
        if "any_of" in expected:
            return any(
                normalize_value(item) == actual_norm
                for item in expected["any_of"]
            )
        if "user_literal" in expected:
            literal = normalize_value(expected["user_literal"])
            # 사용자 발화에 실제로 있는 값이어야 한다. 보정해서 만들면 안 된다.
            return actual_norm == literal and literal in question
        return False
    return normalize_value(expected) == actual_norm


def evaluate_case(contract: CaseContract, question, hop_log, runtime_error=None):
    """실행 trace를 gold contract와 대조해 실패 목록을 만든다."""
    problems: list[dict] = []

    def fail(category, message, **context):
        problems.append({
            "category": category,
            "message": message,
            "context": context,
        })

    calls = analysis_calls(hop_log)
    if runtime_error:
        fail(Failure.EXECUTION_ERROR, f"실행이 실패했습니다: {runtime_error}")

    succeeded = [call for call in calls if not _is_error(call.get("result"))]
    failed = [call for call in calls if _is_error(call.get("result"))]

    if len(failed) > contract.max_failed_calls:
        fail(
            Failure.UNEXPECTED_RETRY,
            f"실패한 Tool 호출이 {len(failed)}회로 허용치"
            f"({contract.max_failed_calls})를 넘었습니다.",
            failed=[call.get("tool") for call in failed],
        )

    # 모든 호출(실패 포함)에 대한 case 단위 규칙
    question_norm = question.replace(" ", "")
    for call in calls:
        arguments = call.get("arguments") or {}
        for argument in contract.forbidden_args:
            if argument in arguments:
                fail(
                    Failure.FORBIDDEN_ARGUMENT,
                    f"{call.get('tool')}에 질문 근거가 없는 {argument}="
                    f"{arguments[argument]!r}가 있습니다.",
                    tool=call.get("tool"), argument=argument,
                )
        for argument in contract.grounded_args:
            value = arguments.get(argument)
            if not isinstance(value, str) or not value.strip():
                continue
            if value.replace(" ", "") not in question_norm:
                fail(
                    Failure.UNGROUNDED_ARGUMENT,
                    f"{call.get('tool')}의 {argument}={value!r}가 질문에 "
                    "없는 값입니다.",
                    tool=call.get("tool"), argument=argument, value=value,
                )
        for value in (arguments or {}).values():
            if isinstance(value, str) and _SCOPE_PATTERN.fullmatch(value):
                known = _SCOPE_PATTERN.findall(question)
                produced = [
                    call2.get("result") for call2 in calls
                    if isinstance(call2.get("result"), str)
                ]
                if value not in known and value not in produced:
                    fail(
                        Failure.SCOPE_PROVENANCE_VIOLATION,
                        f"{call.get('tool')}에 출처 불명 scope {value}가 "
                        "전달되었습니다.",
                        tool=call.get("tool"), scope=value,
                    )

    # Tool 순서 비교는 성공한 호출 기준이다. 장소 복구 재시도는 위에서 따로 센다.
    actual_sequence = [call.get("tool") for call in succeeded]
    if actual_sequence != contract.tool_sequence:
        fail(
            Failure.TOOL_SEQUENCE_MISMATCH,
            f"Tool 순서가 다릅니다. 기대 {contract.tool_sequence}, "
            f"실제 {actual_sequence}",
            expected=contract.tool_sequence, actual=actual_sequence,
        )
        return problems, {"expected": contract.tool_sequence,
                          "actual": actual_sequence}

    results_by_step: dict[str, Any] = {}
    for step, call in zip(contract.steps, succeeded):
        arguments = call.get("arguments") or {}
        if step.id:
            results_by_step[step.id] = call.get("result")

        for argument, expected in step.required_args.items():
            if argument not in arguments:
                fail(
                    Failure.MISSING_REQUIRED_ARGUMENT,
                    f"{step.tool}에 필수 argument {argument}가 없습니다.",
                    tool=step.tool, argument=argument,
                )
            elif not _value_matches(expected, arguments[argument], question):
                fail(
                    Failure.WRONG_ARGUMENT_VALUE,
                    f"{step.tool}.{argument} 값이 다릅니다. 기대 "
                    f"{expected!r}, 실제 {arguments[argument]!r}",
                    tool=step.tool, argument=argument,
                    expected=expected, actual=arguments[argument],
                )

        for argument in step.forbidden_args:
            if argument in arguments:
                fail(
                    Failure.FORBIDDEN_ARGUMENT,
                    f"{step.tool}에 있으면 안 되는 {argument}="
                    f"{arguments[argument]!r}가 있습니다.",
                    tool=step.tool, argument=argument,
                )

        for argument, binding in step.required_bindings.items():
            source = binding["from_step"]
            if argument not in arguments:
                fail(
                    Failure.MISSING_REQUIRED_ARGUMENT,
                    f"{step.tool}에 {argument}가 없습니다. "
                    f"{source} 결과와 연결되어야 합니다.",
                    tool=step.tool, argument=argument,
                )
                continue
            expected_value = results_by_step.get(source)
            if expected_value is None or arguments[argument] != expected_value:
                fail(
                    Failure.DEPENDENCY_BINDING_MISMATCH,
                    f"{step.tool}.{argument}가 {source} 단계의 결과와 "
                    f"다릅니다. 기대 {expected_value!r}, "
                    f"실제 {arguments[argument]!r}",
                    tool=step.tool, argument=argument, from_step=source,
                    expected=expected_value, actual=arguments[argument],
                )

        if step.must_succeed and _is_error(call.get("result")):
            fail(
                Failure.EXECUTION_ERROR,
                f"{step.tool} 호출이 실패했습니다.",
                tool=step.tool,
            )

    return problems, {"expected": contract.tool_sequence,
                      "actual": actual_sequence}
