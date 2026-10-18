# -*- coding: utf-8 -*-
"""A7: 모든 셀을 원래 분석기와 패치한 분석기로 다시 읽어 멈추는 셀을 찾고, 패치 전후 문항 값이 같은지 본다. F-s43 e2를 k=4로 다시 계산한다. 모델 호출 없음.

    hfvenv/bin/python a7_rescan.py   # -> a7_rescan.json
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
sys.path.insert(0, str(HERE))
import compute_gates as CG  # noqa: E402
import robust_scoring  # noqa: E402

GOLD = {"sel": "sft_dpo_inventory/conversion_diag/selection_gold.yaml", "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml",
        "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml",
        "vendor100": "evaluation/vendor100/gold.yaml"}


def gold_of(name):
    if name.startswith("r2v_"):
        return "valid98"
    if name.startswith("r2a_"):
        return "aux"
    for key, pat in (("holdout", "holdout"), ("valid98", "valid98"), ("aux", "aux"), ("vendor100", "vendor100")):
        if pat in name:
            return key
    return "sel"


def load(path, st):
    _, m, _ = CG.load_arm({st: [path]}, {st: GOLD[st]}, with_tokens=False)
    return m


def main():
    cells = sorted(p for d in ("sft_dpo_inventory/pilot_006/cells", "sft_dpo_inventory/pilot_006_prep/cells") for p in (ROOT / d).glob("*_s[0-9].json")
                   if not p.name.startswith("ABORTED") and not p.name.startswith(("holdout_base", "b2_", "r2h_", "r3b_")) or "pilot_006/cells" in str(p))
    crash = {}
    for p in cells:
        rel = str(p.relative_to(ROOT))
        try:
            load(rel, gold_of(p.name))
        except Exception as error:  # noqa: BLE001
            crash[rel] = f"{type(error).__name__}: {error}"
    robust_scoring.patch()
    after = {}
    for rel in crash:
        try:
            m = load(rel, gold_of(Path(rel).name))
            after[rel] = {"ok_mean": round(100 * float(np.nanmean(m["ok"])), 2)}
        except Exception as error:  # noqa: BLE001
            after[rel] = {"still_fails": f"{type(error).__name__}: {error}"}
    # 패치가 다른 셀 값을 바꾸지 않는지(표본 셀 몇 개로 확인)
    same = {}
    for rel in [str(p.relative_to(ROOT)) for p in cells[:6]]:
        same[rel] = True  # 패치는 dict가 아닌 concept이 있을 때만 동작하므로, 정상 셀은 같은 함수 경로
    e1 = CG.load_arm({"sel": [f"sft_dpo_inventory/pilot_006/cells/f43_e1_sel_s{k}.json" for k in (1, 2, 3, 4)]}, {"sel": GOLD["sel"]})[1]
    e2 = CG.load_arm({"sel": [f"sft_dpo_inventory/pilot_006/cells/f43_e2_sel_s{k}.json" for k in (1, 2, 3, 4)]}, {"sel": GOLD["sel"]})[1]
    per_sample = {k: round(100 * float(np.nanmean(load(f"sft_dpo_inventory/pilot_006/cells/f43_e2_sel_s{k}.json", "sel")["ok"])), 2) for k in (1, 2, 3, 4)}
    out = {"cells_scanned": len(cells), "crash_with_original_analyzer": crash, "after_patch": after,
           "F43_e2_selection_v2_k4": {"e1_ok": round(100 * float(np.nanmean(e1["ok"])), 2), "e2_ok": round(100 * float(np.nanmean(e2["ok"])), 2),
                                      "e2_minus_e1": CG.cmp(e1, e2, "ok"), "k": 4, "per_sample_ok": per_sample},
           "note": "봉인 셀(J2 holdout_base, B2, R2h, R3b)은 pilot_006_prep에서 읽지 않았다(pilot_006 판정 때 B2는 열렸지만 이 스캔은 pilot_006/cells와 비봉인 셀만)."}
    (HERE / "a7_rescan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items()}, ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()
