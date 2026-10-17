# -*- coding: utf-8 -*-
"""세션 3 판정 spec(결정 153·154). ``gates/compute_gates.py``에 넣을 spec 둘을 만든다. 모델 호출 없음.

    hfvenv/bin/python make_gate_spec.py   # -> run3/gate_spec_main.json(주 셋 151), run3/gate_spec_sel.json(selection_v2만, 보고)

- base: selection_v2 = B1 + X2 + BASE3(k=12, 결정 134), holdout = B2(k=4, 판정 때 봉인 해제).
- seed_cells: s43 = F43·P43 e1, s1016 = F1016·P1016 e1(각 k=4). 지연 = ``latency/run3/latency_summary.json``의 셀 원문(s43).
- diagnostic_subsets(진단, 결정 140·155): scope 이름 조회 family(정답 호출이 ``get_scope_name`` 하나), implicit endpoint 동사형(``subsets.json``).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
P6 = "sft_dpo_inventory/pilot_006_prep/cells/"
C = "sft_dpo_inventory/pilot_006/cells/"
SETS = {"selection_v2": "sft_dpo_inventory/conversion_diag/selection_gold.yaml",
        "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml"}


def ks(prefix, k=4):
    return [f"{prefix}_s{i}.json" for i in range(1, k + 1)]


def main():
    import evaluate_vendor100 as EV
    base = {"selection_v2": ks(P6 + "b1_sel_base") + ks(P6 + "x2_sel_base_17408") + ks(C + "b5_sel_base_s3"), "holdout": ks(P6 + "b2_holdout_base")}
    seeds = {}
    for s, (f, p) in {"s43": ("f43", "p43"), "s1016": ("f1016", "p1016")}.items():
        seeds[s] = {"F": {"selection_v2": ks(C + f"{f}_e1_sel"), "holdout": ks(C + f"{f}_e1_holdout")},
                    "P": {"selection_v2": ks(C + f"{p}_e1_sel"), "holdout": ks(C + f"{p}_e1_holdout")}}
    k3 = []
    for st, path in SETS.items():
        for it in EV.load_gold(ROOT / path)["items"]:
            calls = it.get("gold") or []
            if isinstance(calls, list) and len(calls) == 1 and calls[0].get("tool") == "get_scope_name":
                k3.append(f"{st}/{it['id']}")
    subs = json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/integration/pg_tools/subsets.json").read_text(encoding="utf-8"))["subsets"]
    imp = ["selection_v2/" + x.split(":", 1)[1] for x in subs.get("implicit_endpoint_verb", []) if x.startswith("sel154:")]
    lat_dir = "sft_dpo_inventory/pilot_006/latency/run3/"
    latency = {"base": lat_dir + "lat6-base_s1.json", "F": lat_dir + "lat6-F_s1.json", "P": lat_dir + "lat6-P_s1.json"}
    diag = {"k3_scope_name_family": k3, "implicit_endpoint_verb(selection_v2)": imp}
    main_spec = {"label": "pilot_006 주 판정(주 셋 151, seed 묶음)", "sets": SETS, "cells": {"base": base}, "seed_cells": seeds, "latency": latency,
                 "latency_seed": "s43", "diagnostic_subsets": diag}
    sel = {**main_spec, "label": "pilot_006 selection_v2만(보고)", "sets": {"selection_v2": SETS["selection_v2"]},
           "cells": {"base": {"selection_v2": base["selection_v2"]}},
           "seed_cells": {s: {a: {"selection_v2": v[a]["selection_v2"]} for a in ("F", "P")} for s, v in seeds.items()}}
    (HERE / "gate_spec_main.json").write_text(json.dumps(main_spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "gate_spec_sel.json").write_text(json.dumps(sel, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(k3), len(imp))


if __name__ == "__main__":
    main()
