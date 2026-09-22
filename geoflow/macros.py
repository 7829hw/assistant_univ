# -*- coding: utf-8 -*-
"""Macro-template 정의와 IO port 계약.

논문의 macro-template ``g_k = (V_k, E_k, in_k, out_k)``에 대응한다. Macro는
"질문 유형"이 아니라 **재사용 가능한 concept transformation 조각**이다. 따라서

* macro는 ``final_node``를 갖지 않는다. 최종 답을 정하는 것은 합성 결과인
  ``GeoFlowPlan``이다.
* macro는 실행할 Tool도, semantic operator 이름도 지정하지 않는다. 그 결정은
  graph를 만든 뒤 ``geoflow/operator_mapping.py``가 수행한다.
* macro는 input/output port의 (CoreConcept, subtype) 계약만 선언하고, 서로
  다른 macro는 이 port를 통해서만 연결된다.

예를 들어 ``PLACE_TO_SCOPE``는 "장소 근처 통행량" 같은 질문 유형이 아니라
``LOCATION/place → LOCATION/scope``라는 변환 하나를 뜻한다. 같은 조각이
통행량·속도·요금·OD 질의에 모두 쓰인다.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from geoflow.errors import MacroError
from geoflow.operator_registry import OPERATORS
from geoflow.types import (
    CONCEPT_SUBTYPES,
    KNOWN_SUBTYPES,
    CoreConcept,
    FunctionalRole,
    NodeSource,
    subtype_allowed,
)

DEFAULT_MACRO_DIR = Path(__file__).resolve().parent.parent / "geoflow_macros"

#: macro가 만든 node의 source로 허용하는 값. 사용자 발화에서만 올 수 있는
#: ``user``를 macro가 선언할 수 없게 막는다. scope를 Tool 없이 만들어 내는
#: 경로를 정의 단계에서 차단하기 위한 것이다(G6와 같은 취지).
PRODUCIBLE_SOURCES = frozenset({NodeSource.TOOL, NodeSource.DERIVED})

#: operator registry가 실제로 만들어 낼 수 있는 (concept, subtype) 조합.
#: macro output port가 이 밖의 값을 선언하면 합성에 성공해도 실행할 수 없다.
PRODUCIBLE_TYPES = frozenset(
    pair
    for spec in OPERATORS.values()
    if spec.output is not None
    for pair in spec.output.allowed
)


@dataclass(frozen=True)
class PortSpec:
    """macro input/output port 하나의 타입 계약.

    ``types``는 (CoreConcept, subtype) 쌍의 집합이다. concept와 subtype을 따로
    두면 ``AMOUNT/vacant_ratio``처럼 실재하지 않는 조합이 계약상 허용되어
    버리므로 쌍으로 묶어 둔다.
    """

    name: str
    types: frozenset[tuple[CoreConcept, str]]
    roles: frozenset[FunctionalRole] = frozenset()
    required: bool = True
    #: node attribute 일치 조건. origin/destination처럼 타입이 같고 의미가
    #: 다른 port를 구분한다. 빈 값이면 attribute를 보지 않는다.
    match_attributes: tuple[tuple[str, Any], ...] = ()

    @property
    def concepts(self):
        return frozenset(concept for concept, _ in self.types)

    @property
    def subtypes(self):
        return frozenset(subtype for _, subtype in self.types)

    def accepts(self, concept, subtype, *, role=None, attributes=None):
        """node 하나가 이 port에 연결 가능한지 판정한다."""
        return (
            self.accepts_type(concept, subtype, role=role)
            and self.matches_attributes(attributes)
        )

    def accepts_type(self, concept, subtype, *, role=None):
        """속성을 빼고 타입과 role만 본다.

        합성 중에는 아직 만들어지지 않은 node의 속성을 알 수 없으므로,
        후보를 고를 때는 타입만 보고 속성은 만든 뒤에 확인한다.
        """
        if (concept, subtype) not in self.types:
            return False
        return not (self.roles and role is not None and role not in self.roles)

    @property
    def required_attributes(self):
        """이 port가 요구하는 속성. 연결 대상 탐색에 그대로 전달된다."""
        return dict(self.match_attributes)

    def matches_attributes(self, attributes):
        if not self.match_attributes:
            return True
        attributes = attributes or {}
        return all(
            attributes.get(key) == value for key, value in self.match_attributes
        )

    def describe(self):
        types = ", ".join(
            f"{concept.value}/{subtype}"
            for concept, subtype in sorted(
                self.types, key=lambda item: (item[0].value, item[1])
            )
        )
        suffix = "" if self.required else " (optional)"
        return f"{self.name}: {types}{suffix}"


@dataclass(frozen=True)
class SubtypeByFactor:
    """factor 값에 따라 생성 node의 subtype을 고르는 규칙.

    "근처/주변" 같은 표현을 질문 유형 분기가 아니라 factor로 다루기 위한
    장치다. Composer는 ``vicinity`` factor 하나로 같은 macro가
    ``LOCATION/scope``를 만들지 ``LOCATION/vicinity_scope``를 만들지 정한다.
    """

    factor: str
    cases: dict[Any, str]
    default: str

    def resolve(self, factors):
        if self.factor not in (factors or {}):
            return self.default
        return self.cases.get(factors[self.factor], self.default)

    @property
    def subtypes(self):
        return frozenset({*self.cases.values(), self.default})


@dataclass(frozen=True)
class MacroNodeSpec:
    """macro가 새로 만드는 concept node의 기본값.

    grounding이 같은 node를 이미 이름 붙여 두었다면 subtype/role은 grounding
    쪽을 따르고, 여기 값은 fallback으로만 쓰인다. 다만 ``source``만은 언제나
    macro가 정한다. 생성 node의 출처를 LLM이 선언하게 두면 Tool이 만들어야 할
    scope를 "사용자가 말한 값"으로 위장할 수 있기 때문이다.
    """

    key: str
    role: FunctionalRole
    source: NodeSource
    subtype: str | None = None
    subtype_by_factor: SubtypeByFactor | None = None
    #: 속성을 물려받을 input port 이름과 속성 이름들. OD의 pickup/dropoff
    #: 구분이 place → scope 변환을 건너뛰지 않게 한다.
    inherit_from: str | None = None
    inherit_attributes: tuple[str, ...] = ()

    def resolve_subtype(self, factors):
        if self.subtype_by_factor is not None:
            return self.subtype_by_factor.resolve(factors)
        return self.subtype

    @property
    def candidate_subtypes(self):
        if self.subtype_by_factor is not None:
            return self.subtype_by_factor.subtypes
        return frozenset({self.subtype}) if self.subtype else frozenset()


@dataclass(frozen=True)
class MacroTransformationSpec:
    """macro 내부의 변환 하나.

    입력은 port/node key 목록으로만 표현한다. 어떤 operator port에 무엇을
    묶을지는 macro가 아니라 operator registry가 정한다.
    """

    id: str
    inputs: tuple[str, ...]
    output: str


@dataclass
class MacroTemplate:
    """재사용 가능한 GeoFlow subgraph 조각."""

    name: str
    description: str
    input_ports: dict[str, PortSpec] = field(default_factory=dict)
    output_ports: dict[str, PortSpec] = field(default_factory=dict)
    concepts: dict[str, MacroNodeSpec] = field(default_factory=dict)
    transformations: list[MacroTransformationSpec] = field(default_factory=list)
    #: 같은 output을 만들 수 있는 macro가 여럿일 때의 선택 순서. 값이 작을수록
    #: 먼저 시도한다. 합성 결과가 실행마다 달라지지 않게 하기 위한 것이다.
    priority: int = 100
    source_path: str = ""

    @property
    def required_input_ports(self):
        return tuple(
            name for name, spec in self.input_ports.items() if spec.required
        )

    def output_port_for(self, concept, subtype):
        """(concept, subtype)을 만들 수 있는 output port 이름을 돌려준다."""
        for name, spec in self.output_ports.items():
            if (concept, subtype) in spec.types:
                return name
        return None

    def produces(self, concept, subtype):
        return self.output_port_for(concept, subtype) is not None

    def describe_for_prompt(self):
        lines = [f"- {self.name}", f"  용도: {self.description}"]
        for spec in self.input_ports.values():
            lines.append(f"  입력 {spec.describe()}")
        for spec in self.output_ports.values():
            lines.append(f"  출력 {spec.describe()}")
        return "\n".join(lines)


# -- 로딩 -------------------------------------------------------------------


_REQUIRED_MACRO_KEYS = ("name", "description", "outputs", "transformations")


def load_macro(path):
    """macro YAML 하나를 읽어 구조 계약을 검증한다."""
    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise MacroError(
            f"macro YAML을 읽을 수 없습니다: {path}\n{error}",
            context={"path": str(path)},
        ) from error

    if not isinstance(document, dict):
        raise MacroError(
            f"{path.name}: 최상위는 object여야 합니다.",
            context={"path": str(path)},
        )
    missing = [key for key in _REQUIRED_MACRO_KEYS if key not in document]
    if missing:
        raise MacroError(
            f"{path.name}: 필수 key가 없습니다: {', '.join(missing)}",
            context={"path": str(path)},
        )
    if "final_node" in document:
        raise MacroError(
            f"{path.name}: macro는 final_node를 갖지 않습니다. 최종 node는 "
            "합성 결과인 GeoFlowPlan이 정합니다.",
            context={"path": str(path)},
        )
    if "operator" in document:
        raise MacroError(
            f"{path.name}: macro는 operator를 직접 지정하지 않습니다. "
            "operator 선택은 operator mapping 단계가 수행합니다.",
            context={"path": str(path)},
        )

    name = str(document["name"]).strip()
    if not name:
        raise MacroError(
            f"{path.name}: name이 비어 있습니다.", context={"path": str(path)},
        )

    input_ports = {
        port_name: _load_port(f"{path.name}.inputs.{port_name}", port_name, raw)
        for port_name, raw in (document.get("inputs") or {}).items()
    }
    output_ports = {
        port_name: _load_port(
            f"{path.name}.outputs.{port_name}", port_name, raw, produced=True,
        )
        for port_name, raw in (document["outputs"] or {}).items()
    }
    if not output_ports:
        raise MacroError(
            f"{path.name}: outputs는 비어 있을 수 없습니다.",
            context={"path": str(path)},
        )
    overlap = sorted(set(input_ports) & set(output_ports))
    if overlap:
        raise MacroError(
            f"{path.name}: 같은 이름의 input/output port가 있습니다: "
            f"{', '.join(overlap)}",
            context={"path": str(path)},
        )

    concepts = {}
    for raw in document.get("concepts") or []:
        spec = _load_node(f"{path.name}.concepts", raw, input_ports)
        if spec.key in concepts:
            raise MacroError(
                f"{path.name}: concept key가 중복되었습니다: {spec.key}",
                context={"path": str(path)},
            )
        concepts[spec.key] = spec

    transformations = []
    seen_transformations = set()
    produced_keys = set()
    for index, raw in enumerate(document["transformations"] or []):
        where = f"{path.name}.transformations[{index}]"
        spec = _load_transformation(where, raw)
        if spec.id in seen_transformations:
            raise MacroError(
                f"{where}: transformation id가 중복되었습니다: {spec.id}",
                context={"path": str(path)},
            )
        seen_transformations.add(spec.id)
        for key in spec.inputs:
            if key not in input_ports and key not in produced_keys:
                raise MacroError(
                    f"{where}: 정의되지 않은 입력을 참조합니다: {key}",
                    context={"path": str(path)},
                )
        if spec.output not in concepts:
            raise MacroError(
                f"{where}: output {spec.output!r}에 해당하는 concepts 정의가 "
                "없습니다.",
                context={"path": str(path)},
            )
        if spec.output in produced_keys:
            raise MacroError(
                f"{where}: {spec.output}를 두 번 생성합니다.",
                context={"path": str(path)},
            )
        produced_keys.add(spec.output)
        transformations.append(spec)

    if not transformations:
        raise MacroError(
            f"{path.name}: transformations는 비어 있을 수 없습니다.",
            context={"path": str(path)},
        )

    unbound = sorted(set(output_ports) - produced_keys)
    if unbound:
        raise MacroError(
            f"{path.name}: 어떤 transformation도 만들지 않는 output port가 "
            f"있습니다: {', '.join(unbound)}",
            context={"path": str(path)},
        )
    orphan = sorted(produced_keys - set(output_ports))
    _check_node_subtypes(path, concepts, output_ports, orphan)

    return MacroTemplate(
        name=name,
        description=str(document["description"]).strip(),
        input_ports=input_ports,
        output_ports=output_ports,
        concepts=concepts,
        transformations=transformations,
        priority=int(document.get("priority", 100)),
        source_path=str(path),
    )


def _check_node_subtypes(path, concepts, output_ports, internal_keys):
    """생성 node가 실제로 만들 수 있는 subtype만 선언하는지 확인한다."""
    for key, spec in concepts.items():
        port = output_ports.get(key)
        candidates = spec.candidate_subtypes
        if port is None:
            # output port로 노출되지 않는 내부 node는 subtype을 스스로 정해야
            # 한다. grounding이 이름 붙일 수 없는 node이기 때문이다.
            if key in internal_keys and not candidates:
                raise MacroError(
                    f"{path.name}.concepts[{key}]: 내부 node는 subtype 또는 "
                    "subtype_by_factor가 있어야 합니다.",
                    context={"path": str(path)},
                )
            continue
        unknown = sorted(candidates - port.subtypes)
        if unknown:
            raise MacroError(
                f"{path.name}.concepts[{key}]: output port가 허용하지 않는 "
                f"subtype입니다: {', '.join(unknown)}",
                context={"path": str(path)},
            )
        if spec.inherit_from is not None and spec.inherit_from not in (
            set(concepts) | set(output_ports)
        ):
            continue


def _load_port(where, name, raw, *, produced=False):
    if not isinstance(raw, dict):
        raise MacroError(f"{where}: object여야 합니다.")

    types = _load_types(where, raw)
    if produced:
        unproducible = sorted(
            f"{concept.value}/{subtype}"
            for concept, subtype in types - PRODUCIBLE_TYPES
        )
        if unproducible:
            raise MacroError(
                f"{where}: 어떤 semantic operator도 만들 수 없는 출력 "
                f"타입입니다: {', '.join(unproducible)}"
            )

    roles = frozenset(
        _require_enum(where, "roles", value, FunctionalRole)
        for value in (raw.get("roles") or [])
    )
    match_attributes = tuple(
        sorted((raw.get("attributes") or {}).items())
    )
    return PortSpec(
        name=name,
        types=types,
        roles=roles,
        required=bool(raw.get("required", True)),
        match_attributes=match_attributes,
    )


def _load_types(where, raw):
    """``concept``+``subtypes`` 또는 ``types`` 목록을 (concept, subtype)로 편다."""
    groups = raw.get("types")
    if groups is None:
        if "concept" not in raw:
            raise MacroError(f"{where}: concept 또는 types가 필요합니다.")
        groups = [{"concept": raw["concept"], "subtypes": raw.get("subtypes")}]
    if not isinstance(groups, list) or not groups:
        raise MacroError(f"{where}.types: 비어 있지 않은 list여야 합니다.")

    types = set()
    for group in groups:
        if not isinstance(group, dict) or "concept" not in group:
            raise MacroError(f"{where}.types: concept이 있는 object여야 합니다.")
        concept = _require_enum(where, "concept", group["concept"], CoreConcept)
        subtypes = group.get("subtypes")
        if not isinstance(subtypes, list) or not subtypes:
            raise MacroError(
                f"{where}.types[{concept.value}].subtypes: 비어 있지 않은 "
                "list여야 합니다."
            )
        for subtype in subtypes:
            subtype = str(subtype)
            # concept과 짝이 맞는지까지 본다. AMOUNT/place처럼 이름은 있으나
            # 그 concept에 속하지 않는 조합을 정의 단계에서 막는다.
            if not subtype_allowed(concept, subtype):
                raise MacroError(
                    f"{where}: {concept.value}에 없는 subtype입니다: "
                    f"{subtype!r}. 허용: "
                    f"{', '.join(sorted(CONCEPT_SUBTYPES[concept])) or '(없음)'}"
                )
            types.add((concept, subtype))
    return frozenset(types)


def _load_node(where, raw, input_ports):
    if not isinstance(raw, dict) or "key" not in raw:
        raise MacroError(f"{where}: key가 있는 object여야 합니다.")
    key = str(raw["key"])
    where = f"{where}[{key}]"
    for required_key in ("role", "source"):
        if required_key not in raw:
            raise MacroError(f"{where}: 필수 key가 없습니다: {required_key}")

    source = _require_enum(where, "source", raw["source"], NodeSource)
    if source not in PRODUCIBLE_SOURCES:
        raise MacroError(
            f"{where}: macro가 만드는 node의 source는 "
            f"{', '.join(sorted(item.value for item in PRODUCIBLE_SOURCES))} "
            f"중 하나여야 합니다. (받은 값: {source.value})"
        )

    subtype = raw.get("subtype")
    if subtype is not None:
        subtype = str(subtype)
        if subtype not in KNOWN_SUBTYPES:
            raise MacroError(f"{where}: 알 수 없는 subtype입니다: {subtype!r}")

    rule = None
    raw_rule = raw.get("subtype_by_factor")
    if raw_rule is not None:
        rule = _load_subtype_rule(f"{where}.subtype_by_factor", raw_rule)

    inherit = raw.get("inherit_attributes") or {}
    if inherit and not isinstance(inherit, dict):
        raise MacroError(f"{where}.inherit_attributes: object여야 합니다.")
    inherit_from = inherit.get("from")
    if inherit_from is not None and inherit_from not in input_ports:
        raise MacroError(
            f"{where}.inherit_attributes.from: 정의되지 않은 input port입니다: "
            f"{inherit_from}"
        )
    return MacroNodeSpec(
        key=key,
        role=_require_enum(where, "role", raw["role"], FunctionalRole),
        source=source,
        subtype=subtype,
        subtype_by_factor=rule,
        inherit_from=inherit_from,
        inherit_attributes=tuple(inherit.get("names") or ()),
    )


def _load_subtype_rule(where, raw):
    if not isinstance(raw, dict) or "factor" not in raw:
        raise MacroError(f"{where}: factor가 있는 object여야 합니다.")
    cases = raw.get("cases") or {}
    if not isinstance(cases, dict) or not cases:
        raise MacroError(f"{where}.cases: 비어 있지 않은 object여야 합니다.")
    default = raw.get("default")
    if not isinstance(default, str) or not default:
        raise MacroError(f"{where}.default: subtype 이름이 필요합니다.")
    for value in (*cases.values(), default):
        if str(value) not in KNOWN_SUBTYPES:
            raise MacroError(f"{where}: 알 수 없는 subtype입니다: {value!r}")
    return SubtypeByFactor(
        factor=str(raw["factor"]),
        cases={key: str(value) for key, value in cases.items()},
        default=str(default),
    )


def _load_transformation(where, raw):
    if not isinstance(raw, dict):
        raise MacroError(f"{where}: object여야 합니다.")
    for key in ("id", "inputs", "output"):
        if key not in raw:
            raise MacroError(f"{where}: 필수 key가 없습니다: {key}")
    inputs = raw["inputs"]
    if isinstance(inputs, str):
        inputs = [inputs]
    if not isinstance(inputs, list):
        raise MacroError(f"{where}.inputs: list여야 합니다.")
    return MacroTransformationSpec(
        id=str(raw["id"]),
        inputs=tuple(str(item) for item in inputs),
        output=str(raw["output"]),
    )


def _require_enum(where, key, value, enum_type):
    try:
        return enum_type(value)
    except ValueError as error:
        allowed = ", ".join(item.value for item in enum_type)
        raise MacroError(
            f"{where}.{key}: 허용되지 않은 값 {value!r} (허용: {allowed})"
        ) from error


class MacroLibrary:
    """macro 디렉터리 전체를 이름과 output 타입으로 조회할 수 있게 담아둔다."""

    def __init__(self, macros):
        self._macros: dict[str, MacroTemplate] = {}
        for macro in macros:
            if macro.name in self._macros:
                raise MacroError(
                    f"macro 이름이 중복되었습니다: {macro.name}",
                    context={"macro": macro.name},
                )
            self._macros[macro.name] = macro

    @classmethod
    def from_directory(cls, directory=DEFAULT_MACRO_DIR):
        directory = Path(directory)
        paths = sorted(directory.glob("*.yaml"))
        if not paths:
            raise MacroError(
                f"macro YAML이 없습니다: {directory}",
                context={"directory": str(directory)},
            )
        return cls([load_macro(path) for path in paths])

    def __contains__(self, name):
        return name in self._macros

    def __len__(self):
        return len(self._macros)

    @property
    def names(self):
        return tuple(self._macros)

    def all(self):
        return tuple(self._macros.values())

    def get(self, name):
        return self._macros.get(name)

    def require(self, name):
        macro = self._macros.get(name)
        if macro is None:
            raise MacroError(
                f"알 수 없는 macro입니다: {name!r}. "
                f"사용 가능한 macro: {', '.join(self.names)}",
                context={"requested": name, "available": list(self.names)},
            )
        return macro

    def producing(self, concept, subtype):
        """(concept, subtype)을 만들 수 있는 macro를 결정적 순서로 돌려준다."""
        return tuple(sorted(
            (
                macro for macro in self._macros.values()
                if macro.produces(concept, subtype)
            ),
            key=lambda macro: (macro.priority, macro.name),
        ))

    def describe_for_prompt(self):
        return "\n".join(macro.describe_for_prompt() for macro in self.all())
