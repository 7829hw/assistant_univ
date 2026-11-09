# -*- coding: utf-8 -*-
"""Figures (hand-written SVG, no matplotlib in the env). Colors: A = blue #2a6fdb, B = orange #d9730d (CVD-safe pair, direct + legend labels)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
T2 = HERE.parent
sys.path.insert(0, str(T2))
CA, CB, INK, MUTE = "#2a6fdb", "#d9730d", "#1f2328", "#6b7280"
W, H, L, R, TOP, BOT = 760, 360, 60, 20, 50, 50


def svg(title, body, legend=True):
    leg = (f'<rect x="{W-170}" y="14" width="12" height="12" fill="{CA}"/><text x="{W-152}" y="24" font-size="12" fill="{INK}">A: original O4′</text>'
           f'<rect x="{W-170}" y="30" width="12" height="12" fill="{CB}"/><text x="{W-152}" y="40" font-size="12" fill="{INK}">B: semantic-balanced</text>') if legend else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif"><rect width="{W}" height="{H}" fill="#fff"/>'
            f'<text x="{L}" y="24" font-size="14" font-weight="600" fill="{INK}">{title}</text>{leg}{body}</svg>')


def grouped(title, cats, A, B, ymax, ylabel, fmt="{:.1f}"):
    n = len(cats)
    pw = (W - L - R) / n
    bw = pw * 0.32
    body = [f'<text x="14" y="{TOP+110}" font-size="11" fill="{MUTE}" transform="rotate(-90 14 {TOP+110})">{ylabel}</text>']
    ph = H - TOP - BOT
    for t in range(5):
        v = ymax * t / 4
        y = TOP + ph - ph * v / ymax
        body.append(f'<line x1="{L}" x2="{W-R}" y1="{y}" y2="{y}" stroke="#e5e7eb"/><text x="{L-6}" y="{y+4}" font-size="10" text-anchor="end" fill="{MUTE}">{v:.0f}</text>')
    for i, c in enumerate(cats):
        x0 = L + pw * i + pw * 0.14
        for j, (val, col) in enumerate(((A[i], CA), (B[i], CB))):
            if val is None:
                continue
            h = max(0, ph * val / ymax)
            x = x0 + j * (bw + 2)
            body.append(f'<rect x="{x}" y="{TOP+ph-h}" width="{bw}" height="{h}" rx="3" fill="{col}"><title>{c} {"AB"[j]}: {val}</title></rect>'
                        f'<text x="{x+bw/2}" y="{TOP+ph-h-3}" font-size="9" text-anchor="middle" fill="{INK}">{fmt.format(val)}</text>')
        body.append(f'<text x="{L+pw*i+pw/2}" y="{H-BOT+16}" font-size="11" text-anchor="middle" fill="{INK}">{c}</text>')
    return svg(title, "".join(body))


def per_seed(res, ds, key, grouping="semantic_fine"):
    b = res[ds][grouping]["per_seed"]
    seeds = res[ds][grouping]["seeds"]
    return seeds, [b["A"][s][key] for s in seeds], [b["B"][s][key] for s in seeds]


def main(path=None, outdir=None):
    res = json.loads(Path(path or HERE / "results_t2.json").read_text(encoding="utf-8"))
    out = Path(outdir or T2 / "figures")
    out.mkdir(exist_ok=True)
    if "ct10k" in res:
        s, a, b = per_seed(res, "ct10k", "overall")
        (out / "fig1_overall_ct10k.svg").write_text(grouped("CT10K overall accuracy by order seed (%)", s, a, b, 100, "accuracy %"), encoding="utf-8")
        s, a, b = per_seed(res, "ct10k", "worst")
        (out / "fig1b_worst_group_ct10k.svg").write_text(grouped("CT10K worst semantic-group accuracy by order seed (%)", s, a, b, 100, "worst group %"), encoding="utf-8")
        s, a, b = per_seed(res, "ct10k", "collapse20")
        (out / "fig2_collapse20_ct10k.svg").write_text(grouped("CT10K # semantic groups >20 pp below base, by order seed", s, a, b, max(a + b + [4]) * 1.15, "groups", "{:.0f}"), encoding="utf-8")
        t = res["ct10k_T1_T5"]
        cats = [f"{k} (CT10K)" for k in t]
        A = [t[k]["A_mean"] for k in t]; B = [t[k]["B_mean"] for k in t]
        if "hdev_T1_T5" in res:
            for k, v in res["hdev_T1_T5"].items():
                cats.append(f"{k} (H-dev)"); A.append(v["A_mean"]); B.append(v["B_mean"])
        (out / "fig3_T1_T5.svg").write_text(grouped("T1 (fare) and T5 (OD top-N) accuracy, mean over seeds (%)", cats, A, B, 100, "accuracy %"), encoding="utf-8")
    # exposure: window total variation per seed (mechanical, from the stored order summaries)
    sm = json.loads((T2 / "orders/offline_validation_summary.json").read_text(encoding="utf-8"))["seeds"]
    seeds = list(sm)
    A = [round(sm[s]["baseline"]["coarse"]["mean_window_total_variation"], 4) * 100 for s in seeds]
    B = [round(sm[s]["balanced"]["coarse"]["mean_window_total_variation"], 4) * 100 for s in seeds]
    (out / "fig4_exposure_distribution.svg").write_text(grouped("Order exposure imbalance (128-record window TV %, not accuracy)", [f"o{s}" for s in seeds], A, B, max(A) * 1.2, "window TV %"), encoding="utf-8")
    print("figures written to", out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
