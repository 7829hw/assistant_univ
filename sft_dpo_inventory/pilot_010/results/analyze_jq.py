# -*- coding: utf-8 -*-
"""pilot_010 JQ 집계(결정 269, PLAN_JQ). **판정 뒤 추가(사후), PF2·H-final 두 번째 사용 — C1–C4는 바꾸지 않는다.** 모델 호출 없음.
``analyze_j.py``·``analyze_jp.py``는 고치지 않고 함수(셀 읽기·채점·U1 bootstrap·결과 분해)를 불러 쓴다.
**PF2 질문·정답 호출·응답은 출력·저장하지 않는다**(집계 수치·형 M·P·C·코드·sha256만).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/results/analyze_jq.py --part A --out sft_dpo_inventory/pilot_010/results/jq_ensemble.json
    runtime/envs/hf/bin/python .../analyze_jq.py --part B --out sft_dpo_inventory/pilot_010/results/jq_v8new.json

A(PLAN_JQ A1–A3): 구성(SFT=B2F·RR=P9·RR+NM4=V4·RR+NM8=V8)마다 seed 앙상블(다수결), n=3 조합, CT10K·H-dev 재현(V4 6 seed), PF2 거부 재확인, 비용.
B(PLAN_JQ B4): V8 새 4 seed의 P1–P4, 비교, 기존 3 seed와 나란히, 7 seed 합, 새 4·7 seed 앙상블.
검사: 단일 모델 seed 평균을 이 스크립트의 표본 기록에서 다시 계산해 ``jp_posthoc.json``(표 A) 값과 같은지 본다(다르면 멈춤).
"""
import argparse
import hashlib
import itertools
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
import analyze_jp as AP  # noqa: E402

PF_CELLS = AJ.PF_CELLS
HF_J, HF_JP, HF_JQ = INV / "pilot_010/cells/J", INV / "pilot_010/cells/JP", INV / "pilot_010/cells/JQ"
V8_NEW = tuple(f"o{s}" for s in json.loads((INV / "pilot_010/build/seeds_jq.json").read_text(encoding="utf-8"))["order_seeds"])
SEEDS = {"B2F": AJ.B2F_SEEDS, "P9": ("o43", "o1016", "o7", "o11", "o2027"), "V4": AJ.V4_SEEDS, "V8": ("o43", "o1016", "o7")}
NAMES = {"B2F": "SFT", "P9": "RR", "V4": "RR+NM4", "V8": "RR+NM8", "base": "base", "V8new": "RR+NM8 새 4", "V8all": "RR+NM8 7"}
PF_METRICS = AP.PF_METRICS
CATS = AP.CATS
LAB = "판정 뒤 추가(사후), PF2·H-final 두 번째 사용 — C1–C4 판정은 바꾸지 않음"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jdump(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, default=str)


def wall(r):
    return AJ._ts(r["finished_at"]) - AJ._ts(r["started_at"]) if r.get("started_at") and r.get("finished_at") else None


# ---------------- 표본 기록 ----------------
def key_pf2(EV, r):
    """PF2 정규형(PLAN_JQ A1): (결과 상태가 거부 상태인가, grounding view). view 없음 → no_grounding."""
    view = EV._grounding_view(r.get("grounding"))
    if view is None:
        return jdump(["no_grounding", r.get("outcome"), r.get("error_code")])
    return jdump([r.get("outcome") in AJ.REFUSAL_OUTCOMES, view])


def key_call(EV, r):
    """H-final·CT10K·H-dev 정규형(PLAN_JQ A1, EV.score가 비교하는 것)."""
    calls = r.get("calls") or []
    if r.get("outcome") != "answered" or not calls:
        return jdump(["no_plan", r.get("outcome"), r.get("error_code")])
    places = sorted(jdump(EV._place_key(c.get("args") or {})) for c in calls if c.get("tool") == "get_place_scope")
    analysis = [c for c in calls if c.get("tool") != "get_place_scope"]
    final = analysis[-1] if analysis else {"tool": None, "args": {}}
    return jdump([r.get("outcome"), places, len(analysis), final.get("tool"), EV._normalized(final.get("tool") or "", final.get("args") or {})])


