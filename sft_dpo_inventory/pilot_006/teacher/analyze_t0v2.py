# -*- coding: utf-8 -*-
"""T0' 판정(결정 131 G1). 실행 전에 커밋한 ``t0v2_rule.json``을 그대로 적용한다. 모델 호출 없음.

    python3 analyze_t0v2.py --main /home/hwkim/assistant_univ   # -> t0v2_verdict.json

- 판정: (ii) ``ii_judge`` 20질문 × 8 = 160건에서 (a) 160/160 그리고 (b) ≥ 136/160.
- 참고(판정 아님): (i) T0와 같은 20문항의 (a)(b), 결론 다섯 줄 항목별 일치율, 결론 줄을 모두 읽은 비율, thinking 한글 비율, eval_count 중앙값.
  v2는 최종 JSON을 쓰지 않으므로 T0의 "최종 JSON 일치"에 대응하는 값은 "결론 다섯 줄이 canonical과 모두 같음"((b)와 같음)이다.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    rule = json.loads((HERE / "t0v2_rule.json").read_text(encoding="utf-8"))
    sets = {t["id"]: t["set"] for t in json.loads((HERE / "t0v2_targets.json").read_text(encoding="utf-8"))}
    rows = [json.loads(l) for l in (main_dir / "training/generated/pilot_006/teacher_t0v2/traces.jsonl").read_text(encoding="utf-8").splitlines()]
    out = {"rule": rule, "sets": {}}
    for s in ("ii_judge", "i_reference"):
        rs = [r for r in rows if sets[r["id"]] == s]
        items = Counter()
        for r in rs:
            for k, v in r["check_b"]["items"].items():
                items[k] += bool(v)
        out["sets"][s] = {"traces": len(rs), "questions": len({r["id"] for r in rs}), "check_a_pass": sum(r["check_a"]["pass"] for r in rs),
                          "check_b_pass": sum(r["check_b"]["pass"] for r in rs), "both_pass": sum(r["pass"] for r in rs),
                          "conclusion_lines_parsed": sum(r["check_b"]["parsed_all_lines"] for r in rs), "items_match": dict(items),
                          "check_a_words": dict(Counter(w for r in rs for w in r["check_a"]["found"]).most_common(10)),
                          "thinking_hangul_start": sum(bool(re.search("[가-힣]", r["thinking"][:200])) for r in rs),
                          "eval_count_median": sorted(r["eval_count"] for r in rs)[len(rs) // 2] if rs else None,
                          "questions_without_pass": sorted({r["id"] for r in rs} - {r["id"] for r in rs if r["pass"]})}
    j = out["sets"]["ii_judge"]
    out["pass"] = j["traces"] == 160 and j["check_a_pass"] == 160 and j["check_b_pass"] >= 136
    (main_dir / "sft_dpo_inventory/pilot_006/teacher/t0v2_verdict.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"pass": out["pass"], **{s: {k: v for k, v in d.items() if k in ("check_a_pass", "check_b_pass", "traces")} for s, d in out["sets"].items()}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
