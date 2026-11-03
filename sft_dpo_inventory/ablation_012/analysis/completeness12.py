# -*- coding: utf-8 -*-
"""ablation_012 셀 완료성·다시 돌리기 기록(결정 262, PLAN_A12 3절). ``ablation_011/analysis/completeness11.py``(그대로)의 사본 방식:
``pilot_007/results/completeness_B.cell``로 셀마다 존재·sha256·행 수·원문 일치·잘림·서버 오류를 세고, scheduler14의 규칙(rdev 잘림 ≥ 2 또는 서버 오류 ≥ 2, 그 밖 > 1%)을 다시 적용해
다시 돌린 셀(``RERUNS_A12.json``)과 맞는지 본다. 모델 호출 없음. 정답률은 읽지 않는다.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_012/analysis/completeness12.py   # -> analysis/completeness12.json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
A12 = HERE.parent
sys.path.insert(0, str(A12.parent / "pilot_007/results"))
import completeness_B as CB  # noqa: E402

CB.CELLS = A12 / "cells"


def main():
    jobs = json.loads((A12 / "gpu/jobs_a12.json").read_text(encoding="utf-8"))["jobs"]
    reruns = json.loads((A12 / "RERUNS_A12.json").read_text(encoding="utf-8"))["reruns"] if (A12 / "RERUNS_A12.json").exists() else {}
    out, missing, flagged = {"cells": {}}, [], []
    for j in jobs:
        for c in j.get("cells", []):
            label, k = c["name"].rsplit("_s", 1)
            r = CB.cell(label, int(k))
            r["job"] = j["id"]
            if r["exists"]:
                rd = label.endswith("_rdevv2")
                r["rerun_rule"] = "rdev: 잘림 ≥ 2 또는 서버 오류 ≥ 2" if rd else "> 1%"
                r["rerun_now"] = ((r.get("truncated_calls") or 0) >= 2 or r.get("server_error_rows", 0) >= 2) if rd else bool(r["rerun"])
                r["already_rerun"] = c["name"] in reruns
                r["integrity_ok"] = bool(r["rows_equal_item_order"] and r["raw_sha256_match"] and r.get("raw_items_cover"))
                if (r["rerun_now"] and not r["already_rerun"]) or not r["integrity_ok"]:
                    flagged.append(c["name"])
            else:
                missing.append(c["name"])
            out["cells"][c["name"]] = r
    out["reruns"] = reruns
    out["summary"] = {"cells_expected": len(out["cells"]), "cells_present": len(out["cells"]) - len(missing), "missing": missing, "flagged": flagged,
                      "reruns": len(reruns), "truncated_calls_total": sum(v.get("truncated_calls", 0) or 0 for v in out["cells"].values()),
                      "calls_total": sum(v.get("raw_lines", 0) or 0 for v in out["cells"].values()),
                      "server_error_rows_total": sum(v.get("server_error_rows", 0) for v in out["cells"].values())}
    (HERE / "completeness12.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
