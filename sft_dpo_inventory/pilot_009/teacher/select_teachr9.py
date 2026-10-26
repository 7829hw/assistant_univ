# -*- coding: utf-8 -*-
"""TEACH-R 대상(결정 228 Y2, 실행 전 커밋, 결정적, 모델 호출 없음).

    python3 select_teachr9.py   # -> teachr_targets.json

- batch011 승인 r1 거부 60(승인 corpus v4 문장, b011-015는 수정 문장) — 지시 ``teacher_refusal_v1``, 이유 범주 = provenance gap.
- batch012 r1 초안 전부(60, ``batch012/candidates_checked.json``; 승인 전 수집 — 거르기·사용은 승인 뒤) — 같은 지시.
- RC6에 못 들어간 batch011 r2 11(b011-077·079·081·089–096; J-b011 base 정답 표본 없음) — 기존 v3b 지시(canonical 다섯 줄 = 승인 corpus v4 semantics).
- 질문당 표본 8, seed_base 20262026, 순서 = 위 순서(문항 id 순).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V4 = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v4.jsonl"
R2_MISSING = ["b011:b011-077", "b011:b011-079", "b011:b011-081", "b011:b011-089", "b011:b011-090", "b011:b011-091", "b011:b011-092",
              "b011:b011-093", "b011:b011-094", "b011:b011-095", "b011:b011-096"]
v4 = {r["id"]: r for r in (json.loads(l) for l in V4.read_text(encoding="utf-8").splitlines())}
rc6 = {json.loads(l)["metadata"]["source_record_id"] for l in (ROOT / "sft_dpo_inventory/pilot_008/build/RC6/full/sft_train.jsonl").read_text(encoding="utf-8").splitlines()}
assert not set(R2_MISSING) & rc6 and all(v4[i]["provenance"]["kind"] == "r2_contrast" for i in R2_MISSING)
out = [{"id": i, "set": "batch011_r1", "variant": "refusal_v1", "gap": r["provenance"]["gap"], "question": r["question"]}
       for i, r in sorted(v4.items()) if i.startswith("b011:") and r["provenance"]["kind"] == "r1_refusal"]
b12 = json.loads((ROOT / "sft_dpo_inventory/batch012/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
out += [{"id": f"b012:{c['id']}", "set": "batch012_r1_draft", "variant": "refusal_v1", "gap": c["gap"], "question": c["question"]}
        for c in sorted(b12, key=lambda c: c["id"]) if c["kind"] == "r1_refusal"]
out += [{"id": i, "set": "batch011_r2_not_in_rc6", "variant": "v3b", "gap": None, "question": v4[i]["question"], "semantics": v4[i]["semantics"]} for i in R2_MISSING]
assert len(out) == 131, len(out)
(HERE / "teachr_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(out), {s: sum(o["set"] == s for o in out) for s in ("batch011_r1", "batch012_r1_draft", "batch011_r2_not_in_rc6")})
