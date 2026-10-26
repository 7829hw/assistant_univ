# -*- coding: utf-8 -*-
"""pilot_009 준비 C3·C4 검정력(결정 231 Y5·232 Y6): bootstrap 모의실험. 모델 호출 없음. protected_final은 쓰지 않는다(v1 끝남, v2 문항 없음).

    hfvenv/bin/python sft_dpo_inventory/pilot_009/analysis/power9.py   # -> analysis/power9.json

문항 성분은 pilot_008 셀(``pilot_008/gates/spec_p8.json``)에서 잡는다: base(refusal_dev k=12, 주 셋 k=12/8)와 후보 대용 P8(순서 seed 5 × k=4 묶음).
refusal_dev 확장 셀(J-rdev2, base·P8 각 k=4)이 있으면 거부 문항 모집단에 더한다(``pool``에 적음).

A. v2 거부 비열등(거부 50, k=8, J-c): 모의 한 번 = 모집단에서 문항 50 복원 추출 → 문항별 참 거부율 base p_b, 후보 p_c = clip(p_b + d_i − mean(d) + s)
   (d_i = P8 − base 문항 차, s는 모집단 평균 차가 Δ가 되게 이분법으로 맞춤) → 각 k=8 이항 표본 → 문항 쌍 bootstrap(2,000) 95% CI → 하한 ≥ −15%p면 통과.
   Δ ∈ {0, +10, −10}%p, 모의 2,000번. 같은 방법으로 거부 30(v2 확정본)도 다시 계산(정규 근사 0.54와 대조).
B. v2 답하는 문항 정답률(100, k=8): 주 셋 151에서 문항 100 복원 추출, base·후보 참 정답률 = 셀 문항 평균(후보 = P8; 평균 차를 Δ로 맞춤) → 같은 bootstrap.
   95% CI 반폭 분포(중앙값, 5–95%)와 우월(하한 > 0) 확률(Δ = 0, +5, +8%p).
C. pilot_009 단계 판정 조건 2 후보(refusal_dev 거부 90, 순서 seed 5 × k=4 대 base k=12): 계층 모의 — seed마다 효과 e_s ~ N(0, σ_seed)(σ_seed = P8 seed 평균의 sd),
   후보 p_cs = clip(p_b + d_i − mean(d) + s + e_s). CI는 seed × 문항 계층 bootstrap(``compute_gates_b.hier_ci``와 같은 구조: seed 복원 추출 × 문항 복원 추출, 2,000).
   하한 ≥ −15%p 통과 확률(Δ = 0, +10, −10), 반폭 중앙값. 같은 모의에서 마진 −10·−20도 함께(참고).
seed: 부분마다 새 ``default_rng(20261026)``.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P9 = HERE.parent
ROOT = P9.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/post"))
SEED = 20261026
REFUSED = ("unsupported", "needs_clarification")
SIMS, BOOT = (int(x) for x in __import__("os").environ.get("POWER9_SIMS_BOOT", "2000,2000").split(","))


def refused_matrix(paths, ids):
    """셀 경로 목록 → 문항 × 표본 0/1(올바른 거부)."""
    cols = []
    for p in paths:
        rows = {r["id"]: r for r in json.loads((ROOT / p).read_text(encoding="utf-8"))["rows"]}
        col = []
        for i in ids:
            r = rows[i]
            analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
            col.append(float(r.get("outcome") in REFUSED and analysis == 0))
        cols.append(col)
    return np.array(cols).T


def calibrate(pb, dc, delta):
    lo, hi = -1.0, 1.0
    for _ in range(60):
        s = (lo + hi) / 2
        m = np.clip(pb + dc + s, 0, 1).mean() - pb.mean()
        lo, hi = (s, hi) if m < delta else (lo, s)
    return (lo + hi) / 2


def paired_ci(diff, rng, boot=BOOT):
    """diff: sims × n → (lower, upper) 각 sims."""
    sims, n = diff.shape
    lows, ups = np.empty(sims), np.empty(sims)
    for j in range(sims):
        idx = rng.integers(0, n, size=(boot, n))
        m = diff[j][idx].mean(axis=1)
        lows[j], ups[j] = np.percentile(m, [2.5, 97.5])
    return lows, ups


def part_ab(pb_pool, dc_pool, n, k, deltas, rng, margin=None):
    out = {}
    for delta in deltas:
        s = calibrate(pb_pool, dc_pool, delta)
        pick = rng.integers(0, len(pb_pool), size=(SIMS, n))
        pb = pb_pool[pick]
        pc = np.clip(pb + dc_pool[pick] + s, 0, 1)
        xb = rng.binomial(k, pb) / k
        xc = rng.binomial(k, pc) / k
        lo, up = paired_ci(xc - xb, rng)
        r = {"true_diff_pp": round(100 * delta, 1), "half_width_pp_median": round(50 * float(np.median(up - lo)), 2),
             "half_width_pp_5_95": [round(50 * float(np.percentile(up - lo, q)), 2) for q in (5, 95)]}
        if margin is not None:
            r["pass_prob(lower>=%+d)" % margin] = round(float((lo >= margin / 100).mean()), 3)
        else:
            r["superior_prob(lower>0)"] = round(float((lo > 0).mean()), 3)
        out[f"{delta * 100:+.0f}"] = r
    return out


def part_c(pb_pool, dc_pool, sd_seed, n, seeds, kc, kb, deltas, rng, margins=(-15, -10, -20)):
    out = {}
    for delta in deltas:
        s = calibrate(pb_pool, dc_pool, delta)
        res = {m: [] for m in margins}
        hws = []
        for _ in range(SIMS // 4):
            pick = rng.integers(0, len(pb_pool), size=n)
            pb = pb_pool[pick]
            e = rng.normal(0, sd_seed, size=seeds)
            pc = np.clip(pb[None, :] + dc_pool[pick][None, :] + s + e[:, None], 0, 1)  # seeds × n
            xb = rng.binomial(kb, pb) / kb
            xc = rng.binomial(kc, pc) / kc
            si = rng.integers(0, seeds, size=(BOOT, seeds))
            ii = rng.integers(0, n, size=(BOOT, n))
            m = np.array([xc[si[b]][:, ii[b]].mean() - xb[ii[b]].mean() for b in range(BOOT)])
            lo, up = np.percentile(m, [2.5, 97.5])
            hws.append((up - lo) / 2)
            for mg in margins:
                res[mg].append(lo >= mg / 100)
        out[f"{delta * 100:+.0f}"] = {"true_diff_pp": round(100 * delta, 1), "half_width_pp_median": round(100 * float(np.median(hws)), 2),
                                      **{f"pass_prob(lower>={mg:+d})": round(float(np.mean(res[mg])), 3) for mg in margins}, "sims": SIMS // 4}
    return out


def main():
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    import evaluate_vendor100 as EV
    spec = json.loads((ROOT / "sft_dpo_inventory/pilot_008/gates/spec_p8.json").read_text(encoding="utf-8"))
    rmeta = json.loads((ROOT / spec["rdev_meta"]).read_text(encoding="utf-8"))
    ref_ids = sorted(i for i, m in rmeta.items() if m["refusal"])
    base_r = refused_matrix(spec["cells"]["base"]["rdev"], ref_ids)
    p8_r = np.hstack([refused_matrix(spec["cells"]["P8"][s]["rdev"], ref_ids) for s in spec["seeds"]])
    p8_seed_means = [refused_matrix(spec["cells"]["P8"][s]["rdev"], ref_ids).mean() for s in spec["seeds"]]
    pb_pool, pc_pool = base_r.mean(axis=1), p8_r.mean(axis=1)
    pool_note = {"refusal_dev_v1_refusal_items": len(ref_ids), "base_k": base_r.shape[1], "p8_samples_per_item": p8_r.shape[1]}
    c9 = ROOT / "sft_dpo_inventory/pilot_009/cells"
    exp_base = [f"sft_dpo_inventory/pilot_009/cells/rdev2_base_s{k}.json" for k in range(1, 5)]
    exp_p8 = [[f"sft_dpo_inventory/pilot_009/cells/rdev2_p8_{s}_s{k}.json" for k in range(1, 5)] for s in spec["seeds"]]
    if all((ROOT / p).exists() for p in exp_base + sum(exp_p8, [])):
        m2 = json.loads((ROOT / "sft_dpo_inventory/pilot_009/refusal_dev2/rdev2_items_meta.json").read_text(encoding="utf-8"))
        ids2 = sorted(m2)
        b2 = refused_matrix(exp_base, ids2).mean(axis=1)
        c2 = np.hstack([refused_matrix(ps, ids2) for ps in exp_p8]).mean(axis=1)
        pb_pool, pc_pool = np.concatenate([pb_pool, b2]), np.concatenate([pc_pool, c2])
        pool_note.update(refusal_dev_expansion_items=len(ids2), expansion_base_k=4, expansion_p8_samples_per_item=20)
    dc_pool = (pc_pool - pb_pool) - (pc_pool - pb_pool).mean()
    sd_seed = float(np.std(p8_seed_means, ddof=1))
    out = {"method": __doc__.split("\n\n")[0], "seed": SEED, "sims": SIMS, "boot": BOOT, "pool": pool_note,
           "pool_rates_pp": {"base": round(100 * float(pb_pool.mean()), 2), "P8": round(100 * float(pc_pool.mean()), 2),
                             "item_diff_sd_pp": round(100 * float((pc_pool - pb_pool).std(ddof=1)), 2)},
           "p8_seed_means_pp": [round(100 * x, 2) for x in p8_seed_means], "sd_seed_pp": round(100 * sd_seed, 2)}
    out["A_v2_refusal_50_k8"] = part_ab(pb_pool, dc_pool, 50, 8, (0.0, 0.10, -0.10), np.random.default_rng(SEED), margin=-15)
    out["A_v2_refusal_30_k8(확정본 비교)"] = part_ab(pb_pool, dc_pool, 30, 8, (0.0, 0.10, -0.10), np.random.default_rng(SEED), margin=-15)
    # B. 정답률
    sets = spec["sets"]
    items_b, mb, _ = CG.load_arm({st: spec["cells"]["base"][st] for st in ("selection_v2", "holdout")}, sets, with_tokens=False)
    mats = []
    for s in spec["seeds"]:
        items_c, mc, _ = CG.load_arm({st: spec["cells"]["P8"][s][st] for st in ("selection_v2", "holdout")}, sets, with_tokens=False)
        assert items_c == items_b
        mats.append(mc["ok"])
    ab, ac = np.asarray(mb["ok"], float), np.vstack(mats).mean(axis=0)
    dacc = (ac - ab) - (ac - ab).mean()
    out["B_v2_answered_100_k8"] = part_ab(ab, dacc, 100, 8, (0.0, 0.05, 0.08), np.random.default_rng(SEED))
    out["B_pool"] = {"items": len(items_b), "base_acc_pp": round(100 * float(ab.mean()), 2), "P8_acc_pp": round(100 * float(ac.mean()), 2)}
    out["C_stage_refusal_dev_90_seeds5_k4_vs_base_k12"] = part_c(pb_pool, dc_pool, sd_seed, 90, 5, 4, 12, (0.0, 0.10, -0.10), np.random.default_rng(SEED))
    (HERE / "power9.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "method"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
