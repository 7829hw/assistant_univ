# -*- coding: utf-8 -*-
"""T0 결과 분석(C5): 자동 검사 통과율, 실패 유형, 대표 예 각 3개, 지시 수정 제안의 근거. 모델 호출 없음. 지시 파일은 고치지 않는다.

    python3 analyze_t0.py   # -> t0_analysis.json

- 판정은 실행 전에 커밋한 ``teacher6.check_field_names``(``FIELD_WORDS``)·``check_conclusion`` 그대로다.
- 참고(판정 아님): 계획서 v2 8.1의 "arm 전용 필드 이름"을 좁게 읽어, Partial 출력에 없는 이름(``ARM_ONLY``: concept·role·source·id 키와
  EVENT·MEASURE·SUPPORT·SUBCOND·COND·EXTENT·implicit·LOCATION·AMOUNT·PROPORTION 값)만 셌을 때의 통과율도 낸다. 두 arm JSON에 모두 나오는 이름
  (vicinity, dimension_target, taxi_status, factors, bucket, od_role, trip_count 등)은 여기서 뺀다. 이 좁은 기준은 결과를 본 뒤 낸 것이다.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARM_ONLY = re.compile(r"\b(concepts?|role|source|EVENT|MEASURE|SUPPORT|SUBCOND|COND|EXTENT|implicit|LOCATION|AMOUNT|PROPORTION)\b|\"id\"")


def snippet(text, word, width=90):
    i = text.find(word)
    return text[max(0, i - width // 2): i + width // 2].replace("\n", " ") if i >= 0 else text[:width].replace("\n", " ")


rows = [json.loads(l) for l in (ROOT / "training/generated/pilot_006/teacher_t0/traces.jsonl").read_text(encoding="utf-8").splitlines()]
n = len(rows)
narrow = [not ARM_ONLY.search(r["thinking"]) for r in rows]
words = Counter(w for r in rows for w in r["check_a"]["found"])
narrow_words = Counter(m.group(0) for r in rows for m in ARM_ONLY.finditer(r["thinking"]))
ex_a = [{"trace_id": r["trace_id"], "found": r["check_a"]["found"][:8], "snippet": snippet(r["thinking"], r["check_a"]["found"][0])} for r in rows[:: max(1, n // 3)][:3]]
fails_final = [r for r in rows if not r["check_b"]["final_matches_canonical"]]
ex_final = [{"trace_id": r["trace_id"], "diffs": r["check_b"]["diffs"], "content": r["content"][:300]} for r in fails_final[:3]]
fails_cue = [r for r in rows if r["check_b"]["final_matches_canonical"] and not r["check_b"]["pass"]]
ex_cue = [{"trace_id": r["trace_id"], "missing": [k for k, v in r["check_b"]["cues"].items() if not v], "thinking_head": r["thinking"][:300].replace("\n", " ")}
          for r in fails_cue[:3]]
per_q = defaultdict(lambda: Counter())
for r, ok in zip(rows, narrow):
    per_q[r["id"]]["final_match"] += r["check_b"]["final_matches_canonical"]
    per_q[r["id"]]["b_pass"] += r["check_b"]["pass"]
    per_q[r["id"]]["narrow_a_and_b"] += ok and r["check_b"]["pass"]
out = {"traces": n, "questions": len(per_q), "guard": "통과(최저 78.8 tok/s ≥ 33.55, 100% GPU)",
       "verdict(pre-registered checks)": {"check_a_pass": sum(r["check_a"]["pass"] for r in rows), "check_b_pass": sum(r["check_b"]["pass"] for r in rows),
                                          "both_pass": sum(r["pass"] for r in rows)},
       "check_a_words(pre-registered list)": dict(words.most_common()),
       "reference_narrow_arm_only": {"pass": sum(narrow), "both_with_b": sum(o and r["check_b"]["pass"] for r, o in zip(rows, narrow)),
                                     "words": dict(narrow_words.most_common(12)), "note": "결과를 본 뒤 낸 참고 기준, 판정 아님"},
       "check_b_failures": {"final_json_differs": len(fails_final), "final_diff_kinds": dict(Counter(d for r in fails_final for d in r["check_b"]["diffs"])),
                            "cue_missing(final ok)": len(fails_cue), "cue_kinds": dict(Counter(k for r in fails_cue for k, v in r["check_b"]["cues"].items() if not v))},
       "examples": {"check_a": ex_a, "final_json_differs": ex_final, "cue_missing": ex_cue},
       "per_question": {k: dict(v) for k, v in per_q.items()},
       "thinking_hangul": sum(bool(re.search("[가-힣]", r["thinking"][:400])) for r in rows),
       "eval_count_median": sorted(r["eval_count"] for r in rows)[n // 2]}
(ROOT / "sft_dpo_inventory/pilot_006/teacher/t0_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: out[k] for k in ("verdict(pre-registered checks)", "reference_narrow_arm_only", "check_b_failures")}, ensure_ascii=False, indent=1))
for e in out["examples"]["check_a"]:
    print("A", e["found"], "|", e["snippet"])
for e in out["examples"]["final_json_differs"]:
    print("F", e["diffs"], "|", e["content"][:200])
for e in out["examples"]["cue_missing"]:
    print("C", e["missing"], "|", e["thinking_head"][:200])
