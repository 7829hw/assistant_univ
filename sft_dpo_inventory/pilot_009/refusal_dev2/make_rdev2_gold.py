# -*- coding: utf-8 -*-
"""refusal_dev 확장 gold(초안, 승인 아님; ``pilot_008/refusal_dev/make_rdev_gold.py``와 같은 형식). 개발 셋 — 학습에 쓰지 않는다.

    python3 make_rdev2_gold.py   # -> rdev2_gold.yaml(확장 60, J-rdev2 진단 셀), rdev2_items_meta.json

거부 문항: ``gold: []``, ``expected_outcome: unsupported``(올바른 거부 = 결과 상태 unsupported·needs_clarification이고 분석 tool 실행 없음).
승인 뒤 v1 승인본(거부 30·대조 30)과 합쳐 refusal_dev v2(거부 90·대조 30)를 만든다(이 세션에서 하지 않음).
"""
import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
c = json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
assert len(c) == 60 and all(r["kind"] == "r1_refusal" for r in c)
items = [{"id": r["id"], "question": r["question"], "gold_text": "", "gold": [], "expected_outcome": "unsupported", "vendor_verdict": "-"} for r in c]
meta = {r["id"]: {"kind": r["kind"], "gap": r["gap"], "refusal": True} for r in c}
(HERE / "rdev2_gold.yaml").write_text(yaml.safe_dump({"note": "refusal_dev 확장 초안(pilot_009 준비 P3, 승인 아님, 개발 셋 — 학습·최종 판정에 쓰지 않음)", "items": items},
                                                     allow_unicode=True, sort_keys=False), encoding="utf-8")
(HERE / "rdev2_items_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(items))
