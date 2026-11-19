# -*- coding: utf-8 -*-
"""pilot_010 JG 집계(결정 270, PLAN_JG 3절). **판정 뒤 추가(사후), PF2·H-final 세 번째 사용 — C1–C4는 바꾸지 않는다.** 측정 전에 커밋한다. 모델 호출 없음.
``analyze_j.py``·``analyze_jp.py``·``analyze_jq.py``는 고치지 않고 함수(셀 읽기·채점·U1 bootstrap·결과 분해)를 불러 쓴다.
**PF2 질문·정답 호출·응답은 출력·저장하지 않는다**(집계 수치·형 M·P·C·코드·sha256만).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/results/analyze_jg.py --cond g0|g1 --out sft_dpo_inventory/pilot_010/results/jg_results.json

운영 조건 셀(``--cond``, PLAN_JG 2절): PF2 ``<700>/cells/pf2<cond>_<arm>_<seed>_s<k>.json``(G0 k=1, G1 k=4), H-final ``cells/JG/hfinal<cond>_<arm>_<seed>_s1.json``.
sampling 셀: J·JP·JQ 셀(``analyze_jq.load_arms`` 그대로; base PF2 k=8·H-final 두 회차 평균).

- arm: base, SFT(B2F 5), RR(P9 5), RR+NM4(V4 5), RR+NM8(V8 7 = 기존 3 + JQ 4), RR+NM 12(V4 5 + V8 7을 한 arm, seed 12).
- 지표: PF2 올바른 거부(50)·과잉 거부(답하는 100·근접 대조 25)·정답률(100), H-final 정답률·과잉 거부. 문항 값 = seed 안 표본 평균. CI = ``analyze_j.boot``(U1, 10,000회).
- 운영 조건 안의 차이: RR+NM4 − SFT, RR+NM8 − SFT, RR+NM4 − base, RR+NM8 − base, RR+NM8 − RR, RR+NM4 − RR+NM8, RR+NM 12 − SFT·− base·− RR.
  기술용 추가: SFT − base, RR − base. sampling 셀에도 같은 표(RR+NM 12 포함)를 낸다.
- 운영 − sampling(arm별): 같은 어댑터의 seed별 차 행렬(운영 문항 값 − sampling 문항 값)을 ``analyze_j.est``로(문항 공유 재추출, seed는 짝째 재추출; base는 문항만).
- 결과 분해(``analyze_jp.classify`` 범주 8개: H-final 3,000·PF2 답하는 100), PF2 형별(M·P·C) 올바른 거부, H-final 도구 유형별 정답률,
  template_group 붕괴 수(30문항 이상 그룹, 같은 조건 base 대비 −20·−30%p), 문항당 호출, wall p50·p95(``analyze_jq.single_cost``), 셀별 잘림 호출(``validity_j.check``).
- 검사: sampling 단일 seed 평균이 ``jp_posthoc.json``과 같은지(``analyze_jq.check_against_jp``, 다르면 멈춤).
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
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
import analyze_jp as AP  # noqa: E402
import analyze_jq as AQ  # noqa: E402
import validity_j as VJ  # noqa: E402

HF_JG = INV / "pilot_010/cells/JG"
SEEDS = {"B2F": AQ.SEEDS["B2F"], "P9": AQ.SEEDS["P9"], "V4": AQ.SEEDS["V4"], "V8": AQ.SEEDS["V8"] + AQ.V8_NEW}
NAMES = {"base": "base", "B2F": "SFT", "P9": "RR", "V4": "RR+NM4", "V8": "RR+NM8 (7)", "RRNM12": "RR+NM 12 seed (RR+NM4 5 + RR+NM8 7)"}
PAIRS = [("V4", "B2F"), ("V8", "B2F"), ("V4", "base"), ("V8", "base"), ("V8", "P9"), ("V4", "V8"), ("RRNM12", "B2F"), ("RRNM12", "base"), ("RRNM12", "P9")]
PAIRS_EXTRA = [("B2F", "base"), ("P9", "base")]
LAB = "판정 뒤 추가(사후), PF2·H-final 세 번째 사용 — C1–C4 판정은 바꾸지 않음"
K_PF = {"g0": 1, "g1": 4}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tag(arm, s):
    return "base" if arm == "base" else f"{arm.lower()}_{s}"


def cond_paths(cond, arm, s):
    pf = [AJ.PF_CELLS / f"pf2{cond}_{tag(arm, s)}_s{k}.json" for k in range(1, K_PF[cond] + 1)]
    return pf, [HF_JG / f"hfinal{cond}_{tag(arm, s)}_s1.json"]


def load_cond(ctx, cond):
    """운영 조건 셀 → PF[arm][s] = [k 표본 기록], HF[arm][s] = [표본 기록], 셀 정보·유효성."""
    PF, HF, cells, validity, missing = {}, {}, [], [], []
    for arm, seeds in {**SEEDS, "base": ("base",)}.items():
        PF[arm], HF[arm] = {}, {}
        for s in seeds:
            pfp, hfp = cond_paths(cond, arm, s)
            if not all(p.exists() for p in pfp + hfp):
                missing.append(f"{arm}:{s}")
                continue
            PF[arm][s], HF[arm][s] = [], []
            for p in pfp:
                rec, info = AQ.load_cell(p, "pf2", ctx)
                PF[arm][s].append(rec)
                cells.append(info)
                validity.append(VJ.check(str(p)))
            for p in hfp:
                rec, info = AQ.load_cell(p, "hfinal", ctx)
                HF[arm][s].append(rec)
                cells.append(info)
                validity.append(VJ.check(str(p)))
    return PF, HF, cells, validity, missing


def add_pool(PF, HF):
    """RR+NM 12 = RR+NM4 5 + RR+NM8 7(seed 키에 arm 접두)."""
    PF["RRNM12"] = {f"{a}:{s}": PF[a][s] for a in ("V4", "V8") for s in PF[a]}
    HF["RRNM12"] = {f"{a}:{s}": HF[a][s] for a in ("V4", "V8") for s in HF[a]}


def seeds_of(PF, arm):
    return tuple(PF[arm])


def form_refusal(PF, arm, seeds, S, meta):
    """PF2 거부 50의 형(M·P·C)별 올바른 거부율: seed마다 형 평균 → seed 평균(점추정)."""
    per = defaultdict(list)
    for s in seeds:
        form = defaultdict(list)
        for i in S.ref:
            form[meta[i]["form"]].append(np.mean([float(x[i]["refused"]) for x in PF[arm][s]]))
        for k, v in form.items():
            per[k].append(np.mean(v))
    n = defaultdict(int)
    for i in S.ref:
        n[meta[i]["form"]] += 1
    return {k: {"items": n[k], "pct": AJ.pp(np.mean(v)), "per_seed_pct": [AJ.pp(x) for x in v]} for k, v in sorted(per.items())}


def pf_decomp(PF, arm, seeds, S):
    return {c: round(float(np.mean([AJ.pp(AQ.cat_vec(PF[arm][s], S.ans)[c].mean()) for s in seeds])), 2) for c in AQ.CATS}


def condition_block(PF, HF, S, ctx, label):
    """한 조건(운영 또는 sampling)의 arm별 추정·차이·세부."""
    arms = [a for a in ("base", "B2F", "P9", "V4", "V8", "RRNM12") if PF.get(a)]
    mats = {a: AQ.metric_mats_single(PF, HF, a, seeds_of(PF, a), S) for a in arms}
    base_hf = AQ.hf_vec(HF["base"]["base"], S.hf)
    out = {"condition": label, "arms": {}, "differences": {}, "differences_extra_descriptive": {}}
    for a in arms:
        sd = seeds_of(PF, a)
        out["arms"][a] = {"name": NAMES[a], "seeds": list(sd), "metrics": AQ.est_all(mats[a]),
                          "pf2_correct_refusal_by_form": form_refusal(PF, a, sd, S, ctx["pf_meta"]), "pf2_decomposition_100_seed_mean": pf_decomp(PF, a, sd, S),
                          "hfinal": AQ.single_hf_details(HF, a, sd, S, base_hf, ctx), "cost_seed_mean": AQ.single_cost(PF, HF, a, sd)}
    for tgt, pairs in (("differences", PAIRS), ("differences_extra_descriptive", PAIRS_EXTRA)):
        for x, y in pairs:
            if x in mats and y in mats:
                out[tgt][f"{x}-{y}"] = AQ.diff_all(mats[x], mats[y])
    return out, mats


def paired(gm, sm, PFg, PFs, arm):
    """운영 − sampling: seed 짝 차 행렬. 운영 조건에 있는 seed만(같은 순서)."""
    if arm == "base":
        return {f: AJ.est(gm[f] - sm[f]) for f in AQ.METRICS}, ["base"]
    gs, ss = seeds_of(PFg, arm), seeds_of(PFs, arm)
    idx = [ss.index(s) for s in gs]
    return {f: AJ.est(gm[f] - sm[f][idx]) for f in AQ.METRICS}, list(gs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond", choices=("g0", "g1"), required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ctx = AQ.setup()
    S = AQ.Sets(ctx)
    # ---- 운영 조건 ----
    PFg, HFg, cells_g, validity, missing = load_cond(ctx, a.cond)
    if "base" in missing or not PFg.get("B2F"):
        raise SystemExit(f"operating-condition cells missing: {missing}")
    add_pool(PFg, HFg)
    # ---- sampling(J·JP·JQ) ----
    PFs, HFs, cells_s = AQ.load_arms(ctx, {**AQ.SEEDS, "V8new": AQ.V8_NEW, "base": ("base",)})
    PFs["V8"] = {**PFs["V8"], **PFs.pop("V8new")}
    HFs["V8"] = {**HFs["V8"], **HFs.pop("V8new")}
    add_pool(PFs, HFs)
    chk = AQ.check_against_jp({k: AQ.metric_mats_single(PFs, HFs, k, AQ.SEEDS[k], S) for k in AQ.SEEDS},
                              AQ.metric_mats_single(PFs, HFs, "base", ("base",), S))
    op, gm = condition_block(PFg, HFg, S, ctx, f"operating {a.cond.upper()}")
    sp, sm = condition_block(PFs, HFs, S, ctx, "sampling (J·JP·JQ, T 0.6)")
    op_minus_s = {}
    for arm in gm:
        d, sd = paired(gm[arm], sm[arm], PFg, PFs, arm)
        op_minus_s[arm] = {"name": NAMES[arm], "seeds": sd, "paired_diff": d}
    res = {"label": LAB, "decision": 270, "plan": "sft_dpo_inventory/pilot_010/PLAN_JG.md", "condition": a.cond.upper(), "names": NAMES,
           "bootstrap": {"reps": AJ.REPS, "rng": f"default_rng({AJ.RNG_SEED}) per statistic", "method": "U1 (items shared, seeds per arm); paired: seed-pair rows"},
           "missing_operating_cells": missing, "check_sampling_single_means_vs_jp_posthoc": chk,
           "operating": op, "sampling": sp, "operating_minus_sampling": op_minus_s,
           "validity_operating_cells": validity, "cells_operating": cells_g, "cells_sampling": cells_s,
           "group_collapse_reference": "같은 조건의 base(운영 = base 운영 셀 1회, sampling = base 두 회차 평균)"}
    res["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    res["inputs"] = {"pf2_gold_sha256": sha(AJ.PF_GOLD), "pf2_meta_sha256": sha(AJ.PF_META), "hfinal_sha256": sha(ROOT / AJ.HF_GOLD), "analysis_sha256": sha(__file__),
                     "analyze_j_sha256": sha(AJ.__file__), "analyze_jp_sha256": sha(AP.__file__), "analyze_jq_sha256": sha(AQ.__file__)}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("written", a.out, "missing", missing)


if __name__ == "__main__":
    main()
