# -*- coding: utf-8 -*-
"""checkpoint 진단 panel(CHECKPOINT_DIAGNOSTIC_PLAN.md 2절). gold metadata만 쓴다. 모델 결과·정답 여부를 읽지 않는다.

    python sft_dpo_inventory/p0_sft_002/build_panel.py   # -> diagnostic_panel.json, diagnostic_panel_gold.yaml

- 모집단: p0_sft_001 평가 403문항(sel154, valid98, vendor100, aux_test_v1). key = "{set}:{id}".
- 문항마다 주 stratum 하나(아래 우선순위 첫 해당):
  scope_reverse > refusal > od_ne_dt > dimension_target > bucket > ordinary(answered, 위 어디에도 없음)
  정의는 p0_sft_001/analyze.py의 부분집합과 같다.
- stratum 안에서 sha256("p0_sft_002:panel:" + key) 오름차순으로 정렬해 앞에서 QUOTA만큼 고른다.
- panel gold: 고른 문항을 원 gold 항목 그대로 복사하고 id만 key로 바꾼다(evaluate_vendor100.load_gold 형식).
"""
import hashlib
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import evaluate_vendor100 as EV  # noqa: E402

SETS = {
    "sel154": "evaluation/partial_grounding/ab_p0_3/sel154_gold.yaml",
    "valid98": "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml",
    "vendor100": "evaluation/vendor100/gold.yaml",
    "aux_test_v1": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml",
}
QUOTA = {"scope_reverse": 6, "refusal": 8, "od_ne_dt": 10, "dimension_target": 10, "bucket": 10, "ordinary": 12}
ORDER = list(QUOTA)


def stratum(item):
    payload = EV.gold_grounding(item) or {}
    f = payload.get("factors") or {}
    concepts = payload.get("concepts") or []
    roles = {(c.get("attributes") or {}).get("od_role") for c in concepts if c.get("subtype") in ("place", "scope")} - {None}
    dt = f.get("dimension_target")
    if any(c.get("subtype") == "scope" and c.get("value") for c in concepts) and \
            any(c.get("subtype") == "place" and not c.get("value") for c in concepts):
        return "scope_reverse"
    if item.get("expected_outcome", "answered") != "answered":
        return "refusal"
    if dt and roles and dt not in roles:
        return "od_ne_dt"
    if dt:
        return "dimension_target"
    if f.get("bucket"):
        return "bucket"
    return "ordinary"


def main():
    pool, raw_items = {s: [] for s in ORDER}, {}
    for set_name, path in SETS.items():
        raw = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
        for original in raw["items"]:
            key = f"{set_name}:{original['id']}"
            item = EV.load_gold(ROOT / path)["items"][[str(x["id"]) for x in raw["items"]].index(str(original["id"]))]
            pool[stratum(item)].append(key)
            raw_items[key] = original
    panel = []
    for s in ORDER:
        ranked = sorted(pool[s], key=lambda k: hashlib.sha256(f"p0_sft_002:panel:{k}".encode()).hexdigest())
        panel += [{"key": k, "stratum": s} for k in ranked[:QUOTA[s]]]
    gold = {"note": "p0_sft_002 checkpoint 진단 panel. 원 gold 항목 복사, id = set:id. 평가 전용.",
            "items": [{**raw_items[p["key"]], "id": p["key"]} for p in panel]}
    (HERE / "diagnostic_panel_gold.yaml").write_text(yaml.safe_dump(gold, allow_unicode=True, sort_keys=False), encoding="utf-8")
    doc = {"rule": "주 stratum 우선순위 " + " > ".join(ORDER) + ", stratum 안 sha256('p0_sft_002:panel:'+key) 오름차순 앞 QUOTA개",
           "quota": QUOTA, "pool_sizes": {s: len(v) for s, v in pool.items()}, "size": len(panel), "items": panel,
           "gold_sha256": hashlib.sha256((HERE / "diagnostic_panel_gold.yaml").read_bytes()).hexdigest()}
    (HERE / "diagnostic_panel.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("pool_sizes", "size", "gold_sha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
