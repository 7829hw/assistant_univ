"""x12_tree.py(트리 계산)가 x12_score.py(순차 계산, X1 결과)와 같은 값을 내는지 확인한다. CPU 전용. 기준은 결과를 보기 전에 정했다.

    python tree_check.py TREE.jsonl X1.jsonl OUT.json
겹치는 (reader, writer, id)에서: 겹침 ≥ 100건, |ΔΔ| 최대 ≤ 0.10, 중앙값 ≤ 0.02, |Δ_순차| ≥ 0.1인 행의 Δ 부호 100% 일치,
logp_loc_given_cont(둘 다 > −20인 행) |차| 최대 ≤ 0.10. 하나라도 어기면 종료 코드 1(레인이 멈추고 X2는 순차 계산 안으로 돌아간다).
"""
import json
import sys

import numpy as np



def load(p):
    """쓰는 중인 파일일 수 있으므로 끝의 덜 쓴 줄은 건너뛴다."""
    out = {}
    for line in open(p, encoding="utf-8"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        out[(d["reader"], d["writer"], d["id"])] = d
    return out


tree, seq = load(sys.argv[1]), load(sys.argv[2])
keys = sorted(set(tree) & set(seq))
dd = np.array([abs(tree[k]["delta"] - seq[k]["delta"]) for k in keys]) if keys else np.array([np.inf])
big = [k for k in keys if abs(seq[k]["delta"]) >= 0.1]
sign = float(np.mean([(tree[k]["delta"] > 0) == (seq[k]["delta"] > 0) for k in big])) if big else 0.0
lk = [k for k in keys if tree[k]["logp_loc_given_cont"] > -20 and seq[k]["logp_loc_given_cont"] > -20]
dl = np.array([abs(tree[k]["logp_loc_given_cont"] - seq[k]["logp_loc_given_cont"]) for k in lk]) if lk else np.array([0.0])
fw = [seq[k]["forwards"] for k in keys]
res = {"overlap": len(keys), "readers": len({k[0] for k in keys}), "delta_absdiff_max": float(dd.max()), "delta_absdiff_median": float(np.median(dd)),
       "delta_absdiff_p99": float(np.quantile(dd, 0.99)), "sign_agree_absdelta_ge_0.1": sign, "n_sign_rows": len(big),
       "loc_absdiff_max": float(dl.max()), "loc_absdiff_median": float(np.median(dl)), "n_loc_rows": len(lk),
       "seq_forwards_mean": float(np.mean(fw)) if fw else None,
       "tree_depths_mean": float(np.mean([tree[k]["tree_depths"] for k in keys])) if keys else None,
       "tree_nodes_mean": float(np.mean([tree[k]["tree_nodes"] for k in keys])) if keys else None}
res["pass"] = bool(len(keys) >= 100 and res["delta_absdiff_max"] <= 0.10 and res["delta_absdiff_median"] <= 0.02 and sign == 1.0
                   and res["loc_absdiff_max"] <= 0.10)
open(sys.argv[3], "w", encoding="utf-8").write(json.dumps(res, indent=1) + "\n")
print(json.dumps(res))
sys.exit(0 if res["pass"] else 1)
