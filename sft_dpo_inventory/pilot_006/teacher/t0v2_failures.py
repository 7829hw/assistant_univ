# -*- coding: utf-8 -*-
"""T0' 결과 뒤 분석(판정 아님, 판정은 ``analyze_t0v2.py``가 실행 전 규칙으로 이미 냈다). 모델 호출 없음. 지시 파일·규칙은 바꾸지 않는다.

    python3 t0v2_failures.py   # -> t0v2_failures.json

- (b) 항목별 불일치 유형(기대값 → teacher 결론), 질문별 통과 수, (a)에 걸린 단어와 위치(thinking/결론), 결론 줄을 못 읽은 경우.
- 수정 제안(사용자 결정용)의 근거로만 쓴다.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sets = {t["id"]: t["set"] for t in json.loads((HERE / "t0v2_targets.json").read_text(encoding="utf-8"))}
rows = [json.loads(l) for l in (ROOT / "training/generated/pilot_006/teacher_t0v2/traces.jsonl").read_text(encoding="utf-8").splitlines()]
out = {}
for s in ("ii_judge", "i_reference"):
    rs = [r for r in rows if sets[r["id"]] == s]
    mism = defaultdict(Counter)
    for r in rs:
        b = r["check_b"]
        for k, ok in b["items"].items():
            if not ok:
                mism[k][f"{json.dumps(b['expected'][k], ensure_ascii=False)} → {json.dumps(b['got'][k], ensure_ascii=False)}"] += 1
    a_where = Counter()
    for r in rs:
        for w in r["check_a"]["found"]:
            a_where[f"{w}@{'content' if w in r['content'] else 'thinking'}"] += 1
    perq = Counter()
    for r in rs:
        perq[r["id"]] += r["pass"]
    out[s] = {"traces": len(rs), "item_fail_counts": {k: sum(v.values()) for k, v in mism.items()},
              "item_mismatch_top": {k: dict(v.most_common(6)) for k, v in mism.items()}, "check_a_words": dict(a_where),
              "unparsed": sum(not r["check_b"]["parsed_all_lines"] for r in rs),
              "questions_pass_dist": dict(Counter(perq.values())), "per_question_pass": dict(perq)}
(HERE / "t0v2_failures.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for s, d in out.items():
    print(s, d["traces"], d["item_fail_counts"], "unparsed", d["unparsed"], d["check_a_words"])
    for k, v in d["item_mismatch_top"].items():
        print("  ", k, v)
