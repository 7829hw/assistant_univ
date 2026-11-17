"""X1-H·X2 분석(PREREGISTRATION 3.3·3.4). CPU 전용. 결과를 보기 전에 쓰고 커밋한다.

    python x2_analyze.py MAIN_REPO
입력(training/generated/topic2_dissociation/x12/): x1_self_final18.jsonl(순차, 자기 풀이), x2_final18_p{1,2}.jsonl(트리, 18×18),
x2_base.jsonl(트리, base 행), x2_bopt.jsonl(트리, B안 행), x1_mid54.jsonl(트리, 중간 체크포인트가 같은 run 최종 풀이를 받음).
렌더링 검증의 재토큰화 길이 차이 출력(x12/render_check.json len_diff)은 모두 뺀다.
p0.6 = σ(Δ/0.6).

등록 문구를 계산으로 옮기며 정한 해석(결과 보기 전, 2026-11-17 23:50 KST):
- X1-H: 대상 = 분석 양식·적용 조건을 만족하고(writer_prefixes) 풀이가 지역 조건을 서술한(features의 states_region_condition) 출력, 18 run 합산.
  지지 = 합산 비율 차(자기 Δ<0 비율 − base Δ<0 비율) ≥ +0.20. 자기 값은 X1(순차), base 값은 X2 base 행(트리)(AMENDMENTS §1).
  run별 차와 그 부호 뒤집기 검정(2^18)은 기술로 함께 적는다.
- X2 분해: M_ij = 풀이 작성자 i의 적용 문항에서 답안 모델 j의 p0.6 평균. 대각도 트리 값(AMENDMENTS §1).
  SS_행 = 18·Σ(행평균−전체)², SS_열 = 18·Σ(열평균−전체)², SS_상호작용 = 나머지. 비중 = 각 SS / 전체 SS.
  bootstrap: 147 대상 문항 id를 복원 추출(2,000회, default_rng(20261116)), 각 칸은 뽑힌 문항(중복 포함)의 그 작성자 행으로 다시 평균.
  95% CI = 2.5·97.5 백분위. 판정은 점 추정(등록 그대로).
- 3원 분해(보조): 18 작성자 모두에 적용되는 공통 문항에서 문항 × 작성자 × 답안. 주효과 3개, 2원 상호작용 3개, 나머지(3원). 칸마다 관측 1개.
- 질문 2 연결: 답안 모델 열 평균 M_·j(대각 포함)와 그 run의 지표 1(기존 기록, x3/x3_results.json의 orig.m1_refusal)의 Spearman을
  arm마다 따로(각 n = 9) 계산한다. "따로 움직인다" 지지 = 두 arm 모두 |ρ| < 0.30. 보조로 arm 중심화(arm 평균을 뺀 값) 18점 Spearman과
  arm 사이 차이(열 평균의 arm 평균 차, 지표 1의 arm 평균 차)를 적는다.
- 중간 체크포인트(기술): run마다 체크포인트(496·992·1488·1984)별 평균 p0.6. 1984는 X1 자기 값(순차). arm별 평균과 run 간 SD.
  496·992·1488은 "자기 풀이가 아니라 같은 run 최종 어댑터의 풀이"다.
- B안 행(기술): B안 어댑터가 18 작성자의 풀이를 받은 p0.6 평균(작성자별·전체). 최종 18 열 평균과 나란히 적는다.
출력: dissociation/x12/x2_results.json
"""
import contextlib
import importlib.util
import io
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

main = Path(sys.argv[1]).resolve()
D = main / "topic2_semantic_order/dissociation"
X = main / "training/generated/topic2_dissociation"
spec = importlib.util.spec_from_file_location("fdc", D / "fare_dissociation_check.py")
fdc = importlib.util.module_from_spec(spec)
argv, sys.argv = sys.argv, ["x", str(main)]
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(fdc)
sys.argv = argv
need = list(fdc.need)
assert len(need) == 147
RUNS = [f"{a}-{s}-r{r}" for a, s, r in fdc.RUNS]
excl = {(r[0], r[1]) for r in json.loads((D / "x12/render_check.json").read_text())["summary"]["len_diff"]}
p06 = lambda d: 1 / (1 + math.exp(-d / 0.6))


