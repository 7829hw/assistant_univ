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


class GeoFlowPlanner:
    """질문을 template + slots로 바꾸는 단일 LLM 호출 단계."""

    def __init__(self, *, client, templates, prompt=None, model=None):
        self.client = client
        self.templates = templates
        self.base_prompt = (
            load_planner_prompt() if prompt is None else prompt.strip()
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
        started_at = time.perf_counter()
        try:
            # tools를 전달하지 않아 Tool Calling 자체를 불가능하게 만든다.
            body = self.client.chat(self.messages(question))
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
