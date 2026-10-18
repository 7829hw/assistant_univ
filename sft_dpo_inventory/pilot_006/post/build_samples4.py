# -*- coding: utf-8 -*-
"""세션 4 셀(``post/cells``) → 표본 단위 행(``samples_s4.jsonl``, thinking 원문 제외). 아직 없는 셀은 건너뛴다(다시 돌리면 덮어씀). 모델 호출 없음.

    hfvenv/bin/python build_samples4.py

셀 라벨은 ``make_jobs4.py``·``davg/make_jobs_davg.py``와 같다. 모델 이름:
- E-rep: ``F43rep``·``F1016rep``(seed_base 20261200, k=4)
- E-greedy: ``baseG``·``F43G``·``F1016G``·``P43G``·``P1016G``(k=1)
- E-D: ``D_F7q100``·``D_P7q100``·``D_F43o1016q100``·``D_F1016o43q100``(k=4)
- E-Dq: ``<D>q25G``·``q50G``·``q75G``(greedy k=1)
- E-D7dev: ``D_F7q100``·``D_P7q100``의 valid98·aux(k=4)·vendor100(k=8)
- D-avg: ``D_avg``(k=4)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import itemdata as I  # noqa: E402

C = "sft_dpo_inventory/pilot_006/post/cells/"
D = ("D_F7", "D_P7", "D_F43o1016", "D_F1016o43")
SPEC = []
for m in ("f43", "f1016"):
    SPEC += [(f"rep_{m}_e1_{g}", g, m.upper() + "rep", 4) for g in ("sel", "holdout")]
SPEC += [(f"greedy_base_{g}", g, "baseG", 1) for g in ("sel", "holdout")]
for m in ("f43", "f1016", "p43", "p1016"):
    SPEC += [(f"greedy_{m}_e1_{g}", g, m.upper() + "G", 1) for g in ("sel", "holdout")]
for d in D:
    SPEC += [(f"{d.lower()}_q100_{g}", g, f"{d}q100", 4) for g in ("sel", "holdout")]
    for q in ("25", "50", "75"):
        SPEC += [(f"{d.lower()}_q{q}_greedy_{g}", g, f"{d}q{q}G", 1) for g in ("sel", "holdout")]
for d in ("D_F7", "D_P7"):
    SPEC += [(f"{d.lower()}_q100_{g}", g, f"{d}q100", k) for g, k in (("valid98", 4), ("aux", 4), ("vendor100", 8))]
SPEC += [(f"d_avg_e1_{g}", g, "D_avg", 4) for g in ("sel", "holdout")]


def main():
    out, done, missing = HERE / "samples_s4.jsonl", [], []
    with out.open("w", encoding="utf-8") as f:
        for label, st, model, k in SPEC:
            if not all((ROOT / f"{C}{label}_s{j}.json").exists() for j in range(1, k + 1)):
                missing.append(label)
                continue
            for r in I.cell_rows(C + label, st, model, k):
                r.pop("thinking")
                r["cell"] = label
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            done.append(label)
            print(label, flush=True)
    print(json.dumps({"built": len(done), "missing": missing}, ensure_ascii=False))


if __name__ == "__main__":
    main()
