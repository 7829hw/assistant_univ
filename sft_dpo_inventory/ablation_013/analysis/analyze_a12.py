# -*- coding: utf-8 -*-
"""ablation_012 분석(결정 262, PLAN_A12 5절). **진단, 판정 아님.** 모델 호출 없음.
ablation_011 고정 도구의 사본(``core_a11copy.py`` = analyze_a11, ``xtab_a12.py`` = xtab_a11)의 함수를 그대로 쓴다:
E1 표본 값 = ``load_model``(compute_gates.load_arm 견고성 패치 ok·U, compute_p9.sample_values refused), 짝 bootstrap = ``boot_paired``, soup CI = ``boot_soup``.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_012/analysis/analyze_a12.py            # -> analysis/results_a12.json
    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_012/analysis/analyze_a12.py --smoke    # -> analysis/smoke_a12.json(기존 셀만: ablation_011·client_test_10000)

1. A3 분리(E1·H-dev): (A3 − A0), (A3R − A0), (A3 − A3R), (A3R-d1 − A3R-d2), (A3R-d1 − A0), (A3R-d2 − A0). 같은 순서 seed 짝, A3R = seed마다 d1·d2 문항 값 평균.
   H-dev 값: match = ``category == "match"``, over = refused(답이 있는 2,000 모두), U = load_arm U. 속도: wall p50·p95, 잘림 호출(점 추정, seed 평균).
   해석 규칙(PLAN 5.1): (A3 − A3R) CI가 0을 포함하지 않으면 "요금 대조 고유 효과", 포함하면 "데이터 양 효과와 구별 안 됨".
   보충(H-dev): A1 − A0, A2 − A0(ablation_011 arm의 넓은 셋 확인).
2. V4 seed 일관성(CT10K 6 seed): seed별 정답률(match), 30문항 이상 template_group별 seed 정답률, 붕괴(seed < base 3회 평균 − 20pp) 수, seed sd 상위 20,
   그 그룹의 학습 데이터 관련(서명 = 분석 tool | 시간 단위 | 지역 유형 + metric; 학습 쪽은 corpus ``execution``, 없으면 ``view.measure.subtype``→tool) 레코드 수와 순서 위치, o43형 붕괴 그룹.
   H-dev 같은 표(보조).
3. soup(CT10K): soup − o43·o1016·o7 문항 짝(문항 재추출 bootstrap 10,000), o43 붕괴 그룹의 soup 정답률, soup − 6 seed 평균(``boot_soup``).
4. 검정력 모의(PLAN 5.4): 안 2·안 3, seed 수 3·5·8, 모의 400 × bootstrap 1,000.
5. 과잉 거부 유형(D6): A0 3 seed + V4 o43·o1016·o7의 거부 표본, E1·CT10K·H-dev, ``xtab_a12.xtab`` + get_trip_metrics·get_billing_metrics 세부(metric·aggregation·시간·지역).
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core_a11copy as CORE  # noqa: E402  (sys.path에 ROOT·gates 경로를 넣는다)
import xtab_a12 as XT  # noqa: E402

ROOT = CORE.ROOT
INV = ROOT / "sft_dpo_inventory"
A12C = "sft_dpo_inventory/ablation_012/cells"
CTD = "sft_dpo_inventory/client_test_10000"
CT_GOLD = f"{CTD}/qa_test_10000.yaml"
HDEV_GOLD = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
NEW, OLD = CORE.NEW_SEEDS, CORE.OLD_SEEDS
REPS, RNG_SEED = CORE.REPS, CORE.RNG_SEED
MIN_TG = 30
COLLAPSE_PP = 20
O43_GROUPS = ("1c3cb876", "449f5bf2", "6c262dd5", "cd5fe2f2")  # client_test_10000 RESULTS 4절
TOOL = {"revenue": "get_billing_metrics", "active_taxi_count": "get_billing_metrics", "active_taxi_ratio": "get_billing_metrics", "operating_days": "get_billing_metrics",
        "trip_count": "get_trip_count", "passage_count": "get_passage_count", "place": "get_scope_name"}
SIM_N, SIM_B, SIM_SEEDS = 400, 1000, (3, 5, 8)
DELTAS = {"acc": (0.0, -0.02, -0.03), "over": (0.0, 0.01), "ref": (0.0, -0.05)}
PLAN2 = {"acc": ("lower", -0.03), "ref": ("lower", -0.05), "over": ("upper", 0.015)}
PLAN3 = {"broad_vs_base_pp": 5.0, "collapse_pp": 20.0, "e1_over_max": 0.030, "e1_ref_min": 0.850}
# 안 3 붕괴 조건 변형(초안 비교용; CRITERIA_v2_DRAFT에서 고름, 확정 안 함): (이름, 붕괴 기준 pp, 허용 붕괴 그룹 수)
PLAN3_VARIANTS = (("strict_20pp_0", 20.0, 0), ("allow5_20pp", 20.0, 5), ("pp30_0", 30.0, 0))


def pp(x):
    return CORE.pp(x)


# ---------- 셀 경로 ----------
def e1_cells(group, seed):
    if group in ("A0", "A3", "A1", "A2"):
        return CORE.new_cells(f"a11_{group.lower()}_{seed}")
    lab = {"valid98": "valid98", "aux": "aux", "rdev": "rdevv2"}
    tag = {"A3R-d1": "a3rd1", "A3R-d2": "a3rd2"}[group]
    return {st: [f"{A12C}/a12_{tag}_{seed}_{lab[st]}_s{k}.json" for k in range(1, 5)] for st in CORE.SETS}


def hd_key(n):
    """분석 이름(A0_o1102·A3R-d1_o1102·V4_o43·soup·base_k1) → H-dev 셀 이름 조각(make_jobs_a12: hdev_<cid의 - → _, 소문자>)."""
    return n if n.startswith("base_k") else n.replace("-", "_").lower()


def hdev_cell(name):
    return f"{A12C}/hdev_{name}_s1.json" if not name.startswith("base_k") else f"{A12C}/hdev_base_s{name[-1]}.json"


def ct_cells(name):
    if name in OLD:
        return [f"{CTD}/cells/ct10k_v4_{name}_c{c}_s1.json" for c in range(1, 6)]
    if name.startswith("base_k"):
        return [f"{CTD}/cells/ct10k_base_c{c}_s{name[-1]}.json" for c in range(1, 6)]
    return [f"{A12C}/ct10k_{name}_c{c}_s1.json" for c in range(1, 6)]


def exists(paths):
    return all((ROOT / p).exists() for p in paths)


def _ts(x):
    return datetime.fromisoformat(x).timestamp()


# ---------- 넓은 셋(H-dev·CT10K) 로더 ----------
_U_GOLD = set()


def install_u_gold(gold_path):
    """U 등급(grounding_v13 ``report.unacceptable``)은 문항 key를 ``dev/<id>``로 보고 ``grounding_v9.compare._gold("dev")``(vendor100 gold)에서 찾는다.
    H-dev·CT10K id(CLIENT-·SYN-…)는 vendor100 id('001'…)와 겹치지 않으므로, 그 캐시(``_GOLD["dev"]``)에 이 셋의 문항을 더해 같은 U 규칙을 적용한다(파일은 그대로)."""
    if gold_path in _U_GOLD:
        return
    import compute_gates as CG
    import evaluate_vendor100 as EV
    C = CG.scorer().C.R.C
    dev = C._gold("dev", None)
    extra = {i["id"]: i for i in EV.load_gold(ROOT / gold_path)["items"]}
    if set(extra) & set(dev):
        raise SystemExit("broad set ids overlap vendor100 ids")
    dev.update(extra)
    _U_GOLD.add(gold_path)


def load_broad(paths, gold_path, with_u=True):
    import compute_gates as CG
    import compute_p9 as C9
    match, refused, walls, trunc, rows_n = {}, {}, [], 0, 0
    for p in paths:
        d = json.loads((ROOT / p).read_text(encoding="utf-8"))
        for r in d["rows"]:
            match[r["id"]] = r.get("category") == "match"
            rows_n += 1
            if r.get("started_at") and r.get("finished_at"):
                walls.append(_ts(r["finished_at"]) - _ts(r["started_at"]))
            trunc += sum(1 for x in (r.get("hf_calls") or []) if x.get("finish_reason") == "length")
        for i, v in C9.sample_values(p).items():
            refused[i] = bool(v["refused"])
    U = {}
    if with_u:
        install_u_gold(gold_path)
        items, mats, _ = CG.load_arm({"b": list(paths)}, {"b": gold_path}, with_tokens=False)
        for key, u in zip(items, mats["U"]):
            U[key.split("/", 1)[1]] = float(u)
    return {"match": match, "refused": refused, "U": U, "speed": {"rows": rows_n, "wall_p50_s": round(float(np.percentile(walls, 50)), 2),
                                                                  "wall_p95_s": round(float(np.percentile(walls, 95)), 2), "truncated_calls": trunc}}


def vec(m, key, ids):
    return np.array([float(m[key][i]) for i in ids])


# ---------- 비교 ----------
def compare(X, Y, seeds, metrics):
    """X, Y: {seed: {metric: 문항 벡터}} → 지표마다 차·CI·seed별 차."""
    out = {"seed_pairs": list(seeds)}
    for met in metrics:
        point, ci = CORE.boot_paired([X[s][met] for s in seeds], [Y[s][met] for s in seeds], np.random.default_rng(RNG_SEED))
        out[met] = {"diff_pp": pp(point), "ci95_pp": [pp(ci[0]), pp(ci[1])], "x_pct": pp(np.mean([X[s][met].mean() for s in seeds])),
                    "y_pct": pp(np.mean([Y[s][met].mean() for s in seeds])), "per_seed_diff_pp": {s: pp(X[s][met].mean() - Y[s][met].mean()) for s in seeds},
                    "ci_excludes_0": bool(ci[0] > 0 or ci[1] < 0)}
    return out


def avg_models(a, b):
    return {k: (a[k] + b[k]) / 2 for k in a}


def speed_mean(speeds):
    return {k: round(float(np.mean([s[k] for s in speeds])), 2) for k in ("wall_p50_s", "wall_p95_s", "truncated_calls")}


def e1_vectors(o):
    return {met: f(o) for met, f in CORE.ITEM_VEC.items()}


# ---------- 1. A3 분리 ----------
def a3_split(models, speeds, metrics, U_samples=None):
    seeds = [s for s in NEW if all(f"{g}_{s}" in models for g in ("A0", "A3", "A3R-d1", "A3R-d2"))]
    res = {"seeds_complete": seeds}
    if not seeds:
        return res
    A0 = {s: models[f"A0_{s}"] for s in seeds}
    A3 = {s: models[f"A3_{s}"] for s in seeds}
    D1 = {s: models[f"A3R-d1_{s}"] for s in seeds}
    D2 = {s: models[f"A3R-d2_{s}"] for s in seeds}
    R = {s: avg_models(D1[s], D2[s]) for s in seeds}
    comps = {"A3-A0": (A3, A0), "A3R-A0": (R, A0), "A3-A3R": (A3, R), "A3Rd1-A3Rd2": (D1, D2), "A3Rd1-A0": (D1, A0), "A3Rd2-A0": (D2, A0)}
    for name, (x, y) in comps.items():
        res[name] = compare(x, y, seeds, metrics)
    interp = {}
    for met in metrics:
        c = res["A3-A3R"][met]
        interp[met] = "요금 대조 고유 효과" if c["ci_excludes_0"] else "데이터 양 효과와 구별 안 됨"
    res["interpretation_A3_minus_A3R"] = interp
    sp = {}
    for g in ("A0", "A3", "A3R-d1", "A3R-d2"):
        sp[g] = speed_mean([speeds[f"{g}_{s}"] for s in seeds])
    sp["A3R"] = {k: round((sp["A3R-d1"][k] + sp["A3R-d2"][k]) / 2, 2) for k in sp["A0"]}
    res["speed_seed_mean"] = sp
    if U_samples:
        res["U_samples_per_model"] = {g: [U_samples[f"{g}_{s}"] for s in seeds] for g in ("A0", "A3", "A3R-d1", "A3R-d2")}
    return res


# ---------- 2·3. CT10K seed 일관성·soup ----------
def tg_groups(gold, ids):
    tg = defaultdict(list)
    for i in ids:
        tg[gold[i]["template_group"]].append(i)
    return tg


def train_signatures():
    """V4 학습 레코드 → (tool, metric, time, region) 서명과 순서 위치(seed별 정규화 위치)."""
    sys.path.insert(0, str(INV / "pilot_007/train_data"))
    import order7b
    recs = [json.loads(l) for l in (INV / "pilot_010/build/V4/full/sft_train.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    corpus = {r["id"]: r for r in (json.loads(l) for l in (INV / "pilot_006_prep/approved/approved_train_v6.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
    sub_tool = defaultdict(Counter)  # execution이 있는 질문에서 measure subtype → 분석 tool(다수)
    for x in corpus.values():
        ex = x.get("execution")
        sub = ((x.get("view") or {}).get("measure") or {}).get("subtype")
        if ex and sub:
            sub_tool[sub][XT.classify(ex)[0]] += 1
    sub_map = {k: v.most_common(1)[0][0] for k, v in sub_tool.items()}
    sig = {}
    for r in recs:
        q = r["metadata"]["source_record_id"]
        x = corpus[q]
        if r["metadata"].get("refusal_source"):
            sig[q] = ("refusal", None, None, None)
            continue
        ex = x.get("execution")
        if ex:
            tool, tu, rg = XT.classify(ex)
            an = next((c for c in ex if c.get("tool") != "get_place_scope"), {})
            sig[q] = (tool, (an.get("args") or {}).get("metric"), tu, rg)
        else:
            sub = ((x.get("view") or {}).get("measure") or {}).get("subtype")
            sig[q] = (sub_map.get(sub, TOOL.get(sub, f"기타({sub})")), None, None, None)
    key = lambda r: f"{r['metadata']['source_record_id']}|{r['metadata']['trace_id']}"  # noqa: E731
    orders = {}
    for s, f in (("o43", "order_b2_o43.json"), ("o1016", "order_b2_o20261016.json"), ("o7", "order_b2_o7.json")):
        o = json.loads((INV / "pilot_010/build/V4" / f).read_text(encoding="utf-8"))
        orders[s] = [key(r) for r in order7b.order_records(recs, o["order"])]
    for s in NEW:
        orders[s] = json.loads((INV / f"ablation_011/build/orders/record_order_A0_o{s.lstrip('o')}.json").read_text(encoding="utf-8"))["record_sequence"]
    return sig, orders, len(recs)


def group_signature(gold, its):
    sigs = Counter()
    for i in its:
        calls = gold[i].get("gold") or []
        tool, tu, rg = XT.classify(calls)
        an = next((c for c in calls if c.get("tool") != "get_place_scope"), {})
        sigs[(tool, (an.get("args") or {}).get("metric"), tu, rg)] += 1
    return sigs


def train_relation(gsig, sig, orders, n_rec):
    (tool, metric, tu, rg), _ = gsig.most_common(1)[0]
    fine = [q for q, v in sig.items() if v == (tool, metric, tu, rg)]
    coarse = [q for q, v in sig.items() if v[0] == tool and (metric is None or v[1] in (metric, None))]
    out = {"group_signature": {"tool": tool, "metric": metric, "time": tu, "region": rg, "share_in_group": round(gsig.most_common(1)[0][1] / sum(gsig.values()), 3)},
           "train_questions_fine": len(fine), "train_questions_tool_metric": len(coarse),
           "train_questions_same_tool": sum(1 for v in sig.values() if v[0] == tool),
           "train_questions_same_time_region_any_tool": sum(1 for v in sig.values() if v[2] == tu and v[3] == rg),
           "positions": {}}
    fq, cq = set(fine), set(coarse)
    for s, seq in orders.items():
        pos_f = [k for k, x in enumerate(seq) if x.split("|", 1)[0] in fq]
        pos_c = [k for k, x in enumerate(seq) if x.split("|", 1)[0] in cq]
        out["positions"][s] = {"records_fine": len(pos_f), "records_tool_metric": len(pos_c),
                               "fine_mean_pos": round(float(np.mean(pos_f)) / n_rec, 3) if pos_f else None,
                               "fine_last10pct": sum(1 for k in pos_f if k >= 0.9 * n_rec), "fine_last25pct": sum(1 for k in pos_f if k >= 0.75 * n_rec),
                               "tool_metric_mean_pos": round(float(np.mean(pos_c)) / n_rec, 3) if pos_c else None,
                               "tool_metric_last10pct": sum(1 for k in pos_c if k >= 0.9 * n_rec), "tool_metric_last25pct": sum(1 for k in pos_c if k >= 0.75 * n_rec)}
    return out


def seed_consistency(gold, mats, v4names, base_names, extra=("soup",), with_train=True, min_tg=MIN_TG):
    ids = sorted(gold)
    acc = {n: 100 * float(np.mean([mats[n]["match"][i] for i in ids])) for n in v4names + base_names + [e for e in extra if e in mats]}
    vals = [acc[n] for n in v4names]
    res = {"items": len(ids), "acc_pct": {n: round(v, 2) for n, v in acc.items()},
           "v4": {"seeds": v4names, "mean_pct": round(float(np.mean(vals)), 2), "sd_pp": round(float(np.std(vals, ddof=1)), 2) if len(vals) > 1 else None,
                  "range_pct": [round(min(vals), 2), round(max(vals), 2)]},
           "base_mean_pct": round(float(np.mean([acc[n] for n in base_names])), 2) if base_names else None}
    tg = tg_groups(gold, ids)
    rows, collapse = [], Counter()
    for g, its in tg.items():
        if len(its) < min_tg:
            continue
        a = {n: 100 * float(np.mean([mats[n]["match"][i] for i in its])) for n in v4names + [e for e in extra if e in mats]}
        b = float(np.mean([100 * np.mean([mats[n]["match"][i] for i in its]) for n in base_names])) if base_names else None
        col = [n for n in v4names if b is not None and a[n] < b - COLLAPSE_PP]
        for n in col:
            collapse[n] += 1
        sv = [a[n] for n in v4names]
        rows.append({"template_group": g, "items": len(its), "by_seed_pct": {n: round(v, 1) for n, v in a.items()}, "base_mean_pct": round(b, 1) if b is not None else None,
                     "sd_pp": round(float(np.std(sv, ddof=1)), 2) if len(sv) > 1 else 0.0, "range_pp": round(max(sv) - min(sv), 1), "collapsed_seeds": col,
                     "o43_type": any(x in g for x in O43_GROUPS)})
    rows.sort(key=lambda r: (-r["sd_pp"], -r["range_pp"], r["template_group"]))
    res["groups_ge_min"] = len(rows)
    res["min_group_items"] = min_tg
    res["collapse_rule"] = f"seed 정답률 < base 평균 − {COLLAPSE_PP}pp(그룹 {min_tg}문항 이상)"
    res["collapse_count_by_seed"] = {n: collapse.get(n, 0) for n in v4names}
    res["collapsed_groups"] = [{k: r[k] for k in ("template_group", "items", "by_seed_pct", "base_mean_pct", "collapsed_seeds")} for r in rows if r["collapsed_seeds"]]
    res["o43_type_groups"] = [{k: r[k] for k in ("template_group", "items", "by_seed_pct", "base_mean_pct", "collapsed_seeds")} for r in rows if r["o43_type"]]
    top = rows[:20]
    if with_train:
        sig, orders, n_rec = train_signatures()
        for r in top:
            its = tg[r["template_group"]]
            r["example"] = gold[its[0]]["question"]
            r["train_relation"] = train_relation(group_signature(gold, its), sig, orders, n_rec)
    res["top20_by_seed_sd"] = top
    return res


def soup_ct(gold, mats, v4names, o43_collapse_groups):
    ids = sorted(gold)
    if "soup" not in mats:
        return None
    s = np.array([float(mats["soup"]["match"][i]) for i in ids])
    out = {"vs_seed": {}}
    for n in OLD:
        if n not in mats:
            continue
        x = np.array([float(mats[n]["match"][i]) for i in ids])
        d = s - x
        rng = np.random.default_rng(RNG_SEED)
        I = len(ids)
        st = np.array([d[rng.integers(0, I, I)].mean() for _ in range(REPS)])
        out["vs_seed"][n] = {"soup_pct": pp(s.mean()), "seed_pct": pp(x.mean()), "diff_pp": pp(d.mean()), "ci95_pp": [pp(np.percentile(st, 2.5)), pp(np.percentile(st, 97.5))],
                             "soup_only_correct": int(((s == 1) & (x == 0)).sum()), "seed_only_correct": int(((s == 0) & (x == 1)).sum())}
    point, ci = CORE.boot_soup(s, [np.array([float(mats[n]["match"][i]) for i in ids]) for n in v4names], np.random.default_rng(RNG_SEED))
    out["soup_minus_v4_mean"] = {"diff_pp": pp(point), "ci95_pp": [pp(ci[0]), pp(ci[1])], "v4_seeds": v4names}
    out["o43_collapse_groups"] = o43_collapse_groups
    return out


# ---------- 4. 검정력 모의 ----------
def shift(v, k, delta, kind, rng):
    """v: 문항 값(표본 평균, k 표본) → 참 차이 delta를 문항 단위 무작위 뒤집기로 넣은 값."""
    c = np.rint(v * k).astype(int)
    if delta == 0:
        return v
    m = v.mean()
    if kind == "down":  # 맞힌(또는 거부) 표본을 확률 |Δ|/평균으로 뒤집음
        q = min(1.0, abs(delta) / m)
        c = rng.binomial(c, 1 - q)
    else:  # 거부 아닌 표본을 확률 Δ/(1 − 평균)로 거부로
        q = min(1.0, delta / (1 - m))
        c = c + rng.binomial(k - c, q)
    return c / k


def plan2_sim(V, k, deltas, kind, rule, rng):
    """V: 6 × I(V4 seed 문항 값). n seed 짝·문항 재추출 bootstrap CI → (반폭 평균, 통과 확률)."""
    S6, I = V.shape
    out = {}
    for n in SIM_SEEDS:
        for dl in deltas:
            hw, ok, pts = [], 0, []
            for _ in range(SIM_N):
                a = V[rng.integers(0, S6, n)]
                b = np.stack([shift(V[j], k, dl, kind, rng) for j in rng.integers(0, S6, n)])
                D = b - a
                ii = rng.integers(0, I, (SIM_B, I))
                M = np.stack([D[s][ii].mean(axis=1) for s in range(n)])  # n × B
                si = rng.integers(0, n, (SIM_B, n))
                st = M[si, np.arange(SIM_B)[:, None]].mean(axis=1)
                lo, hi = np.percentile(st, 2.5), np.percentile(st, 97.5)
                hw.append((hi - lo) / 2)
                pts.append(D.mean())
                side, lim = rule
                ok += (lo > lim) if side == "lower" else (hi < lim)
            out[f"n{n}_d{round(100 * dl, 1)}"] = {"seeds": n, "true_diff_pp": round(100 * dl, 1), "ci_halfwidth_pp_mean": round(100 * float(np.mean(hw)), 2),
                                                  "point_sd_pp": round(100 * float(np.std(pts)), 2), "pass_prob": round(ok / SIM_N, 3)}
    return out


def plan3_sim(ct, hd, e1, rng, variant=PLAN3_VARIANTS[0]):
    """6 seed에서 n seed 복원 추출 + 참 차이 → 안 3(넓은 셋 seed 일관성 + E1 거부 하한) 통과 비율. ct/hd: {"V":6×I, "base_acc":float, "groups":[(idx, base_pct)]}."""
    res = {}
    combos = [("acc0_over0_ref0", 0.0, 0.0, 0.0), ("acc-2", -0.02, 0.0, 0.0), ("acc-3", -0.03, 0.0, 0.0), ("over+1", 0.0, 0.01, 0.0), ("ref-5", 0.0, 0.0, -0.05)]
    for broad_name, broad in (("CT10K", ct), ("H-dev", hd)):
        if broad is None or e1 is None:
            continue
        S6 = broad["V"].shape[0]
        for n in SIM_SEEDS:
            for cname, da, do, dr in combos:
                ok = 0
                fails = Counter()
                for _ in range(SIM_N):
                    js = rng.integers(0, S6, n)
                    good = True
                    overs, refs = [], []
                    for j in js:
                        v = shift(broad["V"][j], 1, da, "down", rng)
                        if 100 * v.mean() < broad["base_acc"] + PLAN3["broad_vs_base_pp"]:
                            good = False
                            fails["broad_acc"] += 1
                        if sum(1 for idx, b in broad["groups"] if 100 * v[idx].mean() < b - variant[1]) > variant[2]:
                            good = False
                            fails["collapse"] += 1
                        overs.append(shift(e1["over"][j], 4, do, "up", rng).mean())
                        refs.append(shift(e1["ref"][j], 4, dr, "down", rng).mean())
                    if np.mean(overs) > PLAN3["e1_over_max"]:
                        good, fails["e1_over"] = False, fails["e1_over"] + 1
                    if np.mean(refs) < PLAN3["e1_ref_min"]:
                        good, fails["e1_ref"] = False, fails["e1_ref"] + 1
                    ok += good
                res[f"{broad_name}_{variant[0]}_n{n}_{cname}"] = {"broad": broad_name, "variant": variant[0], "seeds": n, "combo": cname, "pass_prob": round(ok / SIM_N, 3),
                                                                 "fail_counts": dict(fails)}
    return res


def plan3_per_seed(broad, e1, names):
    out = {}
    for j, n in enumerate(names):
        v = broad["V"][j]
        out[n] = {"broad_acc_pct": round(100 * float(v.mean()), 2), "broad_ok": bool(100 * v.mean() >= broad["base_acc"] + PLAN3["broad_vs_base_pp"]),
                  "collapsed_groups_20pp": sum(1 for idx, b in broad["groups"] if 100 * v[idx].mean() < b - 20.0),
                  "collapsed_groups_30pp": sum(1 for idx, b in broad["groups"] if 100 * v[idx].mean() < b - 30.0),
                  "min_group_minus_base_pp": round(min(100 * v[idx].mean() - b for idx, b in broad["groups"]), 1) if broad["groups"] else None,
                  "e1_over_pct": round(100 * float(e1["over"][j].mean()), 2) if e1 else None, "e1_ref_pct": round(100 * float(e1["ref"][j].mean()), 2) if e1 else None}
    return out


# ---------- 5. 과잉 거부 세부 ----------
def detail_tab(cells_by_model, gold_by_set, tools=("get_trip_metrics", "get_billing_metrics")):
    import compute_p9 as C9
    tab = defaultdict(lambda: {"refused": 0, "samples": 0, "models": set()})
    for mname, by_set in cells_by_model.items():
        for st, cells in by_set.items():
            for c in cells:
                for i, v in C9.sample_values(c).items():
                    it = gold_by_set[st][i]
                    if it.get("expected_outcome", "answered") != "answered":
                        continue
                    calls = it.get("gold") or []
                    tool, tu, rg = XT.classify(calls)
                    if tool not in tools:
                        continue
                    an = next((x for x in calls if x.get("tool") != "get_place_scope"), {})
                    a = an.get("args") or {}
                    k = (tool, a.get("metric"), a.get("aggregation"), "dimension:" + str(a.get("dimension")) if a.get("dimension") else "-", tu, rg)
                    tab[k]["samples"] += 1
                    if v["refused"]:
                        tab[k]["refused"] += 1
                        tab[k]["models"].add(mname)
    rows = [{"tool": k[0], "metric": k[1], "aggregation": k[2], "dimension": k[3], "time": k[4], "region": k[5], "refused": v["refused"], "samples": v["samples"],
             "pct": round(100 * v["refused"] / v["samples"], 2) if v["samples"] else None, "models_with_refusal": len(v["models"]), "models": len(cells_by_model)}
            for k, v in tab.items()]
    rows.sort(key=lambda r: (-r["refused"], -r["samples"]))
    return rows


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--skip-sim", action="store_true")
    ap.add_argument("--test-cells-dir", default=None, help="(도구 시험 전용) ablation_012 셀 위치를 바꿔 가짜 셀로 전체 경로를 돌린다")
    ap.add_argument("--test-hdev-gold", default=None, help="(도구 시험 전용) H-dev gold 대신")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    global A12C, HDEV_GOLD
    if a.test_cells_dir:
        A12C = a.test_cells_dir
    if a.test_hdev_gold:
        HDEV_GOLD = a.test_hdev_gold
    import robust_scoring
    robust_scoring.patch()
    import evaluate_vendor100 as EV
    sets_abs = dict(CORE.SETS)
    gold_e1 = {st: {i["id"]: i for i in EV.load_gold(ROOT / g)["items"]} for st, g in CORE.SETS.items()}
    res = {"note": "진단, 판정 아님. E1(refusal_dev v2·valid98·aux)은 V4 선택에 이미 쓴 셋. CT10K는 V4 자신의 seed 일관성·soup 진단에만(D1). H-final은 측정·열람하지 않음.",
           "smoke": a.smoke, "missing": []}
    # ---- E1 ----
    groups = ["A0", "A3"] if a.smoke else ["A0", "A3", "A3R-d1", "A3R-d2"]
    e1, e1_speed, e1_U = {}, {}, {}
    s10 = json.loads(CORE.SPEC10.read_text(encoding="utf-8"))["cells"]
    for g in groups:
        for s in NEW:
            c = e1_cells(g, s)
            if not exists([p for v in c.values() for p in v]):
                res["missing"].append(f"E1:{g}_{s}")
                continue
            o = CORE.load_model(c, sets_abs, gold_e1, True)
            e1[f"{g}_{s}"], e1_speed[f"{g}_{s}"], e1_U[f"{g}_{s}"] = e1_vectors(o), o["speed"], CORE.values(o)["U_samples"]
            print("E1 loaded", g, s, {k: pp(v.mean()) for k, v in e1[f"{g}_{s}"].items()}, flush=True)
    for s in OLD:
        o = CORE.load_model(s10["V4"][s], sets_abs, gold_e1, False)
        e1[f"V4_{s}"] = e1_vectors(o)
    if a.smoke:  # smoke: A3R 자리에 A3을 넣어 A3 − A0가 ablation_011 결과와 같은지, d1−d2 = 0인지
        for s in NEW:
            if f"A3_{s}" in e1:
                e1[f"A3R-d1_{s}"], e1[f"A3R-d2_{s}"] = e1[f"A3_{s}"], e1[f"A3_{s}"]
                e1_speed[f"A3R-d1_{s}"] = e1_speed[f"A3R-d2_{s}"] = e1_speed[f"A3_{s}"]
                e1_U[f"A3R-d1_{s}"] = e1_U[f"A3R-d2_{s}"] = e1_U[f"A3_{s}"]
    res["e1_a3_split"] = a3_split(e1, e1_speed, list(CORE.ITEM_VEC), e1_U)
    # ---- H-dev ----
    gold_hd = {i["id"]: i for i in EV.load_gold(ROOT / HDEV_GOLD)["items"]}
    hd_ids = sorted(gold_hd)
    hd_names = [f"{g}_{s}" for g in ("A0", "A3", "A3R-d1", "A3R-d2", "A1", "A2") for s in NEW] + ["soup"] + [f"V4_{s}" for s in OLD] + ["base_k1", "base_k2"]
    hd, hd_vec, hd_speed = {}, {}, {}
    if a.smoke:  # 로더 smoke: CT10K c1 묶음 셀을 H-dev 형식 셀로 읽음
        p = f"{CTD}/cells/ct10k_v4_o43_c1_s1.json"
        gct = {i["id"]: i for i in EV.load_gold(ROOT / CT_GOLD)["items"]}
        m = load_broad([p], CT_GOLD)
        rows = json.loads((ROOT / p).read_text(encoding="utf-8"))["rows"]
        res["hdev_loader_smoke"] = {"cell": p, "rows": len(rows), "match": sum(m["match"].values()), "direct_match": sum(r.get("category") == "match" for r in rows),
                                    "refused": sum(m["refused"].values()), "U_items": len(m["U"]), "speed": m["speed"], "gold_items_cover": all(i in gct for i in m["match"])}
    else:
        for n in hd_names:
            p = hdev_cell(hd_key(n))
            if not (ROOT / p).exists():
                res["missing"].append(f"H-dev:{n}")
                continue
            m = load_broad([p], HDEV_GOLD)
            hd[n], hd_speed[n] = m, m["speed"]
            hd_vec[n] = {"acc": vec(m, "match", hd_ids), "over": vec(m, "refused", hd_ids), "U": np.array([m["U"][i] for i in hd_ids])}
            print("H-dev loaded", n, {k: pp(v.mean()) for k, v in hd_vec[n].items()}, flush=True)
        res["hdev_models"] = {n: {**{k: pp(v.mean()) for k, v in hd_vec[n].items()}, "U_samples": int(hd_vec[n]["U"].sum()), "speed": hd_speed[n]} for n in hd_vec}
        res["hdev_a3_split"] = a3_split(hd_vec, hd_speed, ["acc", "over", "U"])
        for arm in ("A1", "A2"):
            seeds = [s for s in NEW if f"{arm}_{s}" in hd_vec and f"A0_{s}" in hd_vec]
            if seeds:
                res.setdefault("hdev_arm_vs_A0", {})[f"{arm}-A0"] = compare({s: hd_vec[f"{arm}_{s}"] for s in seeds}, {s: hd_vec[f"A0_{s}"] for s in seeds}, seeds, ["acc", "over", "U"])
    # ---- CT10K ----
    gold_ct = {i["id"]: i for i in EV.load_gold(ROOT / CT_GOLD)["items"]}
    ct_names = list(OLD) + ([] if a.smoke else [f"a0_{s}" for s in NEW] + ["soup"]) + ["base_k1", "base_k2", "base_k3"]
    ct = {}
    for n in ct_names:
        ps = ct_cells(n)
        if not exists(ps):
            res["missing"].append(f"CT10K:{n}")
            continue
        ct[n] = load_broad(ps, CT_GOLD, with_u=False)
        print("CT10K loaded", n, round(100 * np.mean(list(ct[n]["match"].values())), 2), flush=True)
    v4ct = [n for n in list(OLD) + [f"a0_{s}" for s in NEW] if n in ct]
    bct = [n for n in ("base_k1", "base_k2", "base_k3") if n in ct]
    res["ct10k_seed_consistency"] = seed_consistency(gold_ct, ct, v4ct, bct)
    o43c = [r for r in res["ct10k_seed_consistency"]["collapsed_groups"] if "o43" in r["collapsed_seeds"]]
    res["ct10k_soup"] = soup_ct(gold_ct, ct, v4ct, o43c)
    res["ct10k_models"] = {n: {"acc_pct": round(100 * np.mean(list(m["match"].values())), 2), "refused": int(sum(m["refused"].values())), "speed": m["speed"]} for n, m in ct.items()}
    if hd:
        v4hd = [n for n in [f"V4_{s}" for s in OLD] + [f"A0_{s}" for s in NEW] if n in hd]
        bhd = [n for n in ("base_k1", "base_k2") if n in hd]
        res["hdev_seed_consistency"] = seed_consistency(gold_hd, hd, v4hd, bhd, with_train=False)
        res["hdev_seed_consistency_ge20"] = {k: v for k, v in seed_consistency(gold_hd, hd, v4hd, bhd, with_train=False, min_tg=20).items()
                                             if k in ("groups_ge_min", "min_group_items", "collapse_count_by_seed", "collapsed_groups")}
    # ---- 검정력 모의 ----
    if not a.skip_sim:
        v4e1 = [n for n in [f"V4_{s}" for s in OLD] + [f"A0_{s}" for s in NEW] if n in e1]
        sim = {"seeds_used": {"E1": v4e1}, "rule_plan2": {k: list(v) for k, v in PLAN2.items()}, "rule_plan3": PLAN3, "plan3_variants": [list(v) for v in PLAN3_VARIANTS],
               "sims": SIM_N, "boot": SIM_B}
        rng = np.random.default_rng(20261110)
        if len(v4e1) >= 2:
            E = {met: np.stack([e1[n][key] for n in v4e1]) for met, key in (("acc", "dev_ok"), ("over", "over"), ("ref", "ref"))}
            sim["plan2_E1"] = {met: plan2_sim(E[met], 4, DELTAS[met], "down" if met != "over" else "up", PLAN2[met], rng) for met in ("acc", "over", "ref")}
        v4hd = [n for n in [f"V4_{s}" for s in OLD] + [f"A0_{s}" for s in NEW] if n in hd_vec]
        if len(v4hd) >= 2:
            sim["seeds_used"]["H-dev"] = v4hd
            H = {met: np.stack([hd_vec[n][met] for n in v4hd]) for met in ("acc", "over")}
            sim["plan2_Hdev"] = {met: plan2_sim(H[met], 1, DELTAS[met], "down" if met != "over" else "up", PLAN2[met], rng) for met in ("acc", "over")}

        def broad_pack(mats, names, base_names, gold):
            if len(names) < 2 or not base_names:
                return None
            ids = sorted(gold)
            V = np.stack([vec(mats[n], "match", ids) for n in names])
            tg = tg_groups(gold, ids)
            pos = {i: x for x, i in enumerate(ids)}
            grp = []
            for g, its in tg.items():
                if len(its) >= MIN_TG:
                    idx = np.array([pos[i] for i in its])
                    grp.append((idx, float(np.mean([100 * np.mean([mats[b]["match"][i] for i in its]) for b in base_names]))))
            return {"V": V, "base_acc": float(np.mean([100 * np.mean(list(mats[b]["match"].values())) for b in base_names])), "groups": grp, "names": names}
        ctp = broad_pack(ct, v4ct, bct, gold_ct)
        hdp = broad_pack(hd, [n for n in [f"V4_{s}" for s in OLD] + [f"A0_{s}" for s in NEW] if n in hd], [n for n in ("base_k1", "base_k2") if n in hd], gold_hd) if hd else None
        # E1 seed 순서를 넓은 셋 seed 순서에 맞춤(같은 모델)
        e1map = {"o43": "V4_o43", "o1016": "V4_o1016", "o7": "V4_o7", **{f"a0_{s}": f"A0_{s}" for s in NEW}, **{f"V4_{s}": f"V4_{s}" for s in OLD}, **{f"A0_{s}": f"A0_{s}" for s in NEW}}

        def e1pack(names):
            ns = [e1map[n] for n in names]
            if not all(n in e1 for n in ns):
                return None
            return {"over": np.stack([e1[n]["over"] for n in ns]), "ref": np.stack([e1[n]["ref"] for n in ns])}
        rng3 = np.random.default_rng(20261111)
        sim["plan3"] = {}
        if ctp:
            e1c = e1pack(ctp["names"])
            sim["plan3"]["per_seed_CT10K"] = plan3_per_seed(ctp, e1c, ctp["names"])
            for var in PLAN3_VARIANTS:
                sim["plan3"].update(plan3_sim(ctp, None, e1c, rng3, var))
        if hdp:
            e1h = e1pack(hdp["names"])
            sim["plan3"]["per_seed_Hdev"] = plan3_per_seed(hdp, e1h, hdp["names"])
            for var in PLAN3_VARIANTS:
                sim["plan3"].update(plan3_sim(None, hdp, e1h, rng3, var))
        res["power_sim"] = sim
    # ---- 과잉 거부 유형(D6) ----
    d6 = {"models": {"E1": [], "CT10K": [], "H-dev": []}}
    e1_cells_by = {}
    for s in NEW:
        c = e1_cells("A0", s)
        if exists([p for v in c.values() for p in v]):
            e1_cells_by[f"A0_{s}"] = c
    for s in OLD:
        e1_cells_by[f"V4_{s}"] = s10["V4"][s]
    allc = defaultdict(list)
    for n, c in e1_cells_by.items():
        for st in CORE.OVER:
            allc[st] += c[st]
    d6["models"]["E1"] = list(e1_cells_by)
    d6["E1_xtab"] = XT.xtab(allc, gold_e1)
    d6["E1_detail"] = detail_tab({n: {st: c[st] for st in CORE.OVER} for n, c in e1_cells_by.items()}, gold_e1)[:40]
    ctm = {n: {"ct": ct_cells(n)} for n in v4ct}
    d6["models"]["CT10K"] = v4ct
    d6["CT10K_xtab"] = XT.xtab({"ct": [p for v in ctm.values() for p in v["ct"]]}, {"ct": gold_ct})
    d6["CT10K_detail"] = detail_tab(ctm, {"ct": gold_ct})[:40]
    d6["CT10K_per_seed_refused"] = {n: int(sum(ct[n]["refused"].values())) for n in v4ct}
    if hd:
        hdm = {n: {"hd": [hdev_cell(hd_key(n))]} for n in [f"V4_{s}" for s in OLD] + [f"A0_{s}" for s in NEW] if n in hd}
        d6["models"]["H-dev"] = list(hdm)
        d6["Hdev_xtab"] = XT.xtab({"hd": [p for v in hdm.values() for p in v["hd"]]}, {"hd": gold_hd})
        d6["Hdev_detail"] = detail_tab(hdm, {"hd": gold_hd})[:40]
    res["overrefusal_types"] = d6
    out = Path(a.out) if a.out else HERE / ("smoke_a12.json" if a.smoke else "results_a12.json")
    if a.smoke:
        r11 = json.loads((INV / "ablation_011/analysis/results_a11.json").read_text(encoding="utf-8"))["arm_vs_A0"]["A3-A0"]
        mine = res["e1_a3_split"].get("A3-A0", {})
        ctc = res["ct10k_seed_consistency"]["acc_pct"]
        res["summary"] = {
            "e1_A3-A0_equals_results_a11": all(mine.get(m, {}).get("diff_pp") == r11[m]["diff_pp"] and mine.get(m, {}).get("ci95_pp") == r11[m]["ci95_pp"] for m in ("dev_ok", "ref", "over", "U_rate")),
            "e1_A3-A0": {m: (mine[m]["diff_pp"], mine[m]["ci95_pp"]) for m in ("dev_ok", "ref", "over", "U_rate")} if mine else None,
            "e1_d1-d2_zero_when_same": all(res["e1_a3_split"]["A3Rd1-A3Rd2"][m]["diff_pp"] == 0 for m in ("dev_ok", "ref", "over", "U_rate")) if mine else None,
            "ct10k_v4_acc": {n: ctc[n] for n in OLD}, "ct10k_base_acc": {n: ctc[n] for n in bct},
            "ct10k_matches_client_test_RESULTS": [ctc[n] for n in OLD] == [85.94, 94.23, 93.84] and [ctc[n] for n in bct] == [82.73, 83.0, 83.13],
            "hdev_loader": res.get("hdev_loader_smoke"),
            "e1_A0_xtab_over_refusal": d6["E1_xtab"]["pct"]}
        print(json.dumps(res["summary"], ensure_ascii=False, indent=1))
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print("wrote", out, "missing", res["missing"])


if __name__ == "__main__":
    main()