def load_cell(p, kind, ctx):
    """셀 하나 → {id: 표본 기록}. kind ∈ pf2 | hfinal | broad(CT10K·H-dev: 결과 분해 없음)."""
    p = Path(p)
    d = json.loads(p.read_text(encoding="utf-8"))
    EV, A = ctx["EV"], ctx["A"]
    sv = AJ.sample_rows(d)
    scored = None
    if kind in ("pf2", "hfinal"):
        A.RAW = Path(d["meta"]["hf"]["raw_out"]).parent
        _, scored = A.load_sample(p, ctx["gold_" + kind])
    out = {}
    for r in d["rows"]:
        i = r["id"]
        refused, route, oc, _ = sv[i]
        if kind == "pf2":
            correct = scored[i]["ok"] is True and oc not in AJ.REFUSAL_OUTCOMES
            key = None if refused else key_pf2(EV, r)
        else:
            correct = r.get("category") == "match"
            key = None if refused else key_call(EV, r)
        cat = AP.classify(r, scored[i], correct, refused, route)[0] if scored is not None else None
        out[i] = {"refused": bool(refused), "route": route, "key": key, "correct": bool(correct), "cat": cat,
                  "calls": len(r.get("hf_calls") or []), "wall": wall(r)}
    return out, {"file": str(p.relative_to(ROOT)) if str(p).startswith(str(ROOT)) else p.name, "sha256": sha(p), "rows": len(d["rows"])}


# ---------------- 앙상블 ----------------
def ensemble(models, ids, chk):
    """models: 표본 기록 dict 목록(seed 표기 순서). PLAN_JQ A2. chk: 같은 문항·같은 키의 정답 불일치 수를 센다."""
    n = len(models)
    out = {}
    for i in ids:
        recs = [m[i] for m in models]
        refusers = [r for r in recs if r["refused"]]
        calls = sum(r["calls"] for r in recs)
        ws = [r["wall"] for r in recs if r["wall"] is not None]
        mw = max(ws) if ws else None
        if len(refusers) > n / 2:
            cnt = Counter(r["route"] for r in refusers)
            top = max(cnt.values())
            route = next(r["route"] for r in refusers if cnt[r["route"]] == top)
            out[i] = {"refused": True, "route": route, "correct": False, "cat": f"refused_{route}", "calls": calls, "wall": mw, "key": None}
            continue
        ans = [r for r in recs if not r["refused"]]
        cnt = Counter(r["key"] for r in ans)
        top = max(cnt.values())
        rep = next(r for r in ans if cnt[r["key"]] == top)
        same = {r["correct"] for r in ans if r["key"] == rep["key"]}
        chk["groups"] += 1
        chk["inconsistent"] += len(same) > 1
        out[i] = {"refused": False, "route": None, "correct": rep["correct"], "cat": rep["cat"], "calls": calls, "wall": mw, "key": rep["key"],
                  "support": top, "answered": len(ans)}
    return out


def recheck(first, second, ids):
    """PLAN_JQ A3.4: 첫 표본이 거부가 아니면 첫 표본, 거부면 둘째를 보고 둘 다 거부일 때만 거부, 아니면 둘째 결과."""
    out = {}
    for i in ids:
        a, b = first[i], second[i]
        if not a["refused"]:
            out[i] = dict(a)
        elif b["refused"]:
            out[i] = dict(a, calls=a["calls"] + b["calls"], wall=(a["wall"] or 0) + (b["wall"] or 0))
        else:
            out[i] = dict(b, calls=a["calls"] + b["calls"], wall=(a["wall"] or 0) + (b["wall"] or 0))
    return out


# ---------------- 지표 벡터 ----------------
def pf_vec(samples, ids_ref, ids_ans, ids_con):
    """표본 기록 목록(k개) → 문항 값 벡터 4개(표본 평균)."""
    f = lambda ids, fn: np.array([np.mean([fn(s[i]) for s in samples]) for i in ids])  # noqa: E731
    return {"correct_refusal": f(ids_ref, lambda r: float(r["refused"])), "over_refusal_100": f(ids_ans, lambda r: float(r["refused"])),
            "over_refusal_contrast25": f(ids_con, lambda r: float(r["refused"])), "accuracy_100": f(ids_ans, lambda r: float(r["correct"]))}


