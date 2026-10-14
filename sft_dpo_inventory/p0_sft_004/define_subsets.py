# -*- coding: utf-8 -*-
"""평가 부분집합 사전 정의(지시 59·60절). gold·질문 metadata만 쓴다. 모델 출력을 보지 않는다(평가 전에 commit).

    /data/hwkim/path_repeat_001/venv/py/bin/python sft_dpo_inventory/p0_sft_004/define_subsets.py   # -> subsets.json

p0_sft_001 analyze.subsets_for의 정의(dt_any·dt_pickup·dt_dropoff·dt_both·od_ne_dt·bucket·scope_reverse·refusal·gap_a_event)에 더해:
- order, aggregation, h3, sido, sigungu, emd: gold factors 값
- gap_a_like = gap_a_event(sel154 root_cause EXPRESSION == event, 기존 정의), gap_b_like = od_ne_dt(기존 정의)
- implicit endpoint(Track B와 같은 현상, 결정 84):
  - 대상: expected_outcome answered이고, gold에 pickup/dropoff 끝 slot(dimension_target ∈ {pickup, dropoff} 또는 place·scope od_role ∈ {pickup, dropoff})이 있다.
  - slot이 implicit이려면 그 방향을 가리키는 표현이 승하차 사건 어휘다.
    - pickup 사건 어휘: 승차, 탄, 태운, 태워, 타서, 타고, 올라탄, 잡아탄 / dropoff 사건 어휘: 하차, 내린, 내려, 내렸
    - 명시 역할 어휘(출발, 도착, 목적지, 향한, 들어온, 들어가는, 들어간)로만 그 방향을 말한 slot은 implicit이 아니다.
  - implicit_endpoint_all: 위 slot이 하나라도 있는 문항(승차·하차 명사 포함)
  - implicit_endpoint_verb: 그중 동사형(탄·태운·태워·타서·타고·올라탄·잡아탄·내린·내려·내렸)이 그 방향을 말하는 문항
  - 사건 어휘가 있어도 gold에 해당 방향 slot이 없으면(예: 통행량의 '손님을 태운') 넣지 않는다.
"""
import collections
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("a001", ROOT / "sft_dpo_inventory/p0_sft_001/analyze.py")
A1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A1)
SETS = A1.SETS
P = A1.P

EVENT = {"pickup": re.compile(r"(승차|올라탄|잡아탄|탄 |탄$|탄\b|태운|태워|타서|타고)"),
         "dropoff": re.compile(r"(하차|내린|내려|내렸)")}
VERB = {"pickup": re.compile(r"(올라탄|잡아탄|탄 |탄\b|태운|태워|타서|타고)"), "dropoff": re.compile(r"(내린|내려|내렸)")}
EXPLICIT = {"pickup": re.compile(r"출발"), "dropoff": re.compile(r"(도착|목적지|향한|들어온|들어가는|들어간)")}


def endpoint_slots(payload):
    f = payload.get("factors") or {}
    slots = []
    if f.get("dimension_target") in ("pickup", "dropoff"):
        slots.append(("dimension_target", f["dimension_target"]))
    for c in payload.get("concepts") or []:
        role = (c.get("attributes") or {}).get("od_role")
        if c.get("subtype") in ("place", "scope") and role in ("pickup", "dropoff"):
            slots.append(("od_role", role))
    return slots


def main():
    out = collections.defaultdict(list)
    detail = []
    for set_name, path in SETS.items():
        P.V.GOLD_PATH = path
        gold = {item["id"]: item for item in P.V.load_gold(path)["items"]}
        for k, v in A1.subsets_for(set_name, gold).items():
            out[k].extend(v)
        for i, item in gold.items():
            key = f"{set_name}:{i}"
            payload = P.V.gold_grounding(item) or {}
            f = payload.get("factors") or {}
            for name in ("order", "aggregation", "bucket"):
                if f.get(name) and name != "bucket":
                    out[name].append(key)
            if f.get("dimension") in ("h3", "sido", "sigungu", "emd"):
                out[f["dimension"]].append(key)
            if item.get("expected_outcome", "answered") != "answered":
                continue
            q = item["question"]
            slots = endpoint_slots(payload)
            implicit = [(s, d) for s, d in slots if EVENT[d].search(q)]
            verb = [(s, d) for s, d in implicit if VERB[d].search(q)]
            if implicit:
                out["implicit_endpoint_all"].append(key)
                detail.append({"key": key, "question": q, "slots": slots, "implicit_slots": implicit, "verb_slots": verb,
                               "explicit_words": {d: bool(EXPLICIT[d].search(q)) for d in ("pickup", "dropoff")}})
            if verb:
                out["implicit_endpoint_verb"].append(key)
    out["gap_a_like"] = list(out.get("gap_a_event", []))
    out["gap_b_like"] = list(out.get("od_ne_dt", []))
    doc = {"note": "gold·질문만으로 정의(모델 출력 미사용). 평가 결과 분석 전에 commit한다.",
           "sizes": {k: len(v) for k, v in sorted(out.items())}, "subsets": {k: sorted(v) for k, v in sorted(out.items())},
           "implicit_endpoint_detail": detail}
    (HERE / "subsets.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(doc["sizes"], ensure_ascii=False))
    for d in detail:
        print(d["key"], "|", d["question"], "| implicit", d["implicit_slots"], "| verb", d["verb_slots"])


if __name__ == "__main__":
    main()
