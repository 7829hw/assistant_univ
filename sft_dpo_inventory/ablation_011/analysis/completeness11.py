# -*- coding: utf-8 -*-
"""ablation_011 셀 완료성·다시 돌리기 판단(결정 261, PLAN_A11 5절 = PLAN_S 5절). ``pilot_010/results/completeness10.py``(그대로)와 같은 규칙:
``pilot_007/results/completeness_B.py``의 ``cell``을 그대로 쓰고 대상만 ablation_011 셀(``gpu/jobs_a11.json``의 평가 작업 label). 모델 호출 없음.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/analysis/completeness11.py   # -> analysis/completeness11.json

- valid98·aux 셀: 잘림 또는 서버 오류 > 1%(``cell``의 ``rerun``). refusal_dev v2 셀(label이 ``_rdevv2``로 끝남): 잘림 호출 ≥ 2 또는 서버 오류 행 ≥ 2.
- 같은 seed로 한 번만 다시 돌리고(원본은 ``cells/replaced/``), 다시 돌린 셀이 또 걸려도 그대로 둔다(``replaced/``에 원본이 있으면 표시만).
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
A11 = HERE.parent
sys.path.insert(0, str(A11.parent / "pilot_007/results"))
import completeness_B as CB  # noqa: E402

CB.CELLS = A11 / "cells"


def needs_rerun(label, r):
    if label.endswith("_rdevv2"):
        return (r.get("truncated_calls") or 0) >= 2 or r.get("server_error_rows", 0) >= 2
    return bool(r["rerun"])


def labels():
    jobs = json.loads((A11 / "gpu/jobs_a11.json").read_text(encoding="utf-8"))["jobs"]
    out = []
    for j in jobs:
        if j["id"].startswith("E-"):
            for lab in sorted(set(re.findall(r"--label (\S+)", j["cmd"][2]))):
                out.append((j["id"], lab))
    return out


def main():
    out, missing, rerun = {"cells": {}}, [], []
    for job, label in labels():
        for k in range(1, 5):
            r = CB.cell(label, k)
            r["job"] = job
            if r["exists"]:
                r["rerun_rule"] = "rdev: 잘림 ≥ 2 또는 서버 오류 ≥ 2" if label.endswith("_rdevv2") else "> 1%"
                r["rerun"] = needs_rerun(label, r)
                r["already_rerun"] = (A11 / "cells/replaced" / f"{label}_s{k}.json").exists()
            out["cells"][f"{label}_s{k}"] = r
            if not r["exists"]:
                missing.append(f"{label}_s{k}")
            elif (r["rerun"] and not r["already_rerun"]) or not (r["rows_equal_item_order"] and r["raw_sha256_match"] and r.get("raw_items_cover")):
                rerun.append(f"{label}_s{k}")
    out["summary"] = {"cells_expected": len(out["cells"]), "cells_present": len(out["cells"]) - len(missing), "missing": len(missing), "needs_rerun_or_check": rerun,
                      "truncated_calls_total": sum(v.get("truncated_calls", 0) or 0 for v in out["cells"].values()),
                      "calls_total": sum(v.get("raw_lines", 0) or 0 for v in out["cells"].values()),
                      "server_error_rows_total": sum(v.get("server_error_rows", 0) for v in out["cells"].values())}
    (HERE / "completeness11.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