def hf_vec(samples, ids):
    f = lambda fn: np.array([np.mean([fn(s[i]) for s in samples]) for i in ids])  # noqa: E731
    return {"accuracy": f(lambda r: float(r["correct"])), "over_refusal": f(lambda r: float(r["refused"]))}


def cat_vec(samples, ids):
    return {c: np.array([np.mean([float(s[i]["cat"] == c) for s in samples]) for i in ids]) for c in CATS}


def cost(samples_by_unit):
    """samples_by_unit: [[표본 기록 dict, ...] 단위(앙상블 j 또는 모델 셀)] → 문항당 호출 평균·wall p50·p95(모든 문항×단위)."""
    calls = [r["calls"] for u in samples_by_unit for r in u.values()]
    ws = [r["wall"] for u in samples_by_unit for r in u.values() if r["wall"] is not None]
    return {"llm_calls_per_item": round(float(np.mean(calls)), 3), "wall_p50_s": round(float(np.percentile(ws, 50)), 2), "wall_p95_s": round(float(np.percentile(ws, 95)), 2)}


def mean_cost(costs):
    return {k: round(float(np.mean([c[k] for c in costs])), 3 if k.startswith("llm") else 2) for k in costs[0]}


# ---------------- 읽기 ----------------
def setup():
    import robust_scoring
    robust_scoring.patch()
    import analyze_a12 as AA
    import compute_gates as CG
    import evaluate_vendor100 as EV
    from common_pf2 import TYPE_BY_TOOL
    A = CG.scorer()
    AP.CLS.update({"U": A.CS.U_CLASS, "silent": A.CS.SILENT})
    pgold = {i["id"]: i for i in EV.load_gold(AJ.PF_GOLD)["items"]}
    A.C.R.C._GOLD["pf2"] = {i.split("/", 1)[1]: it for i, it in pgold.items()}
    AA.install_u_gold(AJ.HF_GOLD)
    hl = EV.load_gold(ROOT / AJ.HF_GOLD)["items"]
    return {"EV": EV, "A": A, "TYPE_BY_TOOL": TYPE_BY_TOOL, "gold_pf2": pgold, "gold_hfinal": {i["id"]: i for i in hl}, "hf_list": hl,
            "pf_meta": json.loads(AJ.PF_META.read_text(encoding="utf-8"))}


def pf_paths(arm, s):
    if arm == "base":
        return [PF_CELLS / f"pf2_base_s{k}.json" for k in range(1, 9)]
    a = "v8" if arm in ("V8", "V8new") else arm.lower()
    return [PF_CELLS / f"pf2_{a}_{s}_s{k}.json" for k in range(1, 5)]


def hf_paths(arm, s):
    if arm == "base":
        return [HF_J / "hfinal_base_s1.json", HF_J / "hfinal_base_s2.json"]
    d = {"V4": HF_J, "B2F": HF_J, "P9": HF_JP, "V8": HF_JP, "V8new": HF_JQ}[arm]
    a = "v8" if arm in ("V8", "V8new") else arm.lower()
    return [d / f"hfinal_{a}_{s}_s1.json"]


def load_arms(ctx, arms):
    """arms: {arm: seeds}. → PF[arm][s] = [k 표본 기록], HF[arm][s] = [표본 기록], 셀 목록."""
    PF, HF, cells = {}, {}, []
    for arm, seeds in arms.items():
        PF[arm], HF[arm] = {}, {}
        for s in seeds:
            pp_, hp = pf_paths(arm, s), hf_paths(arm, s)
            if not all(p.exists() for p in pp_ + hp):
                raise SystemExit(f"missing cells for {arm}:{s}")
            PF[arm][s] = []
            for p in pp_:
                rec, info = load_cell(p, "pf2", ctx)
                PF[arm][s].append(rec)
                cells.append(info)
            HF[arm][s] = []
            for p in hp:
                rec, info = load_cell(p, "hfinal", ctx)
                HF[arm][s].append(rec)
                cells.append(info)
    return PF, HF, cells


