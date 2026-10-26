# -*- coding: utf-8 -*-
"""pilot_009 단계 판정(결정 237 Z5). PLAN_009와 함께 학습 전에 고정한다. 모델 호출 없음. ``pilot_008/gates/compute_p8.py``의 사본(그 파일은 고치지 않음):
arm 이름 P8 → P9, refusal_dev v2(거부 90·대조 30), 보조 arm P8(같은 지표 P9 − P8)과 base 범주별 거부율을 더했다. 판정 규칙·bootstrap은 그대로.
계층 bootstrap은 ``pilot_007/gates/compute_gates_b.hier_ci``(a5e96c6, 순서 seed × 문항, 반복 10,000, ``default_rng(20261109)``, 비교마다 새 rng)를 그대로 쓴다.

    hfvenv/bin/python sft_dpo_inventory/pilot_009/gates/compute_p9.py --spec sft_dpo_inventory/pilot_009/gates/spec_p9.json --out sft_dpo_inventory/pilot_009/results/judgment_p9.json

표본 값(셀 행마다):
- ``refused`` = 결과 상태 ∈ {unsupported, needs_clarification} 그리고 분석 tool(``get_place_scope`` 밖) 실행 없음.
- ``route`` = M(오류 코드 UNSUPPORTED_QUESTION) / C(needs_clarification) / P(그 밖 거부).
- ``ok`` = ``compute_gates.load_arm``의 ok(견고성 패치 grounding_ok — pilot_007·008 판정과 같은 채점).
지표(문항 × 순서 seed 행렬, 문항 값 = k표본 평균):
- 올바른 거부율 = refusal_dev v2 거부 90의 refused.
- 과잉 거부율 = 거부 아닌 문항(주 셋 151 + valid98·aux의 ``expected_outcome: answered`` 문항 + refusal_dev 대조 30)의 refused.
- 정답률 = 주 셋 151(selection_v2 98 + holdout 53)의 ok. 개발 셋 = valid98 + aux 문항(문항 수 가중 = 문항을 이어 붙인 평균).
조건(넷 모두 통과면 통과):
1. 거부 개선: 올바른 거부율 P9 − B2 F(같은 seed 짝) CI 하한 > 0.
2. 거부 비열등: 올바른 거부율 P9 − base(refusal_dev v2 k=12, 문항만 재추출) CI 하한 ≥ −15%p.
3. 과잉 거부: 과잉 거부율 P9 − B2 F CI 상한 ≤ +3%p.
4. 정답률 비열등: 주 셋 정답률 P9 − B2 F CI 하한 ≥ −5%p.
판정 불가: 조건이 불통과이고 그 CI 반폭이 해당 마진(1: 0, 2: 15, 3: 3, 4: 5)보다 넓으면(조건 1은 CI가 0을 포함) ``undecidable_if_fail`` 표시(마진은 바꾸지 않는다).
후보(통과 시): seed 단위 refusal_dev v2 올바른 거부율 ≥ base 율인 seed 중 개발 셋 정답률 최대, 같으면 seed 숫자가 작은 쪽.
보조(판정 아님): P8 대비 같은 지표(P9 − P8, 같은 seed 짝), 거부 경로 M·P·C, 범주별 올바른 거부율(P9·B2 F·P8·base), 개발 셋 정답률, 주 셋 대 base, 대 B2 F dt 누락·구조 오류·U.

SPEC: {"sets": {set: gold}, "rdev_gold": path, "rdev_meta": path, "seeds": [o43, ...], "seed_numbers": {o43: 43, ...},
       "cells": {"P9": {seed: {set: [cells]}}, "B2F": {...}, "P8": {...}, "base": {set: [cells]}}}  (set ∈ selection_v2·holdout·valid98·aux·rdev)
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P9 = HERE.parent
ROOT = P9.parents[1]
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
    M = {"P9": defaultdict(list), "B2F": defaultdict(list), "P8": defaultdict(list)}
    per_seed, aux = {}, {"routes": {}, "by_gap": {}}
    ref_ids = None
    for arm in ("P9", "B2F", "P8"):
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
    bg = defaultdict(list)
    for x, i in enumerate(ids_rb):
        bg[rmeta[i.split(":", 1)[1]]["gap"]].append(base_ref[x])
    aux["by_gap"]["base"] = {g: round(100 * float(np.mean(v)), 1) for g, v in sorted(bg.items())}
    res = {}
    c1 = GB.fmt(GB.hier_ci(X["B2F"]["ref"], X["P9"]["ref"]))
    res["1_refusal_improve"] = {**c1, "rule": "올바른 거부율 P9 − B2 F CI 하한 > 0", "pass": c1["ci95_pp"][0] > 0}
    c2 = GB.fmt(GB.hier_ci(X["P9"]["ref"], base=base_ref))
    res["2_refusal_noninferior_base"] = {**c2, "rule": "올바른 거부율 P9 − base CI 하한 ≥ −15%p", "pass": c2["ci95_pp"][0] >= -15.0}
    c3 = GB.fmt(GB.hier_ci(X["B2F"]["over"], X["P9"]["over"]))
    res["3_over_refusal"] = {**c3, "rule": "과잉 거부율 P9 − B2 F CI 상한 ≤ +3%p", "pass": c3["ci95_pp"][1] <= 3.0}
    c4 = GB.fmt(GB.hier_ci(X["B2F"]["ok"], X["P9"]["ok"]))
    res["4_accuracy_noninferior"] = {**c4, "rule": "주 셋 정답률 P9 − B2 F CI 하한 ≥ −5%p", "pass": c4["ci95_pp"][0] >= -5.0}
    for k, v in res.items():
        hw = v["half_width_pp"]
        v["undecidable_if_fail"] = (not v["pass"]) and hw > abs(100 * MARGIN[k]) if MARGIN[k] else (not v["pass"]) and v["ci95_pp"][0] <= 0 <= v["ci95_pp"][1]
    passed = all(v["pass"] for v in res.values())
    cand = None
    if passed:
        ok_seeds = [s for s in seeds if per_seed["P9"][s]["refusal_pct"] >= round(100 * base_ref_rate, 2)]
        if ok_seeds:
            cand = sorted(ok_seeds, key=lambda s: (-per_seed["P9"][s]["dev_ok_pct"], spec["seed_numbers"][s]))[0]
    out = {"seeds": seeds, "conditions": res, "pass": passed,
           "candidate": {"seed": cand, "rule": "seed 단위 refusal_dev 올바른 거부율 ≥ base 율인 seed 중 개발 셋 정답률 최대, 같으면 seed 숫자 작은 쪽",
                         "seeds_meeting_refusal": [s for s in seeds if per_seed["P9"][s]["refusal_pct"] >= round(100 * base_ref_rate, 2)] if passed else None},
           "per_seed": per_seed,
           "base": {"refusal_pct": round(100 * base_ref_rate, 2), "refusal_routes": dict(base_routes), "over_refusal_pct": round(100 * float(base_over.mean()), 2),
                    "main_ok_pct": round(100 * float(mb["ok"].mean()), 2), "dev_ok_pct": round(100 * float(mdb["ok"].mean()), 2)},
           "aux": {"refusal_by_gap_pct": aux["by_gap"],
                   "main_ok_vs_base": GB.fmt(GB.hier_ci(X["P9"]["ok"], base=mb["ok"])),
                   "dev_ok_P9_minus_B2F": GB.fmt(GB.hier_ci(X["B2F"]["dev_ok"], X["P9"]["dev_ok"])),
                   "dt_missing_P9_minus_B2F": GB.fmt(GB.hier_ci(X["B2F"]["dt_missing"], X["P9"]["dt_missing"])),
                   "struct_P9_minus_B2F": GB.fmt(GB.hier_ci(X["B2F"]["struct"], X["P9"]["struct"])),
                   "U_P9_minus_B2F": GB.fmt(GB.hier_ci(X["B2F"]["U"], X["P9"]["U"])),
                   "means_pp": {arm: {k: round(100 * float(v.mean()), 2) for k, v in X[arm].items()} for arm in X},
                   "vs_P8": {"refusal_P9_minus_P8": GB.fmt(GB.hier_ci(X["P8"]["ref"], X["P9"]["ref"])),
                             "over_refusal_P9_minus_P8": GB.fmt(GB.hier_ci(X["P8"]["over"], X["P9"]["over"])),
                             "main_ok_P9_minus_P8": GB.fmt(GB.hier_ci(X["P8"]["ok"], X["P9"]["ok"])),
                             "dev_ok_P9_minus_P8": GB.fmt(GB.hier_ci(X["P8"]["dev_ok"], X["P9"]["dev_ok"])),
                             "P8_refusal_minus_base": GB.fmt(GB.hier_ci(X["P8"]["ref"], base=base_ref))},
                   "B2F_refusal_minus_base": GB.fmt(GB.hier_ci(X["B2F"]["ref"], base=base_ref))},
           "items": {"refusal": len(ref_ids), "non_refusal(over)": len(over_ids), "main": len(main_ids)},
           "bootstrap": {"reps": GB.REPS, "seed": GB.SEED, "kind": "순서 seed × 문항 계층(compute_gates_b.hier_ci)"}}
    Path(ROOT / a.out).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "candidate": cand, "conditions": {k: {kk: v[kk] for kk in ("diff_pp", "ci95_pp", "pass")} for k, v in res.items()}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