def load(name):
    rows = [json.loads(line) for line in open(X / "x12" / name, encoding="utf-8")]
    keys = [(r["reader"], r["writer"], r["id"]) for r in rows]
    assert len(set(keys)) == len(keys), f"{name}: 중복"
    return {(r["reader"], r["writer"], r["id"]): r for r in rows if (r["writer"], r["id"]) not in excl}


wp = [json.loads(line) for line in open(X / "writer_prefixes.jsonl", encoding="utf-8")]
items = {w: [] for w in RUNS}
for r in wp:
    if (r["writer"], r["id"]) not in excl:
        items[r["writer"]].append(r["id"])
n_items = sum(len(v) for v in items.values())

x1 = load("x1_self_final18.jsonl")
x2 = {**load("x2_final18_p1.jsonl"), **load("x2_final18_p2.jsonl")}
base = load("x2_base.jsonl")
bopt = load("x2_bopt.jsonl")
mid = load("x1_mid54.jsonl")
assert len(x2) == 18 * n_items, (len(x2), n_items)
assert len(base) == n_items and len(bopt) == n_items and len(x1) == n_items and len(mid) == 3 * n_items
res = {"n_writer_items": n_items, "excluded_len_diff": len(excl)}

# ---------- X1-H ----------
region = {}
for run, (a, s, rr) in zip(RUNS, fdc.RUNS):
    raw = fdc.load_raw(fdc.raw_path(a, s, rr))
    for i in items[run]:
        f = fdc.features(raw[i], fdc.T1[i])
        assert f["template"] == "analysis"
        region[(run, i)] = f["states_region_condition"]
sel = [(w, i) for w in RUNS for i in items[w] if region[(w, i)]]
self_neg = np.array([x1[(w, w, i)]["delta"] < 0 for w, i in sel])
base_neg = np.array([base[("base", w, i)]["delta"] < 0 for w, i in sel])
per = {}
for w in RUNS:
    idx = [k for k, (ww, _) in enumerate(sel) if ww == w]
    per[w] = {"n": len(idx), "self_share_delta_neg": float(self_neg[idx].mean()), "base_share_delta_neg": float(base_neg[idx].mean()),
              "diff": float(self_neg[idx].mean() - base_neg[idx].mean())}
d = np.array([per[w]["diff"] for w in RUNS])
signs = np.array(list(itertools.product((1, -1), repeat=18)), dtype=np.int8)
pflip = lambda v: float(np.mean(np.abs(signs @ v) / len(v) >= abs(v.mean()) - 1e-12))
res["X1H"] = {"n_region_stating": len(sel), "n_analysis_applicable": n_items,
              "self_share_delta_neg": float(self_neg.mean()), "base_share_delta_neg": float(base_neg.mean()),
              "diff": float(self_neg.mean() - base_neg.mean()), "threshold": 0.20,
              "supported": bool(self_neg.mean() - base_neg.mean() >= 0.20),
              "per_run": per, "per_run_diff_mean": float(d.mean()), "per_run_p_signflip_two_sided": pflip(d),
              "by_arm": {arm: {k: float(np.mean([per[w][k] for w in RUNS if w[0] == arm]))
                               for k in ("self_share_delta_neg", "base_share_delta_neg", "diff")} for arm in "AB"}}

# ---------- X2 행렬 ----------
P = {k: p06(r["delta"]) for k, r in x2.items()}
DL = {k: r["delta"] for k, r in x2.items()}


pos = {i: k for k, i in enumerate(need)}
APPL = np.zeros((18, len(need)))
for a, w in enumerate(RUNS):
    for i in items[w]:
        APPL[a, pos[i]] = 1.0


def tensor(val):
    T = np.zeros((18, 18, len(need)))   # [작성자, 답안, 문항], 적용 안 되는 칸 0
    for a, w in enumerate(RUNS):
        for b, rd in enumerate(RUNS):
            for i in items[w]:
                T[a, b, pos[i]] = val[(rd, w, i)]
    return T


TEN = {}


def matrix(val, counts):
    """counts: id → 가중(복원 추출 횟수). M_ab = Σ_k c_k·T[a,b,k] / Σ_k c_k·적용[a,k]."""
    key = id(val)
    if key not in TEN:
        TEN[key] = tensor(val)
    c = np.array([counts.get(i, 0) for i in need], float)
    return (TEN[key] @ c) / (APPL @ c)[:, None]