# ---------------- 앙상블 단위 계산 ----------------
class Sets:
    def __init__(self, ctx):
        meta = ctx["pf_meta"]
        ids = sorted(ctx["gold_pf2"])
        self.ref = [i for i in ids if meta[i]["refusal"]]
        self.ans = [i for i in ids if not meta[i]["refusal"]]
        self.con = [i for i in self.ans if meta[i]["contrast"] != AJ.NONE]
        self.pf_all = ids
        self.hf = [i["id"] for i in ctx["hf_list"]]
        hg = ctx["gold_hfinal"]
        self.types, self.groups = defaultdict(list), defaultdict(list)
        for x, i in enumerate(self.hf):
            self.types[ctx["TYPE_BY_TOOL"].get(hg[i]["gold"][-1]["tool"], "기타")].append(x)
            self.groups[hg[i]["template_group"]].append(x)


def ens_unit(PF, HF, arm, seeds, S, chk):
    """seed 목록의 앙상블 → PF2 표본 4개(j별), H-final 표본 1개."""
    pf = [ensemble([PF[arm][s][j] for s in seeds], S.pf_all, chk["pf2"]) for j in range(4)]
    hf = [ensemble([HF[arm][s][0] for s in seeds], S.hf, chk["hfinal"])]
    return pf, hf


def metric_mats_single(PF, HF, arm, seeds, S):
    pv = [pf_vec(PF[arm][s], S.ref, S.ans, S.con) for s in seeds]
    hv = [hf_vec(HF[arm][s], S.hf) for s in seeds]
    m = {f: np.vstack([v[f] for v in pv]) for f in PF_METRICS}
    m["hfinal_accuracy"] = np.vstack([v["accuracy"] for v in hv])
    m["hfinal_over_refusal"] = np.vstack([v["over_refusal"] for v in hv])
    return m


def metric_mats_unit(pf, hf, S):
    pv, hv = pf_vec(pf, S.ref, S.ans, S.con), hf_vec(hf, S.hf)
    m = {f: pv[f][None, :] for f in PF_METRICS}
    m["hfinal_accuracy"], m["hfinal_over_refusal"] = hv["accuracy"][None, :], hv["over_refusal"][None, :]
    return m


METRICS = PF_METRICS + ("hfinal_accuracy", "hfinal_over_refusal")


def point(m):
    return {f: AJ.pp(m[f].mean(axis=1).mean()) for f in METRICS}


def est_all(m):
    return {f: AJ.est(m[f]) for f in METRICS}


def diff_all(x, y):
    return {f: AJ.diff(x[f], y[f]) for f in METRICS}


def hf_details(hf, S, base_hf, ctx):
    """앙상블(또는 단일 seed) H-final 표본 1개 → 결과 분해·도구 유형별 정답률·template_group 붕괴 수."""
    acc = np.array([float(hf[i]["correct"]) for i in S.hf])
    cats = {c: AJ.pp(np.mean([float(hf[i]["cat"] == c) for i in S.hf])) for c in CATS}
    types = {k: {"items": len(v), "pct": AJ.pp(acc[v].mean())} for k, v in sorted(S.types.items())}
    big = {g: v for g, v in S.groups.items() if len(v) >= 30}
    bacc = base_hf["accuracy"]
    coll = {"groups_ge30": len(big), "below_base_20pp": int(sum(acc[v].mean() < bacc[v].mean() - 0.20 for v in big.values())),
            "below_base_30pp": int(sum(acc[v].mean() < bacc[v].mean() - 0.30 for v in big.values()))}
    return {"decomposition": cats, "accuracy_by_tool_type": types, "group_collapse": coll}


