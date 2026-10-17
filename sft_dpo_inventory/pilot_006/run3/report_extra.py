# -*- coding: utf-8 -*-
"""세션 3 보고 보조(판정 아님): 개발 셋(s43)·epoch 2·지연·thinking 길이 감시(결정 107)·학습 모델 출력의 "결론" 언급(결정 158 위험). 모델 호출 없음.

    hfvenv/bin/python report_extra.py   # -> results/extra.json
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
import compute_gates as CG  # noqa: E402

C = "sft_dpo_inventory/pilot_006/cells/"
P6 = "sft_dpo_inventory/pilot_006_prep/cells/"
GOLD = {"valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml",
        "vendor100": "evaluation/vendor100/gold.yaml", "selection_v2": "sft_dpo_inventory/conversion_diag/selection_gold.yaml"}


def ks(prefix, k=4):
    return [f"{prefix}_s{i}.json" for i in range(1, k + 1)]


SKIPPED = []


def arm(st, paths):
    """채점기가 멈추는 셀(잘못된 출력의 원문을 분석기가 다시 읽다 실패)은 빼고 계산하고 SKIPPED에 적는다(보고용)."""
    ok = []
    for p in paths:
        try:
            CG.load_arm({st: [p]}, {st: GOLD[st]}, with_tokens=False)
            ok.append(p)
        except Exception as error:  # noqa: BLE001
            SKIPPED.append({"cell": p, "error": f"{type(error).__name__}: {error}"})
    _, m, _ = CG.load_arm({st: ok}, {st: GOLD[st]})
    return m


def summary(m):
    return {f: round(100 * float(np.nanmean(m[f])), 2) for f in ("ok", "U", "silent", "dt_missing", "mm_nm", "repair")}


def mentions(paths):
    n = hit = 0
    for p in paths:
        raw = json.loads((ROOT / p).read_text(encoding="utf-8"))["meta"]["hf"]["raw_out"]
        for line in Path(raw).read_text(encoding="utf-8").splitlines():
            t = json.loads(line).get("raw_text", "")
            think = t.split("</think>")[0]
            n += 1
            hit += bool(re.search(r"결론|conclusion", think, re.I))
    return {"calls": n, "thinking_mentions_결론_or_conclusion": hit, "rate": round(hit / max(1, n), 4)}


def main():
    out = {"dev_sets_s43": {}, "epoch2_selection_v2": {}, "thinking_p90": {}, "conclusion_mentions": {}}
    base = {"valid98": ks(P6 + "b3_valid98_base"), "aux": ks(P6 + "b4_aux_base")}
    for st, k in (("valid98", 4), ("aux", 4), ("vendor100", 8)):
        f, p = arm(st, ks(C + f"f43_e1_{st}", k)), arm(st, ks(C + f"p43_e1_{st}", k))
        row = {"F43": summary(f), "P43": summary(p), "P_minus_F_ok": CG.cmp(f, p, "ok"), "P_minus_F_dt": CG.cmp(f, p, "dt_missing")}
        if st in base:
            b = arm(st, base[st])
            row["base"] = summary(b)
            row["F_minus_base_ok"] = CG.cmp(b, f, "ok")
            row["P_minus_base_ok"] = CG.cmp(b, p, "ok")
        else:
            row["base"] = "pilot_006 17,408 서버의 업체 100 base 셀 없음(개발 셋, 결정 106)"
        out["dev_sets_s43"][st] = row
    for name in ("f43", "p43", "f1016", "p1016"):
        e1, e2 = arm("selection_v2", ks(C + f"{name}_e1_sel")), arm("selection_v2", ks(C + f"{name}_e2_sel"))
        out["epoch2_selection_v2"][name] = {"e1_ok": summary(e1)["ok"], "e2_ok": summary(e2)["ok"], "e2_minus_e1": CG.cmp(e1, e2, "ok")}
    bsel = arm("selection_v2", ks(P6 + "b1_sel_base") + ks(P6 + "x2_sel_base_17408") + ks(C + "b5_sel_base_s3"))
    for name in ("base", "f43", "p43", "f1016", "p1016"):
        m = bsel if name == "base" else arm("selection_v2", ks(C + f"{name}_e1_sel"))
        out["thinking_p90"][name] = float(np.nanpercentile(m["thinking_tokens"], 90))
    bp = out["thinking_p90"]["base"]
    out["thinking_p90"]["partial_drop_vs_base_pct"] = {n: round(100 * (1 - out["thinking_p90"][n] / bp), 1) for n in ("p43", "p1016")}
    out["thinking_p90"]["report_if_drop_over_30pct(decision 107)"] = any(v > 30 for v in out["thinking_p90"]["partial_drop_vs_base_pct"].values())
    for name in ("f43", "p43", "f1016", "p1016"):
        out["conclusion_mentions"][name] = mentions(ks(C + f"{name}_e1_sel") + ks(C + f"{name}_e1_holdout"))
    out["conclusion_mentions"]["base_selection_v2"] = mentions(ks(C + "b5_sel_base_s3"))
    out["cells_skipped(scoring crash)"] = SKIPPED
    lat = json.loads((ROOT / "sft_dpo_inventory/pilot_006/latency/run3/latency_summary.json").read_text(encoding="utf-8"))
    out["latency"] = {k: lat.get(k) for k in ("ratio_vs_base", "d8_pass(≤1.5)")}
    out["latency"]["cells"] = {k: {kk: v[kk] for kk in ("median_model_seconds", "median_generated_tokens", "median_thinking_tokens", "median_json_tokens", "median_input_tokens")}
                               for k, v in lat["cells"].items()}
    (ROOT / "sft_dpo_inventory/pilot_006/results/extra.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
