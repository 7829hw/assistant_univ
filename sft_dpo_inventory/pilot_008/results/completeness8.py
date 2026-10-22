# -*- coding: utf-8 -*-
"""pilot_008 본 세션 셀 완료성(C1). ``pilot_007/results/completeness_B.py``의 셀 검사 함수(``cell``)를 그대로 쓰고 대상만 ``gpu/cell_seeds_main.json``의 label·회차로. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_008/results/completeness8.py   # -> results/completeness8.json

셀마다 존재·sha256·행 수(= item_order)·원문 sha256·원문 문항 포함·잘림 호출 수·서버 오류 행·지문·prompt, 잘림 또는 서버 오류 > 1%면 ``rerun``.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
sys.path.insert(0, str(P8.parent / "pilot_007/results"))
import completeness_B as CB  # noqa: E402

CB.CELLS = P8 / "cells"


def main():
    seeds = json.loads((P8 / "gpu/cell_seeds_main.json").read_text(encoding="utf-8"))["cells"]
    out, missing, rerun = {"cells": {}}, [], []
    for label, s in seeds.items():
        for k in range(1, len(s["round_seeds"]) + 1):
            r = CB.cell(label, k)
            out["cells"][f"{label}_s{k}"] = r
            if not r["exists"]:
                missing.append(f"{label}_s{k}")
            elif r["rerun"] or not (r["rows_equal_item_order"] and r["raw_sha256_match"] and r.get("raw_items_cover")):
                rerun.append(f"{label}_s{k}")
    out["summary"] = {"cells_expected": len(out["cells"]), "cells_present": len(out["cells"]) - len(missing), "missing": missing, "needs_rerun_or_check": rerun,
                      "truncated_calls_total": sum(v.get("truncated_calls", 0) for v in out["cells"].values()),
                      "server_error_rows_total": sum(v.get("server_error_rows", 0) for v in out["cells"].values())}
    (HERE / "completeness8.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
