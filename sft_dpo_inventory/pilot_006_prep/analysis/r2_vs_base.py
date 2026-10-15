# -*- coding: utf-8 -*-
"""C9: Partial base(R2, P0.3 prompt) 대 Full base(같은 17,408 서버) — selection_v2(R2 = J5R', base = B1+X2), valid98(R2v 대 B3), aux_test_v1(R2a 대 B4).
holdout(R2h, B2)은 봉인이라 쓰지 않는다. 모델 호출 없음. **참고 분석**: Gate 기준은 바꾸지 않고, PLAN_DRAFT에 Gate D·E 예상 범위를 참고로만 적는다.

    hfvenv/bin/python r2_vs_base.py   # -> r2_vs_base.json

- 지표·CI는 ``pilot_006/gates/compute_gates``(load_arm, cmp)와 같다(P = R2, F = Full base로 넣어 "P − F"를 Partial − Full로 읽는다).
- 부분집합: partial-grounding ``p0_sft_004/subsets.json``(gold·질문만으로 정의, 이식본) — dt_any·dt_pickup·dt_dropoff·dt_both·od_ne_dt·implicit_endpoint_all·
  implicit_endpoint_verb·scope_reverse 등. 더해서 gold에서: 실차(측정값 trip_count 또는 taxi_status occupied), value 없는 place(답이 장소인 문항, 측정값이 place).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
import compute_gates as CG  # noqa: E402

C = "sft_dpo_inventory/pilot_006_prep/cells/"
SETS = {"selection_v2": ("sft_dpo_inventory/conversion_diag/selection_gold.yaml", "sel154",
                         [f"{C}b1_sel_base_s{k}.json" for k in (1, 2, 3, 4)] + [f"{C}x2_sel_base_17408_s{k}.json" for k in (1, 2, 3, 4)],
                         [f"{C}r2b_partial_base_s{k}.json" for k in (1, 2, 3, 4)]),
        "valid98": ("sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "valid98", [f"{C}b3_valid98_base_s{k}.json" for k in (1, 2, 3, 4)],
                    [f"{C}r2v_partial_base_s{k}.json" for k in (1, 2, 3, 4)]),
        "aux_test_v1": ("sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml", "aux_test_v1", [f"{C}b4_aux_base_s{k}.json" for k in (1, 2, 3, 4)],
                        [f"{C}r2a_partial_base_s{k}.json" for k in (1, 2, 3, 4)])}
FIELDS = ("ok", "U", "silent", "dt_missing", "mm_nm", "struct", "gfail", "repair")


def main():
    import evaluate_vendor100 as EV
    subs = json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/integration/pg_tools/subsets.json").read_text(encoding="utf-8"))["subsets"]
    out = {"note": "참고 분석(판정 아님). Partial base = P0.3 prompt, Full base = 87048d0c, 같은 17,408 서버", "sets": {}}
    for name, (gold_path, prefix, full_cells, part_cells) in SETS.items():
        sets = {name: gold_path}
        items_f, mf, _ = CG.load_arm({name: full_cells}, sets)
        items_p, mp, _ = CG.load_arm({name: part_cells}, sets)
        assert items_f == items_p
        ids = [i.split("/", 1)[1] for i in items_f]
        gold = {i["id"]: i for i in EV.load_gold(ROOT / gold_path)["items"]}
        res = {"items": len(ids), "full_base": {f: round(100 * float(np.nanmean(mf[f])), 2) for f in FIELDS},
               "partial_base": {f: round(100 * float(np.nanmean(mp[f])), 2) for f in FIELDS},
               "partial_minus_full": {f: CG.cmp(mf, mp, f) for f in FIELDS},
               "tokens_median": {arm: {f: float(np.nanmedian(m[f])) for f in ("input_tokens", "gen_tokens", "thinking_tokens", "json_tokens")}
                                 for arm, m in (("full", mf), ("partial", mp))}}
        jf, jp = res["tokens_median"]["full"]["json_tokens"], res["tokens_median"]["partial"]["json_tokens"]
        res["json_reduction_pct"] = round(100 * (1 - jp / jf), 1) if jf else None
        derived = {"silcha": [], "valueless_place": []}
        for i in ids:
            g = EV.gold_grounding(gold[i]) or {}
            subt = {c.get("subtype") for c in g.get("concepts", []) if c.get("role") == "MEASURE"}
            if "trip_count" in subt or (g.get("factors") or {}).get("taxi_status") == "occupied":
                derived["silcha"].append(i)
            if "place" in subt:
                derived["valueless_place"].append(i)
        subsets = {k: [i for i in ids if f"{prefix}:{i}" in set(v)] for k, v in subs.items()}
        subsets.update(derived)
        res["subsets"] = {}
        for k, members in subsets.items():
            if not members:
                continue
            idx = [ids.index(i) for i in members]
            res["subsets"][k] = {"n": len(idx), "ok_full": round(100 * float(mf["ok"][idx].mean()), 1), "ok_partial": round(100 * float(mp["ok"][idx].mean()), 1),
                                 "dt_missing_full": round(100 * float(mf["dt_missing"][idx].mean()), 1),
                                 "dt_missing_partial": round(100 * float(mp["dt_missing"][idx].mean()), 1),
                                 "struct_full": round(100 * float(mf["struct"][idx].mean()), 1), "struct_partial": round(100 * float(mp["struct"][idx].mean()), 1)}
        out["sets"][name] = res
    (HERE / "r2_vs_base.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n",
                                          encoding="utf-8")
    for name, r in out["sets"].items():
        print(name, r["items"], "ok", r["full_base"]["ok"], "->", r["partial_base"]["ok"], r["partial_minus_full"]["ok"], "| dt", r["partial_minus_full"]["dt_missing"],
              "| struct", r["partial_minus_full"]["struct"], "| mm_nm", r["partial_minus_full"]["mm_nm"], "| json -", r["json_reduction_pct"], "% tok", r["tokens_median"])
        for k in ("dt_any", "dt_pickup", "dt_dropoff", "od_ne_dt", "implicit_endpoint_verb", "scope_reverse", "silcha", "valueless_place"):
            if k in r["subsets"]:
                print("   ", k, r["subsets"][k])


if __name__ == "__main__":
    main()
