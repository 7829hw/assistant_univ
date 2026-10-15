# -*- coding: utf-8 -*-
"""semantics → Partial SFT target payload(P0 계약: concept마다 subtype·value·text·attributes만, support EVENT 없음, factors 그대로).

partial-grounding ``evaluation/partial_grounding/sft_p0/build_targets.py``(ab9d215)의 변환 규칙과 같다: id·concept·role·source를 지우고
EVENT를 지운다. 그 밖에, ontology로 정해지지 않는 override(값 있는 장소의 EXTENT 등)가 있으면 그 필드(role/concept)를 남긴다
(P0 계약이 허용하는 "적힌 값은 고치지 않는다", ``complete_grounding_payload``).
"""
import copy
import json


def render_partial(semantics):
    if semantics.get("unsupported"):
        return {"concepts": [], "factors": copy.deepcopy(semantics.get("factors") or {}), "unsupported": semantics["unsupported"]}
    concepts = []
    for node in semantics.get("nodes") or []:
        item = {}
        if node.get("text") is not None:
            item["text"] = node["text"]
        if node.get("concept_override"):
            item["concept"] = node["concept_override"]
        item["subtype"] = node["subtype"]
        if node.get("role_override"):
            item["role"] = node["role_override"]
        for key in ("value", "attributes"):
            if key in node:
                item[key] = copy.deepcopy(node[key])
        concepts.append(item)
    return {"concepts": concepts, "factors": copy.deepcopy(semantics.get("factors") or {})}


def render_partial_text(semantics):
    return json.dumps(render_partial(semantics), ensure_ascii=False)
