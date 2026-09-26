# -*- coding: utf-8 -*-
"""검토된 질문–의미 graph 예시 저장소(논문 부록 E.1의 example store E = {(q_i, G_i)}).

예시는 grounding 단계에 **해석 문맥**으로만 쓴다. 예시 graph를 실행하지 않고, 예시의 조건
값(날짜·장소·택시 유형)이나 계산 값을 현재 질문으로 옮기는 경로도 없다. 현재 질문의 graph는
늘 현재 질문의 LLM grounding을 composer가 조합해 만든다.

예시 하나는 다음을 갖는다.

- ``id``/``version``: 고유 id와 예시 판. 내용을 바꾸면 version을 올린다.
- ``question``: 자연어 질문. 검색 입력은 이것 하나다.
- ``grounding``: 검토한 정답 grounding(구조화 집계 계약, ``factors.aggregation_plan``).
  지원하지 않는 질문이면 ``{"unsupported": true}``다.
- ``graph``: composer가 grounding에서 만든 의미 graph의 직렬화(``serialize_graph``).
  조건 값은 적지 않는다. 확인이 필요하거나 지원하지 않는 예시면 비어 있다.
- ``macros``: 적용된 macro 목록.
- ``result_kind``: scalar | selected_groups | grouped_values | dimension_groups.
- ``aggregation``: bucket·inner·outer·select.
- ``expected_outcome``: answered | needs_clarification | unsupported. 앞의 둘이 아니면
  ``expected_error``(composer/planner가 내야 할 오류 코드)를 적는다.
- ``note``: 검토자가 적은 의미 구분 한 줄. prompt에 그대로 들어간다.
- ``source``/``split``: 출처와 데이터 분할. 저장소 예시의 split은 ``retrieval_store``뿐이다.
- ``reference``(선택): reference provider에서 실행해 맞춰 볼 기대 결과. 기대값은 손으로 세거나
  독립 SQL로 구한 값이며 provider·compiler 코드로 만들지 않는다.

등록 검증(``verify_example``)은 형식·실행 검증이다. grounding과 graph가 서로 맞고, 타입·역할·
연결성 검증(G1–G5)을 통과하며, reference 예시는 계산 결과가 기대값과 같다는 것까지 본다.
질문 의미에 대해 그 grounding이 정답이라는 판단은 사람이 검토한다(``reviewed_by``).
"""

import copy
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from geoflow import validator as geoflow_validator
from geoflow.errors import GeoFlowError

STORE_PATH = Path(__file__).resolve().parent.parent / "geoflow_examples" / "question_graph_examples.yaml"
STORE_SPLIT = "retrieval_store"
#: scalar(값 하나), selected_groups(값이 가장 큰/작은 구간), grouped_values(구간별 값 목록),
#: dimension_groups(dimension으로 나눈 그룹별 값, order·limit은 여기에만 붙는다).
RESULT_KINDS = frozenset({"scalar", "selected_groups", "grouped_values", "dimension_groups"})
OUTCOMES = frozenset({"answered", "needs_clarification", "unsupported"})
#: graph 직렬화에서 값을 적지 않는 조건 parameter. 예시의 조건 값이 prompt로 새지 않게 한다.
CONDITION_PARAMS = frozenset({"date", "time", "taxi_type", "taxi_status"})
#: 예시 기대 결과를 계산할 reference 기준일(지난달 = 2026년 8월).
REFERENCE_DATE = date(2026, 9, 25)


class ExampleStoreError(GeoFlowError):
    """예시 저장소 형식 또는 등록 검증 실패."""

    stage = "example_store"
    default_user_message = "질문 해석 예시 저장소를 읽지 못했습니다."


