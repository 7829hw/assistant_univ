"""AUC 게이트(PREREGISTRATION 3.2-3). CPU 전용.

    python auc_gate.py MAIN_REPO
입력: training/generated/topic2_dissociation/x12/x1_self_final18.jsonl (reader == writer, 최종 18 어댑터).
렌더링 검증에서 재토큰화 길이가 다른 출력(x12/render_check.json len_diff)은 뺀다.
통과 = 합산 AUC(Δ로 기록된 LOCATION 방출 예측) ≥ 0.80 그리고 실행별 평균 p0.6(= σ(Δ/0.6))와 실행별 실제 방출률의 Spearman ρ ≥ 0.90.
실행별 AUC는 두 부류가 각각 10건 이상인 실행만 보고한다. 출력: dissociation/x12/auc_gate.json
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

main = Path(sys.argv[1]).resolve()
D = main / "topic2_semantic_order/dissociation"
rows = [json.loads(line) for line in open(main / "training/generated/topic2_dissociation/x12/x1_self_final18.jsonl", encoding="utf-8")]
excl = {(r[0], r[1]) for r in json.loads((D / "x12/render_check.json").read_text())["summary"]["len_diff"]}
n_wp = sum(1 for _ in open(main / "training/generated/topic2_dissociation/writer_prefixes.jsonl", encoding="utf-8"))
assert all(r["reader"] == r["writer"] for r in rows)
keys = [(r["writer"], r["id"]) for r in rows]
assert len(set(keys)) == len(keys), "중복 행"
used = [r for r in rows if (r["writer"], r["id"]) not in excl]


def ranks(x):
    x = np.asarray(x, float)
    order = np.argsort(x, kind="mergesort")
    rk = np.empty(len(x))
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        rk[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return rk


def auc(score, label):
    label = np.asarray(label, bool)
    n1, n0 = label.sum(), (~label).sum()
    r = ranks(score)
    return float((r[label].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def spearman(a, b):
    return float(np.corrcoef(ranks(a), ranks(b))[0, 1])


p06 = lambda d: 1 / (1 + math.exp(-d / 0.6))
res = {"rows_scored": len(rows), "writer_prefixes": n_wp, "excluded_len_diff": len(rows) - len(used), "rows_used": len(used)}
res["pooled_auc"] = auc([r["delta"] for r in used], [r["emitted"] for r in used])
per = {}
for r in used:
    per.setdefault(r["writer"], []).append(r)
pr = {}
for k, v in sorted(per.items()):
    em = [x["emitted"] for x in v]
    e = {"n": len(v), "emitted": int(sum(em)), "emission_rate": float(np.mean(em)), "mean_p06": float(np.mean([p06(x["delta"]) for x in v])),
         "mean_delta": float(np.mean([x["delta"] for x in v])), "share_delta_neg": float(np.mean([x["delta"] < 0 for x in v]))}
    if sum(em) >= 10 and len(em) - sum(em) >= 10:
        e["auc"] = auc([x["delta"] for x in v], em)
    pr[k] = e
res["per_run"] = pr
res["spearman_meanp06_vs_emission"] = spearman([e["mean_p06"] for e in pr.values()], [e["emission_rate"] for e in pr.values()])
res["n_runs"] = len(pr)
res["agreement_sign_delta_vs_emitted"] = float(np.mean([(r["delta"] > 0) == r["emitted"] for r in used]))
res["gate"] = {"pooled_auc_ge_0.80": res["pooled_auc"] >= 0.80, "spearman_ge_0.90": res["spearman_meanp06_vs_emission"] >= 0.90}
res["gate"]["pass"] = all(res["gate"].values()) and len(pr) == 18 and len(rows) == n_wp
(D / "x12/auc_gate.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "per_run"}, ensure_ascii=False, indent=1))
for k, e in pr.items():
    print(f"{k:<14} n={e['n']:3d} 방출 {100 * e['emission_rate']:5.1f}%  평균 p0.6 {100 * e['mean_p06']:5.1f}%  Δ<0 {100 * e['share_delta_neg']:5.1f}%  AUC {e.get('auc', float('nan')):.3f}")
