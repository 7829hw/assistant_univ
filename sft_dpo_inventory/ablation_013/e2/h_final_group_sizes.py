# -*- coding: utf-8 -*-
"""H-final template_group별 문항 수 분포(결정 263 D2). **문항 내용·정답·그룹 이름은 읽어 출력하지 않는다.** yaml에서 각 문항의 ``template_group`` 값만 세어
그룹 크기 목록(이름 없이 크기만), 히스토그램, 20·30·50문항 이상 그룹 수를 낸다. 비교용으로 H-dev(이미 측정에 쓴 셋)의 같은 통계도 낸다. 모델 호출 없음.

    python3 sft_dpo_inventory/ablation_013/e2/h_final_group_sizes.py   # -> e2/h_final_group_sizes.json
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
E2 = HERE.parents[1] / "ablation_012/e2"
SHA = {"h_final.yaml": "bbc42650", "h_dev.yaml": "9c7a0078"}
BINS = [(1, 4), (5, 9), (10, 14), (15, 19), (20, 29), (30, 39), (40, 49), (50, 74), (75, 99), (100, 10 ** 9)]


def stats(name):
    p = E2 / name
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if not h.startswith(SHA[name]):
        raise SystemExit(f"{name} sha256 {h[:8]} != {SHA[name]}")
    items = yaml.safe_load(p.read_text(encoding="utf-8"))["items"]
    sizes = sorted(Counter(it["template_group"] for it in items).values(), reverse=True)
    del items
    return {"file": f"sft_dpo_inventory/ablation_012/e2/{name}", "sha256": h, "items": sum(sizes), "groups": len(sizes),
            "group_sizes_desc_no_names": sizes,
            "histogram": {f"{a}–{b}" if b < 10 ** 9 else f"{a}+": sum(1 for s in sizes if a <= s <= b) for a, b in BINS},
            "groups_ge": {str(t): sum(1 for s in sizes if s >= t) for t in (20, 30, 50)},
            "items_in_groups_ge": {str(t): sum(s for s in sizes if s >= t) for t in (20, 30, 50)},
            "max": sizes[0], "median": sizes[len(sizes) // 2], "min": sizes[-1]}


def main():
    out = {"note": "결정 263 D2: H-final의 template_group별 문항 수 분포만 연다(문항 내용·정답·그룹 이름은 열지 않음). H-final 봉인 유지, 측정 없음. H-dev는 비교용.",
           "H-final": stats("h_final.yaml"), "H-dev(비교)": stats("h_dev.yaml")}
    (HERE / "h_final_group_sizes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k in ("H-final", "H-dev(비교)"):
        v = out[k]
        print(k, v["items"], v["groups"], v["groups_ge"], v["histogram"], "max", v["max"], "median", v["median"])


if __name__ == "__main__":
    main()
