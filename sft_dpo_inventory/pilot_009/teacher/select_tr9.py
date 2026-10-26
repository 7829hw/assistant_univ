# -*- coding: utf-8 -*-
"""T-R 문항·규칙(결정 228 Y2, 실행 전 커밋, 결정적, 모델 호출 없음).

    python3 select_tr9.py   # -> tr_targets.json, tr_rule.json

- 문항: 승인 corpus v4의 batch011 r1 거부 60(b011-015는 승인 수정 문장) 중 20. 이전 teacher 확인에 쓴 적 없는 질문들(batch011은 teacher 수집 대상이 아니었음).
  ``random.Random(20261026)``로 범주(gap)마다 3개, 남은 40에서 2개 더 → 20.
- 표본 8, seed_base 20261926(표본 seed = seed_base + 1000 × 질문 순번 + 표본 번호), temperature 0.6, think true, 연속 방식(결정 79).
- 통과 규칙(결정 228): trace 통과(``teacher_refusal9.evaluate`` pass: c2 정리 뒤 (a)(c)(d)(e)(ii)(f) 모두) ≥ 144/160 **그리고**
  통과 trace 10개 읽기(결정 150 방식, ``random.Random(READ_SEED)``로 통과 trace에서 10개)에서 "되풀이" ≤ 3. 결과를 본 뒤 바꾸지 않는다.
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEED, SEED_BASE, READ_SEED = 20261026, 20261926, 20261027
V4 = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v4.jsonl"

r1 = sorted((r for r in (json.loads(l) for l in V4.read_text(encoding="utf-8").splitlines())
             if r["id"].startswith("b011:") and r["provenance"]["kind"] == "r1_refusal"), key=lambda r: r["id"])
assert len(r1) == 60
rng = random.Random(SEED)
by_gap = {}
for r in r1:
    by_gap.setdefault(r["provenance"]["gap"], []).append(r)
picked = []
for g in sorted(by_gap):
    picked += rng.sample(by_gap[g], 3)
rest = [r for r in r1 if r not in picked]
picked += rng.sample(rest, 2)
picked.sort(key=lambda r: r["id"])
out = [{"id": r["id"], "set": "T-R", "variant": "refusal_v1", "gap": r["provenance"]["gap"], "question": r["question"]} for r in picked]
(HERE / "tr_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
rule = {"decision": "228 (Y2) T-R", "targets": "tr_targets.json (batch011 승인 r1 20, gap마다 3 + 2, random.Random(20261026))",
        "samples_per_question": 8, "seed_base": SEED_BASE, "temperature": 0.6, "think": True, "model_state": "keep_loaded (결정 79)",
        "ollama": {"version": "0.40.6", "model": "qwen3.8:27b", "digest": "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813",
                   "guard_min_rate": 33.71, "guard_source": "pilot_006/post/o1_speed.json (결정 163 O1)"},
        "instruction": "grounding/prompts/teacher_refusal_v1.md", "trace_pass": "teacher_refusal9.evaluate pass: c2((ii) 줄만) 뒤 a·c·d·e·ii·f 모두 통과, 내용 손실 없음",
        "pass_rule": {"trace_pass_min": 144, "of": 160, "read": {"n": 10, "seed": READ_SEED, "from": "통과 trace", "method": "결정 150(끌어냄/되풀이)",
                                                                  "max_repeat": 3}},
        "if_fail": "TEACH-R 하지 않고 보고(결정 228)", "use_for_training": False, "fixed_before_run": True}
(HERE / "tr_rule.json").write_text(json.dumps(rule, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(out), {g: sum(o["gap"] == g for o in out) for g in sorted(by_gap)})
