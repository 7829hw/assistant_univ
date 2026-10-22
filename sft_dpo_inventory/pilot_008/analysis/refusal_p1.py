# -*- coding: utf-8 -*-
"""pilot_008 P1: 거부·과잉 거부 결과 상태 분류(진단). protected_final_v1은 쓰지 않는다(결정 220) — 이미 있는 주 셋·개발 셋 셀만. 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_008/analysis/refusal_p1.py   # -> analysis/refusal_p1.json

표본(셀 행) 분류 — 파이프라인 결과 상태(``geoflow.pipeline.PipelineResult.outcome``)와 오류 코드:
- 거부 문항(gold ``expected_outcome`` ≠ answered): 올바른 거부 = outcome ∈ {unsupported, needs_clarification}이고 분석 tool 실행 없음(PLAN_FINAL 4절과 같은 규칙).
- 거부 아닌 문항의 결과:
  - ``model_refusal``: 모델이 ``{"unsupported": true}``를 냄(오류 코드 ``UNSUPPORTED_QUESTION``, planner 단계).
  - ``program_unsupported``: 모델 grounding을 프로그램이 계산할 수 없다고 판단(그 밖 ``UNSUPPORTED_CODES``, 예: UNCONSUMED_CONDITION·UNSUPPORTED_AGGREGATION_COMBINATION).
  - ``needs_clarification``: 오류 context의 needs_clarification(예: AMBIGUOUS_*).
  - ``failed``: 그 밖 실패(구조 오류·NOT_FOUND 등), ``answered``: 답함.
  과잉 거부(PLAN_FINAL 정의) = model_refusal + program_unsupported + needs_clarification.
대상: base(selection_v2 = B1·X2·B-base3 k=12, holdout = B2·B-base3 k=8, valid98 = b3 k=4, aux = b4 k=4), F-o11(B2 셀 k=4).
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
P6P, C7 = "sft_dpo_inventory/pilot_006_prep/cells/", "sft_dpo_inventory/pilot_007/cells/"
GOLD = {"sel": "sft_dpo_inventory/conversion_diag/selection_gold.yaml", "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml",
        "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"}
ks = lambda p, k=4: [f"{p}_s{i}.json" for i in range(1, k + 1)]  # noqa: E731
CELLS = {"base": {"sel": ks(P6P + "b1_sel_base") + ks(P6P + "x2_sel_base_17408") + ks(C7 + "b_base3_sel"),
                  "holdout": ks(P6P + "b2_holdout_base") + ks(C7 + "b_base3_holdout"), "valid98": ks(P6P + "b3_valid98_base"), "aux": ks(P6P + "b4_aux_base")},
         "F-o11": {st: ks(f"{C7}b2_f_o11_{st}") for st in GOLD}}
REFUSED = ("model_refusal", "program_unsupported", "needs_clarification")


def classify(row):
    from geoflow.pipeline import UNSUPPORTED_CODES
    out, code = row.get("outcome"), row.get("error_code")
    if out == "answered":
        return "answered"
    if out == "needs_clarification":
        return "needs_clarification"
    if out == "unsupported":
        return "model_refusal" if code == "UNSUPPORTED_QUESTION" else "program_unsupported"
    return "failed" if code not in UNSUPPORTED_CODES else "program_unsupported"


def main():
    import evaluate_vendor100 as EV
    out = {}
    for model, sets in CELLS.items():
        out[model] = {}
        for st, cells in sets.items():
            gold = {i["id"]: i for i in EV.load_gold(ROOT / GOLD[st])["items"]}
            non, ref, codes = Counter(), Counter(), Counter()
            for c in cells:
                for r in json.loads((ROOT / c).read_text(encoding="utf-8"))["rows"]:
                    exp = gold[r["id"]].get("expected_outcome", "answered")
                    cls = classify(r)
                    if exp == "answered":
                        non[cls] += 1
                        if cls in REFUSED:
                            codes[f"{cls}:{r.get('error_code')}"] += 1
                    else:
                        analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
                        ref["correct_refusal" if cls in REFUSED and analysis == 0 else f"not_refused:{cls}"] += 1
                        if cls in REFUSED and analysis == 0:
                            ref[f"correct_via:{cls}:{r.get('error_code')}"] += 1
                        ref[f"expected:{exp}"] += 1
            n_non = sum(non.values())
            out[model][st] = {"samples_non_refusal_items": n_non, "non_refusal_outcomes": dict(non),
                              "over_refusal_pct": round(100 * sum(non[k] for k in REFUSED) / n_non, 2) if n_non else None,
                              "over_refusal_by_class_pct": {k: round(100 * non[k] / n_non, 2) for k in REFUSED},
                              "over_refusal_top_codes": dict(codes.most_common(8)), "refusal_items_samples": dict(ref),
                              "cells": len(cells)}
    (HERE / "refusal_p1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for m, v in out.items():
        for st, x in v.items():
            print(m, st, x["over_refusal_pct"], x["over_refusal_by_class_pct"], x["refusal_items_samples"])


if __name__ == "__main__":
    main()
