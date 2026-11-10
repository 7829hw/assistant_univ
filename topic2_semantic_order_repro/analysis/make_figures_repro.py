"""Figures for the repro study (SVG, no plotting dependency). Inputs: tables/variance_per_model.csv, analysis/variance_results.json, Stage 1 tables,
and a per-cell T1 failure-type recount of the 18 H-dev cells (same classifier as stage1_failure_types.py). Descriptive only."""
import csv, json, sys, statistics as st
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage1_failure_types as F  # noqa: E402  (also puts analyze_t2 on path as F.T)
import variance_repro as V  # noqa: E402
T = F.T
OUT = HERE.parent / "figures"; OUT.mkdir(exist_ok=True)
TAB = HERE.parent / "tables"
INK, MUTED, GRID = "#222", "#666", "#ddd"
CA, CB = "#2a6f97", "#c8553d"
rows = list(csv.DictReader(open(TAB / "variance_per_model.csv")))
R = json.load(open(HERE / "variance_results.json"))
SEEDS = V.SEEDS
W, H, L, Rm, Tp, Bt = 760, 420, 70, 30, 60, 60


def svg(title, body, note="", ab=True):
    leg = ("" if not ab else f'<rect x="{W-190}" y="14" width="10" height="10" fill="{CA}"/><text x="{W-175}" y="23" font-size="11" fill="{INK}">A (O4\')</text>'
           f'<rect x="{W-110}" y="14" width="10" height="10" fill="{CB}"/><text x="{W-95}" y="23" font-size="11" fill="{INK}">B (semantic)</text>')
    nt = f'<text x="{L}" y="{H-10}" font-size="10" fill="{MUTED}">{note}</text>' if note else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif"><rect width="{W}" height="{H}" fill="#fff"/>'
            f'<text x="{L}" y="24" font-size="13" font-weight="600" fill="{INK}">{title}</text>{leg}{body}{nt}</svg>')


def yaxis(lo, hi, label, ticks=5):
    s = ""
    for i in range(ticks + 1):
        v = lo + (hi - lo) * i / ticks
        y = Tp + (H - Tp - Bt) * (1 - i / ticks)
        s += f'<line x1="{L}" x2="{W-Rm}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/><text x="{L-6}" y="{y+4:.1f}" font-size="10" text-anchor="end" fill="{MUTED}">{v:.0f}</text>'
    s += f'<text x="14" y="{(Tp+H-Bt)/2}" font-size="11" fill="{MUTED}" transform="rotate(-90 14 {(Tp+H-Bt)/2})" text-anchor="middle">{label}</text>'
    return s


def Y(v, lo, hi):
    return Tp + (H - Tp - Bt) * (1 - (v - lo) / (hi - lo))


def strip(metric, title, fname, lo=0, hi=100, label="accuracy %"):
    """per order seed, A and B retraining runs as dots (jitter-free), cell mean as bar."""
    body = yaxis(lo, hi, label)
    gw = (W - L - Rm) / len(SEEDS)
    for i, s in enumerate(SEEDS):
        cx = L + gw * (i + 0.5)
        body += f'<text x="{cx}" y="{H-Bt+18}" font-size="11" text-anchor="middle" fill="{INK}">{s}</text>'
        for j, (arm, c) in enumerate((("A", CA), ("B", CB))):
            xs = cx + (-1 if arm == "A" else 1) * gw * 0.18
            v = [float(r[metric]) for r in rows if r["arm"] == arm and r["seed"] == s]
            m = st.mean(v)
            body += f'<line x1="{xs-22}" x2="{xs+22}" y1="{Y(m,lo,hi):.1f}" y2="{Y(m,lo,hi):.1f}" stroke="{c}" stroke-width="2.5"/>'
            for k, x in enumerate(v):
                body += f'<circle cx="{xs-12+12*k:.1f}" cy="{Y(x,lo,hi):.1f}" r="4" fill="{c}" fill-opacity=".75"/>'
    (OUT / fname).write_text(svg(title, body, "dots = individual retraining runs (3 per cell), bar = cell mean; H-dev"), encoding="utf-8")


