"""Stage 3 analysis (frozen BEFORE any new checkpoint was evaluated; PLAN.md section 6).

18 models = 3 order seeds (1102, 211102, 2026131) x 2 arms (A=O4', B=Semantic-balanced) x 3 runs, H-dev 2,000 items, k=1.
Everything here reads H-dev cells only (never CT10K for new models, never H-final). Item type (T1..T5) and semantic groups come from the GOLD calls of the
evaluation items (they describe the question, not model output). `--smoke` uses only the cells that exist and marks the result as incomplete.

Outputs: analysis/variance_results.json, tables/variance_*.csv
"""
import argparse
import csv
import itertools
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.argv_saved = sys.argv
sys.argv = sys.argv[:1]
sys.path.insert(0, str(ROOT / "topic2_semantic_order/analysis"))
import analyze_t2 as T  # noqa: E402  (frozen tool: gold loading, esig, tsig)
import stage1_failure_types as S1  # noqa: E402,F401  (classification rule; same code as Stage 1)
sys.argv = sys.argv_saved

SEEDS = ["o1102", "o211102", "o2026131"]
RUNS = (1, 2, 3)
RNG_SEED = 20261110
REPS = 10000
CELLS_REPRO = "topic2_semantic_order_repro/cells"
T1_COLLAPSE = 50.0  # pp, pre-registered (PLAN 6, Q2)
MIN_GROUP = 20


def path(arm, s, r):
    if r == 1:
        return T.hd_path(arm, s)
    if s == "o2026131" and r == 2:
        return f"topic2_semantic_order/cells/hdev_t2_{'a0' if arm == 'A' else 'b'}_o2026131_r2_s1.json"
    return f"{CELLS_REPRO}/hdev_repro_{'a0' if arm == 'A' else 'b'}_{s}_r{r}_s1.json"


def load_cell(p):
    d = json.loads((T.ROOT / p).read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in d["rows"]}
    return rows


def pct(x):
    return round(100 * float(x), 2)


def anova(y):
    """y[arm][seed] -> list of run values (balanced). Returns table with EMS-based variance components (Arm fixed, Seed random, Arm x Seed random)."""
    A, S = 2, len(SEEDS)
    R = len(y["A"][SEEDS[0]])
    cell = {(a, s): np.array(y[a][s], dtype=float) for a in ("A", "B") for s in SEEDS}
    gm = np.mean([v.mean() for v in cell.values()])
    am = {a: np.mean([cell[(a, s)].mean() for s in SEEDS]) for a in ("A", "B")}
    sm = {s: np.mean([cell[(a, s)].mean() for a in ("A", "B")]) for s in SEEDS}
    ss_a = S * R * sum((am[a] - gm) ** 2 for a in am)
    ss_s = A * R * sum((sm[s] - gm) ** 2 for s in sm)
    ss_as = R * sum((cell[(a, s)].mean() - am[a] - sm[s] + gm) ** 2 for a in am for s in sm)
    ss_e = sum(((v - v.mean()) ** 2).sum() for v in cell.values())
    df = {"arm": A - 1, "seed": S - 1, "arm_x_seed": (A - 1) * (S - 1), "resid": A * S * (R - 1)}
    ms = {"arm": ss_a / df["arm"], "seed": ss_s / df["seed"], "arm_x_seed": ss_as / df["arm_x_seed"], "resid": ss_e / df["resid"]}
    comp = {"resid": ms["resid"], "arm_x_seed": (ms["arm_x_seed"] - ms["resid"]) / R, "seed": (ms["seed"] - ms["resid"]) / (A * R)}
    comp_raw = dict(comp)
    comp = {k: max(0.0, v) for k, v in comp.items()}
    return {"df": df, "MS": ms, "var_components_raw": comp_raw, "var_components_truncated": comp, "sd_components": {k: math.sqrt(v) for k, v in comp.items()},
            "arm_effect_B_minus_A": am["B"] - am["A"], "note": "3 order seeds only: Seed and Arm x Seed components have 2 df and are very imprecise"}


