# -*- coding: utf-8 -*-
"""ablation_011 분석(결정 261, PLAN_A11 6절). **진단, 판정 아님.** 모델 호출 없음. 표본 값은 pilot_010 선택 도구와 같은 함수를 불러 쓴다(그 파일들은 고치지 않음):
ok·U·생성 token·thinking token = ``compute_gates.load_arm``(견고성 패치 채점), refused·경로 = ``compute_p9.sample_values``.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/analysis/analyze_a11.py            # -> analysis/results_a11.json
    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/analysis/analyze_a11.py --smoke    # -> analysis/smoke_a11.json (pilot_010 셀: A0 자리 = V4, A1 자리 = V8)

지표(E1; 문항 값 = 표본 평균, 모델 값 = 문항 평균):
- dev_ok: 개발 셋 149(valid98 + aux) 정답률. ref: refusal_dev v2 거부 90 올바른 거부율. over: 거부 아닌 169(valid98·aux 답하는 문항 + rdev 대조 30) 과잉 거부율.
- U: 개발 셋 U 등급(U1–U4) 표본 비율(모델당 수 = 비율 × 149 × k). 속도: E1 모든 행의 wall(finished_at − started_at) p50·p95, 생성 token(행의 hf_calls 합) 평균,
  thinking token(개발 셋, ``token_parts``) 평균, 잘림 호출(finish_reason length) 수, 거부 경로 M/P/C.
1. arm − A0(같은 순서 seed 짝): 점 추정 = seed 평균 차. bootstrap 10,000: 반복마다 seed 짝 복원 재추출(``rng.integers(0, S, S)``)과 문항 복원 재추출(``rng.integers(0, I, I)``,
   두 arm 같은 번호), 통계량 = 뽑힌 seed 짝·문항에서 (arm − A0) 문항 값 차의 평균. 비교·지표마다 새 ``default_rng(20261109)``, 백분위 2.5·97.5.
2. 순서 편차: V4 6 seed(pilot_010 o43·o1016·o7 + A0 o1102·o211102·o2026113) 값·평균·sd(ddof 1)·범위. 분산 분해(dev ok, 6 seed × 149 × 4 표본, 균형 2원 임의 효과 + 반복, ANOVA 추정):
   seed / 문항 / seed×문항 / sampling. base dev(149 × 4): 문항 / sampling.
3. 유형 칸(template_group 대체): 개발 셋 문항을 정답 호출 서명(분석 tool | 시간 단위 | 지역 유형, ``xtab_a11.classify``)으로 묶고, 문항 4개 이상 칸 중 V4 6 seed 정답률 최대 − 최소 상위 20.
   (PLAN_A11 6절 3의 ``type_target.profile`` 칸은 semantics가 필요한데 E1 gold에는 정답 호출만 있어 정답 호출 서명으로 바꿨다 — FREEZE_A11_tools.json에 적음.)
   o43 약점 대응 부분집합: (a) 정답 tool get_billing_metrics + 장소 scope 있음, (b) 정답에 scope_pickup·scope_dropoff(OD). client_test_10000 보충(기존 셀): V4 3 seed·base 3 회차 정답률,
   두 seed(회차) 사이 문항 정오 불일치율, V4 seed 사이 template_group 정답률 차 상위 20(문항 30 이상).
4. soup: soup 값 − V4 6 seed 평균(CI: 문항 재추출 + 6 seed 복원 재추출, 10,000, ``default_rng(20261109)``), 6 seed 최솟값과 비교.
5. 과잉 거부 교차표: ``xtab_a11.xtab``을 arm(3 seed 합)·soup·V4 기존 3 seed에 적용.
"""
import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
A11 = HERE.parent
ROOT = A11.parents[1]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006/gates", ROOT / "sft_dpo_inventory/pilot_006/post", ROOT / "sft_dpo_inventory/pilot_007/gates",
          ROOT / "sft_dpo_inventory/pilot_009/gates", HERE):
    sys.path.insert(0, str(p))