def decomp(M):
    g = M.mean()
    rm, cm = M.mean(1) - g, M.mean(0) - g
    tot = ((M - g) ** 2).sum()
    ssr, ssc = M.shape[1] * (rm ** 2).sum(), M.shape[0] * (cm ** 2).sum()
    return {"writer": ssr / tot, "reader": ssc / tot, "interaction": (tot - ssr - ssc) / tot, "ss_total": float(tot)}


def verdict(s):
    if s["reader"] >= 0.50 and s["reader"] >= 2.5 * s["writer"]:
        return "답안 모델 주도"
    if s["writer"] >= 0.50 and s["writer"] >= 2.5 * s["reader"]:
        return "풀이 주도"
    return "혼합"


ones = {i: 1 for i in need}
out = {}
for name, val in (("p06", P), ("delta", DL)):
    M = matrix(val, ones)
    s = decomp(M)
    out[name] = {"matrix": M.tolist(), "shares": s, "row_means": M.mean(1).tolist(), "col_means": M.mean(0).tolist(), "grand": float(M.mean())}
rng = np.random.default_rng(20261116)
boot = {"p06": [], "delta": []}
for _ in range(2000):
    pick = rng.integers(0, len(need), len(need))
    cnt = {}
    for k in pick:
        cnt[need[k]] = cnt.get(need[k], 0) + 1
    for name, val in (("p06", P), ("delta", DL)):
        boot[name].append(decomp(matrix(val, cnt)))
for name in boot:
    out[name]["ci95"] = {k: [float(np.percentile([b[k] for b in boot[name]], 2.5)), float(np.percentile([b[k] for b in boot[name]], 97.5))]
                         for k in ("writer", "reader", "interaction")}
    out[name]["verdict_rule_share_of_boot"] = {v: float(np.mean([verdict(b) == v for b in boot[name]])) for v in ("답안 모델 주도", "풀이 주도", "혼합")}
out["p06"]["verdict"] = verdict(out["p06"]["shares"])
out["delta"]["verdict_aux"] = verdict(out["delta"]["shares"])
res["X2"] = out

# 3원(공통 문항)
common = [i for i in need if all(i in set(items[w]) for w in RUNS)]
Y = np.array([[[P[(rd, w, i)] for rd in RUNS] for w in RUNS] for i in common])
g = Y.mean()
mi, mw, mr = Y.mean((1, 2)) - g, Y.mean((0, 2)) - g, Y.mean((0, 1)) - g
iw = Y.mean(2) - g - mi[:, None] - mw[None, :]
ir = Y.mean(1) - g - mi[:, None] - mr[None, :]
wr = Y.mean(0) - g - mw[:, None] - mr[None, :]
tot = ((Y - g) ** 2).sum()
nI, nW, nR = Y.shape
ss = {"item": nW * nR * (mi ** 2).sum(), "writer": nI * nR * (mw ** 2).sum(), "reader": nI * nW * (mr ** 2).sum(),
      "item_x_writer": nR * (iw ** 2).sum(), "item_x_reader": nW * (ir ** 2).sum(), "writer_x_reader": nI * (wr ** 2).sum()}
ss["residual_3way"] = tot - sum(ss.values())
res["X2_threeway_common"] = {"n_common_items": len(common), "shares": {k: float(v / tot) for k, v in ss.items()}}


