# -*- coding: utf-8 -*-
"""결정 150(L2): T0''(iii) v3b trace 중 (a)(b)(c) 통과분에서 10개 무작위 선택. seed는 실행 전에 커밋한다(아래 SEED).

    python3 pick_v3b_read.py   # -> v3b_read_sample.json (trace_id, 질문 id, 순서)
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEED = 20261650
rows = [json.loads(l) for l in (ROOT / "training/generated/pilot_006/teacher_t0v3b/traces.jsonl").read_text(encoding="utf-8").splitlines()]
ok = sorted((r for r in rows if r["pass"]), key=lambda r: r["trace_id"])
pick = random.Random(SEED).sample(ok, 10)
(HERE / "v3b_read_sample.json").write_text(json.dumps({"seed": SEED, "pool": len(ok), "picked": [{"trace_id": r["trace_id"], "id": r["id"]} for r in pick]},
                                                      ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(ok), [r["trace_id"] for r in pick])