import xtab_a11 as XT  # noqa: E402

SETS = {"valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml",
        "rdev": "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"}
DEV, OVER = ("valid98", "aux"), ("valid98", "aux", "rdev")
ARMS, NEW_SEEDS, OLD_SEEDS = ("A0", "A1", "A2", "A3"), ("o1102", "o211102", "o2026113"), ("o43", "o1016", "o7")
REPS, RNG_SEED = 10000, 20261109
MIN_GROUP = 4  # 유형 칸 상위 20은 문항 4개 이상 칸만
CELLS = "sft_dpo_inventory/ablation_011/cells"
SPEC10 = ROOT / "sft_dpo_inventory/pilot_010/gates/spec_s10.json"


def pp(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(100 * float(x), 2)


def new_cells(prefix):
    lab = {"valid98": "valid98", "aux": "aux", "rdev": "rdevv2"}
    return {st: [f"{CELLS}/{prefix}_{lab[st]}_s{k}.json" for k in range(1, 5)] for st in SETS}


def model_table(smoke):
    s10 = json.loads(SPEC10.read_text(encoding="utf-8"))["cells"]
    m = {}
    for s in OLD_SEEDS:
        m[f"V4_{s}"] = {"cells": s10["V4"][s], "group": "V4_old", "seed": s, "tokens": True}
    if smoke:  # A0 자리 = V4 기존 셀, A1 자리 = V8 기존 셀(같은 순서 seed) — 짝 비교·지표 계산 smoke
        for s in OLD_SEEDS:
            m[f"A0_{s}"] = {"cells": s10["V4"][s], "group": "A0", "seed": s, "tokens": True}
            m[f"A1_{s}"] = {"cells": s10["V8"][s], "group": "A1", "seed": s, "tokens": True}
    else:
        for a in ARMS:
            for s in NEW_SEEDS:
                m[f"{a}_{s}"] = {"cells": new_cells(f"a11_{a.lower()}_{s}"), "group": a, "seed": s, "tokens": True}
        m["soup"] = {"cells": new_cells("a11_soup"), "group": "soup", "seed": None, "tokens": True}
    m["base"] = {"cells": s10["base"], "group": "base", "seed": None, "tokens": False}
    for s, c in s10["B2F"].items():
        m[f"B2F_{s}"] = {"cells": c, "group": "B2F", "seed": s, "tokens": False}
    return m


def present(cells):
    return all((ROOT / p).exists() for v in cells.values() for p in v)


def _ts(x):
    return datetime.fromisoformat(x).timestamp()


def load_model(cells, sets_abs, gold, tokens):
    import compute_gates as CG
    import compute_p9 as C9
    K = len(cells["valid98"])
    dev = []
    for k in range(K):
        try:
            items, mats, _ = CG.load_arm({st: [cells[st][k]] for st in DEV}, sets_abs, with_tokens=tokens)
        except Exception:  # noqa: BLE001 - token 원문이 없으면 token 없이
            items, mats, _ = CG.load_arm({st: [cells[st][k]] for st in DEV}, sets_abs, with_tokens=False)
        dev.append((items, mats))
    dev_items = dev[0][0]
    assert all(d[0] == dev_items for d in dev)
    S = lambda f: np.stack([d[1][f] for d in dev], axis=1)  # noqa: E731  items × K
    out = {"dev_items": dev_items, "ok": S("ok"), "U": S("U"), "gen_dev": S("gen_tokens"), "think": S("thinking_tokens")}
    ref, over, routes = defaultdict(list), defaultdict(list), Counter()
    walls, gens, trunc, rows_n = [], [], 0, 0
    for st in OVER:
        for c in cells[st]:
            for i, v in C9.sample_values(c).items():
                exp = gold[st][i].get("expected_outcome", "answered")
                if exp == "answered":
                    over[f"{st}:{i}"].append(float(v["refused"]))
                elif st == "rdev":
                    ref[f"{st}:{i}"].append(float(v["refused"]))
                    if v["route"]:
                        routes[v["route"]] += 1
            d = json.loads((ROOT / c).read_text(encoding="utf-8"))
            for r in d["rows"]:
                rows_n += 1
                if r.get("started_at") and r.get("finished_at"):
                    walls.append(_ts(r["finished_at"]) - _ts(r["started_at"]))
                hc = r.get("hf_calls") or []
                gens.append(sum(x.get("generated_tokens") or 0 for x in hc))
                trunc += sum(1 for x in hc if x.get("finish_reason") == "length")
    out["ref_ids"], out["over_ids"] = sorted(ref), sorted(over)
    out["ref"] = np.array([np.mean(ref[i]) for i in out["ref_ids"]])
    out["over"] = np.array([np.mean(over[i]) for i in out["over_ids"]])
    out["routes"] = dict(routes)
    th = out["think"]
    out["speed"] = {"rows": rows_n, "wall_p50_s": round(float(np.percentile(walls, 50)), 2), "wall_p95_s": round(float(np.percentile(walls, 95)), 2),
                    "gen_tokens_mean": round(float(np.mean(gens)), 1), "gen_tokens_p50": float(np.percentile(gens, 50)),
                    "thinking_tokens_dev_mean": None if np.all(np.isnan(th)) else round(float(np.nanmean(th)), 1),
                    "truncated_calls": trunc}
    return out


def values(o):
    return {"dev_ok": float(o["ok"].mean()), "ref": float(o["ref"].mean()), "over": float(o["over"].mean()), "U_rate": float(o["U"].mean()),
            "U_samples": int(round(float(o["U"].sum())))}


ITEM_VEC = {"dev_ok": lambda o: o["ok"].mean(axis=1), "ref": lambda o: o["ref"], "over": lambda o: o["over"], "U_rate": lambda o: o["U"].mean(axis=1)}


def boot_paired(arm, a0, rng):
    D = np.stack(arm) - np.stack(a0)  # S × I
    S, I = D.shape
    stats = np.empty(REPS)
    for r in range(REPS):
        si = rng.integers(0, S, S)
        ii = rng.integers(0, I, I)
        stats[r] = D[np.ix_(si, ii)].mean()
    return float(D.mean()), [float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))]