@dataclass(frozen=True)
class Example:
    id: str
    version: int
    question: str
    grounding: dict
    result_kind: str
    aggregation: dict
    expected_outcome: str
    note: str
    source: str
    split: str
    reviewed_by: str
    graph: tuple = ()
    macros: tuple = ()
    expected_error: str | None = None
    reference: dict | None = None
    tags: tuple = field(default_factory=tuple)

    @property
    def signature(self):
        """겹침 검사에 쓰는 의미 서명(측정값, bucket, inner, outer, select)."""
        return (_measure(self.grounding),) + tuple(
            self.aggregation.get(key) for key in ("bucket", "inner", "outer", "select"))

    def to_dict(self):
        data = {
            "id": self.id, "version": self.version, "question": self.question,
            "grounding": copy.deepcopy(self.grounding), "graph": list(self.graph),
            "macros": list(self.macros), "result_kind": self.result_kind,
            "aggregation": dict(self.aggregation), "expected_outcome": self.expected_outcome,
            "note": self.note, "source": self.source, "split": self.split,
            "reviewed_by": self.reviewed_by, "tags": list(self.tags),
        }
        if self.expected_error:
            data["expected_error"] = self.expected_error
        if self.reference is not None:
            data["reference"] = copy.deepcopy(self.reference)
        return data


@dataclass(frozen=True)
class ExampleStore:
    path: str
    version: int
    sha256: str
    examples: tuple

    def get(self, example_id):
        for example in self.examples:
            if example.id == example_id:
                return example
        raise KeyError(example_id)

    @property
    def ids(self):
        return [example.id for example in self.examples]


def _measure(grounding):
    for concept in (grounding or {}).get("concepts") or []:
        if concept.get("role") == "MEASURE":
            return concept.get("subtype")
    return None


def _required(raw, key, where):
    if key not in raw or raw[key] in (None, ""):
        raise ExampleStoreError(f"{where}: {key}가 없습니다.", code="EXAMPLE_FIELD_MISSING")
    return raw[key]


