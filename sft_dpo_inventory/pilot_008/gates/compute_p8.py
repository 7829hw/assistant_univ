# -*- coding: utf-8 -*-
"""pilot_008 단계 판정(결정 225 X5). PLAN_008과 함께 학습 전에 고정한다. 모델 호출 없음.
계층 bootstrap은 ``pilot_007/gates/compute_gates_b.hier_ci``(a5e96c6, 순서 seed × 문항, 반복 10,000, ``default_rng(20261109)``, 비교마다 새 rng)를 그대로 쓴다.

    hfvenv/bin/python sft_dpo_inventory/pilot_008/gates/compute_p8.py --spec gates/spec_p8.json --out results/judgment_p8.json

표본 값(셀 행마다):
- ``refused`` = 결과 상태 ∈ {unsupported, needs_clarification} 그리고 분석 tool(``get_place_scope`` 밖) 실행 없음(PLAN_FINAL 4절과 같은 정의).
- ``route`` = M(오류 코드 UNSUPPORTED_QUESTION) / C(needs_clarification) / P(그 밖 거부).
- ``ok`` = ``compute_gates.load_arm``의 ok(견고성 패치 grounding_ok — pilot_007 판정과 같은 채점).
지표(문항 × 순서 seed 행렬, 문항 값 = k표본 평균):
- 올바른 거부율 = refusal_dev 거부 문항의 refused.
- 과잉 거부율 = 거부 아닌 문항(주 셋 151 + valid98·aux의 ``expected_outcome: answered`` 문항 + refusal_dev 대조)의 refused.
- 정답률 = 주 셋 151의 ok.
조건(넷 모두 통과면 통과):
1. 거부 개선: 올바른 거부율 P8 − B2 F(같은 seed 짝) CI 하한 > 0.
2. 거부 비열등: 올바른 거부율 P8 − base(refusal_dev k=12, 문항만 재추출) CI 하한 ≥ −15%p.
3. 과잉 거부: 과잉 거부율 P8 − B2 F CI 상한 ≤ +3%p.
4. 정답률 비열등: 주 셋 정답률 P8 − B2 F CI 하한 ≥ −5%p.
판정 불가: 조건이 불통과이고 그 CI 반폭이 해당 마진(1: 0, 2: 15, 3: 3, 4: 5)보다 넓으면 ``undecidable_if_fail`` 표시(마진은 바꾸지 않는다).
후보(통과 시): seed 단위 거부 비열등(그 seed의 refusal_dev 올바른 거부율 ≥ base 율)을 만족하는 seed 중 개발 셋(valid98 + aux 문항 평균) 정답률 최대, 같으면 seed 숫자가 작은 쪽.
보조: 거부 경로 M·P·C, 범주별 올바른 거부율, 개발 셋 정답률, 주 셋 대 base, 대 B2 F dt 누락·구조 오류.

SPEC: {"sets": {set: gold}, "rdev_gold": path, "rdev_meta": path, "seeds": [o43, ...], "seed_numbers": {o43: 43, ...},
       "cells": {"P8": {seed: {set: [cells]}}, "B2F": {seed: {set: [cells]}}, "base": {set: [cells]}}}  (set ∈ selection_v2·holdout·valid98·aux·rdev)
"""
import argparse
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
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_007/gates"))
REFUSED = ("unsupported", "needs_clarification")
MARGIN = {"1_refusal_improve": 0.0, "2_refusal_noninferior_base": -0.15, "3_over_refusal": 0.03, "4_accuracy_noninferior": -0.05}


def sample_values(path):
    """셀 하나 → {문항 id: (refused, route, expected_answered?)}."""
    d = json.loads((ROOT / path).read_text(encoding="utf-8"))
    out = {}
    for r in d["rows"]:
        out_c = r.get("outcome")
        analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
        refused = out_c in REFUSED and analysis == 0
        route = ("M" if r.get("error_code") == "UNSUPPORTED_QUESTION" else "C" if out_c == "needs_clarification" else "P") if refused else None
        out[r["id"]] = {"refused": refused, "route": route, "error_code": r.get("error_code")}
    return out