def boot_soup(soup, seeds, rng):
    X = np.stack(seeds)  # S × I
    S, I = X.shape
    stats = np.empty(REPS)
    for r in range(REPS):
        si = rng.integers(0, S, S)
        ii = rng.integers(0, I, I)
        stats[r] = soup[ii].mean() - X[np.ix_(si, ii)].mean()
    return float(soup.mean() - X.mean()), [float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))]


def anova2(Y):
    """Y: S × I × K → 분산 성분(ANOVA 추정, 음수는 0으로 적고 원값도 남김)."""
    S, I, K = Y.shape
    g = Y.mean()
    ms = Y.mean(axis=(1, 2))
    mi = Y.mean(axis=(0, 2))
    msi = Y.mean(axis=2)
    MSs = I * K * ((ms - g) ** 2).sum() / (S - 1)
    MSi = S * K * ((mi - g) ** 2).sum() / (I - 1)
    MSsi = K * ((msi - ms[:, None] - mi[None, :] + g) ** 2).sum() / ((S - 1) * (I - 1))
    MSe = ((Y - msi[:, :, None]) ** 2).sum() / (S * I * (K - 1))
    comp = {"sampling": MSe, "seed_x_item": (MSsi - MSe) / K, "seed": (MSs - MSsi) / (I * K), "item": (MSi - MSsi) / (S * K)}
    tot = sum(max(0.0, v) for v in comp.values())
    return {"S": S, "I": I, "K": K, "components_raw": {k: float(v) for k, v in comp.items()},
            "share_pct": {k: round(100 * max(0.0, v) / tot, 2) for k, v in comp.items()},
            "sd_of_model_mean_pp": {"seed": pp(np.sqrt(max(0.0, comp["seed"]))), "seed_x_item_over_items": pp(np.sqrt(max(0.0, comp["seed_x_item"]) / I)),
                                    "sampling_over_items_k": pp(np.sqrt(max(0.0, comp["sampling"]) / (I * K)))}}


