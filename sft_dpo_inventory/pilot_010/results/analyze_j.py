# -*- coding: utf-8 -*-
"""pilot_010 판정 단계 분석(결정 267 D5, PLAN_J 5–7절). 측정 전에 커밋한다. 모델 호출 없음.
**PF2 질문·정답 호출·응답은 출력·저장하지 않는다** — 저장소에 쓰는 것은 집계 수치·문항 번호별 값·코드·sha256뿐.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/results/analyze_j.py --out sft_dpo_inventory/pilot_010/results/j_judgment.json \
        --items-out sft_dpo_inventory/pilot_010/results/j_items.json
    runtime/envs/hf/bin/python .../analyze_j.py --smoke --out <scratch>/smoke.json   # 기존 개발 셀로 경로 시험(판정 아님)

채점(표본 하나, PLAN_J 5절):
- refused = 결과 상태 ∈ {unsupported, needs_clarification} 그리고 실행된 분석 호출(``get_place_scope`` 아닌 호출) 0(``pilot_009/gates/compute_p9.sample_values``와 같음).
  경로 = M(error_code UNSUPPORTED_QUESTION) · C(needs_clarification) · P(그 밖).
- PF2 거부 문항: 올바른 거부 = refused. 답하는 문항: 과잉 거부 = refused, 정답 = ``final_ok``(pilot_007 PLAN_FINAL 4절: grounding_ok 참 그리고 결과 상태가 거부가 아님;
  grounding_ok = robust_scoring 패치를 건 ``compute_gates.scorer().load_sample``).
- H-final: 정답 = 행 ``category == "match"``(``ablation_012/analysis/analyze_a12.load_broad``와 같음).
- 문항 값 = 셀(seed) 안 k 표본 평균(base PF2 k=8, H-final base 두 회차 평균).

CI(PLAN_J 6절, 결정 253 U1): 계층 bootstrap 10,000회, 통계량마다 새 ``numpy.random.default_rng(20261109)``.
반복마다 문항을 n개 복원 추출(모든 arm 공유) → arm마다 seed를 그 arm의 seed 수만큼 복원 추출(base는 seed 없음) → 통계량 = 재추출 seed의 재추출 문항 평균의 평균.
난수 순서: 먼저 모든 반복의 문항 번호 (R × n), 그 다음 비교 안 arm 순서대로 각 arm의 seed 번호 (R × S). 95% CI = 2.5·97.5 백분위. 점추정 = 원래 seed·문항 평균(차).
"""
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INV = ROOT / "sft_dpo_inventory"
for p in (ROOT, INV / "pilot_006/gates", INV / "pilot_006/post"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PFDIR = Path("/data/hwkim/sftdpo_work/protected_final_v2")
PF_GOLD, PF_META, PF_CELLS = PFDIR / "pf2_gold.yaml", PFDIR / "pf2_items_meta.json", PFDIR / "cells"
HF_GOLD = "sft_dpo_inventory/ablation_012/e2/h_final.yaml"
HF_CELLS = INV / "pilot_010/cells/J"
V4_SEEDS = ("o101", "o523", "o2029", "o31", "o20271027")
B2F_SEEDS = ("o43", "o1016", "o7", "o11", "o2027")
REPS, RNG_SEED = 10000, 20261109
REFUSAL_OUTCOMES = ("unsupported", "needs_clarification")
NONE = "-"
# 사전 기준(PLAN_J 7절, %p)
C2_MARGIN, C3_MARGIN, C4_MARGIN = -15.0, 3.0, 5.0


def pp(x):
    return None if x is None else round(100 * float(x), 2)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _ts(x):
    return datetime.fromisoformat(x).timestamp()


# ---------------- 셀 읽기 ----------------
def sample_rows(d):
    """셀 행 → {id: (refused, route, outcome, analysis_calls)}(compute_p9.sample_values와 같은 정의)."""
    out = {}
    for r in d["rows"]:
        oc = r.get("outcome")
        analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
        refused = oc in REFUSAL_OUTCOMES and analysis == 0
        route = ("M" if r.get("error_code") == "UNSUPPORTED_QUESTION" else "C" if oc == "needs_clarification" else "P") if refused else None
        out[r["id"]] = (refused, route, oc, analysis)
    return out


def cell_info(p, d, n_items):
    walls, calls_per_item, trunc, srv_err = [], [], 0, 0
    for r in d["rows"]:
        if r.get("started_at") and r.get("finished_at"):
            walls.append(_ts(r["finished_at"]) - _ts(r["started_at"]))
        hc = r.get("hf_calls") or []
        calls_per_item.append(len(hc))
        trunc += sum(1 for x in hc if x.get("finish_reason") == "length" or x.get("done_reason") == "length")
        exc = ((r.get("planner_trace") or {}).get("exception") or "")
        srv_err += r.get("error_code") == "UNHANDLED_EXCEPTION" and exc.split(":")[0] in ("URLError", "HTTPError", "ConnectionError", "ConnectionResetError",
                                                                                            "ConnectionRefusedError", "RemoteDisconnected", "TimeoutError")
    v = d["meta"].get("vllm") or {}
    raw = (d["meta"].get("hf") or {}).get("raw_out")
    return {"file": str(p.name), "file_sha256": sha(p), "rows": len(d["rows"]), "rows_equal_items": len(d["rows"]) == n_items,
            "raw_sha256_match": bool(raw and Path(raw).exists() and sha(raw) == d["meta"]["hf"].get("raw_out_sha256")),
            "model": d["meta"].get("model"), "prompt_sha256": (d["meta"].get("planner_prompt_sha256") or "")[:8],
            "fingerprint": (d["meta"].get("code_fingerprint") or "")[:8], "code_commit": (d["meta"].get("code_commit") or "")[:7],
            "reference_date": d["meta"].get("reference_date"), "concurrency": (v.get("concurrency") or {}).get("max_concurrent_requests"),
            "kernels": v.get("kernels"), "truncated_calls": int(trunc), "server_error_rows": int(srv_err),
            "llm_calls_per_item_mean": round(float(np.mean(calls_per_item)), 3) if calls_per_item else None,
            "llm_calls_total": int(sum(calls_per_item)),
            "wall_p50_s": round(float(np.percentile(walls, 50)), 2) if walls else None, "wall_p95_s": round(float(np.percentile(walls, 95)), 2) if walls else None,
            "started": d["meta"].get("started_at"), "_walls": walls}


def load_pf2_seed(paths, gold, meta, scorer):
    """한 seed(또는 base)의 PF2 셀 k개 → 문항 값(올바른 거부·과잉 거부·정답)·경로 수·셀 정보."""
    A = scorer
    per = defaultdict(lambda: {"refused": [], "ok": [], "route": Counter()})
    infos = []
    for p in paths:
        p = Path(p)
        d = json.loads(p.read_text(encoding="utf-8"))
        A.RAW = Path(d["meta"]["hf"]["raw_out"]).parent
        _, scored = A.load_sample(p, gold)
        sv = sample_rows(d)
        for i, (refused, route, oc, analysis) in sv.items():
            m = meta[i]
            per[i]["refused"].append(float(refused))
            if route:
                per[i]["route"][route] += 1
            if not m["refusal"]:
                per[i]["ok"].append(float(scored[i]["ok"] is True and oc not in REFUSAL_OUTCOMES))
        infos.append(cell_info(p, d, len(gold)))
    return per, infos


def pf2_vectors(per, meta, ids_ref, ids_ans, ids_con):
    v = lambda ids, f: np.array([np.mean(per[i][f]) for i in ids])  # noqa: E731
    routes = Counter()
    for i in ids_ref:
        routes.update(per[i]["route"])
    return {"correct_refusal": v(ids_ref, "refused"), "over_refusal_100": v(ids_ans, "refused"), "over_refusal_contrast25": v(ids_con, "refused"),
            "accuracy_100": v(ids_ans, "ok"), "routes": dict(routes)}


def load_hf_seed(paths, ids):
    """H-final 셀(들) → 정답 벡터(회차 평균)·셀 정보."""
    vals, infos = defaultdict(list), []
    for p in paths:
        p = Path(p)
        d = json.loads(p.read_text(encoding="utf-8"))
        for r in d["rows"]:
            vals[r["id"]].append(float(r.get("category") == "match"))
        infos.append(cell_info(p, d, len(ids)))
    missing = [i for i in ids if i not in vals]
    if missing:
        raise SystemExit(f"H-final cell missing {len(missing)} items: {paths}")
    return np.array([np.mean(vals[i]) for i in ids]), infos


# ---------------- bootstrap ----------------
def boot(arms, signs, reps=REPS):
    """arms: [행렬 (S × n)], signs: 통계량 = Σ sign·(arm 통계량). → (점추정, (lo, hi), 분포 sd)."""
    n = arms[0].shape[1]
    assert all(a.shape[1] == n for a in arms)
    rng = np.random.default_rng(RNG_SEED)
    items = rng.integers(0, n, size=(reps, n))
    seeds = [rng.integers(0, a.shape[0], size=(reps, a.shape[0])) if a.shape[0] > 1 else None for a in arms]
    stat = np.zeros(reps)
    block = 500
    for b0 in range(0, reps, block):
        it = items[b0:b0 + block]
        for a, s, sg in zip(arms, seeds, signs):
            per_seed = a[:, it].mean(axis=2)  # (S, B)
            if s is None:
                stat[b0:b0 + block] += sg * per_seed[0]
            else:
                ss = s[b0:b0 + block]  # (B, S)
                stat[b0:b0 + block] += sg * per_seed[ss.T, np.arange(ss.shape[0])].mean(axis=0)
    point = sum(sg * a.mean(axis=1).mean() for a, sg in zip(arms, signs))
    lo, hi = np.percentile(stat, [2.5, 97.5])
    return float(point), (float(lo), float(hi)), float(stat.std())


def est(arm):
    m, (lo, hi), sd = boot([arm], [1])
    return {"mean_pct": pp(m), "ci95_pct": [pp(lo), pp(hi)], "per_seed_pct": [pp(x) for x in arm.mean(axis=1)], "seeds": int(arm.shape[0]),
            "seed_sd_pp": pp(arm.mean(axis=1).std(ddof=1)) if arm.shape[0] > 1 else None}


def diff(x, y):
    m, (lo, hi), _ = boot([x, y], [1, -1])
    return {"diff_pp": pp(m), "ci95_pp": [pp(lo), pp(hi)], "x_seeds": int(x.shape[0]), "y_seeds": int(y.shape[0])}


def stack(d, keys, f):
    return np.vstack([d[k][f] for k in keys])


# ---------------- 본 분석 ----------------
def analyze(cfg):
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    import evaluate_vendor100 as EV
    res = {"plan": "sft_dpo_inventory/pilot_010/PLAN_J.md", "decision": 267, "bootstrap": {"reps": REPS, "rng": f"default_rng({RNG_SEED}) per statistic", "method": "U1"},
           "smoke": cfg.get("smoke", False), "inputs": {}}
    # ---- PF2 ----
    gold = {i["id"]: i for i in EV.load_gold(cfg["pf_gold"])["items"]}
    meta = cfg["pf_meta"]
    A = CG.scorer()
    pfx = cfg.get("pf_prefix")
    if pfx:  # PF2 id pf2/NNN → U 분류기가 원본 gold를 찾도록 등록(pilot_007 final_score와 같은 방법)
        A.C.R.C._GOLD[pfx] = {i.split("/", 1)[1]: it for i, it in gold.items()}
    else:  # smoke(rdev id에 '/' 없음 → dev 셋으로 찾음): analyze_a12.install_u_gold와 같은 방법
        dev = A.C.R.C._gold("dev", None)
        if set(gold) & set(dev):
            raise SystemExit("smoke ids overlap vendor100 ids")
        dev.update(gold)
    ids = sorted(gold)
    ids_ref = [i for i in ids if meta[i]["refusal"]]
    ids_ans = [i for i in ids if not meta[i]["refusal"]]
    ids_con = [i for i in ids_ans if meta[i]["contrast"] != NONE]
    res["pf2"] = {"items": len(ids), "refusal": len(ids_ref), "answerable": len(ids_ans), "contrast": len(ids_con), "arms": {}, "cells": {}}
    pf = {}
    item_vals = {}
    for arm, seeds in cfg["pf_cells"].items():
        pf[arm] = {}
        for s, paths in seeds.items():
            if not all(Path(p).exists() for p in paths):
                continue
            per, infos = load_pf2_seed(paths, gold, meta, A)
            pf[arm][s] = pf2_vectors(per, meta, ids_ref, ids_ans, ids_con)
            pf[arm][s]["_per"] = per
            res["pf2"]["cells"][f"{arm}:{s}"] = [{k: v for k, v in x.items() if not k.startswith("_")} for x in infos]
            pf[arm][s]["_walls"] = [w for x in infos for w in x["_walls"]]
    metrics = ("correct_refusal", "over_refusal_100", "over_refusal_contrast25", "accuracy_100")
    M = {arm: {f: stack(pf[arm], list(pf[arm]), f) for f in metrics} for arm in pf if pf[arm]}
    for arm in M:
        res["pf2"]["arms"][arm] = {"seeds_present": list(pf[arm]), **{f: est(M[arm][f]) for f in metrics}}
        res["pf2"]["arms"][arm]["routes_samples"] = dict(sum((Counter(pf[arm][s]["routes"]) for s in pf[arm]), Counter()))
    comp = {}
    for other in ("B2F", "base"):
        if "V4" in M and other in M:
            comp[f"V4-{other}"] = {f: diff(M["V4"][f], M[other][f]) for f in metrics}
    res["pf2"]["comparisons"] = comp
    # 경로·범주별 올바른 거부율(기술): 문항 meta의 거부 형·범주별 arm 평균(seed 평균의 문항 평균)
    by = {}
    for arm in M:
        tab = defaultdict(list)
        for x, i in enumerate(ids_ref):
            v = float(M[arm]["correct_refusal"][:, x].mean())
            tab[f"form:{meta[i]['form']}"].append(v)
            tab[f"category:{meta[i]['form']}:{meta[i]['category']}"].append(v)
        by[arm] = {k: {"items": len(v), "pct": pp(np.mean(v))} for k, v in sorted(tab.items())}
        con = defaultdict(list)
        for x, i in enumerate(ids_con):
            con[meta[i]["contrast"]].append(float(M[arm]["over_refusal_contrast25"][:, ids_con.index(i)].mean()))
        by[arm]["contrast_over_refusal_by_category"] = {k: {"items": len(v), "pct": pp(np.mean(v))} for k, v in sorted(con.items())}
        typ = defaultdict(list)
        for x, i in enumerate(ids_ans):
            typ[meta[i]["type"]].append(float(M[arm]["accuracy_100"][:, x].mean()))
        by[arm]["accuracy_by_type"] = {k: {"items": len(v), "pct": pp(np.mean(v))} for k, v in sorted(typ.items())}
    res["pf2"]["by_route_category"] = by
    item_vals["pf2"] = {arm: {i.split("/", 1)[-1]: {"value": round(float(M[arm]["correct_refusal" if meta[i]["refusal"] else "accuracy_100"][:, (ids_ref if meta[i]["refusal"] else ids_ans).index(i)].mean()), 4),
                                                     "metric": "correct_refusal" if meta[i]["refusal"] else "accuracy"} for i in ids} for arm in M}
    # ---- H-final ----
    hgold = EV.load_gold(ROOT / cfg["hf_gold"])["items"]
    hids = [i["id"] for i in hgold]
    hmeta = {i["id"]: i for i in hgold}
    H, hinfo = {}, {}
    for arm, seeds in cfg["hf_cells"].items():
        H[arm] = {}
        for s, paths in seeds.items():
            if not all(Path(p).exists() for p in paths):
                continue
            H[arm][s], hinfo[f"{arm}:{s}"] = load_hf_seed(paths, hids)
    res["hfinal"] = {"items": len(hids), "cells": {k: [{kk: vv for kk, vv in x.items() if not kk.startswith("_")} for x in v] for k, v in hinfo.items()}, "arms": {}}
    HM = {arm: np.vstack([H[arm][s] for s in H[arm]]) for arm in H if H[arm]}
    for arm in HM:
        e = est(HM[arm])
        e["seeds_present"] = list(H[arm])
        e["min_seed_pct"] = pp(HM[arm].mean(axis=1).min())
        pools, cats = defaultdict(list), defaultdict(list)
        for x, i in enumerate(hids):
            pools[hmeta[i].get("pool")].append(x)
            cats[hmeta[i].get("category")].append(x)
        e["by_pool"] = {k: {"items": len(v), "pct": pp(HM[arm][:, v].mean()), "per_seed_pct": [pp(z) for z in HM[arm][:, v].mean(axis=1)]} for k, v in sorted(pools.items())}
        e["by_category"] = {k: {"items": len(v), "pct": pp(HM[arm][:, v].mean())} for k, v in sorted(cats.items(), key=lambda t: str(t[0]))}
        res["hfinal"]["arms"][arm] = e
    hcomp = {}
    for other in ("base", "B2F"):
        if "V4" in HM and other in HM:
            hcomp[f"V4-{other}"] = diff(HM["V4"], HM[other])
    res["hfinal"]["comparisons"] = hcomp
    if "V4" in HM and "base" in HM:
        groups = defaultdict(list)
        for x, i in enumerate(hids):
            groups[hmeta[i]["template_group"]].append(x)
        big = {g: v for g, v in groups.items() if len(v) >= 30}
        base_g = {g: float(HM["base"][:, v].mean()) for g, v in big.items()}
        coll = {}
        for si, s in enumerate(H["V4"]):
            acc = {g: float(HM["V4"][si, v].mean()) for g, v in big.items()}
            coll[s] = {"below_base_20pp": sum(acc[g] < base_g[g] - 0.20 for g in big), "below_base_30pp": sum(acc[g] < base_g[g] - 0.30 for g in big)}
        res["hfinal"]["group_collapse"] = {"groups_ge30": len(big), "per_seed": coll,
                                           "mean_below_20pp": round(float(np.mean([c["below_base_20pp"] for c in coll.values()])), 2),
                                           "mean_below_30pp": round(float(np.mean([c["below_base_30pp"] for c in coll.values()])), 2)}
    item_vals["hfinal"] = {arm: {i: round(float(HM[arm][:, x].mean()), 4) for x, i in enumerate(hids)} for arm in HM}
    # ---- 기준 ----
    crit = {}
    c = comp.get("V4-B2F")
    crit["C1"] = {"rule": "P1 (V4 - B2F) lower > 0", "value": c["correct_refusal"]["ci95_pp"] if c else None,
                  "pass": (c["correct_refusal"]["ci95_pp"][0] > 0) if c else "판정 불가"}
    c = comp.get("V4-base")
    crit["C2"] = {"rule": "P1 (V4 - base) lower >= -15pp", "value": c["correct_refusal"]["ci95_pp"] if c else None,
                  "pass": (c["correct_refusal"]["ci95_pp"][0] >= C2_MARGIN) if c else None}
    c3 = comp.get("V4-B2F") or comp.get("V4-base")
    crit["C3"] = {"rule": "P2 answerable100 (V4 - B2F) upper <= +3pp" + ("" if comp.get("V4-B2F") else " [no B2F: V4 - base]"),
                  "value": c3["over_refusal_100"]["ci95_pp"] if c3 else None, "pass": (c3["over_refusal_100"]["ci95_pp"][1] <= C3_MARGIN) if c3 else None}
    if "V4" in HM and "base" in HM:
        b = float(HM["base"].mean()) * 100
        mean_v4, min_v4 = float(HM["V4"].mean(axis=1).mean()) * 100, float(HM["V4"].mean(axis=1).min()) * 100
        crit["C4"] = {"rule": "H-final V4 seed mean >= base + 5pp and lowest seed >= base", "v4_mean_pct": round(mean_v4, 2), "v4_min_seed_pct": round(min_v4, 2),
                      "base_pct": round(b, 2), "pass": bool(mean_v4 >= b + C4_MARGIN and min_v4 >= b)}
    else:
        crit["C4"] = {"rule": "H-final V4 seed mean >= base + 5pp and lowest seed >= base", "pass": None}
    res["criteria"] = crit
    return res, item_vals


def real_cfg():
    import evaluate_vendor100 as EV  # noqa: F401
    meta = json.loads(PF_META.read_text(encoding="utf-8"))
    pfc = {"V4": {s: [PF_CELLS / f"pf2_v4_{s}_s{k}.json" for k in range(1, 5)] for s in V4_SEEDS},
           "B2F": {s: [PF_CELLS / f"pf2_b2f_{s}_s{k}.json" for k in range(1, 5)] for s in B2F_SEEDS},
           "base": {"base": [PF_CELLS / f"pf2_base_s{k}.json" for k in range(1, 9)]}}
    hfc = {"V4": {s: [HF_CELLS / f"hfinal_v4_{s}_s1.json"] for s in V4_SEEDS},
           "B2F": {s: [HF_CELLS / f"hfinal_b2f_{s}_s1.json"] for s in B2F_SEEDS},
           "base": {"base": [HF_CELLS / "hfinal_base_s1.json", HF_CELLS / "hfinal_base_s2.json"]}}
    return {"pf_gold": PF_GOLD, "pf_meta": meta, "pf_prefix": "pf2", "pf_cells": pfc, "hf_gold": HF_GOLD, "hf_cells": hfc}


def smoke_cfg():
    """경로 시험: PF2 대신 refusal_dev v2(거부 90·대조 30, 선택 단계 셀), H-final 대신 H-dev(ablation_012·013 셀). 판정 아님."""
    import evaluate_vendor100 as EV
    g = "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"
    meta = {}
    for i in EV.load_gold(ROOT / g)["items"]:
        ref = i.get("expected_outcome", "answered") != "answered"
        tool = (i.get("gold") or [{}])[-1].get("tool", "-") if i.get("gold") else "-"
        meta[i["id"]] = {"refusal": ref, "form": "M" if ref else NONE, "category": "rdev" if ref else NONE, "contrast": NONE if ref else "rdev_contrast",
                         "type": "거부" if ref else tool}
    c = INV / "pilot_010/cells"
    pfc = {"V4": {s: [c / f"s10_v4_{s}_rdevv2_s{k}.json" for k in range(1, 5)] for s in ("o43", "o1016", "o7")},
           "B2F": {s: [c / f"s10_v8_{s}_rdevv2_s{k}.json" for k in range(1, 5)] for s in ("o43", "o1016", "o7")},
           "base": {"base": [c / f"s10_v8_o43_rdevv2_s{k}.json" for k in range(1, 5)]}}
    a12, a13 = INV / "ablation_012/cells", INV / "ablation_013/cells"
    v4h = {"o43": a12 / "hdev_v4_o43_s1.json", "o1016": a12 / "hdev_v4_o1016_s1.json", "o7": a12 / "hdev_v4_o7_s1.json",
           "o1102": a12 / "hdev_a0_o1102_s1.json", "o211102": a12 / "hdev_a0_o211102_s1.json", "o2026113": a12 / "hdev_a0_o2026113_s1.json"}
    hfc = {"V4": {s: [p] for s, p in v4h.items()}, "B2F": {s: [a12 / f"hdev_a3_{s}_s1.json"] for s in ("o1102", "o211102", "o2026113")},
           "base": {"base": [a12 / "hdev_base_s1.json", a12 / "hdev_base_s2.json"]}}
    return {"smoke": True, "pf_gold": ROOT / g, "pf_meta": meta, "pf_prefix": None, "pf_cells": pfc, "hf_gold": "sft_dpo_inventory/ablation_012/e2/h_dev.yaml", "hf_cells": hfc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--items-out")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    cfg = smoke_cfg() if a.smoke else real_cfg()
    res, items = analyze(cfg)
    res["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    if not a.smoke:
        res["inputs"] = {"pf2_gold_sha256": sha(PF_GOLD), "pf2_meta_sha256": sha(PF_META), "hfinal_sha256": sha(ROOT / HF_GOLD), "analysis_sha256": sha(__file__)}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if a.items_out:
        Path(a.items_out).write_text(json.dumps(items, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(json.dumps({"criteria": res["criteria"], "pf2_arms": {k: {f: v[f]["mean_pct"] for f in ("correct_refusal", "over_refusal_100", "accuracy_100")}
                                                                for k, v in res["pf2"]["arms"].items()},
                      "hfinal_arms": {k: v["mean_pct"] for k, v in res["hfinal"]["arms"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