# ---------- 질문 2 연결 ----------
def ranks(x):
    x = np.asarray(x, float)
    o = np.argsort(x, kind="mergesort")
    rk = np.empty(len(x))
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[o[j + 1]] == x[o[i]]:
            j += 1
        rk[o[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return rk


sp = lambda a, b: float(np.corrcoef(ranks(a), ranks(b))[0, 1])
m1 = {r["run"]: r["orig"]["m1_refusal"] for r in json.loads((D / "x3/x3_results.json").read_text())["runs"]}
col = dict(zip(RUNS, out["p06"]["col_means"]))
q2 = {"per_arm": {}}
for arm in "AB":
    ws = [w for w in RUNS if w[0] == arm]
    q2["per_arm"][arm] = {"n": len(ws), "spearman": sp([col[w] for w in ws], [m1[w] for w in ws]),
                          "col_mean_avg": float(np.mean([col[w] for w in ws])), "m1_avg": float(np.mean([m1[w] for w in ws]))}
q2["supported_separate"] = all(abs(q2["per_arm"][a]["spearman"]) < 0.30 for a in "AB")
cc = [col[w] - q2["per_arm"][w[0]]["col_mean_avg"] for w in RUNS]
mc = [m1[w] - q2["per_arm"][w[0]]["m1_avg"] for w in RUNS]
q2["arm_centered_spearman_18"] = sp(cc, mc)
q2["between_arm"] = {"col_mean_B_minus_A": q2["per_arm"]["B"]["col_mean_avg"] - q2["per_arm"]["A"]["col_mean_avg"],
                     "m1_B_minus_A": q2["per_arm"]["B"]["m1_avg"] - q2["per_arm"]["A"]["m1_avg"]}
q2["per_run"] = {w: {"col_mean_p06": col[w], "m1_refusal": m1[w]} for w in RUNS}
res["Q2_link"] = q2

# ---------- 중간 체크포인트 ----------
traj = {}
for w in RUNS:
    t = {}
    for ck in (496, 992, 1488):
        t[str(ck)] = float(np.mean([p06(mid[(f"{w}@{ck}", w, i)]["delta"]) for i in items[w]]))
    t["1984"] = float(np.mean([p06(x1[(w, w, i)]["delta"]) for i in items[w]]))
    traj[w] = t
res["mid_trajectory"] = {"per_run": traj, "note": "496·992·1488은 같은 run 최종 어댑터의 풀이를 받은 값(자기 풀이 아님); 1984는 X1 자기 값(순차)",
                         "by_arm": {arm: {ck: {"mean": float(np.mean([traj[w][ck] for w in RUNS if w[0] == arm])),
                                               "sd_runs": float(np.std([traj[w][ck] for w in RUNS if w[0] == arm], ddof=1))}
                                          for ck in ("496", "992", "1488", "1984")} for arm in "AB"}}

# ---------- B안 행·base 행 ----------
for key, rows, rname in (("Bopt_row", bopt, next(iter(bopt))[0]), ("base_row", base, "base")):
    pw = {w: float(np.mean([p06(rows[(rname, w, i)]["delta"]) for i in items[w]])) for w in RUNS}
    res[key] = {"reader": rname, "per_writer": pw, "mean_over_writers": float(np.mean(list(pw.values()))),
                "share_delta_neg_all": float(np.mean([r["delta"] < 0 for r in rows.values()]))}
res["final18_col_means_by_arm"] = {arm: float(np.mean([col[w] for w in RUNS if w[0] == arm])) for arm in "AB"}

(D / "x12/x2_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
h = res["X1H"]
print(f"X1-H: 지역 서술 {h['n_region_stating']}/{n_items}, 자기 Δ<0 {100*h['self_share_delta_neg']:.1f}% base {100*h['base_share_delta_neg']:.1f}% "
      f"차 {100*h['diff']:+.1f}%p → {'지지' if h['supported'] else '지지 안 됨'}; run별 차 평균 {100*h['per_run_diff_mean']:+.1f}%p p={h['per_run_p_signflip_two_sided']:.2g}")
for name in ("p06", "delta"):
    s, c = out[name]["shares"], out[name]["ci95"]
    print(f"X2 {name}: 작성자 {s['writer']:.3f} {c['writer']}, 답안 {s['reader']:.3f} {c['reader']}, 상호작용 {s['interaction']:.3f} {c['interaction']}")
print("판정:", out["p06"]["verdict"], out["p06"]["verdict_rule_share_of_boot"])
print("3원:", res["X2_threeway_common"])
print("Q2:", json.dumps({k: v for k, v in q2.items() if k != "per_run"}, ensure_ascii=False))
print("궤적:", json.dumps(res["mid_trajectory"]["by_arm"], ensure_ascii=False))
print("B안 행:", res["Bopt_row"]["mean_over_writers"], "base 행:", res["base_row"]["mean_over_writers"], "최종18 열:", res["final18_col_means_by_arm"])