def matrix(cells_by_set, expected, want):
    """cells_by_set: {set: [cells]}, expected: {set: {id: expected_outcome}}, want: 'refusal'|'answered'. → (ids, 문항 값 벡터, route Counter, 표본 수)."""
    vals, routes = defaultdict(list), Counter()
    for st, cells in cells_by_set.items():
        for c in cells:
            for i, v in sample_values(c).items():
                exp = expected[st][i]
                if (want == "refusal") != (exp != "answered"):
                    continue
                vals[f"{st}:{i}"].append(float(v["refused"]))
                if v["route"]:
                    routes[v["route"]] += 1
    ids = sorted(vals)
    return ids, np.array([np.mean(vals[i]) for i in ids]), routes, sum(len(v) for v in vals.values())


def main():
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    import compute_gates_b as GB
    import evaluate_vendor100 as EV
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = json.loads((ROOT / a.spec).read_text(encoding="utf-8"))
    sets = dict(spec["sets"])
    sets["rdev"] = spec["rdev_gold"]
    expected = {st: {i["id"]: i.get("expected_outcome", "answered") for i in EV.load_gold(ROOT / g)["items"]} for st, g in sets.items()}
    rmeta = json.loads((ROOT / spec["rdev_meta"]).read_text(encoding="utf-8"))
    seeds = spec["seeds"]
    over_sets = ("selection_v2", "holdout", "valid98", "aux", "rdev")
    M = {"P8": defaultdict(list), "B2F": defaultdict(list)}
    per_seed, aux = {}, {"routes": {}, "by_gap": {}}
    ref_ids = None
    for arm in ("P8", "B2F"):
        for s in seeds:
            cells = spec["cells"][arm][s]
            ids_r, ref, routes, _ = matrix({"rdev": cells["rdev"]}, expected, "refusal")
            ids_o, over, _, _ = matrix({st: cells[st] for st in over_sets}, expected, "answered")
            items, m, _ = CG.load_arm({st: cells[st] for st in ("selection_v2", "holdout")}, sets, with_tokens=False)
            itd, md, _ = CG.load_arm({st: cells[st] for st in ("valid98", "aux")}, sets, with_tokens=False)
            if ref_ids is None:
                ref_ids, over_ids, main_ids = ids_r, ids_o, items
            assert ids_r == ref_ids and ids_o == over_ids and items == main_ids, (arm, s)
            M[arm]["ref"].append(ref)
            M[arm]["over"].append(over)
            for f in ("ok", "dt_missing", "struct", "U"):
                M[arm][f].append(m[f])
            M[arm]["dev_ok"].append(md["ok"])
            per_seed.setdefault(arm, {})[s] = {"refusal_pct": round(100 * float(ref.mean()), 2), "over_refusal_pct": round(100 * float(over.mean()), 2),
                                              "main_ok_pct": round(100 * float(m["ok"].mean()), 2), "dev_ok_pct": round(100 * float(md["ok"].mean()), 2),
                                              "refusal_routes": dict(routes)}
            gaps = defaultdict(list)
            for x, i in enumerate(ids_r):
                gaps[rmeta[i.split(":", 1)[1]]["gap"]].append(ref[x])
            aux["by_gap"].setdefault(arm, {})[s] = {g: round(100 * float(np.mean(v)), 1) for g, v in sorted(gaps.items())}
    X = {arm: {k: np.vstack(v) for k, v in M[arm].items()} for arm in M}
    ids_rb, base_ref, base_routes, _ = matrix({"rdev": spec["cells"]["base"]["rdev"]}, expected, "refusal")
    assert ids_rb == ref_ids
    ids_ob, base_over, _, _ = matrix({st: spec["cells"]["base"][st] for st in over_sets}, expected, "answered")
    itb, mb, _ = CG.load_arm({st: spec["cells"]["base"][st] for st in ("selection_v2", "holdout")}, sets, with_tokens=False)
    _, mdb, _ = CG.load_arm({st: spec["cells"]["base"][st] for st in ("valid98", "aux")}, sets, with_tokens=False)
    base_ref_rate = float(base_ref.mean())
    res = {}
    c1 = GB.fmt(GB.hier_ci(X["B2F"]["ref"], X["P8"]["ref"]))
    res["1_refusal_improve"] = {**c1, "rule": "올바른 거부율 P8 − B2 F CI 하한 > 0", "pass": c1["ci95_pp"][0] > 0}
    c2 = GB.fmt(GB.hier_ci(X["P8"]["ref"], base=base_ref))
    res["2_refusal_noninferior_base"] = {**c2, "rule": "올바른 거부율 P8 − base CI 하한 ≥ −15%p", "pass": c2["ci95_pp"][0] >= -15.0}
    c3 = GB.fmt(GB.hier_ci(X["B2F"]["over"], X["P8"]["over"]))
    res["3_over_refusal"] = {**c3, "rule": "과잉 거부율 P8 − B2 F CI 상한 ≤ +3%p", "pass": c3["ci95_pp"][1] <= 3.0}
    c4 = GB.fmt(GB.hier_ci(X["B2F"]["ok"], X["P8"]["ok"]))
    res["4_accuracy_noninferior"] = {**c4, "rule": "주 셋 정답률 P8 − B2 F CI 하한 ≥ −5%p", "pass": c4["ci95_pp"][0] >= -5.0}
    for k, v in res.items():
        hw = v["half_width_pp"]
        v["undecidable_if_fail"] = (not v["pass"]) and hw > abs(100 * MARGIN[k]) if MARGIN[k] else (not v["pass"]) and v["ci95_pp"][0] <= 0 <= v["ci95_pp"][1]
    passed = all(v["pass"] for v in res.values())
    cand = None
    if passed:
        ok_seeds = [s for s in seeds if per_seed["P8"][s]["refusal_pct"] >= round(100 * base_ref_rate, 2)]
        if ok_seeds:
            cand = sorted(ok_seeds, key=lambda s: (-per_seed["P8"][s]["dev_ok_pct"], spec["seed_numbers"][s]))[0]
    out = {"seeds": seeds, "conditions": res, "pass": passed,
           "candidate": {"seed": cand, "rule": "seed 단위 refusal_dev 올바른 거부율 ≥ base 율인 seed 중 개발 셋 정답률 최대, 같으면 seed 숫자 작은 쪽",
                         "seeds_meeting_refusal": [s for s in seeds if per_seed["P8"][s]["refusal_pct"] >= round(100 * base_ref_rate, 2)] if passed else None},
           "per_seed": per_seed,
           "base": {"refusal_pct": round(100 * base_ref_rate, 2), "refusal_routes": dict(base_routes), "over_refusal_pct": round(100 * float(base_over.mean()), 2),
                    "main_ok_pct": round(100 * float(mb["ok"].mean()), 2), "dev_ok_pct": round(100 * float(mdb["ok"].mean()), 2)},
           "aux": {"refusal_by_gap_pct": aux["by_gap"],
                   "main_ok_vs_base": GB.fmt(GB.hier_ci(X["P8"]["ok"], base=mb["ok"])),
                   "dev_ok_P8_minus_B2F": GB.fmt(GB.hier_ci(X["B2F"]["dev_ok"], X["P8"]["dev_ok"])),
                   "dt_missing_P8_minus_B2F": GB.fmt(GB.hier_ci(X["B2F"]["dt_missing"], X["P8"]["dt_missing"])),
                   "struct_P8_minus_B2F": GB.fmt(GB.hier_ci(X["B2F"]["struct"], X["P8"]["struct"])),
                   "U_P8_minus_B2F": GB.fmt(GB.hier_ci(X["B2F"]["U"], X["P8"]["U"])),
                   "means_pp": {arm: {k: round(100 * float(v.mean()), 2) for k, v in X[arm].items()} for arm in X}},
           "items": {"refusal": len(ref_ids), "non_refusal(over)": len(over_ids), "main": len(main_ids)},
           "bootstrap": {"reps": GB.REPS, "seed": GB.SEED, "kind": "순서 seed × 문항 계층(compute_gates_b.hier_ci)"}}
    Path(ROOT / a.out).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "candidate": cand, "conditions": {k: {kk: v[kk] for kk in ("diff_pp", "ci95_pp", "pass")} for k, v in res.items()}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
