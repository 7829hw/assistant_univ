# -*- coding: utf-8 -*-
"""T-C 문항·규칙(결정 242 AA2, 실행 전 커밋, 결정적, 모델 호출 없음). ``pilot_009/teacher/select_tr9.py``와 같은 방식.

    python3 select_tc10.py   # -> tc_targets.json, tc_rule.json

- 문항: 승인 corpus v5의 근접 대조(batch011·batch012 r2 승인분 80) 중 이전 teacher 수집에 쓴 적 없는 질문(TEACH-R v3b로 모은 batch011 r2 11 제외 → 69)에서 20.
  ``random.Random(20271026)``로 가까운 거부 범주(gap)마다 3개, 남은 것에서 2개 더 → 20. 문장·semantics는 승인 corpus v5 그대로.
- 지시 ``teacher_contrast_v1``, user에 canonical 다섯 줄 + 가까운 거부 범주(gap 설명).
- 표본 8, seed_base 20271027(표본 seed = seed_base + 1000 × 질문 순번 + 표본 번호), temperature 0.6, think true, 연속 방식(결정 79).
- 통과 규칙(결정 242): trace 통과(``teacher_contrast10.evaluate`` pass: c2 정리 뒤 (a)(b)(c)(d)(e)(ii)(f')(결정 235 거르기) 모두, 내용 손실 없음) ≥ 144/160
  **그리고** 통과 trace 10개 읽기(결정 150 방식, ``random.Random(READ_SEED)``로 통과 trace에서 10개)에서 "되풀이" ≤ 3. 결과를 본 뒤 바꾸지 않는다.
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEED, SEED_BASE, READ_SEED = 20271026, 20271027, 20271028
V5 = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v5.jsonl"
USED = json.loads((ROOT / "sft_dpo_inventory/pilot_009/teacher/teachr_targets.json").read_text(encoding="utf-8"))
USED_IDS = {t["id"] for t in USED if t["variant"] == "v3b"}

r2 = sorted((r for r in (json.loads(l) for l in V5.read_text(encoding="utf-8").splitlines())
             if r["provenance"].get("kind") == "r2_contrast"), key=lambda r: r["id"])
assert len(r2) == 80 and len(USED_IDS) == 11 and USED_IDS <= {r["id"] for r in r2}
pool = [r for r in r2 if r["id"] not in USED_IDS]
rng = random.Random(SEED)
by_gap = {}
for r in pool:
    by_gap.setdefault(r["provenance"]["gap"], []).append(r)
picked = []
for g in sorted(by_gap):
    picked += rng.sample(by_gap[g], 3)
rest = [r for r in pool if r not in picked]
picked += rng.sample(rest, 2)
picked.sort(key=lambda r: r["id"])
out = [{"id": r["id"], "set": "T-C", "variant": "contrast_v1", "gap": r["provenance"]["gap"], "question": r["question"], "semantics": r["semantics"]}
       for r in picked]
(HERE / "tc_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
rule = {"decision": "242 (AA2) T-C", "targets": f"tc_targets.json (승인 corpus v5 근접 대조 80 중 TEACH-R v3b 11 뺀 {len(pool)}에서 20, gap마다 3 + 2, random.Random({SEED}))",
        "samples_per_question": 8, "seed_base": SEED_BASE, "temperature": 0.6, "think": True, "model_state": "keep_loaded (결정 79)",
        "ollama": {"version": "0.40.6", "model": "qwen3.8:27b", "digest": "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813",
                   "guard_min_rate": 33.71, "guard_source": "pilot_006/post/o1_speed.json (결정 163 O1)", "warmup": "첫 호출 전 1회(run_r9b 방식)"},
        "instruction": "grounding/prompts/teacher_contrast_v1.md",
        "trace_pass": "teacher_contrast10.evaluate pass: c2((ii) 줄만) 뒤 a·b·c·d·e·ii·f'·s235(결정 235 금지 절 이름) 모두 통과, 내용 손실 없음",
        "pass_rule": {"trace_pass_min": 144, "of": 160, "read": {"n": 10, "seed": READ_SEED, "from": "통과 trace", "method": "결정 150(끌어냄/되풀이)",
                                                                  "max_repeat": 3}},
        "if_fail": "TEACH-C 하지 않고 보고(결정 242)", "use_for_training": False, "fixed_before_run": True}
(HERE / "tc_rule.json").write_text(json.dumps(rule, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(pool), len(out), {g: sum(o["gap"] == g for o in out) for g in sorted(by_gap)}, {g: len(v) for g, v in sorted(by_gap.items())})