def single_hf_details(HF, arm, seeds, S, base_hf, ctx):
    per = {s: hf_details(HF[arm][s][0], S, base_hf, ctx) for s in seeds}
    return {"decomposition_seed_mean": {c: round(float(np.mean([per[s]["decomposition"][c] for s in seeds])), 2) for c in CATS},
            "accuracy_by_tool_type_seed_mean": {k: {"items": per[seeds[0]]["accuracy_by_tool_type"][k]["items"],
                                                    "pct": round(float(np.mean([per[s]["accuracy_by_tool_type"][k]["pct"] for s in seeds])), 2)}
                                                for k in per[seeds[0]]["accuracy_by_tool_type"]},
            "group_collapse_per_seed": {s: per[s]["group_collapse"] for s in seeds},
            "group_collapse_mean": {k: round(float(np.mean([per[s]["group_collapse"][k] for s in seeds])), 2) for k in ("below_base_20pp", "below_base_30pp")}}


def pf2_ens_extra(pf, S, meta):
    """앙상블 PF2: 거부 경로(올바른 거부 표본)·형별 올바른 거부·답하는 100 결과 분해."""
    routes = Counter(u[i]["route"] for u in pf for i in S.ref if u[i]["refused"])
    form = defaultdict(list)
    for i in S.ref:
        form[meta[i]["form"]].append(np.mean([float(u[i]["refused"]) for u in pf]))
    return {"routes_samples": dict(routes), "correct_refusal_by_form": {k: {"items": len(v), "pct": AJ.pp(np.mean(v))} for k, v in sorted(form.items())},
            "decomposition_100": {c: AJ.pp(np.mean([float(u[i]["cat"] == c) for u in pf for i in S.ans])) for c in CATS}}


def ens_cost(pf, hf):
    return {"pf2": cost(pf), "hfinal": cost(hf)}


def single_cost(PF, HF, arm, seeds):
    return {"pf2": mean_cost([cost(PF[arm][s]) for s in seeds]), "hfinal": mean_cost([cost(HF[arm][s]) for s in seeds])}


def check_against_jp(singles, base_m):
    """단일 모델 seed 평균이 jp_posthoc.json 표 A와 같은지(다르면 멈춤)."""
    jp = json.loads((HERE / "jp_posthoc.json").read_text(encoding="utf-8"))
    bad, n = [], 0
    for arm, m in list(singles.items()) + [("base", base_m)]:
        if arm not in jp["pf2"]["arms"]:
            continue
        for f in PF_METRICS:
            n += 1
            if AJ.pp(m[f].mean(axis=1).mean()) != jp["pf2"]["arms"][arm][f]["mean_pct"]:
                bad.append((arm, f))
        for f, k in (("hfinal_accuracy", "accuracy"), ("hfinal_over_refusal", "over_refusal")):
            n += 1
            if AJ.pp(m[f].mean(axis=1).mean()) != jp["hfinal"]["arms"][arm][k]["mean_pct"]:
                bad.append((arm, f))
    if bad:
        raise SystemExit(f"single-model means differ from jp_posthoc.json: {bad}")
    return {"compared": n, "all_equal": True}


def config_block(PF, HF, arm, seeds, S, ctx, base, base_hf, sft_single, sft_ens, chk_all):
    """한 구성(seed 목록)의 단일 평균·앙상블·차이·비용."""
    single = metric_mats_single(PF, HF, arm, seeds, S)
    chk = {"pf2": {"groups": 0, "inconsistent": 0}, "hfinal": {"groups": 0, "inconsistent": 0}}
    pf, hf = ens_unit(PF, HF, arm, seeds, S, chk)
    em = metric_mats_unit(pf, hf, S)
    chk_all[f"{arm}:{len(seeds)}"] = chk
    blk = {"seeds": list(seeds), "n": len(seeds), "single_mean": est_all(single), "ensemble": est_all(em),
           "ensemble_minus_own_single": diff_all(em, single), "ensemble_minus_sft_single": diff_all(em, sft_single),
           "ensemble_minus_base": diff_all(em, base), "hfinal_ensemble": hf_details(hf[0], S, base_hf, ctx),
           "hfinal_single": single_hf_details(HF, arm, seeds, S, base_hf, ctx), "pf2_ensemble": pf2_ens_extra(pf, S, ctx["pf_meta"]),
           "cost": {"ensemble": ens_cost(pf, hf), "single_mean": single_cost(PF, HF, arm, seeds)},
           "ensemble_support_hfinal": dict(Counter(f"{r.get('support')}/{r.get('answered')}" for r in hf[0].values() if not r["refused"]))}
    if sft_ens is not None:
        blk["ensemble_minus_sft_ensemble"] = diff_all(em, sft_ens)
    return blk, single, em