def mean_ci():
    """A/B marginal means (mean of 9 runs) with hierarchical-bootstrap CI of the arm DIFFERENCE reported in text; here A, B means + seed-level range."""
    body = yaxis(0, 100, "accuracy %")
    mets = [("overall", "overall"), ("T1", "T1 (fare)"), ("T5", "T5 (OD top-N)")]
    gw = (W - L - Rm) / 3
    for i, (m, lab) in enumerate(mets):
        cx = L + gw * (i + 0.5)
        body += f'<text x="{cx}" y="{H-Bt+18}" font-size="11" text-anchor="middle" fill="{INK}">{lab}</text>'
        for arm, c, dx in (("A", CA, -0.15), ("B", CB, 0.15)):
            sm = [st.mean(float(r[m]) for r in rows if r["arm"] == arm and r["seed"] == s) for s in SEEDS]
            mu = st.mean(sm); x = cx + dx * gw
            body += f'<rect x="{x-18}" y="{Y(mu,0,100):.1f}" width="36" height="{Y(0,0,100)-Y(mu,0,100):.1f}" fill="{c}" fill-opacity=".35"/>'
            body += f'<line x1="{x}" x2="{x}" y1="{Y(min(sm),0,100):.1f}" y2="{Y(max(sm),0,100):.1f}" stroke="{c}" stroke-width="2"/>'
            for v in sm:
                body += f'<circle cx="{x}" cy="{Y(v,0,100):.1f}" r="3.5" fill="{c}"/>'
            body += f'<text x="{x}" y="{Y(mu,0,100)-6:.1f}" font-size="10" text-anchor="middle" fill="{INK}">{mu:.1f}</text>'
        d = R["Q3_arm_effect_hier_bootstrap"][m]
        body += f'<text x="{cx}" y="{H-Bt+34}" font-size="10" text-anchor="middle" fill="{MUTED}">B-A {d["point_pp"]:+.1f} [{d["ci95_pp"][0]:+.1f}, {d["ci95_pp"][1]:+.1f}] pp</text>'
    (OUT / "fig2_AB_mean_uncertainty.svg").write_text(svg("A/B mean over 3 order seeds; dots = seed means", body), encoding="utf-8")


def sd_bars(fname, title, items, hi, label="pp"):
    body = yaxis(0, hi, label)
    gw = (W - L - Rm) / len(items)
    for i, (lab, vals) in enumerate(items):
        cx = L + gw * (i + 0.5)
        body += f'<text x="{cx}" y="{H-Bt+18}" font-size="11" text-anchor="middle" fill="{INK}">{lab}</text>'
        for k, (nm, v, c) in enumerate(vals):
            x = cx + (k - (len(vals) - 1) / 2) * 34
            body += f'<rect x="{x-14}" y="{Y(v,0,hi):.1f}" width="28" height="{Y(0,0,hi)-Y(v,0,hi):.1f}" fill="{c}"/><text x="{x}" y="{Y(v,0,hi)-4:.1f}" font-size="9" text-anchor="middle" fill="{INK}">{v:.1f}</text>'
    leg = "".join(f'<text x="{L+k*210}" y="{H-24}" font-size="10" fill="{c}">■ {nm}</text>' for k, (nm, _, c) in enumerate(items[0][1]))
    (OUT / fname).write_text(svg(title, body + leg, ab=False), encoding="utf-8")


