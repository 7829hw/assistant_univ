# -*- coding: utf-8 -*-
"""Topic 2 analysis (decision 264). Diagnostic, not a verdict. No model calls. Rules are fixed in ../PLAN.md BEFORE any B result exists.

    runtime/envs/hf/bin/python topic2_semantic_order/analysis/analyze_t2.py --smoke   # A-only reproduction of earlier numbers + tool test (B := A) -> analysis/smoke_t2.json
    runtime/envs/hf/bin/python topic2_semantic_order/analysis/analyze_t2.py           # -> analysis/results_t2.json, tables/*.csv, tables/summary.md

Reads only cell files (match = row.category == "match", as in ablation_012/013 tools) and the CT10K / H-dev gold files. H-final is never opened.
Reuses the frozen ablation_013 tool code for E1 vectors (CORE.load_model, A12.e1_vectors, A12.compare) and the T1-T5 signature (analyze_a13.tsig).
Hierarchical bootstrap: resample the seed pairs, then template_group clusters (items follow their cluster), same resample for A and B; 10,000 replicates, default_rng(20261108).
"""
import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
T2 = HERE.parent
ROOT = T2.parent
A13A = ROOT / "sft_dpo_inventory/ablation_013/analysis"
sys.path.insert(0, str(A13A))
sys.path.insert(0, str(T2))
import core_a11copy as CORE  # noqa: E402  (frozen tool; also puts the pilot gate dirs on sys.path)
import analyze_a12 as A12  # noqa: E402
import analyze_a13 as A13  # noqa: E402
import semantic_schedule as SS  # noqa: E402

SEEDS = ["o1102", "o211102", "o2026113", "o2026117", "o2026131"]
OLD_V4 = ["o43", "o1016", "o7"]
REPS, RNG_SEED = 10000, 20261108
MIN_CT, MIN_HD = 30, 20
COLLAPSE = (0.20, 0.30)
NONINF = -2.0
CT = "sft_dpo_inventory/client_test_10000/qa_test_10000.yaml"
HDEV = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
assert "h_final" not in CT + HDEV
C12, C13, C2, CB = ("sft_dpo_inventory/ablation_012/cells", "sft_dpo_inventory/ablation_013/cells", "topic2_semantic_order/cells", "sft_dpo_inventory/client_test_10000/cells")