def combos3(PF, HF, arm, seeds, S):
    rows = []
    for c in itertools.combinations(seeds, 3):
        chk = {"pf2": {"groups": 0, "inconsistent": 0}, "hfinal": {"groups": 0, "inconsistent": 0}}
        pf, hf = ens_unit(PF, HF, arm, c, S, chk)
        rows.append({"seeds": list(c), **point(metric_mats_unit(pf, hf, S))})
    summ = {f: {"mean": round(float(np.mean([r[f] for r in rows])), 2), "min": min(r[f] for r in rows), "max": max(r[f] for r in rows)} for f in METRICS}
    return {"combos": len(rows), "summary": summ, "rows": rows}


def recheck_block(PF, arm, seeds, S):
    rc = {s: [recheck(PF[arm][s][0], PF[arm][s][1], S.pf_all), recheck(PF[arm][s][2], PF[arm][s][3], S.pf_all)] for s in seeds}
    m_rc = {f: np.vstack([pf_vec(rc[s], S.ref, S.ans, S.con)[f] for s in seeds]) for f in PF_METRICS}
    m_1 = {f: np.vstack([pf_vec(PF[arm][s], S.ref, S.ans, S.con)[f] for s in seeds]) for f in PF_METRICS}
    return {"seeds": list(seeds), "recheck": {f: AJ.est(m_rc[f]) for f in PF_METRICS}, "single": {f: AJ.est(m_1[f]) for f in PF_METRICS},
            "paired_recheck_minus_single_extra": {f: AJ.est(m_rc[f] - m_1[f]) for f in PF_METRICS},
            "cost": {"recheck": mean_cost([cost(rc[s]) for s in seeds]), "single": mean_cost([cost(PF[arm][s]) for s in seeds])}}


# ---------------- CT10K·H-dev 재현 ----------------
def broad(ctx, name, seeds_paths, base_paths):
    ids, M, chk = None, [], {"groups": 0, "inconsistent": 0}
    recs = []
    for s, paths in seeds_paths:
        rec = {}
        for p in paths:
            r, _ = load_cell(p, "broad", ctx)
            if set(r) & set(rec):
                raise SystemExit(f"{name}: duplicate ids across chunks")
            rec.update(r)
        recs.append(rec)
        ids = sorted(rec) if ids is None else ids
        if sorted(rec) != ids:
            raise SystemExit(f"{name}: item sets differ ({s})")
    bsamp = []
    for paths in base_paths:
        rec = {}
        for p in paths:
            rec.update(load_cell(p, "broad", ctx)[0])
        bsamp.append(rec)
    vec = lambda samples, fld: np.array([np.mean([float(x[i][fld]) for x in samples]) for i in ids])  # noqa: E731
    single = {"accuracy": np.vstack([vec([r], "correct") for r in recs]), "over_refusal": np.vstack([vec([r], "refused") for r in recs])}
    base = {"accuracy": vec(bsamp, "correct")[None, :], "over_refusal": vec(bsamp, "refused")[None, :]}
    e = ensemble(recs, ids, chk)
    em = {"accuracy": vec([e], "correct")[None, :], "over_refusal": vec([e], "refused")[None, :]}
    rows = []
    for c in itertools.combinations(range(len(recs)), 3):
        ec = ensemble([recs[x] for x in c], ids, {"groups": 0, "inconsistent": 0})
        rows.append({"seeds": [seeds_paths[x][0] for x in c], "accuracy": AJ.pp(vec([ec], "correct").mean()), "over_refusal": AJ.pp(vec([ec], "refused").mean())})
    return {"items": len(ids), "seeds": [s for s, _ in seeds_paths], "single_mean": {f: AJ.est(single[f]) for f in single}, "base": {f: AJ.est(base[f]) for f in base},
            "ensemble": {f: AJ.est(em[f]) for f in em}, "ensemble_minus_single": {f: AJ.diff(em[f], single[f]) for f in em},
            "ensemble_minus_base": {f: AJ.diff(em[f], base[f]) for f in em}, "single_minus_base": {f: AJ.diff(single[f], base[f]) for f in em},
            "combos3": {"combos": len(rows), "summary": {f: {"mean": round(float(np.mean([r[f] for r in rows])), 2), "min": min(r[f] for r in rows), "max": max(r[f] for r in rows)}
                                                          for f in ("accuracy", "over_refusal")}, "rows": rows},
            "key_consistency": chk}