def metrics_for(rows_by_cell, ids, tmap, sem, groups, base_acc):
    """metrics of one model; rows_by_cell: id->row."""
    ok = np.array([rows_by_cell[i]["category"] == "match" for i in ids], dtype=float)
    out = {"overall": ok.mean()}
    for t in ("T1", "T5"):
        m = np.array([tmap[i] == t for i in ids])
        out[t] = ok[m].mean()
    cat = Counter(rows_by_cell[i]["category"] for i in ids)
    n = len(ids)
    out["refused"] = cat["refused_unsupported"] / n
    out["silent_wrong"] = cat["answered_mismatch"] / n
    out["tool_failure"] = cat["failed"] / n
    calls = [x for i in ids for x in (rows_by_cell[i].get("hf_calls") or [])]
    out["truncation"] = sum(x.get("finish_reason") == "length" for x in calls) / max(1, len(calls))
    accs = np.array([ok[[k for k, i in enumerate(ids) if sem[i] == g]].mean() for g in groups])
    out["worst_group"] = accs.min()
    out["collapse20"] = float((accs < base_acc - 0.2).sum())
    return out, ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="use only existing cells; marks result incomplete")
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--out", default=str(HERE / "variance_results.json"))
    a = ap.parse_args()
    gold = T.load_gold(T.HDEV)
    ids = sorted(gold)
    tmap = {i: T.A13.tsig(gold[i].get("gold")) for i in ids}
    sem = {i: T.esig(gold[i].get("gold"))[1] for i in ids}
    cl = {i: gold[i]["template_group"] for i in ids}
    cnt = Counter(sem.values())
    groups = sorted(g for g, n in cnt.items() if n >= MIN_GROUP)
    base_rows = [T.load_rows([f"{T.C12}/hdev_base_s{k}.json"]) for k in (1, 2)]
    base_ok = np.mean([[m["cat"][i] == "match" for i in ids] for m in base_rows], axis=0)
    base_acc = np.array([base_ok[[k for k, i in enumerate(ids) if sem[i] == g]].mean() for g in groups])

    models, missing = {}, []
    for arm in ("A", "B"):
        for s in SEEDS:
            for r in RUNS:
                p = path(arm, s, r)
                if (T.ROOT / p).exists():
                    models[(arm, s, r)] = p
                else:
                    missing.append(f"{arm}-{s}-r{r}")
    if missing and not a.smoke:
        raise SystemExit(f"missing cells: {missing}")
    M, OK, rows_all = {}, {}, {}
    for k, p in models.items():
        rows = load_cell(p)
        rows_all[k] = rows
        M[k], OK[k] = metrics_for(rows, ids, tmap, sem, groups, base_acc)
    res = {"complete": not missing, "missing": missing, "n_models": len(models), "items": len(ids), "groups_used": len(groups), "t1_items": sum(v == "T1" for v in tmap.values()),
           "t5_items": sum(v == "T5" for v in tmap.values()), "note": "H-dev only; 3 order seeds"}
    # per model table
    table = [{"arm": k[0], "seed": k[1], "run": k[2], **{m: (pct(v) if m not in ("collapse20",) else v) for m, v in M[k].items()}} for k in sorted(models)]
    res["per_model"] = table
    keys = ["overall", "T1", "T5", "worst_group", "collapse20", "refused", "silent_wrong", "tool_failure", "truncation"]
    # cell stats, pooled retraining SD
    cells = {}
    for arm in ("A", "B"):
        for s in SEEDS:
            runs = [r for r in RUNS if (arm, s, r) in M]
            cells[(arm, s)] = {m: [M[(arm, s, r)][m] for r in runs] for m in keys}
    res["cell_means_sd"] = [{"arm": arm, "seed": s, "runs": len(cells[(arm, s)]["overall"]),
                             **{f"{m}_mean": pct(np.mean(v)) if m != "collapse20" else float(np.mean(v)) for m, v in cells[(arm, s)].items() if v},
                             **{f"{m}_sd": (pct(np.std(v, ddof=1)) if m != "collapse20" else float(np.std(v, ddof=1))) if len(v) > 1 else None for m, v in cells[(arm, s)].items() if v}}
                            for arm in ("A", "B") for s in SEEDS]
    pooled = {}
    for m in keys:
        ss = df = 0
        for c in cells.values():
            v = np.array(c[m])
            if len(v) > 1:
                ss += ((v - v.mean()) ** 2).sum()
                df += len(v) - 1
        pooled[m] = (pct(math.sqrt(ss / df)) if m != "collapse20" else math.sqrt(ss / df)) if df else None
    res["Q1_pooled_retraining_sd_pp"] = pooled
    if not missing:
        res["anova"] = {m: anova({a_: {s: cells[(a_, s)][m] for s in SEEDS} for a_ in ("A", "B")}) for m in ("overall", "T1", "T5", "worst_group", "collapse20")}
        for m, v in res["anova"].items():
            f = 1 if m == "collapse20" else 100
            v["arm_effect_B_minus_A"] = v["arm_effect_B_minus_A"] * f
            v["sd_components"] = {k: x * f for k, x in v["sd_components"].items()}
    # Q2: T1 collapse runs
    res["Q2_T1_collapse_runs"] = {f"{arm}-{s}": {"runs": len(cells[(arm, s)]["T1"]), "t1_acc_pct": [pct(x) for x in cells[(arm, s)]["T1"]],
                                                 "collapse_runs(T1<50%)": int(sum(pct(x) < T1_COLLAPSE for x in cells[(arm, s)]["T1"]))} for arm in ("A", "B") for s in SEEDS}
    # item-level disagreement
    dis = defaultdict(list)
    t1m = np.array([tmap[i] == "T1" for i in ids])
    t5m = np.array([tmap[i] == "T5" for i in ids])
    for (a1, s1, r1), (a2, s2, r2) in itertools.combinations(sorted(models), 2):
        d = OK[(a1, s1, r1)] != OK[(a2, s2, r2)]
        kind = "same_arm_same_seed_retrain" if (a1, s1) == (a2, s2) else "same_seed_cross_arm" if s1 == s2 else "same_arm_cross_seed" if a1 == a2 else "cross_arm_cross_seed"
        dis[kind].append((d.mean(), d[t1m].mean(), d[t5m].mean()))
    res["item_disagreement_pct"] = {k: {"pairs": len(v), "all": pct(np.mean([x[0] for x in v])), "T1": pct(np.mean([x[1] for x in v])), "T5": pct(np.mean([x[2] for x in v]))} for k, v in dis.items()}
    # Arm effect with hierarchical bootstrap: seeds -> runs within cell -> template_group clusters (same cluster weights for every model)
    if not missing:
        clusters = sorted(set(cl.values()))
        ci = {c: k for k, c in enumerate(clusters)}
        K = len(clusters)
        cid = np.array([ci[cl[i]] for i in ids])
        tot = np.bincount(cid, minlength=K).astype(float)
        t1c = np.bincount(cid, weights=t1m.astype(float), minlength=K)
        t5c = np.bincount(cid, weights=t5m.astype(float), minlength=K)
        S_ok = {k: np.bincount(cid, weights=OK[k], minlength=K) for k in models}
        S_t1 = {k: np.bincount(cid, weights=OK[k] * t1m, minlength=K) for k in models}
        S_t5 = {k: np.bincount(cid, weights=OK[k] * t5m, minlength=K) for k in models}
        rng = np.random.default_rng(RNG_SEED)
        boot = {"overall": [], "T1": [], "T5": [], "retrain_sd_overall": [], "retrain_sd_T1": []}
        for _ in range(a.reps):
            c = np.bincount(rng.integers(0, K, K), minlength=K).astype(float)
            ss = rng.integers(0, len(SEEDS), len(SEEDS))
            dif = {"overall": [], "T1": [], "T5": []}
            for si in ss:
                s = SEEDS[si]
                mean = {}
                for arm in ("A", "B"):
                    rr = rng.integers(1, 4, 3)
                    mean[arm] = {"overall": np.mean([(c @ S_ok[(arm, s, r)]) / (c @ tot) for r in rr]),
                                 "T1": np.mean([(c @ S_t1[(arm, s, r)]) / (c @ t1c) for r in rr]),
                                 "T5": np.mean([(c @ S_t5[(arm, s, r)]) / (c @ t5c) for r in rr])}
                for m in dif:
                    dif[m].append(mean["B"][m] - mean["A"][m])
            for m in dif:
                boot[m].append(np.mean(dif[m]))
        ci_out = {m: {"point_pp": pct(np.mean([M[(("B"), s, r)][m] for s in SEEDS for r in RUNS]) - np.mean([M[("A", s, r)][m] for s in SEEDS for r in RUNS])),
                      "ci95_pp": [pct(np.percentile(boot[m], 2.5)), pct(np.percentile(boot[m], 97.5))]} for m in ("overall", "T1", "T5")}
        for m in ci_out:
            ci_out[m]["excludes_0"] = bool(ci_out[m]["ci95_pp"][0] > 0 or ci_out[m]["ci95_pp"][1] < 0)
        res["Q3_arm_effect_hier_bootstrap"] = ci_out
        # seed-level t interval (df=2)
        tcrit = 4.303
        seed_diff = {m: [np.mean([M[("B", s, r)][m] for r in RUNS]) - np.mean([M[("A", s, r)][m] for r in RUNS]) for s in SEEDS] for m in ("overall", "T1", "T5")}
        res["Q3_seed_level_t_interval_df2"] = {m: {"per_seed_diff_pp": [pct(x) for x in v], "mean_pp": pct(np.mean(v)),
                                                   "ci95_pp": [pct(np.mean(v) - tcrit * np.std(v, ddof=1) / math.sqrt(3)), pct(np.mean(v) + tcrit * np.std(v, ddof=1) / math.sqrt(3))]}
                                               for m, v in seed_diff.items()}
        # Q4: contribution of T1 vs other items to the overall B-A difference (point estimates over all 9 B vs 9 A models)
        n = len(ids)
        d_all = np.mean([OK[("B", s, r)] for s in SEEDS for r in RUNS], axis=0) - np.mean([OK[("A", s, r)] for s in SEEDS for r in RUNS], axis=0)
        contrib = {t: pct(d_all[np.array([tmap[i] == t for i in ids])].sum() / n) for t in sorted(set(tmap.values()))}
        res["Q4_contribution_to_overall_B_minus_A_pp"] = {"by_item_type": contrib, "total": pct(d_all.sum() / n)}
        # Q5: design resolution
        sd_e = pooled["overall"] / 100
        sd_seed_diff = float(np.std(seed_diff["overall"], ddof=1)) if len(SEEDS) > 1 else float("nan")
        res["Q5_design"] = {"retrain_sd_overall_pp": pooled["overall"], "sd_of_seed_level_arm_diff_pp": pct(sd_seed_diff),
                            "se_of_arm_effect_pp(3 seeds)": pct(sd_seed_diff / math.sqrt(3)),
                            "min_detectable_effect_pp(80% power, 5% two-sided, 3 seeds, t df=2)": pct((4.303 + 1.061) * sd_seed_diff / math.sqrt(3)),
                            "seeds_needed_for_2pp_effect": int(math.ceil(((1.96 + 0.84) * sd_seed_diff / 0.02) ** 2)) if sd_seed_diff > 0 else None}
    # T1-specific variance ratio
    if pooled["T1"] and pooled["overall"]:
        res["T1_over_overall_retrain_sd_ratio"] = round(pooled["T1"] / pooled["overall"], 2)
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    with (T.ROOT / "topic2_semantic_order_repro/tables/variance_per_model.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print(json.dumps({k: res[k] for k in ("complete", "n_models", "Q1_pooled_retraining_sd_pp", "Q2_T1_collapse_runs", "item_disagreement_pct")}, indent=1, default=float)[:2500])


if __name__ == "__main__":
    main()
