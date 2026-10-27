# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 선택(결정 252 AB6). PLAN_S와 함께 학습 전에 고정한다. 모델 호출 없음. 표본 값·지표 계산은 ``pilot_009/gates/compute_p9.py``의
``sample_values``·``matrix``와 ``compute_gates.load_arm``(견고성 패치 채점)을 그대로 불러 쓴다(그 파일들은 고치지 않음).

    hfvenv/bin/python sft_dpo_inventory/pilot_010/gates/select_s10.py --spec sft_dpo_inventory/pilot_010/gates/spec_s10.json --out sft_dpo_inventory/pilot_010/results/selection_s10.json

지표(문항 × seed, 문항 값 = k표본 평균; 변형 값 = **있는 seed의 평균**, seed마다 문항 평균을 낸 뒤 seed 평균):
- 올바른 거부율 = refusal_dev v2 거부 90의 refused(``compute_p9.sample_values``: 결과 unsupported·needs_clarification이고 분석 tool 실행 없음).
- 과잉 거부율 = 거부 아닌 문항(valid98·aux의 ``expected_outcome: answered`` + refusal_dev 대조 30)의 refused. 주 셋은 쓰지 않는다.
- 개발 셋 정답률 = valid98 + aux의 ok(문항 수 가중 = 문항을 이어 붙인 평균).
기준(이미 있는 셀): base 올바른 거부율 = refusal_dev v2 k=12(``pilot_009/cells/base_rdevv2``), B2 F 과잉 거부율 = B2 F 다섯 seed(o43·o1016·o7·o11·o2027)의
valid98·aux(pilot_007 B2 셀) + refusal_dev 대조(pilot_009 ``b2f_<o>_rdevv2``)를 같은 방식(seed 평균)으로.
규칙(PLAN_S 2절):
- (가) 변형 올바른 거부율 ≥ base 올바른 거부율(27.96%; 셀에서 다시 계산한 값을 쓰고 27.96과 다르면 기록).
- (나) 변형 과잉 거부율 ≤ B2 F 과잉 거부율 + 3%p.
- (가)·(나)를 모두 만족하는 변형 중 개발 셋 정답률이 높은 쪽. 두 변형 모두 만족하고 정답률 차가 0.5%p 미만이면 V4. 하나만 만족하면 그것. 둘 다 못 하면 선택 없음(판정 단계로 가지 않음).
- 비교는 %p 단위 소수 둘째 자리 반올림 값으로 한다(``round(100 · x, 2)``).
보조(선택에 쓰지 않음): seed별 값, 거부 경로 M/P/C, 범주별 올바른 거부율(V4·V8·base·B2 F·P9), 요금 지표 문항(정답 호출에 ``get_billing_metrics``)의 과잉 거부(P9 비교),
일 단위 집계 문항(요금 지표 정답 호출에 ``aggregation``이 있고 ``bucket``이 없음)의 거부 표본 수.

SPEC: {"sets": {valid98, aux}, "rdev_gold", "rdev_meta", "variants": ["V4", "V8"], "seeds": [o43, o1016, o7],
       "cells": {"V4": {seed: {valid98, aux, rdev}}, "V8": {...}, "B2F": {seed: {...}}, "P9": {seed: {...}}, "base": {valid98, aux, rdev}}}
       셀이 없거나 학습에서 빠진 seed는 ``excluded_seeds``: {variant: [seed]}로 적는다(그 seed 없이 평균).
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
ROOT = P10.parents[1]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006/gates", ROOT / "sft_dpo_inventory/pilot_006/post", ROOT / "sft_dpo_inventory/pilot_007/gates",
          ROOT / "sft_dpo_inventory/pilot_009/gates"):
    sys.path.insert(0, str(p))
OVER_SETS = ("valid98", "aux", "rdev")
BASE_REF_EXPECTED_PCT = 27.96
OVER_MARGIN_PP = 3.0
TIE_PP = 0.5


def pp(x):
    return round(100 * float(x), 2)


