# -*- coding: utf-8 -*-
"""semantics → Full SFT target payload(현재 Full 계약: concept마다 id·concept·subtype·role·source, support EVENT 포함 가능).

- concept·role·source는 ontology(``grounding.completion._inferred_fields``)로 정하고, semantics에 override가 있으면 그것을 쓴다.
- id는 ``{subtype}_{순번}``(Partial completion과 같은 규칙), EVENT는 ``event``가 있을 때만 측정값 앞에 넣는다(Full target 관례).
- 직렬화는 trunk 학습 target 직렬화(``training.data.canonicalize.serialize_planner_target``)를 쓴다(``render_full_text``).
"""
import copy

from grounding.completion import _inferred_fields


def render_full(semantics):
    if semantics.get("unsupported"):
        return {"concepts": [], "factors": copy.deepcopy(semantics.get("factors") or {}), "unsupported": semantics["unsupported"]}
    concepts, counters, measure_index = [], {}, None
    for node in semantics.get("nodes") or []:
        inferred = _inferred_fields({"subtype": node.get("subtype"), "value": node.get("value")})
        concept = node.get("concept_override") or inferred["concept"]
        role = node.get("role_override") or inferred["role"]
        source = inferred["source"] if not node.get("role_override") else ("user" if role in ("SUBCOND", "COND", "EXTENT") else "implicit")
        counters[node["subtype"]] = counters.get(node["subtype"], 0) + 1
        item = {"id": f"{node['subtype']}_{counters[node['subtype']]}"}
        if node.get("text") is not None:
            item["text"] = node["text"]
        item.update({"concept": concept, "subtype": node["subtype"], "role": role, "source": source})
        for key in ("value", "attributes"):
            if key in node:
                item[key] = copy.deepcopy(node[key])
        if role == "MEASURE" and measure_index is None:
            measure_index = len(concepts)
        concepts.append(item)
    if semantics.get("event"):
        event = {"id": semantics["event"], "concept": "EVENT", "subtype": semantics["event"], "role": "SUPPORT", "source": "implicit"}
        concepts.insert(measure_index if measure_index is not None else len(concepts), event)
    return {"concepts": concepts, "factors": copy.deepcopy(semantics.get("factors") or {})}


def render_full_text(semantics):
    from training.data.canonicalize import serialize_planner_target
    return serialize_planner_target(render_full(semantics))
