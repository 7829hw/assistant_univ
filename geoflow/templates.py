# -*- coding: utf-8 -*-
"""GeoFlow template 정의 로딩과 slot 채우기.

template YAML은 Planner에게 보여줄 설명문이 아니라, 프로그램이 읽어
``GeoFlowPlan``을 deterministic하게 만들어내는 구조화 데이터다.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_graph import extract_scopes

from geoflow.errors import TemplateError
from geoflow.operator_registry import get_operator
from geoflow.types import (
    GEOFLOW_VERSION,
    ConceptNode,
    CoreConcept,
    FunctionalRole,
    GeoFlowPlan,
    NodeSource,
    Transformation,
    ValueRef,
)

DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "geoflow_templates"

#: slot 값 형식. 최종 검증은 ToolExecutor의 JSON Schema가 다시 수행한다.
SLOT_TYPE_PLACE = "place"
SLOT_TYPE_SCOPE = "scope"
SLOT_TYPE_DATE = "date"
SLOT_TYPE_TIME = "time"
SLOT_TYPE_TEXT = "text"
SLOT_TYPE_BOOLEAN = "boolean"
SLOT_TYPE_INTEGER = "integer"

_SLOT_PATTERNS = {
    SLOT_TYPE_SCOPE: re.compile(r"^scope:[A-Za-z0-9_:.-]+$"),
    SLOT_TYPE_DATE: re.compile(
        r"^(\d{8}(-\d{8})?|last_week|last_month|last_year"
        r"|weekday|weekend|holiday)$"
    ),
    SLOT_TYPE_TIME: re.compile(r"^\d{6}-\d{6}$"),
}

_PLACE_FIELDS = ("name", "region")


@dataclass(frozen=True)
class SlotSpec:
    """slot 하나의 이름/필수여부/형식."""

    name: str
    required: bool
    type: Any = SLOT_TYPE_TEXT

    @property
    def enum_values(self):
        if isinstance(self.type, dict):
            return tuple(self.type.get("enum") or ())
        return ()

    def describe(self):
        if self.enum_values:
            return "|".join(str(value) for value in self.enum_values)
        if self.type == SLOT_TYPE_PLACE:
            return "{name, region}"
        return str(self.type)


@dataclass
class GeoFlowTemplate:
    """단일 template 정의."""

    name: str
    description: str
    slots: dict[str, SlotSpec]
    concepts: list[dict[str, Any]]
    transformations: list[dict[str, Any]]
    final_node: str
    answer: dict[str, Any] = field(default_factory=dict)
    question_examples: list[str] = field(default_factory=list)
    #: slot 사이의 동반 제약. {slot: [함께 있어야 하는 slot, ...]}
    slot_requires: dict[str, tuple[str, ...]] = field(default_factory=dict)
    source_path: str = ""

    @property
    def required_slots(self):
        return tuple(
            name for name, spec in self.slots.items() if spec.required
        )

    @property
    def optional_slots(self):
        return tuple(
            name for name, spec in self.slots.items() if not spec.required
        )

    def instantiate(self, question, slots):
        """slot을 채워 typed ``GeoFlowPlan``을 만든다."""
        filled = self._validate_slots(slots, question)
        dropped = self._dropped_nodes(filled)
        concepts = [
            self._build_concept(spec, filled)
            for spec in self.concepts
            if spec["id"] not in dropped
        ]
        transformations = [
            self._build_transformation(spec, filled, dropped)
            for spec in self.transformations
            if not self._is_dropped(spec, dropped)
        ]
        return GeoFlowPlan(
            version=GEOFLOW_VERSION,
            question=question,
            template=self.name,
            concepts=concepts,
            transformations=transformations,
            final_node=self.final_node,
            slots=filled,
        )

    # -- optional concept -------------------------------------------------

    def _dropped_nodes(self, filled):
        """질문에 없는 optional 조건과 그에 의존하는 node를 걸러낸다.

        예: "평균 택시 요금은?"처럼 장소 조건이 없는 질문에서는 place와
        place_scope가 사라지고 metric tool만 scope 없이 실행된다. 질문에 없는
        조건을 임의로 채우지 않기 위한 장치다.
        """
        dropped = {
            spec["id"]
            for spec in self.concepts
            if spec.get("optional")
            and "from_slot" in spec
            and spec["from_slot"] not in filled
        }
        optional_ids = {
            spec["id"] for spec in self.concepts if spec.get("optional")
        }

        changed = True
        while changed:
            changed = False
            for spec in self.transformations:
                if not self._has_dropped_required_input(spec, dropped):
                    continue
                for output_id in spec.get("outputs") or []:
                    if output_id in dropped:
                        continue
                    if output_id not in optional_ids:
                        raise TemplateError(
                            f"{self.name}: {spec['id']}의 필수 입력이 사라져 "
                            f"{output_id}를 만들 수 없지만 optional이 "
                            "아닙니다.",
                            context={"template": self.name},
                        )
                    dropped.add(output_id)
                    changed = True

        if self.final_node in dropped:
            raise TemplateError(
                f"{self.name}: final_node({self.final_node})가 질문에 없는 "
                "조건에 의존합니다.",
                context={"template": self.name},
            )
        return dropped

    def _has_dropped_required_input(self, spec, dropped):
        operator = get_operator(spec["operator"])
        for port, reference in (spec.get("inputs") or {}).items():
            if reference["node"] not in dropped:
                continue
            port_spec = None if operator is None else operator.input(port)
            # optional port는 argument만 빠지고 transformation은 살아남는다.
            if port_spec is None or port_spec.required:
                return True
        return False

    def _is_dropped(self, spec, dropped):
        outputs = spec.get("outputs") or []
        return bool(outputs) and all(
            output_id in dropped for output_id in outputs
        )

    # -- slot -------------------------------------------------------------

    def _validate_slots(self, slots, question=""):
        if not isinstance(slots, dict):
            raise TemplateError(
                f"{self.name}: slots는 object여야 합니다. (받은 형식: "
                f"{type(slots).__name__})",
                context={"template": self.name},
            )

        unknown = sorted(set(slots) - set(self.slots))
        if unknown:
            raise TemplateError(
                f"{self.name}: 허용되지 않은 slot입니다: {', '.join(unknown)}. "
                f"사용 가능한 slot: {', '.join(self.slots)}",
                context={"template": self.name, "unknown_slots": unknown},
            )

        filled: dict[str, Any] = {}
        for name, spec in self.slots.items():
            if name not in slots or slots[name] in (None, ""):
                if spec.required:
                    raise TemplateError(
                        f"{self.name}: 필수 slot이 없습니다: {name}",
                        context={"template": self.name, "missing_slot": name},
                    )
                continue
            filled[name] = self._coerce_slot(spec, slots[name], question)
        self._check_slot_requirements(filled)
        return filled

    def _check_slot_requirements(self, filled):
        """혼자 쓰일 수 없는 slot이 짝 없이 들어온 경우를 막는다.

        Tool이 INVALID_ARGUMENT로 거절할 조합을 실행 전에 걸러 낸다.
        """
        for name, companions in self.slot_requires.items():
            if name not in filled:
                continue
            missing = [item for item in companions if item not in filled]
            if missing:
                raise TemplateError(
                    f"{self.name}: slot {name!r}을 쓰려면 "
                    f"{', '.join(repr(item) for item in missing)}도 함께 "
                    "필요합니다.",
                    context={"template": self.name, "slot": name},
                )

    def _coerce_slot(self, spec, value, question=""):
        where = f"{self.name}.{spec.name}"
        enum_values = spec.enum_values
        if enum_values:
            if value not in enum_values:
                raise TemplateError(
                    f"{where}: 허용되지 않은 값 {value!r}. "
                    f"허용: {', '.join(str(item) for item in enum_values)}",
                    context={"template": self.name, "slot": spec.name},
                )
            return value

        if spec.type == SLOT_TYPE_PLACE:
            return self._coerce_place(where, value, spec)
        if spec.type == SLOT_TYPE_BOOLEAN:
            if not isinstance(value, bool):
                raise TemplateError(
                    f"{where}: boolean이어야 합니다. (받은 값: {value!r})",
                    context={"template": self.name, "slot": spec.name},
                )
            return value
        if spec.type == SLOT_TYPE_INTEGER:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TemplateError(
                    f"{where}: 정수여야 합니다. (받은 값: {value!r})",
                    context={"template": self.name, "slot": spec.name},
                )
            return value

        if not isinstance(value, str) or not value.strip():
            raise TemplateError(
                f"{where}: 비어 있지 않은 문자열이어야 합니다. (받은 값: {value!r})",
                context={"template": self.name, "slot": spec.name},
            )
        text = value.strip()
        pattern = _SLOT_PATTERNS.get(spec.type)
        if pattern is not None and not pattern.fullmatch(text):
            if spec.type == SLOT_TYPE_SCOPE:
                return self._restore_scope_prefix(where, spec, text, question)
            raise TemplateError(
                f"{where}: {spec.type} 형식이 아닙니다: {text!r}",
                context={"template": self.name, "slot": spec.name},
            )
        return text

    def _restore_scope_prefix(self, where, spec, text, question):
        """Planner가 "scope:" 접두어를 빠뜨린 경우에만 복원한다.

        복원 결과가 사용자 발화에 토큰 단위로 실재할 때만 인정하므로 scope를
        새로 만들어내는 경로가 되지 않는다. 복원 여부와 무관하게 Validator의
        G6 provenance 검사는 그대로 다시 수행된다.
        """
        candidate = f"scope:{text}"
        if candidate in extract_scopes(question):
            return candidate
        raise TemplateError(
            f"{where}: scope 형식이 아닙니다: {text!r}. scope 값은 "
            '"scope:"로 시작하며 사용자 발화에 있는 값을 그대로 사용해야 '
            "합니다.",
            context={"template": self.name, "slot": spec.name},
        )

    def _coerce_place(self, where, value, spec):
        if isinstance(value, str):
            value = {"name": value}
        if not isinstance(value, dict):
            raise TemplateError(
                f"{where}: 장소 slot은 {{name, region}} object여야 합니다. "
                f"(받은 형식: {type(value).__name__})",
                context={"template": self.name, "slot": spec.name},
            )
        unknown = sorted(set(value) - set(_PLACE_FIELDS))
        if unknown:
            raise TemplateError(
                f"{where}: 장소 slot에 허용되지 않은 필드가 있습니다: "
                f"{', '.join(unknown)}",
                context={"template": self.name, "slot": spec.name},
            )
        name = value.get("name")
        if not isinstance(name, str) or not name.strip():
            raise TemplateError(
                f"{where}: 장소 slot의 name이 비어 있습니다.",
                context={"template": self.name, "slot": spec.name},
            )
        region = value.get("region") or ""
        if not isinstance(region, str):
            raise TemplateError(
                f"{where}: 장소 slot의 region은 문자열이어야 합니다.",
                context={"template": self.name, "slot": spec.name},
            )
        return {"name": name.strip(), "region": region.strip()}

    # -- concept / transformation ----------------------------------------

    def _build_concept(self, spec, slots):
        node_id = spec["id"]
        source = NodeSource(spec["source"])
        concept_name = spec["concept"]
        subtype = spec["subtype"]
        by_slot = spec.get("by_slot")
        if by_slot is not None:
            # metric처럼 slot 값이 곧 subtype이 되는 node를 표현한다.
            slot_name = by_slot["slot"]
            case = (by_slot.get("cases") or {}).get(slots.get(slot_name))
            if case is None:
                raise TemplateError(
                    f"{self.name}.{node_id}: slot {slot_name!r} 값 "
                    f"{slots.get(slot_name)!r}에 대응하는 concept 정의가 "
                    "없습니다.",
                    context={"template": self.name, "node": node_id},
                )
            concept_name = case.get("concept", concept_name)
            subtype = case.get("subtype", subtype)

        if "from_slot" in spec:
            slot_name = spec["from_slot"]
            if slot_name not in slots:
                raise TemplateError(
                    f"{self.name}.{node_id}: slot {slot_name!r} 값이 없어 "
                    "concept를 만들 수 없습니다.",
                    context={"template": self.name, "node": node_id},
                )
            value = slots[slot_name]
        else:
            value = spec.get("value")
        return ConceptNode(
            id=node_id,
            concept=CoreConcept(concept_name),
            subtype=subtype,
            role=FunctionalRole(spec["role"]),
            source=source,
            value=value,
            attributes=dict(spec.get("attributes") or {}),
        )

    def _build_transformation(self, spec, slots, dropped=frozenset()):
        inputs = {}
        for port, reference in (spec.get("inputs") or {}).items():
            if reference["node"] in dropped:
                continue
            inputs[port] = ValueRef(
                node_id=reference["node"],
                field=reference.get("field"),
            )
        params = {}
        for name, raw in (spec.get("params") or {}).items():
            resolved, present = self._resolve_param(raw, slots)
            if present:
                params[name] = resolved
        return Transformation(
            id=spec["id"],
            operator=spec["operator"],
            inputs=inputs,
            outputs=list(spec.get("outputs") or []),
            params=params,
        )

    def _resolve_param(self, raw, slots):
        """template param 표기를 실제 값으로 바꾼다.

        ``{slot: X}``는 slot이 없으면 argument 자체를 생략한다. 질문에 없는
        parameter를 임의로 채우지 않기 위해서다.
        """
        if isinstance(raw, dict):
            if "const" in raw:
                return raw["const"], True
            if "slot" in raw:
                slot_name = raw["slot"]
                if slot_name not in slots:
                    return None, "default" in raw
                value = slots[slot_name]
                inner = raw.get("field")
                if inner is not None:
                    if not isinstance(value, dict) or inner not in value:
                        return None, False
                    value = value[inner]
                return value, True
            raise TemplateError(
                f"{self.name}: 알 수 없는 param 표기입니다: {raw!r}",
                context={"template": self.name},
            )
        return raw, True

    # -- prompt -----------------------------------------------------------

    def describe_for_prompt(self):
        """Planner prompt에 넣을 template 설명을 정의에서 직접 만든다."""
        lines = [f"- {self.name}", f"  용도: {self.description}"]
        required = [
            f"{name}({self.slots[name].describe()})"
            for name in self.required_slots
        ]
        optional = [
            f"{name}({self.slots[name].describe()})"
            for name in self.optional_slots
        ]
        lines.append(f"  required_slots: {', '.join(required) or '(없음)'}")
        lines.append(f"  optional_slots: {', '.join(optional) or '(없음)'}")
        for example in self.question_examples:
            lines.append(f"  예시 질문: {example}")
        return "\n".join(lines)


_REQUIRED_TEMPLATE_KEYS = (
    "name", "description", "concepts", "transformations", "final_node",
)


def load_template(path):
    """template YAML 하나를 읽어 구조 계약을 검증한다."""
    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise TemplateError(
            f"template YAML을 읽을 수 없습니다: {path}\n{error}",
            context={"path": str(path)},
        ) from error

    if not isinstance(document, dict):
        raise TemplateError(
            f"{path.name}: 최상위는 object여야 합니다.",
            context={"path": str(path)},
        )
    missing = [key for key in _REQUIRED_TEMPLATE_KEYS if key not in document]
    if missing:
        raise TemplateError(
            f"{path.name}: 필수 key가 없습니다: {', '.join(missing)}",
            context={"path": str(path)},
        )

    required_slots = list(document.get("required_slots") or [])
    optional_slots = list(document.get("optional_slots") or [])
    duplicated = sorted(set(required_slots) & set(optional_slots))
    if duplicated:
        raise TemplateError(
            f"{path.name}: slot이 required와 optional에 동시에 있습니다: "
            f"{', '.join(duplicated)}",
            context={"path": str(path)},
        )
    slot_types = dict(document.get("slot_types") or {})
    unknown_typed = sorted(
        set(slot_types) - set(required_slots) - set(optional_slots)
    )
    if unknown_typed:
        raise TemplateError(
            f"{path.name}: slot_types에만 있는 slot이 있습니다: "
            f"{', '.join(unknown_typed)}",
            context={"path": str(path)},
        )

    slot_requires_raw = dict(document.get("slot_requires") or {})
    slot_names = set(required_slots) | set(optional_slots)
    slot_requires = {}
    for name, companions in slot_requires_raw.items():
        if name not in slot_names:
            raise TemplateError(
                f"{path.name}: slot_requires에 정의되지 않은 slot이 "
                f"있습니다: {name}",
                context={"path": str(path)},
            )
        if isinstance(companions, str):
            companions = [companions]
        unknown_companions = [
            item for item in companions if item not in slot_names
        ]
        if unknown_companions:
            raise TemplateError(
                f"{path.name}: slot_requires[{name!r}]가 정의되지 않은 "
                f"slot을 참조합니다: {', '.join(unknown_companions)}",
                context={"path": str(path)},
            )
        slot_requires[name] = tuple(companions)

    slots = {}
    for name in [*required_slots, *optional_slots]:
        slots[name] = SlotSpec(
            name=name,
            required=name in required_slots,
            type=slot_types.get(name, SLOT_TYPE_TEXT),
        )

    concepts = document["concepts"]
    transformations = document["transformations"]
    if not isinstance(concepts, list) or not concepts:
        raise TemplateError(
            f"{path.name}: concepts는 비어 있지 않은 list여야 합니다.",
            context={"path": str(path)},
        )
    if not isinstance(transformations, list) or not transformations:
        raise TemplateError(
            f"{path.name}: transformations는 비어 있지 않은 list여야 합니다.",
            context={"path": str(path)},
        )

    node_ids = set()
    for index, spec in enumerate(concepts):
        where = f"{path.name}.concepts[{index}]"
        _require_keys(where, spec, ("id", "concept", "subtype", "role", "source"))
        if spec["id"] in node_ids:
            raise TemplateError(
                f"{where}: concept id가 중복되었습니다: {spec['id']}",
                context={"path": str(path)},
            )
        node_ids.add(spec["id"])
        _require_enum(where, "concept", spec["concept"], CoreConcept)
        _require_enum(where, "role", spec["role"], FunctionalRole)
        _require_enum(where, "source", spec["source"], NodeSource)
        slot_name = spec.get("from_slot")
        if slot_name is not None and slot_name not in slots:
            raise TemplateError(
                f"{where}: 정의되지 않은 slot을 참조합니다: {slot_name}",
                context={"path": str(path)},
            )
        _validate_by_slot(where, spec.get("by_slot"), slots, path)
        if spec.get("optional") and slot_name is not None:
            if slots[slot_name].required:
                raise TemplateError(
                    f"{where}: optional concept가 required slot "
                    f"{slot_name!r}을 참조합니다.",
                    context={"path": str(path)},
                )

    for index, spec in enumerate(transformations):
        where = f"{path.name}.transformations[{index}]"
        _require_keys(where, spec, ("id", "operator", "outputs"))

    final_node = document["final_node"]
    if final_node not in node_ids:
        raise TemplateError(
            f"{path.name}: final_node가 concepts에 없습니다: {final_node}",
            context={"path": str(path)},
        )

    return GeoFlowTemplate(
        name=str(document["name"]),
        description=str(document["description"]).strip(),
        slots=slots,
        concepts=concepts,
        transformations=transformations,
        final_node=final_node,
        answer=dict(document.get("answer") or {}),
        slot_requires=slot_requires,
        question_examples=[
            str(item) for item in (document.get("question_examples") or [])
        ],
        source_path=str(path),
    )


def _validate_by_slot(where, by_slot, slots, path):
    """by_slot이 slot enum을 빠짐없이 덮는지 로딩 시점에 확인한다."""
    if by_slot is None:
        return
    if not isinstance(by_slot, dict) or "slot" not in by_slot:
        raise TemplateError(
            f"{where}.by_slot: slot key가 있는 object여야 합니다.",
            context={"path": str(path)},
        )
    slot_name = by_slot["slot"]
    slot_spec = slots.get(slot_name)
    if slot_spec is None:
        raise TemplateError(
            f"{where}.by_slot: 정의되지 않은 slot을 참조합니다: {slot_name}",
            context={"path": str(path)},
        )
    cases = by_slot.get("cases") or {}
    if not isinstance(cases, dict) or not cases:
        raise TemplateError(
            f"{where}.by_slot: cases가 비어 있습니다.",
            context={"path": str(path)},
        )
    for value, case in cases.items():
        if not isinstance(case, dict):
            raise TemplateError(
                f"{where}.by_slot.cases[{value!r}]: object여야 합니다.",
                context={"path": str(path)},
            )
        if "concept" in case:
            _require_enum(
                f"{where}.by_slot.cases[{value!r}]",
                "concept",
                case["concept"],
                CoreConcept,
            )
    enum_values = slot_spec.enum_values
    missing = [value for value in enum_values if value not in cases]
    if missing:
        raise TemplateError(
            f"{where}.by_slot: slot {slot_name!r}의 값 "
            f"{', '.join(str(item) for item in missing)}에 대한 case가 "
            "없습니다.",
            context={"path": str(path)},
        )


def _require_keys(where, spec, keys):
    if not isinstance(spec, dict):
        raise TemplateError(f"{where}: object여야 합니다.")
    missing = [key for key in keys if key not in spec]
    if missing:
        raise TemplateError(f"{where}: 필수 key가 없습니다: {', '.join(missing)}")


def _require_enum(where, key, value, enum_type):
    try:
        enum_type(value)
    except ValueError as error:
        allowed = ", ".join(item.value for item in enum_type)
        raise TemplateError(
            f"{where}.{key}: 허용되지 않은 값 {value!r} (허용: {allowed})"
        ) from error


class TemplateRegistry:
    """template 디렉터리 전체를 이름으로 조회할 수 있게 담아둔다."""

    def __init__(self, templates):
        self._templates: dict[str, GeoFlowTemplate] = {}
        for template in templates:
            if template.name in self._templates:
                raise TemplateError(
                    f"template 이름이 중복되었습니다: {template.name}"
                )
            self._templates[template.name] = template

    @classmethod
    def from_directory(cls, directory=DEFAULT_TEMPLATE_DIR):
        directory = Path(directory)
        paths = sorted(directory.glob("*.yaml"))
        if not paths:
            raise TemplateError(
                f"template YAML이 없습니다: {directory}",
                context={"directory": str(directory)},
            )
        return cls([load_template(path) for path in paths])

    def __contains__(self, name):
        return name in self._templates

    def __len__(self):
        return len(self._templates)

    @property
    def names(self):
        return tuple(self._templates)

    def all(self):
        return tuple(self._templates.values())

    def get(self, name):
        return self._templates.get(name)

    def require(self, name):
        template = self._templates.get(name)
        if template is None:
            raise TemplateError(
                f"알 수 없는 template입니다: {name!r}. "
                f"사용 가능한 template: {', '.join(self.names)}",
                context={"requested": name, "available": list(self.names)},
            )
        return template

    def describe_for_prompt(self):
        return "\n".join(
            template.describe_for_prompt() for template in self.all()
        )