def billing_flags(gold_items):
    """문항 id → (요금 지표, 일 단위 집계)."""
    out = {}
    for it in gold_items:
        calls = it.get("gold") or []
        bm = [c for c in calls if c.get("tool") == "get_billing_metrics"]
        daily = any("aggregation" in c.get("args", {}) and "bucket" not in c.get("args", {}) for c in bm)
        out[it["id"]] = (bool(bm), daily)
    return out


def main():
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    import compute_p9 as C9
    import evaluate_vendor100 as EV
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = json.loads((ROOT / a.spec).read_text(encoding="utf-8"))
    sets = dict(spec["sets"])
    sets["rdev"] = spec["rdev_gold"]
    gold = {st: EV.load_gold(ROOT / g)["items"] for st, g in sets.items()}
    expected = {st: {i["id"]: i.get("expected_outcome", "answered") for i in items} for st, items in gold.items()}
    flags = {st: billing_flags(items) for st, items in gold.items()}
    rmeta = json.loads((ROOT / spec["rdev_meta"]).read_text(encoding="utf-8"))
    excluded = spec.get("excluded_seeds", {})

    def arm_seed(cells):
        ids_r, ref, routes, _ = C9.matrix({"rdev": cells["rdev"]}, expected, "refusal")
        ids_o, over, _, _ = C9.matrix({st: cells[st] for st in OVER_SETS}, expected, "answered")
        _, md, _ = CG.load_arm({st: cells[st] for st in ("valid98", "aux")}, sets, with_tokens=False)
        gaps = defaultdict(list)
        for x, i in enumerate(ids_r):
            gaps[rmeta[i.split(":", 1)[1]]["gap"]].append(ref[x])
        bill, daily = Counter(), Counter()
        for st in OVER_SETS:
            for c in cells[st]:
                for i, v in C9.sample_values(c).items():
                    if expected[st][i] != "answered":
                        continue
                    b, d = flags[st].get(i, (False, False))
                    if b:
                        bill["samples"] += 1
                        bill["refused"] += v["refused"]
                    if d:
                        daily["samples"] += 1
                        daily["refused"] += v["refused"]
        return {"ref": ref, "over": over, "dev_ok": md["ok"], "routes": dict(routes), "by_gap": {g: pp(np.mean(v)) for g, v in sorted(gaps.items())},
                "billing_over": dict(bill), "daily_agg": dict(daily), "ids_r": ids_r, "ids_o": ids_o}

    def summarize(name, seed_list):
        per = {}
        for s in seed_list:
            r = arm_seed(spec["cells"][name][s])
            per[s] = r
        refs = [float(per[s]["ref"].mean()) for s in per]
        overs = [float(per[s]["over"].mean()) for s in per]
        devs = [float(per[s]["dev_ok"].mean()) for s in per]
        tot = lambda k, f: sum(per[s][k].get(f, 0) for s in per)  # noqa: E731
        return {"seeds": list(per), "refusal_pct": pp(np.mean(refs)), "over_refusal_pct": pp(np.mean(overs)), "dev_ok_pct": pp(np.mean(devs)),
                "per_seed": {s: {"refusal_pct": pp(per[s]["ref"].mean()), "over_refusal_pct": pp(per[s]["over"].mean()), "dev_ok_pct": pp(per[s]["dev_ok"].mean()),
                                 "refusal_routes": per[s]["routes"], "billing_over_refusal": per[s]["billing_over"], "daily_agg_refused": per[s]["daily_agg"]}
                             for s in per},
                "refusal_routes": dict(sum((Counter(per[s]["routes"]) for s in per), Counter())),
                "refusal_by_gap_pct": {g: round(float(np.mean([per[s]["by_gap"][g] for s in per])), 2) for g in next(iter(per.values()))["by_gap"]},
                "billing_over_refusal": {"refused": tot("billing_over", "refused"), "samples": tot("billing_over", "samples"),
                                         "pct": pp(tot("billing_over", "refused") / max(1, tot("billing_over", "samples")))},
                "daily_agg": {"refused": tot("daily_agg", "refused"), "samples": tot("daily_agg", "samples")},
                "_ids": (per[next(iter(per))]["ids_r"], per[next(iter(per))]["ids_o"])}

    res = {}
    for v in spec["variants"]:
        seeds = [s for s in spec["seeds"] if s not in excluded.get(v, [])]
        res[v] = summarize(v, seeds) if seeds else None
    b2 = summarize("B2F", list(spec["cells"]["B2F"]))
    p9 = summarize("P9", list(spec["cells"]["P9"])) if spec["cells"].get("P9") else None
    base = spec["cells"]["base"]
    ids_rb, base_ref, base_routes, _ = C9.matrix({"rdev": base["rdev"]}, expected, "refusal")
    ids_ob, base_over, _, _ = C9.matrix({st: base[st] for st in OVER_SETS}, expected, "answered")
    _, mdb, _ = CG.load_arm({st: base[st] for st in ("valid98", "aux")}, sets, with_tokens=False)
    bg = defaultdict(list)
    for x, i in enumerate(ids_rb):
        bg[rmeta[i.split(":", 1)[1]]["gap"]].append(base_ref[x])
    base_ref_pct = pp(base_ref.mean())
    for v, r in res.items():
        if r:
            assert r["_ids"] == (ids_rb, ids_ob) == b2["_ids"], v
    over_limit = round(b2["over_refusal_pct"] + OVER_MARGIN_PP, 2)
    rules = {}
    for v, r in res.items():
        if r is None:
            rules[v] = {"ga": False, "na": False, "both": False, "note": "seed 없음"}
            continue
        ga, na = r["refusal_pct"] >= base_ref_pct, r["over_refusal_pct"] <= over_limit
        rules[v] = {"ga_refusal_ge_base": ga, "na_over_le_B2F_plus3": na, "both": ga and na, "dev_ok_pct": r["dev_ok_pct"]}
    ok = [v for v in spec["variants"] if rules[v].get("both")]
    if not ok:
        selected, why = None, "(가)·(나)를 모두 만족하는 변형 없음 — 판정 단계로 가지 않음"
    elif len(ok) == 1:
        selected, why = ok[0], f"{ok[0]}만 (가)·(나)를 모두 만족"
    else:
        d = round(res["V8"]["dev_ok_pct"] - res["V4"]["dev_ok_pct"], 2)
        if abs(d) < TIE_PP:
            selected, why = "V4", f"둘 다 만족, 개발 셋 정답률 차 V8 − V4 = {d}%p (< {TIE_PP}) → V4"
        else:
            selected = "V8" if d > 0 else "V4"
            why = f"둘 다 만족, 개발 셋 정답률 차 V8 − V4 = {d}%p → {selected}"
    for r in [*res.values(), b2, p9]:
        if r:
            r.pop("_ids", None)
    out = {"rule": {"ga": f"refusal_dev v2 거부 90 올바른 거부율(seed 평균) ≥ base {base_ref_pct}%",
                    "na": f"과잉 거부율(valid98·aux 답하는 문항 + refusal_dev 대조 30, seed 평균) ≤ B2 F {b2['over_refusal_pct']}% + {OVER_MARGIN_PP}%p = {over_limit}%",
                    "pick": f"둘 다 만족하는 변형 중 개발 셋(valid98 + aux, 문항 수 가중) 정답률 높은 쪽, 차 < {TIE_PP}%p면 V4; 없으면 판정 단계로 가지 않음"},
           "selected": selected, "why": why, "rules": rules, "variants": res, "excluded_seeds": excluded,
           "reference": {"base": {"refusal_pct": base_ref_pct, "refusal_pct_expected": BASE_REF_EXPECTED_PCT, "matches_expected": base_ref_pct == BASE_REF_EXPECTED_PCT,
                                  "refusal_routes": dict(base_routes), "over_refusal_pct": pp(base_over.mean()), "dev_ok_pct": pp(mdb["ok"].mean()),
                                  "refusal_by_gap_pct": {g: pp(np.mean(v)) for g, v in sorted(bg.items())}},
                         "B2F": b2, "P9": p9},
           "items": {"refusal": len(ids_rb), "non_refusal(over)": len(ids_ob)}}
    Path(ROOT / a.out).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"selected": selected, "why": why, "rules": rules, "base_refusal_pct": base_ref_pct, "over_limit_pct": over_limit,
                      "variants": {v: {k: r[k] for k in ("refusal_pct", "over_refusal_pct", "dev_ok_pct")} if r else None for v, r in res.items()}},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
