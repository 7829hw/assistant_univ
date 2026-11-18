# -*- coding: utf-8 -*-
"""pilot_010 판정 뒤 사후 집계(결정 268, PLAN_J_POSTHOC 4절). **판정 뒤 추가(사후)·기술 집계 — C1–C4는 바꾸지 않는다.** 모델 호출 없음.
``analyze_j.py``(판정 단계, 고정)는 고치지 않고 함수를 불러 쓴다(셀 읽기·채점·U1 bootstrap이 같다).
**PF2 질문·정답 호출·응답은 출력·저장하지 않는다.** PF2 거부 범주는 형(M·P·C)으로만 낸다.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/results/analyze_jp.py --out sft_dpo_inventory/pilot_010/results/jp_posthoc.json
    runtime/envs/hf/bin/python .../analyze_jp.py --smoke --out <scratch>/smoke_jp.json   # 사후 셀 없이(J 셀만) 경로 시험

1. arm(base·B2 F·P9·V8·V4)별 PF2 네 지표(analyze_j와 같음)와 H-final 정답률·과잉 거부율(H-final 3,000은 모두 답하는 문항; 거부 정의 = analyze_j.sample_rows).
2. 답하는 문항 결과 분해(표본마다 하나, 이 순서로 먼저 맞는 것): 정답(H-final ``category == match``, PF2 final_ok) → 거부 M·P·C(sample_rows 경로)
   → 잘림(호출 하나라도 ``finish_reason == length``) → U(용납할 수 없는 실패, ``compute_gates.scorer().load_sample`` 등급) → 조용한 오답(U 아님)
   → 그 밖 실패(안전한 실패 중 거부·잘림이 아닌 것: 실행 실패 등). U 안에서 U1–U4 flag 별 표본 비율(한 표본이 여러 flag일 수 있어 겹침)도 낸다.
3. H-final V4 − B2 F: 정답률 차를 범주 차(거부·잘림·U·조용한 오답·그 밖)로 나눈다(Δ정답 = −Σ Δ범주). 전체는 U1 CI, 도구 유형·template_group별은 점추정.
4. P1–P4(+ H-final 과잉 거부) 비교: V8 − P9, V4 − P9, V4 − V8, 각 arm − B2 F, − base(V4 − B2 F·V4 − base는 판정 단계와 같은 계산).
5. 개발 셋 대 보호 셋: ``gates/select_s10.py``(그대로) 출력 두 개 — 선택 단계 ``selection_s10.json``(V4 3 seed)과 사후 ``selection_jp_dev.json``(새 V4 5 seed, E-A).
CI = analyze_j.boot(U1 계층 bootstrap 10,000, 통계량마다 default_rng(20261109)).
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
for p in (ROOT, HERE, INV / "pilot_006/gates", INV / "pilot_006/post", INV / "pilot_009/gates", INV / "ablation_012/analysis", INV / "pilot_009/protected_final_v2"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import analyze_j as AJ  # noqa: E402

PF_CELLS, HF_J, HF_JP = AJ.PF_CELLS, INV / "pilot_010/cells/J", INV / "pilot_010/cells/JP"
SEEDS = {"V4": AJ.V4_SEEDS, "B2F": AJ.B2F_SEEDS, "P9": ("o43", "o1016", "o7", "o11", "o2027"), "V8": ("o43", "o1016", "o7")}
ARMS = ("base", "B2F", "P9", "V8", "V4")
CATS = ("correct", "refused_M", "refused_P", "refused_C", "truncated", "U", "silent", "other_fail")
PAIRS = [("V8", "P9"), ("V4", "P9"), ("V4", "V8"), ("P9", "B2F"), ("V8", "B2F"), ("V4", "B2F"), ("P9", "base"), ("V8", "base"), ("V4", "base")]
PF_METRICS = ("correct_refusal", "over_refusal_100", "over_refusal_contrast25", "accuracy_100")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def classify(row, scored, correct, refused, route):
    """표본 하나의 결과 범주(2절 순서)와 U flag 족(U1–U4)."""
    if correct:
        return "correct", ()
    if refused:
        return f"refused_{route}", ()
    if any(x.get("finish_reason") == "length" or x.get("done_reason") == "length" for x in (row.get("hf_calls") or [])):
        return "truncated", ()
    cls = scored.get("class")
    if cls == CLS["U"]:
        return "U", tuple(sorted({f.split(":")[0] for f in (scored.get("u_flags") or [])}))
    if cls == CLS["silent"]:
        return "silent", ()
    return "other_fail", ()


CLS = {}


def decompose(paths, gold, A, ids, correct_fn):
    """셀들(한 seed) → {범주: 문항 벡터(표본 평균)}, {U 족: 문항 벡터}, 문항별 표본 수."""
    acc = {c: defaultdict(list) for c in CATS}
    ufam = {f: defaultdict(list) for f in ("U1", "U2", "U3", "U4")}
    for p in paths:
        p = Path(p)
        d = json.loads(p.read_text(encoding="utf-8"))
        A.RAW = Path(d["meta"]["hf"]["raw_out"]).parent
        _, scored = A.load_sample(p, gold)
        sv = AJ.sample_rows(d)
        src = {r["id"]: r for r in d["rows"]}
        for i in ids:
            refused, route, oc, _ = sv[i]
            cat, fams = classify(src[i], scored[i], correct_fn(src[i], scored[i], oc), refused, route)
            for c in CATS:
                acc[c][i].append(float(c == cat))
            for f in ufam:
                ufam[f][i].append(float(cat == "U" and f in fams))
    vec = lambda t: np.array([np.mean(t[i]) for i in ids])  # noqa: E731
    return {c: vec(acc[c]) for c in CATS}, {f: vec(ufam[f]) for f in ufam}


def pf_correct(row, scored, oc):
    return scored["ok"] is True and oc not in AJ.REFUSAL_OUTCOMES


def hf_correct(row, scored, oc):
    return row.get("category") == "match"


def est_tab(mats):
    return {k: AJ.est(v) for k, v in mats.items()}


def analyze(cfg):
    import robust_scoring
    robust_scoring.patch()
    import analyze_a12 as AA
    import compute_gates as CG
    import evaluate_vendor100 as EV
    from common_pf2 import TYPE_BY_TOOL
    A = CG.scorer()
    CLS.update({"U": A.CS.U_CLASS, "silent": A.CS.SILENT})
    res = {"label": "판정 뒤 추가(사후)·기술 집계 — C1–C4 판정은 바꾸지 않음", "decision": 268, "plan": "sft_dpo_inventory/pilot_010/PLAN_J_POSTHOC.md",
           "bootstrap": {"reps": AJ.REPS, "rng": f"default_rng({AJ.RNG_SEED}) per statistic", "method": "U1"}, "smoke": cfg.get("smoke", False), "skipped": {}}
    # ---------- PF2 ----------
    gold = {i["id"]: i for i in EV.load_gold(cfg["pf_gold"])["items"]}
    meta = cfg["pf_meta"]
    if cfg.get("pf_prefix"):
        A.C.R.C._GOLD[cfg["pf_prefix"]] = {i.split("/", 1)[1]: it for i, it in gold.items()}
    ids = sorted(gold)
    ids_ref = [i for i in ids if meta[i]["refusal"]]
    ids_ans = [i for i in ids if not meta[i]["refusal"]]
    ids_con = [i for i in ids_ans if meta[i]["contrast"] != AJ.NONE]
    PM, PD, PU, pinfo = {}, {}, {}, {}
    for arm in ARMS:
        vecs, dec, uf = {}, defaultdict(list), defaultdict(list)
        for s, paths in cfg["pf_cells"].get(arm, {}).items():
            if not all(Path(p).exists() for p in paths):
                res["skipped"].setdefault("pf2", []).append(f"{arm}:{s}")
                continue
            per, infos = AJ.load_pf2_seed(paths, gold, meta, A)
            vecs[s] = AJ.pf2_vectors(per, meta, ids_ref, ids_ans, ids_con)
            pinfo[f"{arm}:{s}"] = [{k: v for k, v in x.items() if not k.startswith("_")} for x in infos]
            dc, du = decompose(paths, gold, A, ids_ans, pf_correct)
            for c in CATS:
                dec[c].append(dc[c])
            for f in du:
                uf[f].append(du[f])
        if vecs:
            PM[arm] = {f: AJ.stack(vecs, list(vecs), f) for f in PF_METRICS}
            PM[arm]["_seeds"] = list(vecs)
            PM[arm]["_routes"] = dict(sum((Counter(v["routes"]) for v in vecs.values()), Counter()))
            PD[arm] = {c: np.vstack(dec[c]) for c in CATS}
            PU[arm] = {f: np.vstack(uf[f]) for f in uf}
    res["pf2"] = {"items": len(ids), "refusal": len(ids_ref), "answerable": len(ids_ans), "contrast": len(ids_con), "cells": pinfo, "arms": {}, "decomposition_100": {}}
    for arm in PM:
        res["pf2"]["arms"][arm] = {"seeds_present": PM[arm]["_seeds"], **{f: AJ.est(PM[arm][f]) for f in PF_METRICS}, "routes_samples": PM[arm]["_routes"]}
        # 거부 형별 올바른 거부(기술)
        form = defaultdict(list)
        for x, i in enumerate(ids_ref):
            form[meta[i]["form"]].append(float(PM[arm]["correct_refusal"][:, x].mean()))
        res["pf2"]["arms"][arm]["correct_refusal_by_form"] = {k: {"items": len(v), "pct": AJ.pp(np.mean(v))} for k, v in sorted(form.items())}
        res["pf2"]["decomposition_100"][arm] = {"categories": est_tab(PD[arm]), "U_flag_families_overlapping": est_tab(PU[arm])}
    # ---------- H-final ----------
    AA.install_u_gold(cfg["hf_gold"])
    hgold_l = EV.load_gold(ROOT / cfg["hf_gold"])["items"]
    hgold = {i["id"]: i for i in hgold_l}
    hids = [i["id"] for i in hgold_l]
    HM, HO, HD, HU, hinfo = {}, {}, {}, {}, {}
    for arm in ARMS:
        accs, overs, dec, uf = {}, {}, defaultdict(list), defaultdict(list)
        for s, paths in cfg["hf_cells"].get(arm, {}).items():
            if not all(Path(p).exists() for p in paths):
                res["skipped"].setdefault("hfinal", []).append(f"{arm}:{s}")
                continue
            accs[s], hinfo[f"{arm}:{s}"] = AJ.load_hf_seed(paths, hids)
            ref = defaultdict(list)
            for p in paths:
                for i, v in AJ.sample_rows(json.loads(Path(p).read_text(encoding="utf-8"))).items():
                    ref[i].append(float(v[0]))
            overs[s] = np.array([np.mean(ref[i]) for i in hids])
            dc, du = decompose(paths, hgold, A, hids, hf_correct)
            for c in CATS:
                dec[c].append(dc[c])
            for f in du:
                uf[f].append(du[f])
        if accs:
            HM[arm], HO[arm] = np.vstack(list(accs.values())), np.vstack(list(overs.values()))
            HD[arm] = {c: np.vstack(dec[c]) for c in CATS}
            HU[arm] = {f: np.vstack(uf[f]) for f in uf}
            HM[arm + "_seeds"] = list(accs)
    res["hfinal"] = {"items": len(hids), "cells": {k: [{kk: vv for kk, vv in x.items() if not kk.startswith("_")} for x in v] for k, v in hinfo.items()},
                     "arms": {}, "decomposition_3000": {}}
    for arm in ARMS:
        if arm not in HM:
            continue
        e = AJ.est(HM[arm])
        e.update(seeds_present=HM[arm + "_seeds"], min_seed_pct=AJ.pp(HM[arm].mean(axis=1).min()))
        res["hfinal"]["arms"][arm] = {"accuracy": e, "over_refusal": AJ.est(HO[arm])}
        res["hfinal"]["decomposition_3000"][arm] = {"categories": est_tab(HD[arm]), "U_flag_families_overlapping": est_tab(HU[arm])}
    # ---------- 비교 ----------
    comp = {}
    for x, y in PAIRS:
        key = f"{x}-{y}"
        c = {}
        if x in PM and y in PM:
            c.update({f"pf2_{f}": AJ.diff(PM[x][f], PM[y][f]) for f in PF_METRICS})
        if x in HM and y in HM:
            c["hfinal_accuracy"] = AJ.diff(HM[x], HM[y])
            c["hfinal_over_refusal"] = AJ.diff(HO[x], HO[y])
        if c:
            comp[key] = c
    res["comparisons"] = comp
    # ---------- H-final V4 − B2 F 분해 ----------
    if "V4" in HD and "B2F" in HD:
        whole = {c: AJ.diff(HD["V4"][c], HD["B2F"][c]) for c in CATS}
        types, groups = defaultdict(list), defaultdict(list)
        for x, i in enumerate(hids):
            types[TYPE_BY_TOOL.get(hgold[i]["gold"][-1]["tool"], "기타")].append(x)
            groups[hgold[i]["template_group"]].append(x)

        def part(idx):
            return {"items": len(idx), **{c: AJ.pp(HD["V4"][c][:, idx].mean() - HD["B2F"][c][:, idx].mean()) for c in CATS}}
        res["hfinal_v4_minus_b2f_decomposition"] = {
            "note": "Δ정답 = −(Δ거부 M+P+C + Δ잘림 + ΔU + Δ조용한 오답 + Δ그 밖 실패); 표본 범주는 2절 순서로 하나",
            "overall": whole, "by_tool_type": {k: part(v) for k, v in sorted(types.items())},
            "by_template_group": dict(sorted(((g, part(v)) for g, v in groups.items()), key=lambda t: t[1]["correct"]))}
    # ---------- 개발 셋 대 보호 셋 ----------
    dev = {}
    for tag, p in cfg["dev_selection"].items():
        if Path(p).exists():
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            dev[tag] = {"file": str(Path(p).relative_to(ROOT)), "sha256": sha(p), "variants": {v: {k: d["variants"][v].get(k) for k in ("seeds", "refusal_pct", "over_refusal_pct", "dev_ok_pct")}
                                                                                             | {"per_seed": {s: {k: x[k] for k in ("refusal_pct", "over_refusal_pct", "dev_ok_pct")}
                                                                                                             for s, x in d["variants"][v]["per_seed"].items()}} for v in d["variants"]},
                        "reference": d.get("reference")}
        else:
            res["skipped"].setdefault("dev", []).append(tag)
    res["dev_vs_protected"] = dev
    return res


def cfg(smoke):
    meta = json.loads(AJ.PF_META.read_text(encoding="utf-8"))
    pfc = {"base": {"base": [PF_CELLS / f"pf2_base_s{k}.json" for k in range(1, 9)]}}
    hfc = {"base": {"base": [HF_J / "hfinal_base_s1.json", HF_J / "hfinal_base_s2.json"]}}
    for arm, seeds in SEEDS.items():
        if smoke and arm in ("P9", "V8"):
            continue
        pfc[arm] = {s: [PF_CELLS / f"pf2_{arm.lower()}_{s}_s{k}.json" for k in range(1, 5)] for s in seeds}
        hdir = HF_J if arm in ("V4", "B2F") else HF_JP
        hfc[arm] = {s: [hdir / f"hfinal_{arm.lower()}_{s}_s1.json"] for s in seeds}
    return {"smoke": smoke, "pf_gold": AJ.PF_GOLD, "pf_meta": meta, "pf_prefix": "pf2", "pf_cells": pfc, "hf_gold": AJ.HF_GOLD, "hf_cells": hfc,
            "dev_selection": {"selection_stage_V4_3seeds": INV / "pilot_010/results/selection_s10.json",
                              "posthoc_EA_V4_5seeds": INV / "pilot_010/results/selection_jp_dev.json"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--smoke", action="store_true", help="사후 셀(P9·V8) 없이 J 셀만으로 경로 시험")
    a = ap.parse_args()
    res = analyze(cfg(a.smoke))
    res["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    res["inputs"] = {"pf2_gold_sha256": sha(AJ.PF_GOLD), "pf2_meta_sha256": sha(AJ.PF_META), "hfinal_sha256": sha(ROOT / AJ.HF_GOLD),
                     "analysis_sha256": sha(__file__), "analyze_j_sha256": sha(AJ.__file__)}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"pf2": {k: {f: v[f]["mean_pct"] for f in ("correct_refusal", "over_refusal_100", "accuracy_100")} for k, v in res["pf2"]["arms"].items()},
                      "hfinal": {k: [v["accuracy"]["mean_pct"], v["over_refusal"]["mean_pct"]] for k, v in res["hfinal"]["arms"].items()},
                      "skipped": res["skipped"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