def arm_effect_per_seed():
    body = yaxis(-100, 60, "B - A (pp)", 8)
    gw = (W - L - Rm) / 3
    body += f'<line x1="{L}" x2="{W-Rm}" y1="{Y(0,-100,60):.1f}" y2="{Y(0,-100,60):.1f}" stroke="{INK}"/>'
    cols = {"overall": "#555", "T1": CB, "T5": "#3a7d44"}
    for i, s in enumerate(SEEDS):
        cx = L + gw * (i + 0.5)
        body += f'<text x="{cx}" y="{H-Bt+18}" font-size="11" text-anchor="middle" fill="{INK}">{s}</text>'
        for k, m in enumerate(("overall", "T1", "T5")):
            x = cx + (k - 1) * 70
            a = [float(r[m]) for r in rows if r["arm"] == "A" and r["seed"] == s]; b = [float(r[m]) for r in rows if r["arm"] == "B" and r["seed"] == s]
            d = st.mean(b) - st.mean(a)
            allp = [y - x_ for x_ in a for y in b]  # 9 retraining pairings
            body += f'<line x1="{x}" x2="{x}" y1="{Y(min(allp),-100,60):.1f}" y2="{Y(max(allp),-100,60):.1f}" stroke="{cols[m]}" stroke-width="3" stroke-opacity=".35"/>'
            body += f'<circle cx="{x}" cy="{Y(d,-100,60):.1f}" r="5" fill="{cols[m]}"/><text x="{x+9}" y="{Y(d,-100,60)+4:.1f}" font-size="9" fill="{INK}">{d:+.1f}</text>'
    leg = "".join(f'<text x="{L+k*120}" y="{H-24}" font-size="10" fill="{c}">● {m}</text>' for k, (m, c) in enumerate(cols.items()))
    (OUT / "fig4_arm_effect_per_seed.svg").write_text(svg("B - A per order seed (dot = mean of 3 runs; whisker = range of 9 run pairings)", body + leg, ab=False), encoding="utf-8")


def t1_position():
    ex = [r for r in csv.DictReader(open(TAB / "stage1_order_exposure.csv")) if r["group"] == "billing_contrast_teacher"]
    body = yaxis(0, 100, "% of 298 records in last 25% of steps")
    gw = (W - L - Rm) / 5
    for i, s in enumerate(ex[0:10:2]):
        pass
    seeds = sorted({r["seed"] for r in ex}, key=int)
    for i, sd in enumerate(seeds):
        cx = L + gw * (i + 0.5)
        body += f'<text x="{cx}" y="{H-Bt+18}" font-size="11" text-anchor="middle" fill="{INK}">{sd}</text>'
        for arm, c, dx in (("A", CA, -1), ("B", CB, 1)):
            r = next(x for x in ex if x["seed"] == sd and x["arm"] == arm)
            v = 100 * int(r["last25pct"]) / int(r["records"]); x = cx + dx * 22
            body += f'<rect x="{x-18}" y="{Y(v,0,100):.1f}" width="36" height="{Y(0,0,100)-Y(v,0,100):.1f}" fill="{c}"/><text x="{x}" y="{Y(v,0,100)-4:.1f}" font-size="10" text-anchor="middle">{v:.1f}</text>'
    (OUT / "fig5_T1_neighbour_position.svg").write_text(svg("Billing-contrast teacher records (nearest training neighbours of T1) in the last 25% of the order", body, "uniform order would give 25%; train data/order only, no accuracy"), encoding="utf-8")


def lr_exposure():
    ex = [r for r in csv.DictReader(open(TAB / "stage1_order_exposure.csv"))]
    groups = ["billing_contrast_teacher", "contrast_teacher_all", "billing_all"]
    body = yaxis(0, 60, "LR-weighted exposure share %")
    gw = (W - L - Rm) / len(groups)
    for i, g in enumerate(groups):
        cx = L + gw * (i + 0.5)
        body += f'<text x="{cx}" y="{H-Bt+18}" font-size="11" text-anchor="middle" fill="{INK}">{g}</text>'
        for arm, c, dx in (("A", CA, -1), ("B", CB, 1)):
            v = [100 * float(r["lr_weighted_share"]) for r in ex if r["group"] == g and r["arm"] == arm]
            tok = 100 * float(next(r for r in ex if r["group"] == g)["token_share"]); x = cx + dx * 40
            m = st.mean(v)
            body += f'<rect x="{x-24}" y="{Y(m,0,60):.1f}" width="48" height="{Y(0,0,60)-Y(m,0,60):.1f}" fill="{c}"/><text x="{x}" y="{Y(m,0,60)-4:.1f}" font-size="10" text-anchor="middle">{m:.1f}</text>'
        body += f'<line x1="{cx-80}" x2="{cx+80}" y1="{Y(tok,0,60):.1f}" y2="{Y(tok,0,60):.1f}" stroke="{INK}" stroke-dasharray="4 3"/>'
    (OUT / "fig6_lr_weighted_exposure.svg").write_text(svg("LR-weighted exposure share (mean over 5 order seeds); dashed = token share (uniform-LR reference)", body), encoding="utf-8")