def broad_cfg():
    ct, a12 = INV / "client_test_10000/cells", INV / "ablation_012/cells"
    v4 = [(s, [ct / f"ct10k_v4_{s}_c{c}_s1.json" for c in range(1, 6)]) for s in ("o43", "o1016", "o7")]
    a0 = [(s, [a12 / f"ct10k_a0_{s}_c{c}_s1.json" for c in range(1, 6)]) for s in ("o1102", "o211102", "o2026113")]
    ctb = [[ct / f"ct10k_base_c{c}_s{k}.json" for c in range(1, 6)] for k in (1, 2, 3)]
    hv4 = [(s, [a12 / f"hdev_v4_{s}_s1.json"]) for s in ("o43", "o1016", "o7")] + [(s, [a12 / f"hdev_a0_{s}_s1.json"]) for s in ("o1102", "o211102", "o2026113")]
    hb = [[a12 / "hdev_base_s1.json"], [a12 / "hdev_base_s2.json"]]
    return {"CT10K": (v4 + a0, ctb), "H-dev": (hv4, hb)}


# ---------------- 본 분석 ----------------
def part_a(ctx):
    S = Sets(ctx)
    PF, HF, cells = load_arms(ctx, {**SEEDS, "base": ("base",)})
    base = metric_mats_single(PF, HF, "base", ("base",), S)
    # base: PF2 k=8 한 단위, H-final 두 회차 평균(load_arms가 표본 목록으로 둠)
    base_hf = hf_vec(HF["base"]["base"], S.hf)
    singles = {arm: metric_mats_single(PF, HF, arm, SEEDS[arm], S) for arm in SEEDS}
    res = {"label": LAB, "decision": 269, "plan": "sft_dpo_inventory/pilot_010/PLAN_JQ.md", "names": NAMES,
           "bootstrap": {"reps": AJ.REPS, "rng": f"default_rng({AJ.RNG_SEED}) per statistic", "ensemble": "items only (1 unit)", "single": "U1"},
           "check_single_means_vs_jp_posthoc": check_against_jp(singles, base), "base": {"metrics": est_all(base), "cost": single_cost(PF, HF, "base", ("base",))},
           "configs": {}, "combos3": {}, "recheck": {}, "key_consistency": {}}
    sft_chk = {"pf2": {"groups": 0, "inconsistent": 0}, "hfinal": {"groups": 0, "inconsistent": 0}}
    pf, hf = ens_unit(PF, HF, "B2F", SEEDS["B2F"], S, sft_chk)
    sft_ens = metric_mats_unit(pf, hf, S)
    for arm in ("B2F", "P9", "V4", "V8"):
        blk, _, _ = config_block(PF, HF, arm, SEEDS[arm], S, ctx, base, base_hf, singles["B2F"], None if arm == "B2F" else sft_ens, res["key_consistency"])
        res["configs"][arm] = blk
        if len(SEEDS[arm]) == 5:
            res["combos3"][arm] = combos3(PF, HF, arm, SEEDS[arm], S)
        res["recheck"][arm] = recheck_block(PF, arm, SEEDS[arm], S)
    res["combos3"]["V8"] = {"combos": 1, "note": "seed 3개 = 전체 앙상블", "summary": {f: {"mean": v["mean_pct"], "min": v["mean_pct"], "max": v["mean_pct"]}
                                                                                for f, v in res["configs"]["V8"]["ensemble"].items()}}
    res["base_hfinal_group_reference"] = "template_group 붕괴: 30문항 이상 그룹, base 두 회차 평균 대비 −20·−30%p"
    res["broad"] = {name: broad(ctx, name, sp, bp) for name, (sp, bp) in broad_cfg().items()}
    res["broad_note"] = "V4 6 seed(지시의 수). 같은 V4 데이터의 다른 A0 seed(ablation_013 hdev_a0_o2026117·o2026131, topic2 ct10k_t2_a0_*)는 넣지 않음."
    res["cells"] = cells
    return res


