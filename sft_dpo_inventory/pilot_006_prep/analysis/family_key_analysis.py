# -*- coding: utf-8 -*-
"""H3 준비: family 키 분석(문장은 읽거나 출력하지 않고, 정답 grounding의 family 구조만 센다). 모델 호출 없음.

    hfvenv/bin/python family_key_analysis.py   # -> family_key_analysis.json

- family 키(``training.annotations.inventory.family_key``) = digest([측정 (concept, subtype) 목록, 장소 od_role 목록,
  factors 중 aggregation·rollup·bucket·answer(value 제외)·dimension·dimension_target·order·vicinity]).
  날짜·시간·택시 유형·운행 상태·limit·장소 값·문장은 들어가지 않는다.
- 결정 120: selection_v2, augmentation_holdout_v1, valid98, aux_test_v1 중 하나와 family가 같으면 뺀다(업체 100만·template만은 되살림).
- 출력: 셋별 family 구조 목록(읽을 수 있는 형태, 문항 수), 약점 네 가지 구조 공간에서 넷과 겹치는 구조.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300"))
KEEP_OUT = ("selection_v2", "holdout", "valid98", "aux_test_v1")


def struct(payload):
    from training.data.canonicalize import flatten_source
    raw = flatten_source(payload)
    if raw.get("unsupported"):
        return {"unsupported": True}
    meas = sorted(f"{c.get('concept')}:{c.get('subtype')}" for c in raw["concepts"] if c.get("concept") in {"AMOUNT", "PROPORTION"})
    od = sorted((c.get("attributes") or {}).get("od_role", c.get("od_role", "")) for c in raw["concepts"] if c.get("concept") == "LOCATION")
    f = {k: v for k, v in raw["factors"].items() if k in {"aggregation", "rollup", "bucket", "answer", "dimension", "dimension_target", "order", "vicinity"}}
    if f.get("answer") == "value":
        f.pop("answer")
    return {"measures": meas, "od": [x for x in od if x], "factors": f}


def main():
    import evaluate_vendor100 as EV
    from check_aug300 import load_targets
    from training.annotations.inventory import family_key
    tg = load_targets(None)
    hold = {i["id"] for i in json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/holdout_v1.json").read_text(encoding="utf-8"))["list"]}
    tg["holdout"] = [(i["id"], None, EV.derive_grounding(i["gold"])) for i in
                     (json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_300.jsonl").read_text(encoding="utf-8").splitlines())
                     if i["id"] in hold]
    fam = defaultdict(lambda: {"struct": None, "sets": Counter()})
    for name, rows in tg.items():
        if name not in KEEP_OUT + ("vendor100", "selection_v1"):
            continue
        for _, _, payload in rows:
            if not payload:
                continue
            try:
                k = family_key(payload)
            except Exception:  # noqa: BLE001
                continue
            fam[k]["struct"] = struct(payload)
            fam[k]["sets"][name] += 1
    rows = [{"family": k[:12], **v["struct"], "sets": dict(v["sets"]), "blocks_training(decision 120)": any(s in KEEP_OUT for s in v["sets"])}
            for k, v in fam.items()]
    rows.sort(key=lambda r: (r.get("measures") or [], r.get("od") or [], json.dumps(r.get("factors"), sort_keys=True)))
    blocked = [r for r in rows if r["blocks_training(decision 120)"]]
    summary = {"families_total": len(rows), "families_blocking": len(blocked),
               "blocking_by_set": {s: sum(1 for r in rows if s in r["sets"]) for s in KEEP_OUT},
               "blocking_with_dimension_target": sum(1 for r in blocked if r.get("factors", {}).get("dimension_target")),
               "blocking_valueless_place(no measure)": [r for r in blocked if not r.get("measures") and not r.get("unsupported")],
               "blocking_dt_no_order": [r for r in blocked if r.get("factors", {}).get("dimension_target") and not r.get("factors", {}).get("order")],
               "blocking_od_ne_dt": [r for r in blocked if r.get("factors", {}).get("dimension_target") and r.get("od")
                                     and set(r["od"]) != {r["factors"]["dimension_target"]}]}
    (HERE / "family_key_analysis.json").write_text(json.dumps({"summary": summary, "families": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in summary.items()}, ensure_ascii=False))
    for r in blocked:
        if r.get("factors", {}).get("dimension_target") or not r.get("measures"):
            print(r["measures"], r["od"], r["factors"], r["sets"])


if __name__ == "__main__":
    main()