def t1_errors():
    gold = T.load_gold(T.HDEV); tmap = {i: T.A13.tsig(g.get("gold")) for i, g in gold.items()}
    cls = ["match", "wrong_region", "refused_unsupported", "wrong_time", "other_fail"]
    cnt = {"A": Counter(), "B": Counter()}; n = Counter()
    for arm in "AB":
        for s in SEEDS:
            for r in (1, 2, 3):
                rows_ = F.load([V.path(arm, s, r)])
                for i, row in rows_.items():
                    if tmap.get(i) != "T1": continue
                    c = F.classify(row); c = c if c in cls else "other_fail"
                    cnt[arm][c] += 1; n[arm] += 1
    body = yaxis(0, 100, "% of T1 items (pooled 9 runs)")
    gw = (W - L - Rm) / len(cls)
    out = {}
    for i, c in enumerate(cls):
        cx = L + gw * (i + 0.5)
        body += f'<text x="{cx}" y="{H-Bt+18}" font-size="11" text-anchor="middle" fill="{INK}">{c}</text>'
        for arm, col, dx in (("A", CA, -1), ("B", CB, 1)):
            v = 100 * cnt[arm][c] / n[arm]; x = cx + dx * 24; out[f"{arm}_{c}"] = round(v, 2)
            body += f'<rect x="{x-20}" y="{Y(v,0,100):.1f}" width="40" height="{Y(0,0,100)-Y(v,0,100):.1f}" fill="{col}"/><text x="{x}" y="{Y(v,0,100)-4:.1f}" font-size="10" text-anchor="middle">{v:.1f}</text>'
    (OUT / "fig7_T1_error_types.svg").write_text(svg("H-dev T1 outcome breakdown, 9 runs per arm pooled", body, "same classifier as Stage 1 (scorer fields only)"), encoding="utf-8")
    (TAB / "repro_t1_error_types.json").write_text(json.dumps({"counts": {a: dict(cnt[a]) for a in cnt}, "n_per_arm": dict(n), "pct": out}, indent=1))


mean_ci_ = mean_ci
strip("overall", "H-dev overall accuracy: retraining runs per order seed", "fig1_retrain_overall.svg")
strip("T1", "H-dev T1 (fare) accuracy: retraining runs per order seed", "fig1b_retrain_T1.svg")
strip("T5", "H-dev T5 (OD top-N) accuracy: retraining runs per order seed", "fig1c_retrain_T5.svg")
mean_ci()
q1 = R["Q1_pooled_retraining_sd_pp"]; an = R["anova"]
sd_bars("fig3_T1_T5_variance.svg", "Retraining SD vs |B-A| arm effect (pp)", [
    (m, [("retraining SD (pooled)", q1[m], "#888"), ("|arm effect B-A|", abs(an[m]["arm_effect_B_minus_A"]), CB)]) for m in ("overall", "T1", "T5")], 40)
sd_bars("fig8_noise_vs_order.svg", "Variance components, SD pp (ANOVA, negatives truncated to 0; 2 df for seed/interaction)", [
    (m, [("retraining residual", an[m]["sd_components"]["resid"], "#888"), ("Arm x Seed", an[m]["sd_components"]["arm_x_seed"], CB), ("order seed", an[m]["sd_components"]["seed"], CA)]) for m in ("overall", "T1", "T5")], 30)
arm_effect_per_seed()
t1_position(); lr_exposure(); t1_errors()
print(sorted(p.name for p in OUT.iterdir()))
