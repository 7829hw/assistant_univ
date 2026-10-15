# -*- coding: utf-8 -*-
"""Canonical gold(계획서 v2 5절, W5). 질문마다 하나의 레코드: execution 층 + semantics 층.

- **execution**: vendor 형식 Tool 호출 열(``[{tool, args}]``). 정답의 불변 조건. 출처가 Full target뿐이면 그 target을 trunk 경로로 실행한
  호출 열을 적는다(``execution_source``로 구분).
- **semantics**: 표현과 무관한 의미 판단.
  - ``nodes``: concept 노드 목록(측정값·장소·scope 등). 노드마다 ``subtype``, ``value``, ``text``(질문 span), ``attributes``(od_role 등),
    그리고 ontology로 정해지지 않는 것만 ``concept_override``·``role_override``(예: 값 있는 장소의 EXTENT). id·source는 넣지 않는다.
  - ``event``: Full target에 적힌 support EVENT subtype(없으면 None). Partial 표현은 적지 않는다(composer가 측정값으로 붙인다).
  - ``factors``: 모든 factor(조건 date·time·taxi_type·taxi_status와 구조 dimension·dimension_target·bucket·rollup·aggregation·order·limit·
    vicinity·answer 등) 그대로.
  - ``unsupported``: 거부(refusal) 표시.
  - ``view``(읽기용 요약, 렌더링에 쓰지 않음): measure(subtype, text), conditions(subtype, span, value, od_role), dimension, dimension_target,
    bucket/rollup, aggregation, order/limit, vicinity, refusal.
- 렌더러: ``grounding.full_renderer.render_full``, ``grounding.partial_renderer.render_partial``. 검증 사슬: ``grounding.validation``.
"""
import copy
import hashlib
import json

from grounding.completion import _inferred_fields

STRUCTURAL = ("id", "concept", "role", "source")
STRUCTURE_FACTORS = ("dimension", "dimension_target", "bucket", "rollup", "aggregation", "order", "limit", "vicinity", "answer",
                     "aggregation_plan")
CONDITION_FACTORS = ("date", "time", "taxi_type", "taxi_status")
NODE_KEYS = ("subtype", "value", "text", "attributes", "concept_override", "role_override")


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def semantics_from_full(payload):
    """Full target payload → semantics. 자연어를 읽지 않는다(결정적)."""
    payload = copy.deepcopy(payload)
    if payload.get("unsupported"):
        return {"nodes": [], "event": None, "factors": payload.get("factors") or {}, "unsupported": payload["unsupported"]}
    nodes, event = [], None
    for raw in payload.get("concepts") or []:
        if raw.get("concept") == "EVENT":
            event = raw.get("subtype")
            continue
        node = {k: raw[k] for k in ("subtype", "value", "text", "attributes") if raw.get(k) not in (None, "", {})}
        inferred = _inferred_fields({k: raw.get(k) for k in ("subtype", "value")})
        if raw.get("concept") and raw.get("concept") != inferred["concept"]:
            node["concept_override"] = raw["concept"]
        if raw.get("role") and raw.get("role") != inferred["role"]:
            node["role_override"] = raw["role"]
        nodes.append(node)
    return {"nodes": nodes, "event": event, "factors": payload.get("factors") or {}, "unsupported": None}


def semantics_from_partial(payload):
    """Partial target payload → semantics(구조 필드가 있으면 Full과 같이 처리)."""
    return semantics_from_full(payload)


def view(semantics):
    """읽기용 요약(계획서 v2 5.1의 항목). 비교·충돌 판정에도 쓴다."""
    factors = semantics.get("factors") or {}
    measure, conditions = None, []
    for node in semantics.get("nodes") or []:
        inferred = _inferred_fields({"subtype": node.get("subtype"), "value": node.get("value")})
        role = node.get("role_override") or inferred["role"]
        if role == "MEASURE":
            measure = {"subtype": node.get("subtype"), "text": node.get("text")}
        else:
            conditions.append({"subtype": node.get("subtype"), "span": node.get("text"), "value": node.get("value"),
                               "od_role": (node.get("attributes") or {}).get("od_role"),
                               **({"role": node["role_override"]} if node.get("role_override") else {})})
    conditions += [{"subtype": key, "span": None, "value": factors[key], "od_role": None} for key in CONDITION_FACTORS if key in factors]
    out = {"measure": measure, "conditions": conditions,
           **{key: factors.get(key) for key in STRUCTURE_FACTORS if key in factors},
           "refusal": semantics.get("unsupported")}
    return out


def semantic_key(semantics, *, with_text=False):
    """같은 뜻인지 비교하는 키. 기본은 text span을 뺀다(span 차이는 따로 보고)."""
    nodes = []
    for node in semantics.get("nodes") or []:
        item = {k: node[k] for k in NODE_KEYS if k in node and (with_text or k != "text")}
        nodes.append(_dump(item))
    body = {"nodes": sorted(nodes), "event": semantics.get("event"), "factors": semantics.get("factors") or {},
            "unsupported": semantics.get("unsupported")}
    return hashlib.sha256(_dump(body).encode("utf-8")).hexdigest()


def record(record_id, question, source, *, semantics, execution=None, execution_source=None, status=None, provenance=None):
    """canonical 레코드 하나."""
    return {"id": record_id, "question": question, "source": source, "status": status,
            "execution": execution, "execution_source": execution_source,
            "semantics": semantics, "view": view(semantics),
            "semantic_key": semantic_key(semantics), "semantic_key_with_text": semantic_key(semantics, with_text=True),
            "provenance": provenance or {}}
