# -*- coding: utf-8 -*-
"""A1 분산 분해(주 셋 151, 판정 아님). ``samples_s3.jsonl`` + ``samples_s4.jsonl``. 모델 호출 없음. 없는 셀은 건너뛴다.

    hfvenv/bin/python a1_variance.py   # -> a1_variance.json

- 표본 잡음(E-rep): 같은 adapter, 새 sampling seed(20261200) — F43e1 대 F43rep, F1016e1 대 F1016rep. 지시 정지 규칙: 원래 셀과 6%p 넘게 다르면 보고.
- 초기화 대 순서(2×2): (init, order) = F43e1 (43, 43), F1016e1 (1016, 1016), D_F43o1016q100 (43, 1016), D_F1016o43q100 (1016, 43).
  순서 효과 = 초기화마다 (order 43 − order 1016)의 평균, 초기화 효과 = 순서마다 (init 43 − init 1016)의 평균, 교호 = 두 대각 차.
  진단 100%는 2 epoch 일정 그대로 epoch 1에서 멈춘 checkpoint라 세션 3 e1 checkpoint와 같은 지점이다.
- seed 셋(43, 1016, 7): F·P 평균·sd, 같은 seed P − F.
- epoch 1 안 궤적(E-Dq greedy): 25·50·75%(greedy k=1) + 100%(k=4 평균과 greedy 둘 다 있으면 둘 다).
- greedy(k=1) 대 sampling 평균(k=4): base·F43·F1016·P43·P1016.
차이 CI = 문항 짝 bootstrap 10,000(default_rng(20261109)).
"""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
rng = np.random.default_rng(20261109)


def load():
    rows = []
    for p in (HERE / "samples_s3.jsonl", HERE / "samples_s4.jsonl"):
        if p.exists():
            rows += [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["set"] in ("sel", "holdout"):
            acc[r["model"]][(r["set"], r["id"])].append(r["ok"])
    return acc


ACC = load()
ITEMS = sorted(ACC["F43e1"])


def vec(m):
    if m not in ACC or not all(i in ACC[m] for i in ITEMS):
        return None
    return np.array([np.mean(ACC[m][i]) for i in ITEMS])


def ci(d):
    b = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)]
    return [round(100 * float(np.percentile(b, 2.5)), 2), round(100 * float(np.percentile(b, 97.5)), 2)]


def diff(a, b):
    va, vb = vec(a), vec(b)
    if va is None or vb is None:
        return None
    d = va - vb
    return {"a": a, "b": b, "a_ok": round(100 * va.mean(), 2), "b_ok": round(100 * vb.mean(), 2), "a_minus_b": round(100 * d.mean(), 2), "ci95": ci(d)}


def mean(m):
    v = vec(m)
    return None if v is None else round(100 * float(v.mean()), 2)


def main():
    out = {"items": len(ITEMS)}
    rep = {m: diff(f"{m}rep", f"{m}e1") for m in ("F43", "F1016")}
    for v in rep.values():
        if v:
            v["over_6pp(stop rule: report)"] = bool(abs(v["a_minus_b"]) > 6)
    out["sampling_noise_E_rep"] = rep
    cells = {("43", "43"): "F43e1", ("1016", "1016"): "F1016e1", ("43", "1016"): "D_F43o1016q100", ("1016", "43"): "D_F1016o43q100"}
    m = {k: vec(v) for k, v in cells.items()}
    if all(x is not None for x in m.values()):
        order = ((m[("43", "43")] - m[("43", "1016")]) + (m[("1016", "43")] - m[("1016", "1016")])) / 2
        init = ((m[("43", "43")] - m[("1016", "43")]) + (m[("43", "1016")] - m[("1016", "1016")])) / 2
        inter = ((m[("43", "43")] - m[("43", "1016")]) - (m[("1016", "43")] - m[("1016", "1016")])) / 2
        out["init_vs_order_2x2"] = {"cells_ok": {f"init{k[0]}_order{k[1]}": round(100 * float(v.mean()), 2) for k, v in m.items()},
                                    "order_effect(43−1016)": {"pp": round(100 * order.mean(), 2), "ci95": ci(order)},
                                    "init_effect(43−1016)": {"pp": round(100 * init.mean(), 2), "ci95": ci(init)},
                                    "interaction": {"pp": round(100 * inter.mean(), 2), "ci95": ci(inter)}}
    else:
        out["init_vs_order_2x2"] = {"missing": [v for k, v in cells.items() if m[k] is None]}
    seeds = {}
    for arm, ms in (("F", ("F43e1", "F1016e1", "D_F7q100")), ("P", ("P43e1", "P1016e1", "D_P7q100"))):
        vals = {x: mean(x) for x in ms}
        got = [v for v in vals.values() if v is not None]
        seeds[arm] = {"per_seed": vals, "mean": round(float(np.mean(got)), 2), "sd": round(float(np.std(got, ddof=1)), 2) if len(got) > 1 else None, "n_seeds": len(got)}
    seeds["same_seed_P_minus_F"] = {s: diff(p, f) for s, f, p in (("43", "F43e1", "P43e1"), ("1016", "F1016e1", "P1016e1"), ("7", "D_F7q100", "D_P7q100"))}
    out["seed_set"] = seeds
    traj = {}
    for d, e1 in (("D_F7", None), ("D_P7", None), ("D_F43o1016", None), ("D_F1016o43", None)):
        traj[d] = {f"q{q}_greedy": mean(f"{d}q{q}G") for q in ("25", "50", "75")} | {"q100_k4": mean(f"{d}q100")}
    out["epoch1_trajectory"] = traj
    out["greedy_vs_sampling"] = {mm: {"greedy_k1": mean(g), "sampling_k4": mean(s)} for mm, g, s in
                                 (("base", "baseG", "base"), ("F43", "F43G", "F43e1"), ("F1016", "F1016G", "F1016e1"), ("P43", "P43G", "P43e1"), ("P1016", "P1016G", "P1016e1"))}
    out["greedy_s43_minus_s1016"] = {"F": diff("F43G", "F1016G"), "P": diff("P43G", "P1016G")}
    out["d_avg"] = {"D_avg": mean("D_avg"), "vs_F43e1": diff("D_avg", "F43e1"), "vs_F1016e1": diff("D_avg", "F1016e1"), "vs_base": diff("D_avg", "base")}
    (HERE / "a1_variance.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
