# -*- coding: utf-8 -*-
"""GeoFlow Planner.

Planner LLM은 Tool Call을 생성하지 않는다. 반환하는 것은 template 이름과
slot 값뿐이며, 그 출력은 전부 untrusted input으로 취급해 프로그램이 검증한다.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from build import BuildError, build_prompt

from geoflow.errors import PlannerError

DEFAULT_PLANNER_PROMPT = (
    Path(__file__).resolve().parent.parent / "prompts" / "geoflow_planner.yaml"
)

#: 어떤 template으로도 표현할 수 없을 때 Planner가 쓰는 값.
NO_TEMPLATE = "NONE"

#: 계약에 없지만 모델이 습관적으로 덧붙이는 설명 key. 값은 사용하지 않는다.
IGNORABLE_KEYS = frozenset({
    "reason", "reasoning", "explanation", "note", "notes", "thought",
})

_TEMPLATE_SECTION_HEADING = "[사용 가능한 Template]"


@dataclass
class PlannerOutput:
    """Planner 1회 호출의 결과와 계측값."""

    template: str
    slots: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    duration_ms: float = 0.0
    model: str | None = None

    def to_dict(self):
        return {
            "template": self.template,
            "slots": dict(self.slots),
            "raw_text": self.raw_text,
            "duration_ms": self.duration_ms,
            "model": self.model,
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


class GeoFlowPlanner:
    """질문을 template + slots로 바꾸는 단일 LLM 호출 단계."""

    def __init__(
        self,
        *,
        client,
        templates,
        prompt=None,
        model=None,
        repair_instruction=None,
    ):
        self.client = client
        self.templates = templates
        self.base_prompt = (
            load_planner_prompt() if prompt is None else prompt.strip()
        )
        self.repair_instruction = (
            load_repair_instruction() if repair_instruction is None
            else repair_instruction.strip()
        )
        self.model = model if model is not None else getattr(client, "model", None)

    def system_prompt(self):
        """template 목록을 정의에서 직접 만들어 prompt 표류를 막는다."""
        return "\n\n".join([
            self.base_prompt,
            f"{_TEMPLATE_SECTION_HEADING}\n{self.templates.describe_for_prompt()}",
        ])

    def messages(self, question):
        return [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": question},
        ]

    def plan(self, question):
        """Planner를 1회 호출하고 검증된 ``PlannerOutput``을 반환한다."""
        return self._ask(self.messages(question))

    def repair(self, question, previous, failure):
        """Tool 오류를 알려주고 같은 template의 slot만 고쳐 받는다.

        재계획 결과도 template/validator/compiler 전 경로를 다시 통과하므로
        어떤 guard도 우회하지 않는다.
        """
        instruction = _fill_instruction(self.repair_instruction, {
            "slot": failure.get("slot", "(알 수 없음)"),
            "name": failure.get("name", ""),
            "region": failure.get("region", ""),
            "message": failure.get("message", "Tool 오류"),
        })
        output = self._ask([
            *self.messages(question),
            {
                "role": "assistant",
                "content": json.dumps(
                    {"template": previous.template, "slots": previous.slots},
                    ensure_ascii=False,
                ),
            },
            {"role": "user", "content": instruction},
        ])
        if output.template != previous.template:
            raise PlannerError(
                f"재계획이 template을 {previous.template}에서 "
                f"{output.template}으로 바꿨습니다. slot만 수정해야 합니다.",
                code="REPAIR_CHANGED_TEMPLATE",
                context={"raw_text": output.raw_text},
            )
        output.slots = drop_invented_regions(previous.slots, output.slots)
        if output.slots == previous.slots:
            raise PlannerError(
                "재계획이 같은 slot을 그대로 반복했습니다.",
                code="REPAIR_NO_CHANGE",
                context={"raw_text": output.raw_text},
            )
        return output

    def _ask(self, messages):
        started_at = time.perf_counter()
        try:
            # tools를 전달하지 않아 Tool Calling 자체를 불가능하게 만든다.
            body = self.client.chat(messages)
        except Exception as error:  # noqa: BLE001 - client 오류를 단계 오류로 변환
            raise PlannerError(
                f"Planner 모델 호출에 실패했습니다: {type(error).__name__}: {error}",
                code="PLANNER_CALL_FAILED",
                context={"model": self.model},
            ) from error
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)

        text = _response_text(body)
        payload = parse_planner_json(text)
        template_name, slots = self._validate_payload(payload, text)
        return PlannerOutput(
            template=template_name,
            slots=slots,
            raw_text=text,
            duration_ms=duration_ms,
            model=self.model,
        )

    def _validate_payload(self, payload, text):
        unknown = sorted(set(payload) - {"template", "slots"} - IGNORABLE_KEYS)
        if unknown:
            raise PlannerError(
                f"Planner 출력에 허용되지 않은 key가 있습니다: "
                f"{', '.join(unknown)}",
                code="UNKNOWN_KEY",
                context={"raw_text": text},
            )

        template_name = payload.get("template")
        if not isinstance(template_name, str) or not template_name.strip():
            raise PlannerError(
                f"Planner 출력의 template이 비어 있습니다: {template_name!r}",
                code="MISSING_TEMPLATE",
                context={"raw_text": text},
            )
        template_name = template_name.strip()

        if template_name == NO_TEMPLATE:
            raise PlannerError(
                "질문을 현재 지원하는 분석 template으로 표현할 수 없습니다.",
                user_message=(
                    "현재 지원하는 분석 유형으로는 이 질문을 처리할 수 없습니다."
                ),
                code="NO_MATCHING_TEMPLATE",
                context={"available": list(self.templates.names)},
            )

        if template_name not in self.templates:
            raise PlannerError(
                f"알 수 없는 template입니다: {template_name!r}. "
                f"사용 가능한 template: {', '.join(self.templates.names)}",
                code="UNKNOWN_TEMPLATE",
                context={
                    "requested": template_name,
                    "available": list(self.templates.names),
                    "raw_text": text,
                },
            )

        slots = payload.get("slots", {})
        if slots is None:
            slots = {}
        if not isinstance(slots, dict):
            raise PlannerError(
                f"Planner 출력의 slots는 object여야 합니다. "
                f"(받은 형식: {type(slots).__name__})",
                code="INVALID_SLOTS",
                context={"raw_text": text},
            )
        return template_name, slots


#: 재계획 요청문에서 치환할 자리표시자. 그 밖의 중괄호는 그대로 둔다.
_INSTRUCTION_FIELDS = ("slot", "name", "region", "message")


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


def drop_invented_regions(previous_slots, repaired_slots):
    """재계획이 새로 만들어낸 상위 지역을 제거한다.

    최초 Planner 호출이 이미 질문에서 region을 추출했으므로, 장소 조회가
    실패한 뒤에야 처음 나타난 region은 정의상 사용자가 말한 값이 아니라
    모델의 추측이다. 실제로 관측된 사례가 두 가지다.

        "대구시의 평균 택시 요금은?"  → name=대구, region=경상북도
        "대구시의 평균 택시 요금은?"  → name=대구, region=시

    앞의 것은 존재하지 않는 상위 지역을 지어낸 것이고, 뒤의 것은 행정구역
    접미사를 지역으로 승격시킨 것이다. 둘 다 조회를 더 어긋나게 만든다.

    거부가 아니라 제거로 처리한다. 이름 수정 자체는 정당한 복구이므로
    살리고, 근거 없는 정보만 덜어 내는 편이 낫다.
    """
    sanitized = {}
    for name, value in repaired_slots.items():
        previous = previous_slots.get(name)
        if (
            isinstance(value, dict)
            and value.get("region")
            and not (isinstance(previous, dict) and previous.get("region"))
        ):
            value = {**value, "region": ""}
        sanitized[name] = value
    return sanitized


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
