# -*- coding: utf-8 -*-
"""ablation_013 분석(결정 263, PLAN_A13 5절). **진단, 판정 아님.** 모델 호출 없음.
ablation_012 고정 도구의 바이트 사본(``core_a11copy.py``·``xtab_a12.py``·``analyze_a12.py``, 이 디렉터리)의 함수를 그대로 불러 쓴다:
E1 표본 값 = ``core_a11copy.load_model``, 넓은 셋 = ``analyze_a12.load_broad``(U는 ``install_u_gold``), 짝 비교 = ``analyze_a12.compare``(``boot_paired``, 10,000, ``default_rng(20261109)``),
참 차이 넣기 = ``analyze_a12.shift``, 분류 = ``xtab_a12.classify``.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_013/analysis/analyze_a13.py            # -> analysis/results_a13.json, analysis/fig_share_a13.svg
    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_013/analysis/analyze_a13.py --smoke    # -> analysis/smoke_a13.json(기존 셀만: ablation_011·012)

1. A3 분리 2판(5.1): 같은 순서 seed 짝(o1102·o211102·o2026113)으로 (A3 − A3T), (A3T − A0), (A3 − A3R); 참고 (A3 − A0), (A3R − A0), (A3T − A3R). A3R = seed마다 d1·d2 문항 값 평균.
   E1 지표 dev_ok·ref·over·U_rate, H-dev 지표 acc·over·U. 해석 규칙은 PLAN 5.1(구성 차이 병기).
2. 서명 분리(5.2): 위 비교를 T1–T5 서명 문항 / 그 밖으로 나눠(E1 dev_ok·over·U_rate, H-dev acc·over·U; ref는 전체만) 같은 bootstrap. T유형별 점 추정도 낸다.
3. 그림(5.1): x = 근접 대조 teacher 손실 비중, y = 과잉 거부율·정답률(E1·H-dev), 점 = 모델 × 순서 seed, 회귀선 없음 → ``fig_share_a13.svg``.
4. A0 5 seed 분포와 CRITERIA_DEV_v1 검정력(5.3, 보고만): 모의 400 × bootstrap 1,000, ``default_rng(20261113)``.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core_a11copy as CORE  # noqa: E402
import xtab_a12 as XT  # noqa: E402
import analyze_a12 as A12  # noqa: E402  (ablation_012 고정 도구 바이트 사본)

ROOT = CORE.ROOT
INV = ROOT / "sft_dpo_inventory"
A13C = "sft_dpo_inventory/ablation_013/cells"
A12C = "sft_dpo_inventory/ablation_012/cells"
HDEV_GOLD = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
NEW, OLD = CORE.NEW_SEEDS, CORE.OLD_SEEDS  # o1102·o211102·o2026113 / o43·o1016·o7
ADD = ("o2026117", "o2026131")
A0_5 = NEW + ADD
pp = CORE.pp
CRIT = json.loads((HERE.parent / "CRITERIA_DEV_v1.json").read_text(encoding="utf-8"))
SIM_N, SIM_B, SIM_SEED = 400, 1000, 20261113
SIM_DELTAS = {"hdev_acc": (0.0, -0.02, -0.03, -0.04), "e1_ref": (0.0, -0.05, -0.07), "e1_over": (0.0, 0.01, 0.015), "hdev_over": (0.0, 0.01, 0.015)}
SIM_RULES = {"hdev_acc": ("lower", -0.04, "down", 1), "e1_ref": ("lower", -0.07, "down", 4), "e1_over": ("upper", 0.015, "up", 4), "hdev_over": ("upper", 0.015, "up", 1)}
SPLIT_MET_E1 = {"dev_ok": "dev", "over": "over", "U_rate": "dev"}
SPLIT_MET_HD = {"acc": "all", "over": "all", "U": "all"}


# ---------- 서명 ----------
def tsig(calls):
    """PLAN_A13 5.2 T1–T5(정답 호출). 여러 칸이면 앞 번호."""
    calls = calls or []
    tool, tu, rg = XT.classify(calls)
    an = next((c for c in calls if c.get("tool") != "get_place_scope"), {})
    a = an.get("args") or {}
    if tool == "get_trip_metrics":
        if (a.get("aggregation") or "avg") in ("avg", "med", "min", "max") and tu in ("일", "기간", "주") and rg in ("시도", "없음"):
            return "T1"
        if rg == "시군구" or tu == "요일유형":
            return "T2"
    if tool == "get_billing_metrics" and a.get("metric") in ("revenue", "active_taxi_count", "active_taxi_ratio") and \
            ((rg == "시도" and tu in ("일", "월")) or a.get("dimension") in ("sido", "dayofweek")):
        return "T3"
    if tool == "get_trip_count":
        if not a.get("dimension") and tu == "일" and rg in ("없음", "POI"):
            return "T4"
        if a.get("dimension") and a.get("limit") is not None:
            return "T5"
    return "other"


# ---------- 셀 경로 ----------
def e1_cells13(group, seed, cells_dir):
    if group in ("A0", "A3") and seed in NEW:
        return CORE.new_cells(f"a11_{group.lower()}_{seed}")
    if group in ("A3R-d1", "A3R-d2"):
        return A12.e1_cells(group, seed)
    lab = {"valid98": "valid98", "aux": "aux", "rdev": "rdevv2"}
    tag = f"{group.lower()}_{seed}"
    return {st: [f"{cells_dir}/a13_{tag}_{lab[st]}_s{k}.json" for k in range(1, 5)] for st in CORE.SETS}


def hdev_cell13(name, cells_dir):
    g, _, s = name.rpartition("_")
    if name.startswith("base_k"):
        return f"{A12C}/hdev_base_s{name[-1]}.json"
    if g == "A3T" or (g == "A0" and s in ADD):
        return f"{cells_dir}/hdev_{g.lower()}_{s}_s1.json"
    return f"{A12C}/hdev_{A12.hd_key(name)}_s1.json"


def exists(paths):
    return all((ROOT / p).exists() for p in paths)


# ---------- 비교 ----------
def subset(models, keys, masks):
    """models: {seed: {met: 벡터}}, masks: {met: bool 배열} → 부분 벡터."""
    return {s: {m: models[s][m][masks[m]] for m in keys} for s in models}


def split_compare(X, Y, seeds, met_scope, sig_by_scope):
    out = {}
    for part in ("T1-T5", "other"):
        masks = {m: (sig_by_scope[sc] != "other") if part == "T1-T5" else (sig_by_scope[sc] == "other") for m, sc in met_scope.items()}
        out[part] = {"items": {m: int(masks[m].sum()) for m in met_scope}, **A12.compare(subset(X, met_scope, masks), subset(Y, met_scope, masks), seeds, list(met_scope))}
    per_t = {}
    for t in ("T1", "T2", "T3", "T4", "T5"):
        row = {}
        for m, sc in met_scope.items():
            mk = sig_by_scope[sc] == t
            if mk.sum():
                row[m] = {"items": int(mk.sum()), "diff_pp": pp(np.mean([X[s][m][mk].mean() - Y[s][m][mk].mean() for s in seeds])),
                          "x_pct": pp(np.mean([X[s][m][mk].mean() for s in seeds])), "y_pct": pp(np.mean([Y[s][m][mk].mean() for s in seeds]))}
        per_t[t] = row
    out["per_T_point_only"] = per_t
    return out


def a3_split2(models, speeds, metrics, met_scope, sig_by_scope, composition):
    seeds = [s for s in NEW if all(f"{g}_{s}" in models for g in ("A0", "A3", "A3R-d1", "A3R-d2", "A3T"))]
    res = {"seeds_complete": seeds}
    if not seeds:
        return res
    G = {g: {s: models[f"{g}_{s}"] for s in seeds} for g in ("A0", "A3", "A3R-d1", "A3R-d2", "A3T")}
    R = {s: A12.avg_models(G["A3R-d1"][s], G["A3R-d2"][s]) for s in seeds}
    comps = {"A3-A3T": (G["A3"], G["A3T"]), "A3T-A0": (G["A3T"], G["A0"]), "A3-A3R": (G["A3"], R),
             "A3-A0": (G["A3"], G["A0"]), "A3R-A0": (R, G["A0"]), "A3T-A3R": (G["A3T"], R)}
    for name, (x, y) in comps.items():
        res[name] = A12.compare(x, y, seeds, metrics)
        res[name]["signature_split"] = split_compare(x, y, seeds, met_scope, sig_by_scope)
    cap = (f"구성 차이: 근접 대조 teacher 손실 비중 A3 {composition['A3']}% · A3T {composition['A3T']}%(목표 16.2±2에 닿지 않음) · A0 {composition['A0']}%, "
           f"레코드 A3 1,522 · A3T 1,786 · A0 1,984")
    interp = {}
    for met in metrics:
        c = res["A3-A3T"][met]
        t = "근접 대조 비중을 맞춰도 남는 요금 대조 고유 효과" if c["ci_excludes_0"] else "근접 대조 비중 효과와 구별 안 됨"
        interp[met] = f"{t} ({cap})"
    res["interpretation_A3_minus_A3T"] = interp
    o = res["A3T-A0"].get("over")
    if o:
        res["interpretation_A3T_minus_A0_over"] = ("요금 외 근접 대조도 과잉 거부를 막음" if o["ci95_pp"][0] > 0 else "요금 외 근접 대조의 과잉 거부 효과는 보이지 않음") + f" ({cap})"
    res["interpretation_A3_minus_A3R"] = {met: "요금 대조 고유 효과" if res["A3-A3R"][met]["ci_excludes_0"] else "데이터 양 효과와 구별 안 됨" for met in metrics}
    res["speed_seed_mean"] = {g: A12.speed_mean([speeds[f"{g}_{s}"] for s in seeds]) for g in ("A0", "A3", "A3R-d1", "A3R-d2", "A3T")}
    return res


# ---------- 분포·검정력 ----------
def dist(vals):
    v = [x for x in vals.values()]
    return {"per_seed_pct": {k: pp(x) for k, x in vals.items()}, "n": len(v), "mean_pct": pp(np.mean(v)),
            "sd_pp": pp(np.std(v, ddof=1)) if len(v) > 1 else None, "range_pct": [pp(min(v)), pp(max(v))]}


def boot_ci(D, rng, B):
    n, I = D.shape
    ii = rng.integers(0, I, (B, I))
    M = np.stack([D[s][ii].mean(axis=1) for s in range(n)])
    si = rng.integers(0, n, (B, n))
    st = M[si, np.arange(B)[:, None]].mean(axis=1)
    return np.percentile(st, 2.5), np.percentile(st, 97.5)


def power_dev_v1(P, sim_n, sim_b, rng):
    """P: {met: S × I}(A0 seed 문항 값). 지표별 참 차이 통과 확률 + Δ=0 네 조건 동시 통과(같은 seed 뽑기)."""
    n = CRIT["comparison"]["seeds"]
    S = next(iter(P.values())).shape[0]
    out = {"pool_seeds": S, "n": n, "sims": sim_n, "boot": sim_b, "rules": {k: list(v[:2]) for k, v in SIM_RULES.items()}, "per_metric": {}}
    for met, deltas in SIM_DELTAS.items():
        side, lim, kind, k = SIM_RULES[met]
        for dl in deltas:
            hw, ok, pts = [], 0, []
            for _ in range(sim_n):
                a = P[met][rng.integers(0, S, n)]
                b = np.stack([A12.shift(P[met][j], k, dl, kind, rng) for j in rng.integers(0, S, n)])
                lo, hi = boot_ci(b - a, rng, sim_b)
                hw.append((hi - lo) / 2)
                pts.append((b - a).mean())
                ok += (lo > lim) if side == "lower" else (hi < lim)
            out["per_metric"][f"{met}_d{round(100 * dl, 1)}"] = {"metric": met, "true_diff_pp": round(100 * dl, 1), "ci_halfwidth_pp_mean": round(100 * float(np.mean(hw)), 2),
                                                                 "point_sd_pp": round(100 * float(np.std(pts)), 2), "pass_prob": round(ok / sim_n, 3)}
    ok_all = 0
    for _ in range(sim_n):
        ja, jb = rng.integers(0, S, n), rng.integers(0, S, n)
        good = True
        for met, (side, lim, _, _) in SIM_RULES.items():
            lo, hi = boot_ci(P[met][jb] - P[met][ja], rng, sim_b)
            good &= bool((lo > lim) if side == "lower" else (hi < lim))
        ok_all += good
    out["joint_pass_prob_delta0"] = round(ok_all / sim_n, 3)
    return out


# ---------- 그림 ----------
COLORS = {"A0": "#2a78d6", "A3": "#eb6834", "A3R-d1": "#1baf7a", "A3R-d2": "#eda100", "A3T": "#e87ba4"}
SHAPES = {"A0": "circle", "A3": "square", "A3R-d1": "triangle", "A3R-d2": "diamond", "A3T": "cross"}


def svg_marker(shape, x, y, c, title):
    """점 하나 = <g><title/>도형</g>(마우스를 올리면 값). 흰 테두리 1.5px로 겹친 점을 가른다."""
    st = f'fill="{c}" stroke="#ffffff" stroke-width="1.5"'
    if shape == "circle":
        m = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" {st}/>'
    elif shape == "square":
        m = f'<rect x="{x - 4.5:.1f}" y="{y - 4.5:.1f}" width="9" height="9" rx="1" {st}/>'
    elif shape == "triangle":
        m = f'<polygon points="{x:.1f},{y - 5.5:.1f} {x - 5:.1f},{y + 4:.1f} {x + 5:.1f},{y + 4:.1f}" {st}/>'
    elif shape == "diamond":
        m = f'<polygon points="{x:.1f},{y - 5.5:.1f} {x - 5:.1f},{y:.1f} {x:.1f},{y + 5.5:.1f} {x + 5:.1f},{y:.1f}" {st}/>'
    else:
        m = (f'<line x1="{x - 4.5:.1f}" y1="{y - 4.5:.1f}" x2="{x + 4.5:.1f}" y2="{y + 4.5:.1f}" stroke="{c}" stroke-width="2.5" stroke-linecap="round"/>'
             f'<line x1="{x - 4.5:.1f}" y1="{y + 4.5:.1f}" x2="{x + 4.5:.1f}" y2="{y - 4.5:.1f}" stroke="{c}" stroke-width="2.5" stroke-linecap="round"/>')
    return f"<g><title>{title}</title>{m}</g>"


def figure(points, share, path):
    """points: [(panel, group, seed, y_pct)]. 2 × 2 작은 그림, 같은 x 축(비중 %), 회귀선 없음."""
    panels = [("E1 과잉 거부율 (%)", "e1_over"), ("H-dev 과잉 거부율 (%)", "hd_over"), ("E1 개발 셋 정답률 (%)", "e1_acc"), ("H-dev 정답률 (%)", "hd_acc")]
    W, H, pw, ph, ml, mt = 900, 640, 360, 210, 70, 70
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Noto Sans CJK KR, Noto Serif CJK KR, NanumGothic, sans-serif" font-size="11">',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
           '<text x="20" y="24" font-size="14" fill="#1f1f1e">근접 대조 teacher 손실 비중과 과잉 거부·정답률 (모델 × 순서 seed, 회귀선 없음)</text>',
           '<text x="20" y="42" fill="#5f5e58">ablation_013 — 진단, 판정 아님. x 위치는 arm마다 하나(빌드 손실 비중). E1 k=4 평균, H-dev k=1.</text>']
    lx = 20
    for g in COLORS:
        out.append(svg_marker(SHAPES[g], lx + 6, 56, COLORS[g], g))
        out.append(f'<text x="{lx + 16}" y="60" fill="#1f1f1e">{g} ({share[g]}%)</text>')
        lx += 150
    x0, x1 = 10.0, 50.0
    for pi, (title, key) in enumerate(panels):
        ox, oy = ml + (pi % 2) * (pw + 90), mt + 20 + (pi // 2) * (ph + 75)
        ys = [p[3] for p in points if p[0] == key]
        if not ys:
            continue
        lo, hi = min(ys), max(ys)
        pad = max(0.5, 0.1 * (hi - lo))
        lo, hi = lo - pad, hi + pad
        X = lambda v: ox + (v - x0) / (x1 - x0) * pw  # noqa: E731
        Y = lambda v: oy + ph - (v - lo) / (hi - lo) * ph  # noqa: E731
        out.append(f'<text x="{ox}" y="{oy - 8}" font-size="12" fill="#1f1f1e">{title}</text>')
        for t in np.linspace(lo, hi, 5):
            out.append(f'<line x1="{ox}" y1="{Y(t):.1f}" x2="{ox + pw}" y2="{Y(t):.1f}" stroke="#e7e6e1" stroke-width="1"/>')
            out.append(f'<text x="{ox - 6}" y="{Y(t) + 4:.1f}" text-anchor="end" fill="#5f5e58">{t:.1f}</text>')
        for t in (10, 20, 30, 40, 50):
            out.append(f'<text x="{X(t):.1f}" y="{oy + ph + 16}" text-anchor="middle" fill="#5f5e58">{t}</text>')
        out.append(f'<line x1="{ox}" y1="{oy + ph}" x2="{ox + pw}" y2="{oy + ph}" stroke="#a9a89f" stroke-width="1"/>')
        out.append(f'<text x="{ox + pw / 2}" y="{oy + ph + 32}" text-anchor="middle" fill="#5f5e58">근접 대조 teacher 손실 비중 (%)</text>')
        for (k, g, s, y) in points:
            if k == key:
                out.append(svg_marker(SHAPES[g], X(share[g]), Y(y), COLORS[g], f"{g} {s}: {y:.2f}%"))
    out.append("</svg>")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--skip-sim", action="store_true")
    ap.add_argument("--sim-n", type=int, default=SIM_N, help="(도구 시험 전용) 모의 횟수")
    ap.add_argument("--sim-b", type=int, default=SIM_B, help="(도구 시험 전용) 모의 bootstrap 횟수")
    ap.add_argument("--test-cells-dir", default=None, help="(도구 시험 전용) ablation_013 셀 위치를 바꿔 가짜 셀로 전체 경로를 돌린다")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cells_dir = a.test_cells_dir or A13C
    import robust_scoring
    robust_scoring.patch()
    import evaluate_vendor100 as EV
    gold_e1 = {st: {i["id"]: i for i in EV.load_gold(ROOT / g)["items"]} for st, g in CORE.SETS.items()}
    bs = json.loads((INV / "ablation_013/build/build_summary.json").read_text(encoding="utf-8"))["composition"]
    share = {g: bs[g]["loss_share_pct"]["contrast_teacher"] for g in ("A0", "A3", "A3R-d1", "A3R-d2", "A3T")}
    res = {"note": "진단, 판정 아님. E1(refusal_dev v2·valid98·aux)은 V4 선택에 이미 쓴 셋. A3T·A3R은 3 seed라 CRITERIA_DEV_v1을 적용하지 않음(수치만). H-final은 측정·열람하지 않음.",
           "smoke": a.smoke, "missing": [], "contrast_teacher_loss_share_pct": share, "signature_definition": "PLAN_A13 5.2 (tsig)"}
    # ---- E1 ----
    e1, e1_speed, e1_ids = {}, {}, None
    plan = [(g, s) for g in ("A0", "A3", "A3R-d1", "A3R-d2") for s in NEW] + ([] if a.smoke else [("A3T", s) for s in NEW] + [("A0", s) for s in ADD])
    for g, s in plan:
        c = e1_cells13(g, s, cells_dir)
        if not exists([p for v in c.values() for p in v]):
            res["missing"].append(f"E1:{g}_{s}")
            continue
        o = CORE.load_model(c, dict(CORE.SETS), gold_e1, True)
        ids = (tuple(o["dev_items"]), tuple(o["over_ids"]))
        if e1_ids is None:
            e1_ids = ids
        assert ids == e1_ids, "E1 item order differs"
        e1[f"{g}_{s}"], e1_speed[f"{g}_{s}"] = A12.e1_vectors(o), o["speed"]
        print("E1", g, s, {k: pp(v.mean()) for k, v in e1[f"{g}_{s}"].items()}, flush=True)
    for s in OLD:
        e1[f"V4_{s}"] = A12.e1_vectors(CORE.load_model(json.loads(CORE.SPEC10.read_text(encoding="utf-8"))["cells"]["V4"][s], dict(CORE.SETS), gold_e1, False))
    if a.smoke:  # A3T 자리 = A3R(d1·d2 평균) → A3 − A3T가 results_a12 A3 − A3R과 같아야 한다
        for s in NEW:
            e1[f"A3T_{s}"] = A12.avg_models(e1[f"A3R-d1_{s}"], e1[f"A3R-d2_{s}"])
            e1_speed[f"A3T_{s}"] = e1_speed[f"A3R-d1_{s}"]
    dev_sig = np.array([tsig(gold_e1[k.split("/", 1)[0]][k.split("/", 1)[1]].get("gold")) for k in e1_ids[0]])
    over_sig = np.array([tsig(gold_e1[k.split(":", 1)[0]][k.split(":", 1)[1]].get("gold")) for k in e1_ids[1]])
    res["e1_signature_items"] = {"dev": {t: int((dev_sig == t).sum()) for t in ("T1", "T2", "T3", "T4", "T5", "other")},
                                 "over": {t: int((over_sig == t).sum()) for t in ("T1", "T2", "T3", "T4", "T5", "other")}}
    res["e1_a3_split2"] = a3_split2(e1, e1_speed, list(CORE.ITEM_VEC), SPLIT_MET_E1, {"dev": dev_sig, "over": over_sig}, share)
    # ---- H-dev ----
    gold_hd = {i["id"]: i for i in EV.load_gold(ROOT / HDEV_GOLD)["items"]}
    hd_ids = sorted(gold_hd)
    hd_sig = np.array([tsig(gold_hd[i].get("gold")) for i in hd_ids])
    res["hdev_signature_items"] = {t: int((hd_sig == t).sum()) for t in ("T1", "T2", "T3", "T4", "T5", "other")}
    names = [f"{g}_{s}" for g in ("A0", "A3", "A3R-d1", "A3R-d2") for s in NEW] + [f"V4_{s}" for s in OLD] + ["base_k1", "base_k2"]
    if not a.smoke:
        names += [f"A3T_{s}" for s in NEW] + [f"A0_{s}" for s in ADD]
    hd_vec, hd_speed = {}, {}
    for n in names:
        p = hdev_cell13(n, cells_dir)
        if not (ROOT / p).exists():
            res["missing"].append(f"H-dev:{n}")
            continue
        m = A12.load_broad([p], HDEV_GOLD)
        hd_speed[n] = m["speed"]
        hd_vec[n] = {"acc": A12.vec(m, "match", hd_ids), "over": A12.vec(m, "refused", hd_ids), "U": np.array([m["U"][i] for i in hd_ids])}
        print("H-dev", n, {k: pp(v.mean()) for k, v in hd_vec[n].items()}, flush=True)
    if a.smoke:
        for s in NEW:
            if f"A3R-d1_{s}" in hd_vec and f"A3R-d2_{s}" in hd_vec:
                hd_vec[f"A3T_{s}"] = A12.avg_models(hd_vec[f"A3R-d1_{s}"], hd_vec[f"A3R-d2_{s}"])
                hd_speed[f"A3T_{s}"] = hd_speed[f"A3R-d1_{s}"]
    res["hdev_models"] = {n: {**{k: pp(v.mean()) for k, v in hd_vec[n].items()}, "U_samples": int(hd_vec[n]["U"].sum()), "speed": hd_speed[n]} for n in hd_vec}
    res["hdev_a3_split2"] = a3_split2(hd_vec, hd_speed, ["acc", "over", "U"], SPLIT_MET_HD, {"all": hd_sig}, share)
    # ---- 그림 ----
    pts = []
    for g in COLORS:
        for s in (A0_5 if g == "A0" else NEW):
            k = f"{g}_{s}"
            if k in e1:
                pts += [("e1_over", g, s, 100 * float(e1[k]["over"].mean())), ("e1_acc", g, s, 100 * float(e1[k]["dev_ok"].mean()))]
            if k in hd_vec:
                pts += [("hd_over", g, s, 100 * float(hd_vec[k]["over"].mean())), ("hd_acc", g, s, 100 * float(hd_vec[k]["acc"].mean()))]
    fig = HERE / ("fig_share_a13_smoke.svg" if a.smoke else "fig_share_a13.svg")
    figure(pts, share, fig)
    res["figure"] = {"file": str(fig.relative_to(ROOT)), "points": [{"panel": p[0], "arm": p[1], "seed": p[2], "y_pct": round(p[3], 2), "x_share_pct": share[p[1]]} for p in pts]}
    # ---- A0 5 seed 분포 ----
    a0e = [s for s in A0_5 if f"A0_{s}" in e1]
    a0h = [s for s in A0_5 if f"A0_{s}" in hd_vec]
    res["a0_distribution"] = {
        "seeds_e1": a0e, "seeds_hdev": a0h,
        "E1_dev_ok": dist({s: e1[f"A0_{s}"]["dev_ok"].mean() for s in a0e}), "E1_ref": dist({s: e1[f"A0_{s}"]["ref"].mean() for s in a0e}),
        "E1_over": dist({s: e1[f"A0_{s}"]["over"].mean() for s in a0e}),
        "Hdev_acc": dist({s: hd_vec[f"A0_{s}"]["acc"].mean() for s in a0h}), "Hdev_over": dist({s: hd_vec[f"A0_{s}"]["over"].mean() for s in a0h}),
        "reference_V4_old": {"E1_dev_ok": dist({s: e1[f"V4_{s}"]["dev_ok"].mean() for s in OLD}), "E1_ref": dist({s: e1[f"V4_{s}"]["ref"].mean() for s in OLD}),
                             "E1_over": dist({s: e1[f"V4_{s}"]["over"].mean() for s in OLD}),
                             "Hdev_acc": dist({s: hd_vec[f"V4_{s}"]["acc"].mean() for s in OLD if f"V4_{s}" in hd_vec}),
                             "Hdev_over": dist({s: hd_vec[f"V4_{s}"]["over"].mean() for s in OLD if f"V4_{s}" in hd_vec})}}
    if not a.skip_sim:
        common = [s for s in a0e if s in a0h]
        if len(common) >= 2:
            P = {"hdev_acc": np.stack([hd_vec[f"A0_{s}"]["acc"] for s in common]), "hdev_over": np.stack([hd_vec[f"A0_{s}"]["over"] for s in common]),
                 "e1_ref": np.stack([e1[f"A0_{s}"]["ref"] for s in common]), "e1_over": np.stack([e1[f"A0_{s}"]["over"] for s in common])}
            res["criteria_dev_v1_power"] = {"pool": common, "note": "보고만; 기준(CRITERIA_DEV_v1)은 바꾸지 않음", **power_dev_v1(P, a.sim_n, a.sim_b, np.random.default_rng(SIM_SEED))}
    out = Path(a.out) if a.out else HERE / ("smoke_a13.json" if a.smoke else "results_a13.json")
    if a.smoke:
        r12 = json.loads((INV / "ablation_012/analysis/results_a12.json").read_text(encoding="utf-8"))
        chk = {}
        for setn, mine, theirs, mets in (("E1", res["e1_a3_split2"], r12["e1_a3_split"], ("dev_ok", "ref", "over", "U_rate")),
                                          ("H-dev", res["hdev_a3_split2"], r12["hdev_a3_split"], ("acc", "over", "U"))):
            for comp_m, comp_t in (("A3-A3T", "A3-A3R"), ("A3-A3R", "A3-A3R"), ("A3-A0", "A3-A0"), ("A3T-A0", "A3R-A0"), ("A3R-A0", "A3R-A0")):
                chk[f"{setn}:{comp_m}=={comp_t}"] = all(mine[comp_m][m]["diff_pp"] == theirs[comp_t][m]["diff_pp"] and mine[comp_m][m]["ci95_pp"] == theirs[comp_t][m]["ci95_pp"] for m in mets)
        res["summary"] = {"equals_results_a12": chk, "all_equal": all(chk.values()), "e1_signature_items": res["e1_signature_items"], "hdev_signature_items": res["hdev_signature_items"],
                          "a0_distribution_seeds": {"e1": a0e, "hdev": a0h}, "figure_points": len(pts), "missing": res["missing"]}
        print(json.dumps(res["summary"], ensure_ascii=False, indent=1))
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print("wrote", out, "missing", res["missing"])


if __name__ == "__main__":
    main()
