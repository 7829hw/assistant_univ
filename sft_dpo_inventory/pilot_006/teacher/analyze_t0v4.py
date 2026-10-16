# -*- coding: utf-8 -*-
"""T0''' 판정과 L3 선택(결정 149–151). 실행 전에 커밋한 ``t0v4_rule.json``을 그대로 적용한다. 모델 호출 없음.

    python3 analyze_t0v4.py --main /home/hwkim/assistant_univ [--skip-v3c]   # -> pilot_006/teacher/t0v4_verdict.json

- v3c (iv): ``training/generated/pilot_006/teacher_t0v3c/traces.jsonl``의 ``pass``(a·b·c(EXPOSURE_V3C)) 수 ≥ 144.
- ``--skip-v3c``: L2 불통과로 T0'''를 건너뛴 경우(v3c 판정 없음).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    p.add_argument("--skip-v3c", action="store_true")
    a = p.parse_args()
    main_dir = Path(a.main)
    rule = json.loads((HERE / "t0v4_rule.json").read_text(encoding="utf-8"))
    l2 = rule["L2"]["pass"]
    out = {"rule": rule, "v3c": None}
    if not a.skip_v3c:
        rows = [json.loads(l) for l in (main_dir / "training/generated/pilot_006/teacher_t0v3c/traces.jsonl").read_text(encoding="utf-8").splitlines()]
        items = Counter()
        for r in rows:
            for k, v in r["check_b"]["items"].items():
                items[k] += bool(v)
        n = sum(r["pass"] for r in rows)
        out["v3c"] = {"traces": len(rows), "check_a_pass": sum(r["check_a"]["pass"] for r in rows), "check_b_pass": sum(r["check_b"]["pass"] for r in rows),
                      "check_c_exposed": sum(r["check_c"]["exposed"] for r in rows), "trace_pass": n, "items_match": dict(items),
                      "exposure_phrases": dict(Counter(w for r in rows for w in r["check_c"]["found"])),
                      "english_start": sum(r["thinking"].lstrip().startswith(("Let me", "Okay", "OK", "Alright", "First")) for r in rows),
                      "instruction_pass": len(rows) == 160 and n >= 144}
    iii = rule["iii_recount"]
    if l2 and out["v3c"] and out["v3c"]["instruction_pass"]:
        sel = "v3c"
    elif l2 and iii["v3b"]["trace_pass_ge_144"]:
        sel = "v3b"
    elif iii["v3a"]["trace_pass_ge_144"]:
        sel = "v3a"
    else:
        sel = "none"
    out["selected"] = sel
    (main_dir / "sft_dpo_inventory/pilot_006/teacher/t0v4_verdict.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"selected": sel, "v3c": out["v3c"] and {k: out["v3c"][k] for k in ("check_a_pass", "check_b_pass", "check_c_exposed", "trace_pass", "instruction_pass")}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
