# -*- coding: utf-8 -*-
"""refusal_dev 평가 gold(초안, 승인 아님): ``candidates_checked.json`` → ``rdev_gold.yaml``(``evaluate_vendor100.load_gold`` 형식). 개발 셋 — 학습에 쓰지 않는다.

    python3 make_rdev_gold.py

- 거부 문항(r1): ``gold: []``, ``expected_outcome: unsupported``(올바른 거부 = 결과 상태 unsupported·needs_clarification이고 분석 tool 실행 없음, PLAN_FINAL 4절과 같은 규칙).
- 근접 대조(r2): ``gold`` = 정답 호출, ``expected_outcome: answered``.
- 문항 메타(묶음·종류)는 ``rdev_items_meta.json``.
"""
import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
c = json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
items, meta = [], {}
for r in c:
    refusal = r["kind"] == "r1_refusal"
    items.append({"id": r["id"], "question": r["question"], "gold_text": r["gold_text"], "gold": [] if refusal else r["gold"],
                  "expected_outcome": "unsupported" if refusal else "answered", "vendor_verdict": "-"})
    meta[r["id"]] = {"kind": r["kind"], "gap": r["gap"], "refusal": refusal}
(HERE / "rdev_gold.yaml").write_text(yaml.safe_dump({"note": "refusal_dev 초안(pilot_008 P3, 승인 아님, 개발 셋 — 학습·최종 판정에 쓰지 않음)", "items": items},
                                                    allow_unicode=True, sort_keys=False), encoding="utf-8")
(HERE / "rdev_items_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(items), sum(m["refusal"] for m in meta.values()))
