# -*- coding: utf-8 -*-
"""T-C2·TEACH-C 분석 2판(결정 248·249, 모델 호출 없음). ``analyze_c10.py``(그대로)의 사본: job 이름·규칙 파일(``tc2_rule.json``)·읽기 seed만 바꿈.

    hfvenv/bin/python analyze_c10b.py --main /home/hwkim/assistant_univ --job T-C2|TEACH-C
    -> teacher/{tc2,teachc}_analysis.json, {tc2,teachc}_read_sample.json(통과 trace 10개, 읽기용)

- 검사별 불통과 수(원본·c2 뒤), trace 통과 수, 질문별 통과 수, 통과 trace가 없는 질문, 묶음(문항 ``set``)별·가까운 거부 범주(gap)별 통과율, c2로 지운 줄 수,
  결정 235 금지 절 이름 인용 수.
- T-C2: 규칙(``tc2_rule.json``)의 1부(통과 ≥ 144/160)를 계산한다. 2부(읽기 되풀이 ≤ 3)는 사람이 읽은 뒤 ``finalize_tc2_10.py``가 합쳐 ``tc2_verdict.json``.
- 읽기 표본: 통과 trace에서 ``random.Random(seed)``로 10개(T-C2 20271032 = 규칙 고정값, TEACH-C 20272028).
"""
import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = {"T-C2": ("tc2", 20271032), "TEACH-C": ("teachc", 20272028)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    p.add_argument("--job", required=True, choices=sorted(CFG))
    a = p.parse_args()
    main_dir = Path(a.main)
    rec = main_dir / "sft_dpo_inventory/pilot_010/teacher"
    tag, read_seed = CFG[a.job]
    rows = [json.loads(l) for l in (main_dir / f"training/generated/pilot_010/teacher_{tag}/traces.jsonl").read_text(encoding="utf-8").splitlines()]
    targets = {t["id"]: t for t in json.loads((rec / f"{tag}_targets.json").read_text(encoding="utf-8"))}
    fail_raw, fail_after = Counter(), Counter()
    per_q, per_cat, per_set = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    s235 = Counter(n for r in rows for n in r["checks_after_c2"]["s235"])
    for r in rows:
        fail_raw.update(r["checks_raw"]["reasons"])
        fail_after.update(r["checks_after_c2"]["reasons"])
        if r["c2"]["content_lost"]:
            fail_after["c2_content_lost"] += 1
        q = per_q[r["id"]]
        q[0] += r["pass"]
        q[1] += 1
        c = per_cat[r["gap"] or "gap 없음"]
        c[0] += r["pass"]
        c[1] += 1
        st = per_set[targets[r["id"]]["set"]]
        st[0] += r["pass"]
        st[1] += 1
    passed = [r for r in rows if r["pass"]]
    qtext = {i: t["question"] for i, t in targets.items()}
    rate = lambda eval_count, ms: eval_count / (ms / 1000) if ms else None  # noqa: E731
    rates = [rate(r["eval_count"], r.get("eval_duration_ms")) for r in rows if r.get("eval_duration_ms")]
    out = {"job": a.job, "traces": len(rows), "questions": len(per_q), "pass": len(passed), "raw_pass": sum(r["checks_raw"]["pass"] for r in rows),
           "fail_by_check_raw": dict(fail_raw), "fail_by_check_after_c2": dict(fail_after),
           "c2_edited_traces": sum(bool(r["c2"]["removed_lines"]) for r in rows), "c2_removed_lines": sum(len(r["c2"]["removed_lines"]) for r in rows),
           "per_category": {k: {"pass": v[0], "traces": v[1], "rate": round(v[0] / v[1], 4)} for k, v in sorted(per_cat.items())},
           "per_set": {k: {"pass": v[0], "traces": v[1], "rate": round(v[0] / v[1], 4)} for k, v in sorted(per_set.items())},
           "s235_citations_after_c2": dict(s235),
           "per_question": {k: v[0] for k, v in sorted(per_q.items())},
           "questions_without_pass": sorted(k for k, v in per_q.items() if v[0] == 0),
           "questions_without_pass_by_set": dict(Counter(targets[k]["set"] for k, v in per_q.items() if v[0] == 0)),
           "questions_pass_lt4": sorted(k for k, v in per_q.items() if v[0] < 4),
           "done_reason": dict(Counter(r.get("done_reason") for r in rows)),
           "eval_tok_s": {"min": round(min(rates), 2), "median": round(sorted(rates)[len(rates) // 2], 2)} if rates else None,
           "eval_count": {"median": sorted(r["eval_count"] or 0 for r in rows)[len(rows) // 2], "max": max(r["eval_count"] or 0 for r in rows)}}
    if a.job == "T-C2":
        rule = json.loads((rec / "tc2_rule.json").read_text(encoding="utf-8"))
        out["rule_part1"] = {"trace_pass": len(passed), "min": rule["pass_rule"]["trace_pass_min"], "of": rule["pass_rule"]["of"],
                             "ok": len(passed) >= rule["pass_rule"]["trace_pass_min"]}
        read_seed = rule["pass_rule"]["read"]["seed"]
    sample = random.Random(read_seed).sample(passed, min(10, len(passed)))
    (rec / f"{tag}_read_sample.json").write_text(json.dumps({"seed": read_seed, "from": "pass traces", "n": len(sample),
                                                           "traces": [{"trace_id": r["trace_id"], "gap": r["gap"], "set": targets[r["id"]]["set"],
                                                                       "question": qtext.get(r["id"]), "thinking": r["thinking"], "content": r["content"],
                                                                       "c2_removed": r["c2"]["removed_lines"]} for r in sample]},
                                                          ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (rec / f"{tag}_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("traces", "pass", "fail_by_check_after_c2", "questions_without_pass")}, ensure_ascii=False))
    print(json.dumps(out.get("rule_part1"), ensure_ascii=False))


if __name__ == "__main__":
    main()
