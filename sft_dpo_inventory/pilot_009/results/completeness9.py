# -*- coding: utf-8 -*-
"""pilot_009 본 세션 셀 완료성(C1). ``pilot_008/results/completeness8.py``의 사본: ``pilot_007/results/completeness_B.py``의 셀 검사 함수(``cell``)를 그대로 쓰고
대상만 ``gpu/cell_seeds_main.json``의 label·회차로. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_009/results/completeness9.py   # -> results/completeness9.json

다시 돌리기 규칙(결정 237·지시 2.1, PLAN_009 5절):
- 주 셋·개발 셋 셀: 잘림 또는 서버 오류 > 1%(``cell``의 ``rerun``).
- refusal_dev v2 셀(label이 ``_rdevv2``로 끝남): 잘림 호출 ≥ 2 또는 서버 오류 행 ≥ 2일 때만.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P9 = HERE.parent
sys.path.insert(0, str(P9.parent / "pilot_007/results"))
import completeness_B as CB  # noqa: E402

CB.CELLS = P9 / "cells"


def needs_rerun(label, r):
    if label.endswith("_rdevv2"):
        return (r.get("truncated_calls") or 0) >= 2 or r.get("server_error_rows", 0) >= 2
    return bool(r["rerun"])


def main():
    seeds = json.loads((P9 / "gpu/cell_seeds_main.json").read_text(encoding="utf-8"))["cells"]
    out, missing, rerun = {"cells": {}}, [], []
    for label, s in seeds.items():
        for k in range(1, len(s["round_seeds"]) + 1):
            r = CB.cell(label, k)
            if r["exists"]:
                r["rerun_rule"] = "rdev: 잘림 ≥ 2 또는 서버 오류 ≥ 2" if label.endswith("_rdevv2") else "> 1%"
                r["rerun"] = needs_rerun(label, r)
            out["cells"][f"{label}_s{k}"] = r
            if not r["exists"]:
                missing.append(f"{label}_s{k}")
            elif r["rerun"] or not (r["rows_equal_item_order"] and r["raw_sha256_match"] and r.get("raw_items_cover")):
                rerun.append(f"{label}_s{k}")
    out["summary"] = {"cells_expected": len(out["cells"]), "cells_present": len(out["cells"]) - len(missing), "missing": missing, "needs_rerun_or_check": rerun,
                      "truncated_calls_total": sum(v.get("truncated_calls", 0) or 0 for v in out["cells"].values()),
                      "calls_total": sum(v.get("raw_lines", 0) or 0 for v in out["cells"].values()),
                      "server_error_rows_total": sum(v.get("server_error_rows", 0) for v in out["cells"].values())}
    (HERE / "completeness9.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
