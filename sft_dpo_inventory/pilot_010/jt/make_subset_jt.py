# -*- coding: utf-8 -*-
"""pilot_010 JT(결정 271, PLAN_JT 1절) H-final 층화 부분집합 1,000문항 id 목록. 모델 호출 없음, 정답·응답을 보지 않는다(id·template_group만).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/jt/make_subset_jt.py

- 모집단: ``ablation_012/e2/h_final.yaml``(3,000문항, sha256 ``bbc42650…``), 층 = ``template_group``(160개).
- 배정: 층 크기 n_g × 1000/3000의 정수 부분을 먼저 주고, 남은 수를 소수 부분이 큰 층부터 하나씩(동률은 층 이름 순) 준다(최대 잉여 방식).
- 층 안 추출: ``numpy.random.default_rng(20261119)``를 층 이름 순으로 차례로 써서 층 문항(원래 순서)의 ``permutation``에서 앞 m_g개.
- 출력 순서는 h_final.yaml의 원래 문항 순서. ``hfinal_subset1000_ids.txt``(쉼표 구분 한 줄)와 ``hfinal_subset1000.json``(층별 수·sha256).
- 범위 규칙(PLAN_JT 3절)에서 "넘으면"일 때만 쓴다.
"""
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GOLD = ROOT / "sft_dpo_inventory/ablation_012/e2/h_final.yaml"
N, SEED = 1000, 20261119


def main():
    items = yaml.safe_load(GOLD.read_text(encoding="utf-8"))["items"]
    total = len(items)
    groups = defaultdict(list)
    for it in items:
        groups[it["template_group"]].append(it["id"])
    names = sorted(groups)
    quota = {g: len(groups[g]) * N / total for g in names}
    alloc = {g: math.floor(q) for g, q in quota.items()}
    rest = N - sum(alloc.values())
    for g in sorted(names, key=lambda g: (-(quota[g] - alloc[g]), g))[:rest]:
        alloc[g] += 1
    assert sum(alloc.values()) == N
    rng = np.random.default_rng(SEED)
    chosen = set()
    for g in names:
        ids = groups[g]
        perm = rng.permutation(len(ids))
        chosen.update(ids[i] for i in perm[:alloc[g]])
    out = [it["id"] for it in items if it["id"] in chosen]
    assert len(out) == N
    line = ",".join(out)
    (HERE / "hfinal_subset1000_ids.txt").write_text(line + "\n", encoding="utf-8")
    rec = {"decision": 271, "plan": "sft_dpo_inventory/pilot_010/PLAN_JT.md", "population": str(GOLD.relative_to(ROOT)),
           "population_sha256": hashlib.sha256(GOLD.read_bytes()).hexdigest(), "population_items": total, "n": N, "rng": f"numpy default_rng({SEED})",
           "method": "template_group 비례, 최대 잉여 배정(동률 층 이름 순), 층 이름 순으로 층마다 permutation 앞 m_g개, 원래 순서로 출력",
           "groups": len(names), "alloc": {g: {"n": len(groups[g]), "m": alloc[g]} for g in names},
           "ids_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(), "ids_file": "sft_dpo_inventory/pilot_010/jt/hfinal_subset1000_ids.txt"}
    (HERE / "hfinal_subset1000.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"n": N, "groups": len(names), "ids_sha256": rec["ids_sha256"][:12], "min_m": min(alloc.values()), "max_m": max(alloc.values())}))


if __name__ == "__main__":
    main()
