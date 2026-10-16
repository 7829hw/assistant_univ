# -*- coding: utf-8 -*-
"""T0'' 판정과 선택(결정 144 K7). 실행 전에 커밋한 ``t0v3_rule.json``을 그대로 적용한다. 모델 호출 없음.

    python3 analyze_t0v3.py --main /home/hwkim/assistant_univ   # -> pilot_006/teacher/t0v3_verdict.json

두 안 원문(``training/generated/pilot_006/teacher_t0v3{a,b}/traces.jsonl``)이 모두 있어야 선택한다. 하나만 있으면 그 안의 수치만 적고 ``selected``는 비운다.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def stats(rows):
    items = Counter()
    for r in rows:
        for k, v in r["check_b"]["items"].items():
            items[k] += bool(v)
    return {"traces": len(rows), "check_a_pass": sum(r["check_a"]["pass"] for r in rows), "check_b_pass": sum(r["check_b"]["pass"] for r in rows),
            "check_c_exposed": sum(r["check_c"]["exposed"] for r in rows), "all_pass": sum(r["pass"] for r in rows),
            "conclusion_lines_parsed": sum(r["check_b"]["parsed_all_lines"] for r in rows), "items_match": dict(items),
            "exposure_phrases": dict(Counter(w for r in rows for w in r["check_c"]["found"])),
            "questions_with_pass": len({r["id"] for r in rows if r["pass"]})}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    rule = json.loads((HERE / "t0v3_rule.json").read_text(encoding="utf-8"))
    out = {"rule": rule, "variants": {}}
    for v in ("v3b", "v3a"):
        f = main_dir / f"training/generated/pilot_006/teacher_t0{v}/traces.jsonl"
        if f.exists():
            out["variants"][v] = stats([json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()])
    b, aa = out["variants"].get("v3b"), out["variants"].get("v3a")
    if b:
        b["pass"] = b["traces"] == 160 and b["check_a_pass"] >= 157 and b["check_b_pass"] >= 152 and b["check_c_exposed"] <= 3
    if aa:
        aa["pass"] = aa["traces"] == 160 and aa["check_a_pass"] >= 157 and aa["check_b_pass"] >= 136
    out["selected"] = None
    if b and aa:
        out["selected"] = "v3b" if b["pass"] else ("v3a" if aa["pass"] else "none")
    (main_dir / "sft_dpo_inventory/pilot_006/teacher/t0v3_verdict.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"selected": out["selected"], **{v: {k: s[k] for k in ("check_a_pass", "check_b_pass", "check_c_exposed", "pass") if k in s}
                                                      for v, s in out["variants"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