def anova1(Y):
    I, K = Y.shape
    mi = Y.mean(axis=1)
    MSi = K * ((mi - Y.mean()) ** 2).sum() / (I - 1)
    MSe = ((Y - mi[:, None]) ** 2).sum() / (I * (K - 1))
    return {"I": I, "K": K, "item": float((MSi - MSe) / K), "sampling": float(MSe), "sd_of_model_mean_pp_sampling": pp(np.sqrt(MSe / (I * K)))}


def signature(item):
    calls = item.get("gold") or []
    tool, tu, rg = XT.classify(calls)
    return f"{tool}|{tu}|{rg}"


def client10k():
    ct = ROOT / "sft_dpo_inventory/client_test_10000"
    import evaluate_vendor100 as EV
    gold = {i["id"]: i for i in EV.load_gold(ct / "qa_test_10000.yaml")["items"]}

    def load(pat):
        out = {}
        for c in range(1, 6):
            for r in json.loads((ct / "cells" / pat.format(c=c)).read_text(encoding="utf-8"))["rows"]:
                out[r["id"]] = r.get("category") == "match"
        return out
    v4 = {s: load(f"ct10k_v4_{s}_c{{c}}_s1.json") for s in OLD_SEEDS}
    base = {k: load(f"ct10k_base_c{{c}}_s{k}.json") for k in (1, 2, 3)}
    ids = sorted(gold)

    def disagree(a, b):
        return round(100 * sum(a[i] != b[i] for i in ids) / len(ids), 2)
    tg = defaultdict(list)
    for i in ids:
        tg[gold[i]["template_group"]].append(i)
    rows = []
    for g, its in tg.items():
        if len(its) < 30:
            continue
        acc = {s: 100 * np.mean([v4[s][i] for i in its]) for s in OLD_SEEDS}
        bacc = 100 * np.mean([base[k][i] for k in base for i in its])
        rows.append({"template_group": g, "items": len(its), "v4_by_seed_pct": {s: round(v, 1) for s, v in acc.items()}, "range_pp": round(max(acc.values()) - min(acc.values()), 1),
                     "base_mean_pct": round(float(bacc), 1), "example": gold[its[0]]["question"]})
    rows.sort(key=lambda r: (-r["range_pp"], -r["items"]))
    return {"note": "기존 셀(새 측정 아님), 10,000문항 k=1",
            "v4_acc_pct": {s: round(100 * np.mean(list(v4[s].values())), 2) for s in OLD_SEEDS},
            "base_acc_pct": {k: round(100 * np.mean(list(base[k].values())), 2) for k in base},
            "item_disagreement_pct": {"v4_seed_pairs": {f"{a}-{b}": disagree(v4[a], v4[b]) for a, b in (("o43", "o1016"), ("o43", "o7"), ("o1016", "o7"))},
                                      "base_round_pairs": {f"k{a}-k{b}": disagree(base[a], base[b]) for a, b in ((1, 2), (1, 3), (2, 3))}},
            "template_group_top20": rows[:20], "template_groups_ge30": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    import robust_scoring
    robust_scoring.patch()
    import evaluate_vendor100 as EV
    sets_abs = dict(SETS)
    gold = {st: {i["id"]: i for i in EV.load_gold(ROOT / g)["items"]} for st, g in SETS.items()}
    table = model_table(a.smoke)
    loaded, missing = {}, []
    for name, spec in table.items():
        if not present(spec["cells"]):
            missing.append(name)
            continue
        loaded[name] = load_model(spec["cells"], sets_abs, gold, spec["tokens"])
        print("loaded", name, {k: pp(v) if k != "U_samples" else v for k, v in values(loaded[name]).items()}, flush=True)
    ref_ids = {tuple(o["ref_ids"]) for o in loaded.values()}
    over_ids = {tuple(o["over_ids"]) for o in loaded.values()}
    dev_ids = {tuple(o["dev_items"]) for o in loaded.values()}
    assert len(ref_ids) == len(over_ids) == len(dev_ids) == 1, "cells cover different items"
    res = {"note": "진단, 판정 아님. E1(refusal_dev v2·valid98·aux)은 V4 선택에 이미 쓴 셋이다. E2 없음(30k 원천 없음).",
           "smoke": a.smoke, "items": {"dev": len(next(iter(dev_ids))), "ref": len(next(iter(ref_ids))), "over": len(next(iter(over_ids)))},
           "missing_models": missing, "models": {}}
    for name, o in loaded.items():
        res["models"][name] = {"group": table[name]["group"], "seed": table[name]["seed"], **{k: (pp(v) if k != "U_samples" else v) for k, v in values(o).items()},
                               "routes": o["routes"], "speed": o["speed"], "k": int(o["ok"].shape[1])}
    # 1. arm − A0
    comps = {}
    for arm in ("A1", "A2", "A3"):
        seeds = [s for s in (OLD_SEEDS if a.smoke else NEW_SEEDS) if f"{arm}_{s}" in loaded and f"A0_{s}" in loaded]
        if not seeds:
            continue
        c = {"seed_pairs": seeds}
        for met, f in ITEM_VEC.items():
            point, ci = boot_paired([f(loaded[f"{arm}_{s}"]) for s in seeds], [f(loaded[f"A0_{s}"]) for s in seeds], np.random.default_rng(RNG_SEED))
            c[met] = {"diff_pp": pp(point), "ci95_pp": [pp(ci[0]), pp(ci[1])],
                      "arm_pct": pp(np.mean([f(loaded[f"{arm}_{s}"]).mean() for s in seeds])), "a0_pct": pp(np.mean([f(loaded[f"A0_{s}"]).mean() for s in seeds])),
                      "per_seed_diff_pp": {s: pp(f(loaded[f"{arm}_{s}"]).mean() - f(loaded[f"A0_{s}"]).mean()) for s in seeds}}
        sp = lambda n, k: np.mean([loaded[f"{n}_{s}"]["speed"][k] for s in seeds if loaded[f"{n}_{s}"]["speed"][k] is not None])  # noqa: E731
        c["speed"] = {k: {"arm": round(float(sp(arm, k)), 2), "a0": round(float(sp("A0", k)), 2)} for k in ("wall_p50_s", "wall_p95_s", "gen_tokens_mean", "thinking_tokens_dev_mean", "truncated_calls")}
        c["U_samples"] = {"arm": [values(loaded[f"{arm}_{s}"])["U_samples"] for s in seeds], "a0": [values(loaded[f"A0_{s}"])["U_samples"] for s in seeds]}
        comps[f"{arm}-A0"] = c
    res["arm_vs_A0"] = comps
    # 2. 순서 편차
    v4names = [f"V4_{s}" for s in OLD_SEEDS] + ([] if a.smoke else [f"A0_{s}" for s in NEW_SEEDS])
    v4names = [n for n in v4names if n in loaded]
    spread = {}
    for met in ("dev_ok", "ref", "over"):
        vals = [values(loaded[n])[met] for n in v4names]
        spread[met] = {"by_seed_pct": {n: pp(v) for n, v in zip(v4names, vals)}, "mean_pct": pp(np.mean(vals)), "sd_pp": pp(np.std(vals, ddof=1)) if len(vals) > 1 else None,
                       "range_pp": [pp(min(vals)), pp(max(vals))]}
    res["order_spread_v4"] = {"seeds": v4names, "metrics": spread,
                              "variance_dev_ok": anova2(np.stack([loaded[n]["ok"] for n in v4names])) if len(v4names) > 1 else None,
                              "variance_base_dev_ok": anova1(loaded["base"]["ok"]) if "base" in loaded else None}
    # 3. 유형 칸
    dev_list = list(next(iter(dev_ids)))
    sig = {}
    for key in dev_list:
        st, i = key.split("/", 1)
        sig[key] = signature(gold[st][i])
    groups = defaultdict(list)
    for x, key in enumerate(dev_list):
        groups[sig[key]].append(x)
    trows = []
    for gname, idx in groups.items():
        if len(idx) < MIN_GROUP:
            continue
        acc = {n: pp(loaded[n]["ok"][idx].mean()) for n in v4names}
        trows.append({"signature": gname, "items": len(idx), "by_seed_pct": acc, "range_pp": round(max(acc.values()) - min(acc.values()), 2)})
    trows.sort(key=lambda r: (-r["range_pp"], -r["items"]))
    weak = {}
    for wname, cond in (("billing_with_place", lambda it: XT.classify(it.get("gold"))[0] == "get_billing_metrics" and XT.classify(it.get("gold"))[2] != "없음"),
                        ("od_pickup_dropoff", lambda it: any(k in ((c.get("args") or {})) for c in (it.get("gold") or []) for k in ("scope_pickup", "scope_dropoff")))):
        idx = [x for x, key in enumerate(dev_list) if cond(gold[key.split("/", 1)[0]][key.split("/", 1)[1]])]
        weak[wname] = {"items": len(idx), "by_seed_pct": {n: pp(loaded[n]["ok"][idx].mean()) if idx else None for n in v4names}}
    res["type_cells"] = {"definition": f"정답 호출 서명 = 분석 tool | 시간 단위 | 지역 유형(xtab_a11 분류), 문항 {MIN_GROUP}개 이상 칸", "groups": len(groups),
                         "groups_ge_min": sum(1 for v in groups.values() if len(v) >= MIN_GROUP),
                         "top20_by_v4_seed_range": trows[:20], "o43_weak_subsets": weak}
    if not a.smoke:
        res["client10k_supplement"] = client10k()
    # 4. soup
    if "soup" in loaded and v4names:
        sv = {}
        for met, f in ITEM_VEC.items():
            point, ci = boot_soup(f(loaded["soup"]), [f(loaded[n]) for n in v4names], np.random.default_rng(RNG_SEED))
            per = [f(loaded[n]).mean() for n in v4names]
            sv[met] = {"soup_pct": pp(f(loaded["soup"]).mean()), "v4_mean_pct": pp(np.mean(per)), "v4_min_pct": pp(min(per)), "v4_max_pct": pp(max(per)),
                       "soup_minus_mean_pp": pp(point), "ci95_pp": [pp(ci[0]), pp(ci[1])]}
        res["soup"] = sv
    # 5. 과잉 거부 교차표
    xt = {}
    for grp in (["A0", "A1", "A2", "A3"] if not a.smoke else ["A0", "A1"]) + (["soup"] if "soup" in loaded else []) + ["V4_old"]:
        names = [n for n in loaded if table[n]["group"] == grp]
        if names:
            cells = defaultdict(list)
            for n in names:
                for st in OVER:
                    cells[st] += table[n]["cells"][st]
            xt[grp] = XT.xtab(cells, gold) | {"models": names}
    res["overrefusal_xtab"] = xt
    out = Path(a.out) if a.out else HERE / ("smoke_a11.json" if a.smoke else "results_a11.json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"arm_vs_A0": {k: {m: v[m] for m in ("dev_ok", "ref", "over", "U_rate")} for k, v in comps.items()},
                      "order_spread": {m: (v["mean_pct"], v["sd_pp"], v["range_pp"]) for m, v in spread.items()}, "missing": missing}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