def pp(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(100 * float(x), 2)


# ---------------- paths ----------------
def ct_paths(arm, s):
    if arm == "A":
        d = C12 if s in ("o1102", "o211102", "o2026113") else C2
        pre = "ct10k_a0_" if d == C12 else "ct10k_t2_a0_"
        return [f"{d}/{pre}{s}_c{c}_s1.json" for c in range(1, 6)]
    if arm == "B":
        return [f"{C2}/ct10k_t2_b_{s}_c{c}_s1.json" for c in range(1, 6)]
    if arm == "V4old":
        return [f"{CB}/ct10k_v4_{s}_c{c}_s1.json" for c in range(1, 6)]
    raise ValueError(arm)


def ct_base_paths():
    return [[f"{CB}/ct10k_base_c{c}_s{k}.json" for c in range(1, 6)] for k in (1, 2, 3)]


def hd_path(arm, s):
    if arm == "A":
        return f"{C12 if s in ('o1102', 'o211102', 'o2026113') else C13}/hdev_a0_{s}_s1.json"
    if arm == "B":
        return f"{C2}/hdev_t2_b_{s}_s1.json"
    raise ValueError(arm)


def e1_cells(arm, s):
    lab = {"valid98": "valid98", "aux": "aux", "rdev": "rdevv2"}
    if arm == "A":
        if s in ("o1102", "o211102", "o2026113"):
            return CORE.new_cells(f"a11_a0_{s}")
        return {st: [f"{C13}/a13_a0_{s}_{lab[st]}_s{k}.json" for k in range(1, 5)] for st in CORE.SETS}
    return {st: [f"{C2}/t2_b_{s}_{lab[st]}_s{k}.json" for k in range(1, 5)] for st in CORE.SETS}


def exists(paths):
    return all((ROOT / p).exists() for p in paths)


# ---------------- loading ----------------
def load_rows(paths):
    out, walls, trunc, calls = {}, [], 0, 0
    for p in paths:
        d = json.loads((ROOT / p).read_text(encoding="utf-8"))
        for r in d["rows"]:
            out[r["id"]] = r.get("category")
            if r.get("started_at") and r.get("finished_at"):
                walls.append(A12._ts(r["finished_at"]) - A12._ts(r["started_at"]))
            for x in r.get("hf_calls") or []:
                calls += 1
                trunc += x.get("finish_reason") == "length"
    return {"cat": out, "wall_p50": float(np.percentile(walls, 50)) if walls else None, "wall_p95": float(np.percentile(walls, 95)) if walls else None,
            "trunc_rate": trunc / calls if calls else None}


def vec(model, ids, cls="match"):
    return np.array([float(model["cat"][i] == cls) for i in ids])


# ---------------- signatures from the gold calls of the EVALUATION item (describes the question, never model output) ----------------
def esig(calls):
    calls = calls or []
    an = next((c for c in calls if c.get("tool") != "get_place_scope"), {})
    a = an.get("args") or {}
    tool = an.get("tool", "none")
    metric = a.get("metric") or {"get_trip_count": "trip_count", "get_passage_count": "passage_count", "get_scope_name": "place"}.get(tool, "none")
    agg = str(a.get("aggregation") or "none") + (f"/{a['rollup']}" if a.get("rollup") else "")
    unit = str(a.get("bucket") or SS._date_unit(a.get("date")))
    vic = any((c.get("args") or {}).get("include_vicinity") for c in calls if c.get("tool") == "get_place_scope")
    regs = [SS._name_region_type((c.get("args") or {}).get("name", ""), vic) for c in calls if c.get("tool") == "get_place_scope"]
    region = next((r for r in ("poi", "dong", "district", "province") if r in regs), "none")
    od = [r for r, k in (("pickup", "scope_pickup"), ("dropoff", "scope_dropoff")) if a.get(k)]
    od = "+".join(od) if od else "none"
    if a.get("dimension_target"):
        od += f">{a['dimension_target']}"
    coarse = f"{tool}|{metric}"
    return coarse, f"{coarse}|agg={agg}|t={unit}|reg={region}|od={od}"


# ---------------- group tables and hierarchical bootstrap ----------------
class Tab:
    """cluster x group tables for fast resampling."""

    def __init__(self, ids, group_of, cluster_of, min_size):
        cnt = Counter(group_of[i] for i in ids)
        self.groups = sorted(g for g, n in cnt.items() if n >= min_size)
        self.small = {g: n for g, n in cnt.items() if n < min_size}
        self.gi = {g: k for k, g in enumerate(self.groups)}
        self.clusters = sorted({cluster_of[i] for i in ids})
        ci = {c: k for k, c in enumerate(self.clusters)}
        self.idx = [(ci[cluster_of[i]], self.gi.get(group_of[i])) for i in ids]
        K, G = len(self.clusters), len(self.groups)
        self.K, self.G = K, G
        self.ids = ids
        self.N = np.zeros((K, G))
        self.itemN = np.zeros(K)  # all items per cluster (overall accuracy uses every item)
        for k, g in self.idx:
            self.itemN[k] += 1
            if g is not None:
                self.N[k, g] += 1
        self.sizes = np.array([cnt[g] for g in self.groups])

    def sums(self, y):
        M = np.zeros((self.K, self.G))
        tot = np.zeros(self.K)
        for (k, g), v in zip(self.idx, y):
            tot[k] += v
            if g is not None:
                M[k, g] += v
        return M, tot


def per_group_metrics(Ms, base_acc, N, c, sidx, tots, itemN, extra=None):
    """Ms: list over seeds of K x G match sums. Returns dict of metrics for the chosen seed indices under cluster weights c."""
    den = c @ N
    ok = den > 0
    accs = np.array([(c @ Ms[s])[ok] / den[ok] for s in sidx])  # S x G'
    base = base_acc[ok]
    nlow = max(1, math.ceil(0.10 * accs.shape[1]))
    worst = accs.min(axis=1)
    low10 = np.sort(accs, axis=1)[:, :nlow].mean(axis=1)
    out = {"worst": worst.mean(), "low10": low10.mean()}
    for t in COLLAPSE:
        out[f"collapse{int(t * 100)}"] = (accs < base[None, :] - t).sum(axis=1).mean()
    out["group_var"] = accs.var(axis=0, ddof=1).mean() if len(sidx) > 1 else 0.0
    overall = np.array([(c @ tots[s]) / (c @ itemN) for s in sidx])
    out["overall"] = overall.mean()
    out["overall_sd"] = overall.std(ddof=1) if len(sidx) > 1 else 0.0
    out["overall_range"] = overall.max() - overall.min()
    return out, accs


def hier_boot(tab, A_vecs, B_vecs, base_vec, reps=None, seed=RNG_SEED, seeds_fixed=False):
    """Paired hierarchical bootstrap of B - A for every metric. A_vecs/B_vecs: lists (same seed order) of item match vectors."""
    reps = REPS if reps is None else reps
    MA, TA = zip(*[tab.sums(v) for v in A_vecs])
    MB, TB = zip(*[tab.sums(v) for v in B_vecs])
    Mb, Tb = tab.sums(base_vec)
    S = len(A_vecs)
    c1 = np.ones(tab.K)
    base_acc1 = (c1 @ Mb) / (c1 @ tab.N)

    def one(c, sidx):
        bd = c @ tab.N
        okb = bd > 0
        base_acc = np.where(okb, (c @ Mb) / np.where(okb, bd, 1), 0.0)
        a, _ = per_group_metrics(MA, base_acc, tab.N, c, sidx, TA, tab.itemN)
        b, _ = per_group_metrics(MB, base_acc, tab.N, c, sidx, TB, tab.itemN)
        return a, b

    all_idx = list(range(S))
    a0, b0 = one(c1, all_idx)
    rng = np.random.default_rng(seed)
    keys = list(a0)
    diffs = {k: [] for k in keys}
    aa = {k: [] for k in keys}
    bb = {k: [] for k in keys}
    for _ in range(reps):
        sidx = all_idx if seeds_fixed else list(rng.integers(0, S, S))
        c = rng.multinomial(tab.K, np.full(tab.K, 1.0 / tab.K)).astype(float)
        a, b = one(c, sidx)
        for k in keys:
            diffs[k].append(b[k] - a[k])
            aa[k].append(a[k])
            bb[k].append(b[k])
    res = {}
    for k in keys:
        d = np.array(diffs[k])
        lo, hi = np.percentile(d, [2.5, 97.5])
        res[k] = {"A": a0[k], "B": b0[k], "diff": b0[k] - a0[k], "ci95": [float(lo), float(hi)], "p_B_better_or_equal": None}
    return res, base_acc1


def seed_table(tab, vecs, base_vec, names):
    Mb, Tb = tab.sums(base_vec)
    base_acc = (np.ones(tab.K) @ Mb) / (np.ones(tab.K) @ tab.N)
    rows = {}
    for n, v in zip(names, vecs):
        M, T = tab.sums(v)
        m, accs = per_group_metrics([M], base_acc, tab.N, np.ones(tab.K), [0], [T], tab.itemN)
        rows[n] = {**{k: float(x) for k, x in m.items() if k not in ("group_var", "overall_sd", "overall_range")}, "acc_by_group": accs[0].tolist()}
    return rows, base_acc


# ---------------- main ----------------
def load_gold(path):
    import robust_scoring
    robust_scoring.patch()
    import evaluate_vendor100 as EV
    return {i["id"]: i for i in EV.load_gold(ROOT / path)["items"]}


PCT = {"worst", "low10", "overall", "overall_sd", "overall_range"}


def conv(k, r):
    f = pp if k in PCT else (lambda x: round(float(x), 4))
    return {"A": f(r["A"]), "B": f(r["B"]), "diff": f(r["diff"]), "ci95": [f(x) for x in r["ci95"]], "unit": "pp" if k in PCT else "count_or_variance"}


def dataset_block(name, gold, min_size, arm_models, base_models, seeds, grouping_name, group_of, cluster_of, detail=False):
    ids = sorted(gold)
    A = [vec(arm_models["A"][s], ids) for s in seeds]
    B = [vec(arm_models["B"][s], ids) for s in seeds]
    base = np.mean([vec(m, ids) for m in base_models], axis=0)
    tab = Tab(ids, group_of, cluster_of, min_size)
    res, base_acc = hier_boot(tab, A, B, base)
    fixed, _ = hier_boot(tab, A, B, base, reps=2000, seed=RNG_SEED + 1, seeds_fixed=True)
    persA, _ = seed_table(tab, A, base, seeds)
    persB, _ = seed_table(tab, B, base, seeds)
    out = {"dataset": name, "grouping": grouping_name, "min_group_items": min_size, "groups_used": tab.G, "small_groups_excluded": len(tab.small),
           "items_in_small_groups": int(sum(tab.small.values())), "clusters": tab.K, "seeds": list(seeds), "reps": REPS,
           "paired_hier_bootstrap": {k: conv(k, r) for k, r in res.items()},
           "per_seed": {"A": {s: {k: (pp(v) if k in ("worst", "low10", "overall") else v) for k, v in persA[s].items() if k != "acc_by_group"} for s in seeds},
                        "B": {s: {k: (pp(v) if k in ("worst", "low10", "overall") else v) for k, v in persB[s].items() if k != "acc_by_group"} for s in seeds}}}
    if detail:
        rows = []
        for gi, g in enumerate(tab.groups):
            a = [persA[s]["acc_by_group"][gi] for s in seeds]
            b = [persB[s]["acc_by_group"][gi] for s in seeds]
            rows.append({"group": g, "items": int(tab.sizes[gi]), "base_pct": pp(base_acc[gi]), "A_mean_pct": pp(np.mean(a)), "B_mean_pct": pp(np.mean(b)),
                         "diff_pp": pp(np.mean(b) - np.mean(a)), "A_min_pct": pp(min(a)), "B_min_pct": pp(min(b)), "A_sd_pp": pp(np.std(a, ddof=1)), "B_sd_pp": pp(np.std(b, ddof=1)),
                         "A_collapse20_seeds": int(sum(x < base_acc[gi] - 0.2 for x in a)), "B_collapse20_seeds": int(sum(x < base_acc[gi] - 0.2 for x in b))})
        out["group_table"] = rows
    return out


def category_secondary(ids, models_by_arm, seeds):
    out = {}
    for arm in ("A", "B"):
        rows = []
        for s in seeds:
            m = models_by_arm[arm][s]
            n = len(ids)
            cats = Counter(m["cat"][i] for i in ids)
            rows.append({"seed": s, "overall": pp(cats["match"] / n), "silent_wrong(answered_mismatch)": pp(cats["answered_mismatch"] / n), "tool_failure(failed)": pp(cats["failed"] / n),
                         "refusal(refused_unsupported)": pp(cats["refused_unsupported"] / n), "wall_p50_s": m["wall_p50"], "wall_p95_s": m["wall_p95"], "truncation_rate": m["trunc_rate"]})
        out[arm] = rows
    return out


def t_split(ids, tsig_of, models_by_arm, seeds):
    out = {}
    for t in ("T1", "T5"):
        mk = np.array([tsig_of[i] == t for i in ids])
        if mk.sum() == 0:
            continue
        d = {"items": int(mk.sum())}
        for arm in ("A", "B"):
            d[arm] = {s: pp(vec(models_by_arm[arm][s], ids)[mk].mean()) for s in seeds}
        d["A_mean"], d["B_mean"] = pp(np.mean([vec(models_by_arm["A"][s], ids)[mk].mean() for s in seeds])), pp(np.mean([vec(models_by_arm["B"][s], ids)[mk].mean() for s in seeds]))
        d["A_sd_pp"] = pp(np.std([vec(models_by_arm["A"][s], ids)[mk].mean() for s in seeds], ddof=1))
        d["B_sd_pp"] = pp(np.std([vec(models_by_arm["B"][s], ids)[mk].mean() for s in seeds], ddof=1))
        out[t] = d
    return out


def reproduction_check(res_out):
    """A-only: reproduce results_a12.ct10k_seed_consistency (overall acc, base mean, 95 groups, collapse counts per seed)."""
    ref = json.loads((ROOT / "sft_dpo_inventory/ablation_012/analysis/results_a12.json").read_text(encoding="utf-8"))["ct10k_seed_consistency"]
    gold = load_gold(CT)
    ids = sorted(gold)
    tg = {i: gold[i]["template_group"] for i in ids}
    base_models = [load_rows(list(grp)) for grp in ct_base_paths()]
    base = np.mean([vec(m, ids) for m in base_models], axis=0)
    tab = Tab(ids, tg, tg, 30)
    rows = {}
    for key, arm, s in (("o43", "V4old", "o43"), ("o1016", "V4old", "o1016"), ("o7", "V4old", "o7"), ("a0_o1102", "A", "o1102"), ("a0_o211102", "A", "o211102"), ("a0_o2026113", "A", "o2026113")):
        m = load_rows(ct_paths(arm, s))
        v = vec(m, ids)
        M, T = tab.sums(v)
        Mb, _ = tab.sums(base)
        base_acc = (np.ones(tab.K) @ Mb) / (np.ones(tab.K) @ tab.N)
        acc = (np.ones(tab.K) @ M) / (np.ones(tab.K) @ tab.N)
        rows[key] = {"overall_pct": round(100 * v.mean(), 2), "collapse20": int((acc < base_acc - 0.20).sum()),
                     "ref_overall": ref["acc_pct"][key], "ref_collapse20": ref["collapse_count_by_seed"][key]}
    ok = all(r["overall_pct"] == r["ref_overall"] and r["collapse20"] == r["ref_collapse20"] for r in rows.values()) and tab.G == ref["groups_ge_min"]
    return {"ok": bool(ok), "groups_ge30": tab.G, "ref_groups": ref["groups_ge_min"], "base_mean_pct": round(100 * base.mean(), 2), "ref_base_mean_pct": ref["base_mean_pct"], "per_model": rows}


def main():
    global REPS
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    REPS = a.reps
    out = {"note": "Diagnostic, not a verdict. Decision 264. H-final never opened. Criteria fixed in PLAN.md before any B result.", "smoke": a.smoke, "missing": []}
    if a.smoke:
        out["reproduction_of_ablation_012_ct10k"] = reproduction_check(out)
        print("reproduction:", out["reproduction_of_ablation_012_ct10k"]["ok"], flush=True)
    # ---------- CT10K ----------
    gold = load_gold(CT)
    ids = sorted(gold)
    tg = {i: gold[i]["template_group"] for i in ids}
    sem = {i: esig(gold[i].get("gold")) for i in ids}
    base_ct = [load_rows(list(grp)) for grp in ct_base_paths()]
    seeds_ct = [s for s in SEEDS if exists(ct_paths("A", s)) and (a.smoke or exists(ct_paths("B", s)))]
    for s in SEEDS:
        for arm in ("A", "B"):
            if not exists(ct_paths(arm, s)) and not (a.smoke and arm == "B"):
                out["missing"].append(f"CT10K:{arm}:{s}")
    out["ct10k_seeds_complete"] = seeds_ct
    if len(seeds_ct) >= 2:
        models = {"A": {s: load_rows(ct_paths("A", s)) for s in seeds_ct}}
        models["B"] = models["A"] if a.smoke else {s: load_rows(ct_paths("B", s)) for s in seeds_ct}
        out["ct10k"] = {}
        for gname, gof in (("semantic_fine", {i: sem[i][1] for i in ids}), ("template_group", tg), ("semantic_coarse", {i: sem[i][0] for i in ids})):
            blk = dataset_block("CT10K", gold, MIN_CT, models, base_ct, seeds_ct, gname, gof, tg, detail=True)
            out["ct10k"][gname] = blk
            print("CT10K", gname, "groups", blk["groups_used"], {k: blk["paired_hier_bootstrap"][k]["diff"] for k in ("worst", "overall", "collapse20")}, flush=True)
        out["ct10k_secondary"] = category_secondary(ids, models, seeds_ct)
        tsg = {i: A13.tsig(gold[i].get("gold")) for i in ids}
        out["ct10k_T1_T5"] = t_split(ids, tsg, models, seeds_ct)
        # S1-S4 (PLAN.md) on semantic_fine
        b = out["ct10k"]["semantic_fine"]["paired_hier_bootstrap"]
        s1 = b["worst"]["diff"] > 0 and b["worst"]["ci95"][0] > 0
        s2 = b["collapse20"]["B"] < b["collapse20"]["A"] and b["collapse20"]["ci95"][1] < 0
        s3 = b["overall_sd"]["B"] < b["overall_sd"]["A"] and b["group_var"]["B"] < b["group_var"]["A"]
        s4 = b["overall"]["ci95"][0] > NONINF
        out["criteria_S1_S4"] = {"S1_worst_group": bool(s1), "S2_collapse20_fewer": bool(s2), "S3_seed_spread_smaller_point_estimates": bool(s3), "S4_overall_noninferior_-2pp": bool(s4),
                                 "H1_supported": bool(s1 and s2 and s3 and s4), "seeds_used": seeds_ct, "grouping": "semantic_fine, CT10K, min 30"}
    # ---------- H-dev ----------
    gh = load_gold(HDEV)
    hid = sorted(gh)
    seeds_h = [s for s in SEEDS if exists([hd_path("A", s)]) and (a.smoke or exists([hd_path("B", s)]))]
    out["hdev_seeds_complete"] = seeds_h
    if len(seeds_h) >= 2:
        tgh = {i: gh[i]["template_group"] for i in hid}
        semh = {i: esig(gh[i].get("gold")) for i in hid}
        mh = {"A": {s: load_rows([hd_path("A", s)]) for s in seeds_h}}
        mh["B"] = mh["A"] if a.smoke else {s: load_rows([hd_path("B", s)]) for s in seeds_h}
        base_h = [load_rows([f"{C12}/hdev_base_s{k}.json"]) for k in (1, 2)]
        out["hdev"] = {}
        for gname, gof in (("semantic_fine", {i: semh[i][1] for i in hid}), ("template_group", tgh), ("semantic_coarse", {i: semh[i][0] for i in hid})):
            out["hdev"][gname] = dataset_block("H-dev", gh, MIN_HD, mh, base_h, seeds_h, gname, gof, tgh, detail=True)
        out["hdev_secondary"] = category_secondary(hid, mh, seeds_h)
        out["hdev_T1_T5"] = t_split(hid, {i: A13.tsig(gh[i].get("gold")) for i in hid}, mh, seeds_h)
    # ---------- E1 (secondary; frozen tool functions) ----------
    if not a.smoke:
        import robust_scoring
        robust_scoring.patch()
        import evaluate_vendor100 as EV
        gold_e1 = {st: {i["id"]: i for i in EV.load_gold(ROOT / g)["items"]} for st, g in CORE.SETS.items()}
        X, Y, es = {}, {}, []
        for s in SEEDS:
            ca, cb = e1_cells("A", s), e1_cells("B", s)
            if not (exists([p for v in ca.values() for p in v]) and exists([p for v in cb.values() for p in v])):
                out["missing"].append(f"E1:{s}")
                continue
            X[s] = A12.e1_vectors(CORE.load_model(cb, dict(CORE.SETS), gold_e1, False))
            Y[s] = A12.e1_vectors(CORE.load_model(ca, dict(CORE.SETS), gold_e1, False))
            es.append(s)
        if len(es) >= 2:
            out["e1_B_minus_A"] = A12.compare(X, Y, es, list(CORE.ITEM_VEC))
    p = Path(a.out) if a.out else HERE / ("smoke_t2.json" if a.smoke else "results_t2.json")
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n", encoding="utf-8")
    print("wrote", p)


if __name__ == "__main__":
    main()
