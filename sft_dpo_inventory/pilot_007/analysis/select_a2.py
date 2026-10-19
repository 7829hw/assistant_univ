# -*- coding: utf-8 -*-
"""A2 판정·해석(결정 179 P5). PLAN_A2와 함께 학습 전에 고정한다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/analysis/select_a2.py   # -> analysis/select_a2.json

채점·정답률 정의는 A단계 ``select_a.py``와 같다(pilot_006 채점기, 문항 정답률 = k=4 평균, 셋 정답률 = 문항 평균, 개발 셋 = valid98 98 + aux 51 문항 평균).

(b) R1' 선택(결정 167 규칙·문턱 그대로): 주 셋 seed sd(ddof 1) ≤ 3.0%p 그리고 개발 셋 평균(세 모델 평균) ≥ 64.19(A단계와 같은 기준값 66.19 − 2).
    둘 다 통과면 "B단계 recipe 후보", 아니면 "후보 없음". 주 셋 평균은 쓰지 않는다.

(a) 해석(진단, 판정 아님): 같은 seed 짝으로 (a) − pilot_006 F.
    - 짝: s43 = (C_s43, pilot_006 F-s43 e1), s1016 = (C_s1016, F-s1016 e1), s7 = (C_s7, D-F7 100%)(세션 4 진단 학습 = pilot_006 F recipe·seed 7).
    - 개발 셋: pilot_006 F-s43·D-F7은 세션 3·4 셀, F-s1016은 이 세션의 기준 셀(E-ref_F1016dev, valid98·aux k=4, 같은 프로토콜)을 쓴다.
    - 짝별 차이와 그 평균을 개발 셋·주 셋에서 각각 낸다. **개발 셋 평균 차(세 짝 평균) ≥ −2%p → "teacher 정리는 성능을 떨어뜨리지 않았다(A단계 하락의 주 원인은 일정)"**,
      < −2%p → "teacher 정리가 성능을 떨어뜨렸다". 기준 셀이 없으면 있는 짝만으로 내고 그 사실을 적는다.
    - 참고(판정에 안 씀): 짝 차의 문항 짝 bootstrap 95% CI(짝을 묶은 문항 평균 차).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
P6POST = ROOT / "sft_dpo_inventory/pilot_006/post"
sys.path.insert(0, str(P6POST))
sys.path.insert(0, str(HERE))
from select_a import SD_MAX, TIE_SD, item_means, reference, set_acc  # noqa: E402,F401

CELLS = "sft_dpo_inventory/pilot_007/cells/"
DEV_DROP = -2.0
SEEDS = (("s43", "C_s43", "F43e1"), ("s1016", "C_s1016", "F1016e1"), ("s7", "C_s7", "D_F7q100"))


def rows_for(name, sets, label=None):
    import itemdata as I
    out = []
    for st in sets:
        p = f"{CELLS}{(label or name).lower()}_{st}"
        if all((ROOT / f"{p}_s{k}.json").exists() for k in range(1, 5)):
            out += I.cell_rows(p, st, name, 4, with_tokens=False)
    return out


def p6_rows():
    rows = []
    for f in ("samples_s3.jsonl", "samples_s4.jsonl"):
        rows += [json.loads(l) for l in (P6POST / f).read_text(encoding="utf-8").splitlines()]
    return rows


def paired(a, b, sets, rng):
    ka = {k for k in a if k[0] in sets}
    kb = {k for k in b if k[0] in sets}
    keys = sorted(ka & kb)
    if not keys:
        return None
    d = np.array([a[k] - b[k] for k in keys])
    boots = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)]
    return {"items": len(keys), "a": round(100 * float(np.mean([a[k] for k in keys])), 2), "ref": round(100 * float(np.mean([b[k] for k in keys])), 2),
            "diff": round(100 * float(d.mean()), 2), "ci95": [round(100 * float(np.percentile(boots, 2.5)), 2), round(100 * float(np.percentile(boots, 97.5)), 2)]}


def main():
    ref_dev, ref_models = reference()
    threshold = ref_dev - 2.0
    rng = np.random.default_rng(20261109)
    # (b)
    mains, devs, per = [], [], {}
    for o in ("o43", "o1016", "o7"):
        nm = f"R1p_{o}"
        im = item_means(rows_for(nm, ("sel", "holdout", "valid98", "aux")))
        m, nm_n = set_acc(im, ("sel", "holdout"))
        dv, nd = set_acc(im, ("valid98", "aux"))
        assert nm_n == 151 and nd == 149, (nm, nm_n, nd)
        per[nm] = {"main(sd 근거만)": round(m, 2), "dev_mean": round(dv, 2)}
        mains.append(m)
        devs.append(dv)
    sd, dev = float(np.std(mains, ddof=1)), float(np.mean(devs))
    b_pass = {"seed_sd_ok": sd <= SD_MAX, "dev_ok": dev >= threshold}
    b = {"per_model": per, "main_seed_sd": round(sd, 3), "dev_mean": round(dev, 3), "pass": b_pass,
         "result": "B단계 recipe 후보" if all(b_pass.values()) else "후보 없음", "dev_threshold": round(threshold, 3), "sd_max": SD_MAX}
    # (a)
    p6 = defaultdict(list)
    for r in p6_rows():
        p6[r["model"]].append(r)
    pairs, dev_diffs, main_diffs = {}, [], []
    for seed, cname, ref in SEEDS:
        ca = item_means(rows_for(cname, ("sel", "holdout", "valid98", "aux")))
        rr = list(p6[ref])
        if seed == "s1016":
            rr += rows_for("F1016e1", ("valid98", "aux"), label="ref_f1016_e1")
        rb = item_means(rr)
        pm, pd = paired(ca, rb, ("sel", "holdout"), rng), paired(ca, rb, ("valid98", "aux"), rng)
        pairs[seed] = {"a": cname, "ref": ref, "main": pm, "dev": pd}
        if pm:
            main_diffs.append(pm["diff"])
        if pd and pd["items"] == 149:
            dev_diffs.append(pd["diff"])
    dev_mean_diff = float(np.mean(dev_diffs)) if dev_diffs else None
    interp = None if dev_mean_diff is None else ("teacher 정리는 성능을 떨어뜨리지 않았다(A단계 하락의 주 원인은 학습 일정)" if dev_mean_diff >= DEV_DROP
                                                 else "teacher 정리가 성능을 떨어뜨렸다")
    a = {"pairs": pairs, "dev_pairs_used": len(dev_diffs), "dev_mean_diff": None if dev_mean_diff is None else round(dev_mean_diff, 2),
         "main_mean_diff(진단)": round(float(np.mean(main_diffs)), 2) if main_diffs else None, "rule": f"개발 셋 평균 차 ≥ {DEV_DROP}%p → 떨어뜨리지 않음", "interpretation": interp}
    out = {"b_R1prime": b, "a_control": a, "reference_dev(pilot_006 F s43·s7)": round(ref_dev, 3), "note": "주 셋 평균은 recipe 선택에 쓰지 않는다(결정 179)."}
    (HERE / "select_a2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
