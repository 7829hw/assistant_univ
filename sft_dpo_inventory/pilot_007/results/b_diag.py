# -*- coding: utf-8 -*-
"""B단계 진단(판정 아님, R7 확인 뒤). 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/results/b_diag.py   # -> results/b_diag.json

1. 다시 돌린 셀 13개의 영향: 원래 셀(``cells/replaced_B/``)로 바꾼 spec 사본을 같은 판정 도구(``compute_gates_b``)로 계산해 판정값과 비교.
   원본 json의 ``meta.hf.raw_out``은 옮긴 원문(``cells_raw/replaced_B/``)을 가리키도록 바꾼 사본을 scratch에 둔다(저장소의 원본은 그대로).
2. 다시 돌린 뒤에도 잘림 > 1%인 셀 5개: 주 셋 셀이면 그 셀의 잘린 문항 수와, 그 문항이 모두 맞았다고 해도 arm 정답률이 얼마나 오를 수 있는지(상한).
3. 순서 효과 참고: 같은 모델 seed·recipe인 A3 R1''(무작위 순서)와 B F(공유 순서) — 주 셋 정답률(seed 43·1016·7).
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
P7 = HERE.parent
ROOT = P7.parents[1]
sys.path.insert(0, str(P7 / "gates"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/post"))
import compute_gates_b as G  # noqa: E402

RAW = ROOT / "training/generated/pilot_007/cells_raw"


def run(spec):
    items, seeds, F, P, base = G.load(spec)
    import compute_gates as CG
    lb = CG.latency(spec["latency"]["base"])
    lat = {arm: round(CG.latency(spec["latency"][arm]) / lb, 3) for arm in ("F", "P")}
    out = G.decide(F, P, base, lat)
    return {"prerequisite": {a: {"ok": v["ok_vs_base"], "U": v["U_vs_base"], "pass": v["pass"]} for a, v in out["prerequisite"].items()},
            "A": {k: out["gates"]["A"][k] for k in ("diff_pp", "ci95_pp", "pass")}, "D_pass": out["gates"]["D"]["pass"],
            "adopt": out["adopt"]["candidate"], "arm_ok": {a: out["arm_means_pp"][a]["ok"] for a in ("F", "P")}, "per_seed_ok": {a: out["per_seed_means_pp"][a]["ok"] for a in ("F", "P")}}


def main():
    spec = json.loads((P7 / "gates/gate_spec_B.json").read_text(encoding="utf-8"))
    rr = json.loads((P7 / "B_RERUNS.json").read_text(encoding="utf-8"))["reruns"]
    comp = json.loads((HERE / "completeness_B.json").read_text(encoding="utf-8"))["cells"]
    out = {"judgment_as_registered": run(spec)}
    tmp = Path(tempfile.mkdtemp(prefix="b_diag_"))
    alt = json.loads(json.dumps(spec))
    swapped = []
    for name in rr:
        src = P7 / "cells/replaced_B" / f"{name}.json"
        d = json.loads(src.read_text(encoding="utf-8"))
        d["meta"]["hf"]["raw_out"] = str(RAW / "replaced_B" / f"{name}_raw.jsonl")
        dst = tmp / f"{name}.json"
        dst.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        rel = f"sft_dpo_inventory/pilot_007/cells/{name}.json"
        for o in alt["seed_cells"].values():
            for arm in o.values():
                for st, cells in arm.items():
                    if rel in cells:
                        cells[cells.index(rel)] = str(dst)
                        swapped.append(name)
    out["with_original_cells"] = {"swapped_main_cells": sorted(swapped), **run(alt)}
    shutil.rmtree(tmp)
    still = [n for n in rr if comp[n].get("rerun")]
    main_still = {}
    for n in still:
        if "_sel_" in n or "_holdout_" in n:
            arm = "F" if n.startswith("b_f_") else "P"
            main_still[n] = {"arm": arm, "truncated_calls": comp[n]["truncated_calls"],
                             "max_arm_ok_shift_pp_if_all_truncated_items_were_correct": round(100 * comp[n]["truncated_calls"] / (151 * 4 * 5), 3)}
    out["still_over_1pct"] = {"cells": still, "main_set_cells": main_still,
                              "note": "주 셋 arm 정답률 = 5 seed × k4 × 151문항 평균 → 잘린 문항 1개는 arm 평균에 최대 1/3020 = 0.033%p"}
    a3 = json.loads((P7 / "analysis/a3_report.json").read_text(encoding="utf-8"))["models"]
    js = out["judgment_as_registered"]["per_seed_ok"]["F"]
    out["order_effect_reference"] = {s: {"A3_R1pp_random_order_main": a3[f"A3_R1pp_{s}"]["main"], "B_F_shared_order_main": js[i]}
                                     for i, s in enumerate(("o43", "o1016", "o7"))}
    (HERE / "b_diag.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
