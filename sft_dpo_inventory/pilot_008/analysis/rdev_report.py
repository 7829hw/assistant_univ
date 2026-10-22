# -*- coding: utf-8 -*-
"""J-rdev 진단(판정 아님): refusal_dev 초안(거부 30·대조 30)에서 base 대 F-o11, 각 k=4. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_008/analysis/rdev_report.py   # -> analysis/rdev_report.json

- 거부 문항: 올바른 거부 = 결과 상태 unsupported·needs_clarification이고 분석 tool 실행 없음(PLAN_FINAL 4절). 경로(모델 거부 UNSUPPORTED_QUESTION / 프로그램 거부 / 확인 요청).
- 대조 문항: 과잉 거부(거부로 끝난 표본), 정답(grounding_ok, 견고성 패치 채점, 거부로 끝나면 오답).
- F-o11 − base 차이와 문항 단위 bootstrap 95% CI(10,000, ``default_rng(20261109)``, ``compute_gates.ci``). 묶음(범주)별 올바른 거부율.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
ROOT = P8.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/post"))
REFUSED = ("unsupported", "needs_clarification")


def main():
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    import evaluate_vendor100 as EV
    meta = json.loads((P8 / "refusal_dev/rdev_items_meta.json").read_text(encoding="utf-8"))
    gold = {i["id"]: i for i in EV.load_gold(P8 / "refusal_dev/rdev_gold.yaml")["items"]}
    data = {}
    for m in ("base", "o11"):
        per = defaultdict(list)
        for k in range(1, 5):
            p = P8 / f"cells/rdev_{m}_s{k}.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            for r in d["rows"]:
                out = r.get("outcome")
                analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
                refused = out in REFUSED and analysis == 0
                route = ("model" if r.get("error_code") == "UNSUPPORTED_QUESTION" else "clarification" if out == "needs_clarification" else "program") if refused else None
                ok = None
                if not meta[r["id"]]["refusal"]:
                    g_ok, _ = EV.grounding_check(gold[r["id"]], r.get("grounding"))
                    ok = bool(g_ok) and out not in REFUSED
                per[r["id"]].append({"refused": refused, "route": route, "ok": ok, "outcome": f"{out}:{r.get('error_code')}"})
        data[m] = per
    ref = sorted(i for i in meta if meta[i]["refusal"])
    con = sorted(i for i in meta if not meta[i]["refusal"])
    out = {"note": "refusal_dev 초안(승인 아님) 진단, 판정에 쓰지 않음", "items": {"refusal": len(ref), "contrast": len(con)}, "models": {}}
    mats = {}
    for m, per in data.items():
        R = np.array([[s["refused"] for s in per[i]] for i in ref], dtype=float)
        O = np.array([[s["refused"] for s in per[i]] for i in con], dtype=float)
        A = np.array([[s["ok"] for s in per[i]] for i in con], dtype=float)
        mats[m] = (R, O, A)
        routes = Counter(s["route"] for i in ref for s in per[i] if s["refused"])
        non = Counter(s["outcome"] for i in ref for s in per[i] if not s["refused"])
        by_gap = {}
        for g in sorted({meta[i]["gap"] for i in ref}):
            ix = [x for x, i in enumerate(ref) if meta[i]["gap"] == g]
            by_gap[g] = round(100 * float(R[ix].mean()), 1)
        out["models"][m] = {"correct_refusal_pct": round(100 * float(R.mean()), 2), "correct_refusal_samples": f"{int(R.sum())}/{R.size}",
                            "items_majority_refused": int((R.mean(axis=1) >= 0.5).sum()), "refusal_routes": dict(routes),
                            "refusal_items_not_refused_outcomes": dict(non.most_common(6)), "correct_refusal_by_gap_pct": by_gap,
                            "over_refusal_pct(contrast)": round(100 * float(O.mean()), 2), "over_refusal_samples": f"{int(O.sum())}/{O.size}",
                            "contrast_accuracy_pct": round(100 * float(A.mean()), 2)}
    for name, idx in (("correct_refusal", 0), ("over_refusal", 1), ("contrast_accuracy", 2)):
        dlt = mats["o11"][idx].mean(axis=1) - mats["base"][idx].mean(axis=1)
        mm, (lo, hi) = CG.ci(dlt)
        out[f"o11_minus_base_{name}_pp"] = {"diff": round(100 * mm, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)]}
    (HERE / "rdev_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