def load_store(path=STORE_PATH):
    """저장소 YAML을 읽는다. 형식만 확인한다(등록 검증은 ``verify_store``)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    document = yaml.safe_load(text) or {}
    examples, seen = [], set()
    for index, raw in enumerate(document.get("examples") or []):
        where = f"examples[{index}]"
        example_id = _required(raw, "id", where)
        if example_id in seen:
            raise ExampleStoreError(f"예시 id가 중복되었습니다: {example_id}",
                                    code="EXAMPLE_DUPLICATE_ID")
        seen.add(example_id)
        where = f"{where}({example_id})"
        kind = _required(raw, "result_kind", where)
        outcome = _required(raw, "expected_outcome", where)
        split = _required(raw, "split", where)
        if kind not in RESULT_KINDS:
            raise ExampleStoreError(f"{where}: result_kind {kind!r}", code="EXAMPLE_FIELD_INVALID")
        if outcome not in OUTCOMES:
            raise ExampleStoreError(f"{where}: expected_outcome {outcome!r}",
                                    code="EXAMPLE_FIELD_INVALID")
        if split != STORE_SPLIT:
            raise ExampleStoreError(f"{where}: 저장소 예시의 split은 {STORE_SPLIT}뿐입니다({split}).",
                                    code="EXAMPLE_SPLIT_INVALID")
        if outcome != "answered" and not raw.get("expected_error"):
            raise ExampleStoreError(f"{where}: {outcome} 예시에는 expected_error가 필요합니다.",
                                    code="EXAMPLE_FIELD_MISSING")
        examples.append(Example(
            id=example_id, version=int(_required(raw, "version", where)),
            question=_required(raw, "question", where),
            grounding=_required(raw, "grounding", where), result_kind=kind,
            aggregation=dict(raw.get("aggregation") or {}), expected_outcome=outcome,
            note=_required(raw, "note", where), source=_required(raw, "source", where),
            split=split, reviewed_by=_required(raw, "reviewed_by", where),
            graph=tuple(raw.get("graph") or ()), macros=tuple(raw.get("macros") or ()),
            expected_error=raw.get("expected_error"), reference=raw.get("reference"),
            tags=tuple(raw.get("tags") or ()),
        ))
    if not examples:
        raise ExampleStoreError(f"예시가 없습니다: {path}", code="EXAMPLE_STORE_EMPTY")
    return ExampleStore(path=str(path), version=int(document.get("version") or 0),
                        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        examples=tuple(examples))


# -- 의미 graph 직렬화 ------------------------------------------------------------


def _node_label(node):
    group = (node.attributes or {}).get("group_by")
    suffix = f", 구간={group['bucket']}" if isinstance(group, dict) and group.get("bucket") else ""
    return f"{node.id}({node.concept.value}/{node.subtype}, {node.role.value}{suffix})"


def serialize_graph(plan):
    """의미 graph를 transformation마다 한 줄로 적는다(부록 E.1 "textual description").

    조건 parameter(``CONDITION_PARAMS``)는 이름만 남기고 값은 적지 않는다. 예시의 날짜·택시
    유형이 prompt로 새지 않게 하기 위해서다. 장소 이름도 node 값이므로 적지 않는다.
    """
    nodes = {node.id: node for node in plan.concepts}
    lines = []
    for step in plan.transformations:
        refs = list(dict.fromkeys(ref.node_id for ref in step.inputs.values()))
        inputs = " + ".join(_node_label(nodes[node_id]) if nodes[node_id].source.value
                            in ("user", "implicit") else node_id for node_id in refs)
        params = [f"{key}={value}" for key, value in sorted(step.params.items())
                  if key not in CONDITION_PARAMS]
        conditions = sorted(key for key in step.params if key in CONDITION_PARAMS)
        if conditions:
            params.append("조건: " + ", ".join(conditions))
        outputs = ", ".join(_node_label(nodes[node_id]) for node_id in step.outputs)
        lines.append(f"{inputs} --{step.operator}[{'; '.join(params)}]--> {outputs}")
    return lines


# -- 등록 검증 ---------------------------------------------------------------------


def _parse(example):
    from geoflow.grounding import parse_grounding
    from geoflow.planner import UNSUPPORTED_KEY

    if example.grounding.get(UNSUPPORTED_KEY):
        return None
    return parse_grounding(copy.deepcopy(example.grounding), example.question,
                           structured_aggregation=True)


def _aggregation_of(grounding):
    spec = grounding.aggregation.to_dict()
    return {key: spec[key] for key in ("bucket", "inner", "outer", "select")}


def result_kind_of(aggregation, factors=None):
    """aggregation spec과 dimension factor에서 유도한 결과 형태."""
    if (factors or {}).get("dimension"):
        return "dimension_groups"
    if aggregation.get("select"):
        return "selected_groups"
    if aggregation.get("bucket") and not aggregation.get("outer"):
        return "grouped_values"
    return "scalar"


def verify_example(example, *, composer=None, execute_reference=True):
    """예시 하나의 등록 검증. 문제 목록을 돌려준다(비면 통과)."""
    from geoflow.composer import MacroComposer

    problems = []
    composer = composer or MacroComposer()
    try:
        grounding = _parse(example)
    except GeoFlowError as error:
        return [f"grounding 파싱 실패: {error.code}: {error.detail}"]

    if grounding is None:
        # 지원하지 않는 질문의 정답 응답. planner가 이 출력을 거부 오류로 바꾸는지 본다.
        if example.expected_outcome != "unsupported":
            problems.append("unsupported grounding인데 expected_outcome이 unsupported가 아니다")
        if example.graph or example.macros:
            problems.append("unsupported 예시에 graph/macros가 있다")
        if example.expected_error != "UNSUPPORTED_QUESTION":
            problems.append("unsupported 예시의 expected_error는 UNSUPPORTED_QUESTION이다")
        return problems

    aggregation = _aggregation_of(grounding)
    if aggregation != {key: example.aggregation.get(key)
                       for key in ("bucket", "inner", "outer", "select")}:
        problems.append(f"aggregation 불일치: grounding={aggregation}, 예시={example.aggregation}")
    kind = result_kind_of(aggregation, grounding.factors)
    if kind != example.result_kind:
        problems.append(f"result_kind 불일치: 유도={kind}, "
                        f"예시={example.result_kind}")
    try:
        plan = composer.compose(grounding)
    except GeoFlowError as error:
        if example.expected_outcome == "answered":
            problems.append(f"조합 실패: {error.code}: {error.detail}")
        elif error.code != example.expected_error:
            problems.append(f"조합 오류 코드 {error.code} != 기대 {example.expected_error}")
        if example.graph or example.macros:
            problems.append("조합되지 않는 예시에 graph/macros가 있다")
        return problems
    if example.expected_outcome != "answered":
        problems.append(f"{example.expected_outcome} 예시인데 조합에 성공했다")
        return problems

    report = geoflow_validator.validate(plan)
    if not report.ok:
        problems.append(f"G1–G5 검증 실패: {report.to_dict()}")
    if tuple(plan.applied_macros) != example.macros:
        problems.append(f"macros 불일치: 조합={plan.applied_macros}, 예시={list(example.macros)}")
    if tuple(serialize_graph(plan)) != example.graph:
        problems.append("graph 직렬화 불일치:\n  조합=" + json.dumps(serialize_graph(plan),
                                                                ensure_ascii=False)
                        + "\n  예시=" + json.dumps(list(example.graph), ensure_ascii=False))
    if example.reference is not None and execute_reference:
        problems.extend(_verify_reference(example))
    return problems


def _verify_reference(example):
    """reference provider에서 예시 grounding을 끝까지 실행해 기대 결과와 맞춘다."""
    from geoflow.pipeline import GeoFlowPipeline
    from geoflow.providers import REFERENCE, profile_for
    from build import build
    from tool_executor import ToolExecutor
    from tool_handlers import get_tool_handlers

    class _Scripted:
        model = "example-store"

        def chat(self, messages, tools=None, **kwargs):
            return {"message": {"content": json.dumps(example.grounding, ensure_ascii=False)}}

    tools, _prompt = build()
    executor = ToolExecutor(tools=tools, handlers=get_tool_handlers(REFERENCE), provider=REFERENCE)
    run = GeoFlowPipeline.create(
        client=_Scripted(), tool_executor=executor, aggregation_grounding="structured",
        clock=lambda: REFERENCE_DATE, execution_profile=profile_for(REFERENCE),
    ).run(example.question)
    want = example.reference
    if run.outcome != "answered":
        return [f"reference 실행 실패: {(run.error or {}).get('code')}"]
    value = (run.execution or {}).get("final_value")
    if isinstance(value, dict):
        labels = [group.get("label") for group in value.get("groups") or []]
        if labels != list(want.get("groups") or []) or not _close(value.get("value"),
                                                                   want.get("value")):
            return [f"reference 결과 불일치: {value} != {want}"]
        return []
    if want.get("groups") or not _close(value, want.get("value")):
        return [f"reference 결과 불일치: {value} != {want}"]
    return []


def _close(a, b):
    return isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) < 1e-6


def verify_store(store, *, execute_reference=True):
    """저장소 전체 등록 검증. {예시 id: 문제 목록}(문제가 있는 예시만)."""
    from geoflow.composer import MacroComposer

    composer = MacroComposer()
    failures = {}
    for example in store.examples:
        problems = verify_example(example, composer=composer,
                                  execute_reference=execute_reference)
        if problems:
            failures[example.id] = problems
    return failures


def draft_entry(question, grounding: dict[str, Any]):
    """새 예시 초안의 유도 필드(graph, macros, aggregation, result_kind). 검토 전 초안이다."""
    from geoflow.composer import MacroComposer

    draft = Example(id="draft", version=1, question=question, grounding=grounding,
                    result_kind="scalar", aggregation={}, expected_outcome="answered",
                    note="-", source="-", split=STORE_SPLIT, reviewed_by="-")
    try:
        parsed = _parse(draft)
    except GeoFlowError as error:
        return {"parse_error": f"{error.code}: {error.detail}"}
    if parsed is None:
        return {"grounding": grounding}
    aggregation = _aggregation_of(parsed)
    entry = {"aggregation": aggregation,
             "result_kind": result_kind_of(aggregation, parsed.factors)}
    try:
        plan = MacroComposer().compose(parsed)
    except GeoFlowError as error:
        entry["compose_error"] = error.code
        return entry
    entry.update(graph=serialize_graph(plan), macros=list(plan.applied_macros))
    return entry
