# -*- coding: utf-8 -*-
"""세션 3 셀 전부 → 표본 단위 행(``samples_s3.jsonl``, thinking 원문 제외 — 원문은 ignore 경로에 있다). 모델 호출 없음.

    hfvenv/bin/python build_samples.py [--extra post/cells]   # 세션 4 진단 셀이 생기면 --extra로 더한다(samples_s4.jsonl)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import itemdata as I  # noqa: E402

C, P6 = "sft_dpo_inventory/pilot_006/cells/", "sft_dpo_inventory/pilot_006_prep/cells/"
S3 = [(P6 + "b1_sel_base", "sel", "base", 4, "B1"), (P6 + "x2_sel_base_17408", "sel", "base", 4, "X2"), (C + "b5_sel_base_s3", "sel", "base", 4, "BASE3"),
      (P6 + "b2_holdout_base", "holdout", "base", 4, "B2"), (P6 + "b3_valid98_base", "valid98", "base", 4, "B3"), (P6 + "b4_aux_base", "aux", "base", 4, "B4"),
      (P6 + "r2b_partial_base", "sel", "R2", 4, "R2b"), (P6 + "r2v_partial_base", "valid98", "R2", 4, "R2v"), (P6 + "r2a_partial_base", "aux", "R2", 4, "R2a")]
for m in ("f43", "p43", "f1016", "p1016"):
    S3 += [(C + f"{m}_e1_sel", "sel", m.upper() + "e1", 4, f"{m}_e1_sel"), (C + f"{m}_e1_holdout", "holdout", m.upper() + "e1", 4, f"{m}_e1_holdout"),
           (C + f"{m}_e2_sel", "sel", m.upper() + "e2", 4, f"{m}_e2_sel")]
for m in ("f43", "p43"):
    S3 += [(C + f"{m}_e1_valid98", "valid98", m.upper() + "e1", 4, f"{m}_e1_valid98"), (C + f"{m}_e1_aux", "aux", m.upper() + "e1", 4, f"{m}_e1_aux"),
           (C + f"{m}_e1_vendor100", "vendor100", m.upper() + "e1", 8, f"{m}_e1_vendor100")]


def main():
    out = HERE / "samples_s3.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for prefix, st, model, k, cell in S3:
            for r in I.cell_rows(prefix, st, model, k):
                r.pop("thinking")
                r["cell"] = cell
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(cell, flush=True)


if __name__ == "__main__":
    main()