def part_b(ctx):
    S = Sets(ctx)
    arms = {**SEEDS, "V8new": V8_NEW, "base": ("base",)}
    PF, HF, cells = load_arms(ctx, arms)
    PF["V8all"] = {**PF["V8"], **PF["V8new"]}
    HF["V8all"] = {**HF["V8"], **HF["V8new"]}
    all7 = SEEDS["V8"] + V8_NEW
    base = metric_mats_single(PF, HF, "base", ("base",), S)
    base_hf = hf_vec(HF["base"]["base"], S.hf)
    singles = {arm: metric_mats_single(PF, HF, arm, SEEDS[arm], S) for arm in SEEDS}
    new = metric_mats_single(PF, HF, "V8new", V8_NEW, S)
    allm = metric_mats_single(PF, HF, "V8all", all7, S)
    res = {"label": LAB, "decision": 269, "plan": "sft_dpo_inventory/pilot_010/PLAN_JQ.md", "names": NAMES, "new_seeds": list(V8_NEW), "all7_seeds": list(all7),
           "check_single_means_vs_jp_posthoc": check_against_jp(singles, base),
           "single": {"V8new": est_all(new), "V8old": est_all(singles["V8"]), "V8all": est_all(allm)},
           "per_seed": {s: point(metric_mats_single(PF, HF, "V8all", (s,), S)) for s in all7},
           "comparisons": {}, "ensembles": {}, "key_consistency": {}}
    for tag, m in (("V8new", new), ("V8all", allm)):
        for o in ("B2F", "base", "P9", "V4"):
            res["comparisons"][f"{tag}-{o}"] = diff_all(m, base if o == "base" else singles[o])
    res["comparisons"]["V8new-V8old"] = diff_all(new, singles["V8"])
    res["hfinal_single"] = {"V8new": single_hf_details(HF, "V8new", V8_NEW, S, base_hf, ctx), "V8all": single_hf_details(HF, "V8all", all7, S, base_hf, ctx)}
    sft_chk = {"pf2": {"groups": 0, "inconsistent": 0}, "hfinal": {"groups": 0, "inconsistent": 0}}
    pf, hf = ens_unit(PF, HF, "B2F", SEEDS["B2F"], S, sft_chk)
    sft_ens = metric_mats_unit(pf, hf, S)
    for tag, seeds in (("V8new", V8_NEW), ("V8all", all7)):
        blk, _, _ = config_block(PF, HF, tag, seeds, S, ctx, base, base_hf, singles["B2F"], sft_ens, res["key_consistency"])
        res["ensembles"][tag] = blk
    res["cost_single"] = {"V8new": single_cost(PF, HF, "V8new", V8_NEW)}
    res["cells"] = cells
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("A", "B"), required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ctx = setup()
    res = part_a(ctx) if a.part == "A" else part_b(ctx)
    res["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    res["inputs"] = {"pf2_gold_sha256": sha(AJ.PF_GOLD), "pf2_meta_sha256": sha(AJ.PF_META), "hfinal_sha256": sha(ROOT / AJ.HF_GOLD),
                     "analysis_sha256": sha(__file__), "analyze_j_sha256": sha(AJ.__file__), "analyze_jp_sha256": sha(AP.__file__)}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("written", a.out)


if __name__ == "__main__":
    main()
