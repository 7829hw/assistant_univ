# -*- coding: utf-8 -*-
"""GeoFlow Planner (Concept Grounder).

Planner LLM은 Tool Call을 생성하지 않고, 질문 유형도 고르지 않는다. 반환하는
것은 질문 표현의 **의미 grounding**뿐이다. 즉 어떤 core concept / subtype /
functional role에 해당하는지와 조건(factor)이다.

어떤 조각을 어떤 순서로 이어 붙일지는 composer가, 어떤 Tool을 부를지는
operator mapping이 정한다. Planner 출력은 전부 untrusted input으로 취급해
프로그램이 검증한다.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from build import BuildError, build_prompt

from geoflow.errors import PlannerError
from geoflow.factors import FACTOR_SPECS
from geoflow.grounding import drop_unsupported_regions, parse_grounding
from geoflow.operator_registry import OPERATORS

DEFAULT_PLANNER_PROMPT = (
    Path(__file__).resolve().parent.parent / "prompts" / "geoflow_planner.yaml"
)

#: 지원 범위 밖임을 Planner가 스스로 밝힐 때 쓰는 평가 라벨.
NO_TEMPLATE = "NONE"

#: 지원 범위 밖임을 밝히는 출력 key. ``{"unsupported": true}`` 하나만 보낸다.
UNSUPPORTED_KEY = "unsupported"

#: Planner 호출 1회당 총 시도 횟수(최초 호출 + 재시도).
DEFAULT_MAX_ATTEMPTS = 2

#: 재시도 대상 오류. 생성이 끝나지 않았거나 읽을 수 없는 응답만 해당한다.
#: 같은 입력이라도 다시 부르면 끝나는 경우가 관측되어 재시도가 의미를 갖는다.
#: 반대로 grounding 판단이 어긋난 출력은 다시 불러도 같은 결과이므로
#: 재시도하지 않고 그대로 올린다.
RETRYABLE_CODES = frozenset({
    "PLANNER_CALL_FAILED",
    "EMPTY_RESPONSE",
    "OUTPUT_TRUNCATED",
})

#: 계약에 없지만 모델이 습관적으로 덧붙이는 설명 key. 값은 사용하지 않는다.
IGNORABLE_KEYS = frozenset({
    "reason", "reasoning", "explanation", "note", "notes", "thought",
})

_VOCABULARY_HEADING = "[분석 개체와 측정값]"
_FACTOR_HEADING = "[사용 가능한 factor]"


@dataclass
class PlannerOutput:
    """Planner 1회 호출의 결과와 계측값."""

    grounding: Any
    raw_text: str = ""
    duration_ms: float = 0.0
    model: str | None = None
    attempts: int = 1

    @property
    def concepts(self):
        return self.grounding.concepts

    @property
    def factors(self):
        return self.grounding.factors

    def to_dict(self):
        return {
            "grounding": self.grounding.to_dict(),
            "raw_text": self.raw_text,
            "duration_ms": self.duration_ms,
            "model": self.model,
            "attempts": self.attempts,
        }


def load_planner_prompt(path=DEFAULT_PLANNER_PROMPT):
    """기존 build.build_prompt를 그대로 재사용해 section을 결합한다."""
    try:
        return build_prompt(Path(path)).strip()
    except BuildError as error:
        raise PlannerError(
            f"Planner prompt를 만들 수 없습니다: {error}",
            code="PROMPT_BUILD_FAILED",
            context={"path": str(path)},
        ) from error


def load_repair_instruction(path=DEFAULT_PLANNER_PROMPT):
    """재계획 요청문을 YAML 최상위 key에서 읽는다.

    ``sections``가 아니므로 System Prompt에는 포함되지 않는다.
    """
    try:
        document = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise PlannerError(
            f"Planner prompt YAML을 읽을 수 없습니다: {path}\n{error}",
            code="PROMPT_BUILD_FAILED",
            context={"path": str(path)},
        ) from error
    instruction = document.get("repair_instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        raise PlannerError(
            f"{Path(path).name}: repair_instruction이 비어 있습니다.",
            code="PROMPT_BUILD_FAILED",
            context={"path": str(path)},
        )
    return instruction.strip()


def describe_vocabulary():
    """측정값 어휘를 operator registry에서 직접 만든다.

    Prompt에 손으로 적어 두면 Tool이 늘어날 때 조용히 어긋난다. 어떤 사건에서
    어떤 측정값을 얻을 수 있는지는 registry가 이미 알고 있으므로 그대로 읽는다.
    """
    lines = []
    for spec in sorted(OPERATORS.values(), key=lambda item: item.name):
        events = sorted(spec.event_subtypes)
        if not events or spec.output is None:
            continue
        outputs = ", ".join(
            f"{concept.value}/{subtype}"
            for concept, subtype in sorted(
                spec.output.allowed, key=lambda item: item[1]
            )
        )
        for event in events:
            lines.append(f"- EVENT/{event} → {outputs}")
    return "\n".join(sorted(set(lines)))


def describe_factors():
    """사용 가능한 factor 이름과 값 형식을 정의에서 만든다."""
    lines = []
    for name, spec in sorted(FACTOR_SPECS.items()):
        if spec.values:
            shape = " | ".join(sorted(spec.values))
        elif spec.kind == "boolean":
            shape = "true | false"
        elif spec.kind == "integer":
            shape = "정수"
        else:
            shape = spec.pattern.pattern if spec.pattern else "문자열"
        lines.append(f"- {name}: {shape}")
    return "\n".join(lines)


class GeoFlowPlanner:
    """질문을 concept grounding으로 바꾸는 단일 LLM 호출 단계."""

    def __init__(
        self,
        *,
        client,
        prompt=None,
        model=None,
        repair_instruction=None,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
    ):
        if max_attempts < 1:
            raise ValueError(f"max_attempts는 1 이상이어야 합니다: {max_attempts}")
        self.max_attempts = max_attempts
        self.client = client
        self.base_prompt = (
            load_planner_prompt() if prompt is None else prompt.strip()
        )
        self.repair_instruction = (
            load_repair_instruction() if repair_instruction is None
            else repair_instruction.strip()
        )
        self.model = model if model is not None else getattr(client, "model", None)

    def system_prompt(self):
        """어휘를 정의에서 직접 만들어 prompt 표류를 막는다."""
        return "\n\n".join([
            self.base_prompt,
            f"{_VOCABULARY_HEADING}\n{describe_vocabulary()}",
            f"{_FACTOR_HEADING}\n{describe_factors()}",
        ])

    def messages(self, question):
        return [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": question},
        ]

    def plan(self, question):
        """Planner를 1회 호출하고 검증된 ``PlannerOutput``을 반환한다."""
        return self._ask(self.messages(question), question)

    def repair(self, question, previous, failure):
        """Tool 오류를 알려주고 실패한 개념의 값만 고쳐 받는다.

        재계획 결과도 grounding/composer/validator/compiler 전 경로를 다시
        통과하므로 어떤 guard도 우회하지 않는다.
        """
        instruction = _fill_instruction(self.repair_instruction, {
            "concept": failure.get("concept", "(알 수 없음)"),
            "name": failure.get("name", ""),
            "region": failure.get("region", ""),
            "message": failure.get("message", "Tool 오류"),
        })
        output = self._ask(
            [
                *self.messages(question),
                {
                    "role": "assistant",
                    "content": json.dumps(
                        previous.grounding.to_dict(), ensure_ascii=False,
                    ),
                },
                {"role": "user", "content": instruction},
            ],
            question,
        )
        changed = _changed_structure(previous.grounding, output.grounding)
        if changed:
            raise PlannerError(
                f"재계획이 개념 구조를 바꿨습니다: {changed}. "
                "값만 수정해야 합니다.",
                code="REPAIR_CHANGED_STRUCTURE",
                context={"raw_text": output.raw_text},
            )
        keep_untouched_values(
            previous.grounding, output.grounding, failure.get("concept"),
        )
        drop_invented_regions(previous.grounding, output.grounding)
        if _same_values(previous.grounding, output.grounding):
            raise PlannerError(
                "재계획이 같은 값을 그대로 반복했습니다.",
                code="REPAIR_NO_CHANGE",
                context={"raw_text": output.raw_text},
            )
        return output

    def _ask(self, messages, question):
        """호출이 응답을 반환하지 못하면 정해진 횟수까지 다시 부른다.

        작은 모델이 thinking 안에서 같은 문장을 반복하다 생성을 끝내지 못하는
        경우가 관측되었고, 같은 입력이라도 다시 부르면 끝나는 경우가 있다.
        재시도 대상은 ``RETRYABLE_CODES``로 한정한다.
        """
        started_at = time.perf_counter()
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                output = self._ask_once(messages, question)
            except PlannerError as error:
                if error.code not in RETRYABLE_CODES:
                    raise
                last_error = error
                continue
            output.duration_ms = _elapsed_ms(started_at)
            output.attempts = attempt
            return output
        last_error.context["attempts"] = self.max_attempts
        last_error.context["duration_ms"] = _elapsed_ms(started_at)
        raise last_error

    def _ask_once(self, messages, question):
        try:
            # tools를 전달하지 않아 Tool Calling 자체를 불가능하게 만든다.
            body = self.client.chat(messages)
        except Exception as error:  # noqa: BLE001 - client 오류를 단계 오류로 변환
            raise PlannerError(
                f"Planner 모델 호출에 실패했습니다: {type(error).__name__}: {error}",
                code="PLANNER_CALL_FAILED",
                context={"model": self.model},
            ) from error

        _reject_truncated(body, self.model)
        text = _response_text(body)
        payload = parse_planner_json(text)
        grounding = self._validate_payload(payload, text, question)
        return PlannerOutput(
            grounding=grounding,
            raw_text=text,
            model=self.model,
        )

    def _validate_payload(self, payload, text, question):
        """Planner 출력이 grounding 계약을 만족하는지 확인한다."""
        unknown = sorted(
            set(payload)
            - {"concepts", "factors", UNSUPPORTED_KEY}
            - IGNORABLE_KEYS
        )
        if unknown:
            raise PlannerError(
                f"Planner 출력에 허용되지 않은 key가 있습니다: "
                f"{', '.join(unknown)}",
                code="UNKNOWN_KEY",
                context={"raw_text": text},
            )

        if payload.get(UNSUPPORTED_KEY):
            raise PlannerError(
                "질문을 현재 지원하는 분석 개념으로 표현할 수 없습니다.",
                user_message=(
                    "현재 지원하는 분석 유형으로는 이 질문을 처리할 수 없습니다."
                ),
                code="UNSUPPORTED_QUESTION",
                context={"raw_text": text},
            )

        grounding = parse_grounding(payload, question, raw_text=text)
        # 발화에 없는 상위 지역은 조회를 어긋나게 만들 뿐이므로 덜어 낸다.
        # 거부가 아니라 제거로 처리하는 이유는 drop_invented_regions와 같다.
        drop_unsupported_regions(grounding)
        return grounding


#: 재계획 요청문에서 치환할 자리표시자. 그 밖의 중괄호는 그대로 둔다.
_INSTRUCTION_FIELDS = ("concept", "name", "region", "message")


def _fill_instruction(template, values):
    """지정한 자리표시자만 치환한다.

    ``str.format``을 쓰면 요청문에 넣은 JSON 예시의 중괄호까지 자리표시자로
    해석된다. 요청문에 JSON을 보여 주는 편이 모델에게 더 분명하므로,
    치환 쪽을 제한한다.
    """
    filled = template
    for field_name in _INSTRUCTION_FIELDS:
        filled = filled.replace(
            "{" + field_name + "}", str(values.get(field_name, "")),
        )
    return filled


def _values_of(grounding):
    return {item.id: item.value for item in grounding.concepts}


def _structure_of(grounding):
    """값을 뺀 개념 구조. 재계획이 바꾸면 안 되는 부분이다."""
    return {
        item.id: (item.concept, item.subtype, item.role, item.od_role)
        for item in grounding.concepts
    }, dict(grounding.factors)


def _changed_structure(previous, repaired):
    """재계획이 개념/역할/조건을 바꿨는지 본다.

    고쳐야 할 것은 조회에 실패한 이름 하나뿐이다. 그 김에 측정 대상이나
    조건까지 바꾸면 사용자가 묻지 않은 질문에 답하게 된다.
    """
    previous_nodes, previous_factors = _structure_of(previous)
    repaired_nodes, repaired_factors = _structure_of(repaired)
    if previous_nodes != repaired_nodes:
        added = sorted(set(repaired_nodes) - set(previous_nodes))
        removed = sorted(set(previous_nodes) - set(repaired_nodes))
        changed = sorted(
            key for key in set(previous_nodes) & set(repaired_nodes)
            if previous_nodes[key] != repaired_nodes[key]
        )
        return "; ".join(filter(None, [
            f"추가된 개념: {', '.join(added)}" if added else "",
            f"사라진 개념: {', '.join(removed)}" if removed else "",
            f"바뀐 개념: {', '.join(changed)}" if changed else "",
        ]))
    if previous_factors != repaired_factors:
        return "조건(factor)이 바뀌었습니다."
    return ""


def _same_values(previous, repaired):
    return _values_of(previous) == _values_of(repaired)


def keep_untouched_values(previous, repaired, failed_id):
    """조회에 실패한 개념 외에는 재계획 결과를 받아들이지 않는다.

    재계획 요청은 접미사를 뗀 이름을 시도하라고 알려 주는데, 모델이 그 규칙을
    다른 개념에까지 적용해 이미 조회에 성공한 이름을 망가뜨리는 경우가 있다.

        origin "동성로동" → "동성로"   (고쳐야 할 개념. 올바른 수정)
        destination "신천동" → "신천"  (건드리면 안 되는 개념. 조회가 깨진다)

    고칠 대상은 오류가 난 개념 하나뿐이므로 나머지는 직전 값을 그대로 둔다.
    어느 개념이 실패했는지 알 수 없을 때만 재계획 결과를 그대로 받는다.
    """
    previous_values = _values_of(previous)
    if failed_id not in previous_values:
        return repaired
    for concept in repaired.concepts:
        if concept.id != failed_id and concept.id in previous_values:
            concept.value = previous_values[concept.id]
    return repaired


def drop_invented_regions(previous, repaired):
    """재계획이 새로 만들어낸 상위 지역을 제거한다.

    최초 grounding이 이미 질문에서 region을 추출했으므로, 장소 조회가
    실패한 뒤에야 처음 나타난 region은 정의상 사용자가 말한 값이 아니라
    모델의 추측이다. 실제로 관측된 사례가 두 가지다.

        "대구시의 평균 택시 요금은?"  → name=대구, region=경상북도
        "대구시의 평균 택시 요금은?"  → name=대구, region=시

    앞의 것은 존재하지 않는 상위 지역을 지어낸 것이고, 뒤의 것은 행정구역
    접미사를 지역으로 승격시킨 것이다. 둘 다 조회를 더 어긋나게 만든다.

    거부가 아니라 제거로 처리한다. 이름 수정 자체는 정당한 복구이므로
    살리고, 근거 없는 정보만 덜어 내는 편이 낫다.
    """
    previous_values = _values_of(previous)
    for concept in repaired.concepts:
        value = concept.value
        if not isinstance(value, dict) or not value.get("region"):
            continue
        before = previous_values.get(concept.id)
        if not (isinstance(before, dict) and before.get("region")):
            concept.value = {**value, "region": ""}
    return repaired


def _elapsed_ms(started_at):
    return round((time.perf_counter() - started_at) * 1000, 3)


def _reject_truncated(body, model):
    """생성 상한(num_predict)에 걸려 잘린 응답을 재시도 대상으로 올린다.

    잘린 본문은 JSON으로 읽히더라도 계획으로 신뢰할 수 없다.
    """
    if not isinstance(body, dict):
        return
    if body.get("done_reason") != "length":
        return
    raise PlannerError(
        "Planner 응답이 생성 상한에서 잘렸습니다.",
        code="OUTPUT_TRUNCATED",
        context={"model": model, "eval_count": body.get("eval_count")},
    )


def _response_text(body):
    if not isinstance(body, dict):
        raise PlannerError(
            f"Planner 응답 형식이 올바르지 않습니다: {type(body).__name__}",
            code="INVALID_RESPONSE",
        )
    message = body.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise PlannerError(
            "Planner 응답에 content가 없습니다.",
            code="EMPTY_RESPONSE",
            context={"message_keys": sorted(message)},
        )
    return content.strip()


def parse_planner_json(text):
    """설명 문장이나 코드 블록이 섞여 있어도 JSON 객체 하나를 찾아 읽는다."""
    candidate = _first_json_object(text)
    if candidate is None:
        raise PlannerError(
            f"Planner 출력에서 JSON 객체를 찾지 못했습니다: {text[:300]!r}",
            code="JSON_NOT_FOUND",
            context={"raw_text": text},
        )
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise PlannerError(
            f"Planner 출력 JSON을 파싱하지 못했습니다: {error}",
            code="JSON_PARSE_FAILED",
            context={"raw_text": text},
        ) from error
    if not isinstance(payload, dict):
        raise PlannerError(
            f"Planner 출력 최상위는 object여야 합니다. "
            f"(받은 형식: {type(payload).__name__})",
            code="JSON_NOT_OBJECT",
            context={"raw_text": text},
        )
    return payload


def _first_json_object(text):
    """문자열 리터럴을 고려해 중괄호 균형이 맞는 첫 구간을 잘라낸다."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                continue
            if character == '"':
                in_string = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        start = text.find("{", start + 1)
    return None
