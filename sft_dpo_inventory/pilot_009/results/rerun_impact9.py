# -*- coding: utf-8 -*-
"""pilot_009 진단(``pilot_008/results/rerun_impact8.py`` 사본)(판정 아님): 다시 돌린 셀 53개 대신 원래 셀(``cells/replaced_main/``)로 같은 판정 도구를 돌려 결과를 비교한다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_009/results/rerun_impact9.py SCRATCH_DIR   # -> results/rerun_impact9.json

원본 json의 ``meta.hf.raw_out``은 옮긴 원문(``cells_raw/replaced_main``)을 가리키도록 바꾼 사본을 SCRATCH_DIR(저장소 밖)에 두고 spec 사본을 거기서 쓴다.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P9 = HERE.parent
ROOT = P9.parents[1]
RAW = ROOT / "training/generated/pilot_009/cells_raw/replaced_main"
sp = Path(sys.argv[1])
spec = json.loads((P9 / "gates/spec_p9.json").read_text(encoding="utf-8"))
rr = json.loads((P9 / "RERUNS_main.json").read_text(encoding="utf-8"))["reruns"]
swapped = []
for name in rr:
    d = json.loads((P9 / "cells/replaced_main" / f"{name}.json").read_text(encoding="utf-8"))
    d["meta"]["hf"]["raw_out"] = str(RAW / f"{name}_raw.jsonl")
    (sp / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    rel = f"sft_dpo_inventory/pilot_009/cells/{name}.json"
    for arm in ("P9", "B2F", "P8"):
        for s in spec["cells"][arm].values():
            for st, cells in s.items():
                if rel in cells:
                    cells[cells.index(rel)] = str(sp / f"{name}.json")
                    swapped.append(name)
    for st, cells in spec["cells"]["base"].items():
        if rel in cells:
            cells[cells.index(rel)] = str(sp / f"{name}.json")
            swapped.append(name)
(sp / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
subprocess.run([sys.executable, str(P9 / "gates/compute_p9.py"), "--spec", str(sp / "spec.json"), "--out", str(sp / "out.json")], check=True, cwd=str(ROOT), capture_output=True)
o = json.loads((sp / "out.json").read_text(encoding="utf-8"))
j = json.loads((HERE / "judgment_p9.json").read_text(encoding="utf-8"))
res = {"swapped": sorted(swapped), "with_original_cells": {k: {kk: v[kk] for kk in ("diff_pp", "ci95_pp", "pass")} for k, v in o["conditions"].items()},
       "as_registered": {k: {kk: v[kk] for kk in ("diff_pp", "ci95_pp", "pass")} for k, v in j["conditions"].items()}, "pass_with_original": o["pass"]}
(HERE / "rerun_impact9.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
