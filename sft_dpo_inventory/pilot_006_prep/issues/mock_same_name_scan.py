# -*- coding: utf-8 -*-
"""P9: mock gazetteer 동명 시군구 문제의 영향 범위(문항 수만, 보호 셋은 문장·id를 쓰지 않음). 모델 호출 없음. mock은 고치지 않는다.

    hfvenv/bin/python mock_same_name_scan.py   # -> mock_same_name_scan.json

정답 grounding의 장소 값({name, region}) 가운데 (1) name에 상위 지역이 붙은 표기("부산 동구"), (2) name이 대구 시군구와 같은 이름(동구·중구·서구)인데
region이 부산·서울·인천처럼 대구가 아닌 경우를 센다. (2)는 현재 mock에서 NOT_FOUND가 된다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300"))
DUP = {"동구", "중구", "서구"}


def places(payload):
    for c in (payload or {}).get("concepts") or []:
        v = c.get("value")
        if c.get("subtype") == "place" and isinstance(v, dict):
            yield v.get("name") or "", v.get("region") or ""


def classify(payload):
    kinds = set()
    for name, region in places(payload):
        if " " in name and name.split()[-1] in DUP:
            kinds.add("name_with_region_prefix")
        if name in DUP and region and "대구" not in region:
            kinds.add("dup_name_other_region(NOT_FOUND)")
        if name in DUP and not region:
            kinds.add("dup_name_no_region(resolves to 대구)")
    return kinds


def main():
    import evaluate_vendor100 as EV
    from check_aug300 import load_targets
    from grounding.full_renderer import render_full
    tg = load_targets(None)
    out = {}
    for name, rows in tg.items():
        c = Counter()
        for _, _, pl in rows:
            for k in classify(pl):
                c[k] += 1
        out[name] = {"items": len(rows), **c}
    appr = [json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl").read_text(encoding="utf-8").splitlines()]
    c, ids = Counter(), {}
    for r in appr:
        for k in classify(render_full(r["semantics"])):
            c[k] += 1
            ids.setdefault(k, []).append(r["id"])
    out["approved_train_v2"] = {"items": len(appr), **c, "ids": ids}
    hold = [json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_300.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(l)["status"] == "holdout"]
    c = Counter(k for i in hold for k in classify(EV.derive_grounding(i["gold"])))
    out["augmentation_holdout_v1"] = {"items": len(hold), **c}
    b9 = json.loads((ROOT / "sft_dpo_inventory/batch009/excluded.json").read_text(encoding="utf-8")) + \
        json.loads((ROOT / "sft_dpo_inventory/batch009/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    out["batch009_all_drafts"] = {"items": len(b9), "ids": {k: [r["id"] for r in b9 if k in classify(r["draft_grounding"])] for k in
                                                            ("name_with_region_prefix", "dup_name_other_region(NOT_FOUND)")}}
    protected = ("selection_v1", "selection_v2", "aux_test_v1", "valid98", "vendor100", "augmentation_holdout_v1")
    out["note"] = "보호 셋(" + ", ".join(protected) + ")은 문항 수만 적는다"
    (HERE / "mock_same_name_scan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "ids"} if isinstance(v, dict) else v for k, v in out.items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
