# -*- coding: utf-8 -*-
"""pilot_007 최종 판정 채점·판정(결정 214 V4, 215 V5). PLAN_FINAL과 함께 측정 전에 고정한다. 모델 호출 없음.
**질문·정답 호출·응답은 출력·저장하지 않는다** — 저장소에 쓰는 것은 문항 번호별 판정 값·집계·sha256뿐.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/final/final_score.py --out sft_dpo_inventory/pilot_007/results/final_judgment.json \
        --items-out sft_dpo_inventory/pilot_007/results/final_items.json

채점(표본마다):
- 거부가 아닌 문항(gold ``expected_outcome: answered``): 정답 = 기존 grounding_ok(``analyze_cal.load_sample``의 ``EV.grounding_check``, 견고성 패치)가 참이고
  결과 상태가 거부(``REFUSAL_OUTCOMES``)가 아님. → 거부로 끝나면 오답(과잉 거부).
- 거부 문항(``expected_outcome: unsupported``, gold 호출 없음): 정답 = 결과 상태가 거부(기존 분류 refused_unsupported·refused_clarification의 outcome
  ``unsupported``·``needs_clarification``)이고 분석 tool(``get_place_scope`` 밖) 호출이 실행되지 않음. 그 밖(답함·실패)은 오답.
- U·조용한 오답: 기존 분류(``report_class``: U = "용납할 수 없는 실패", 조용한 오답 = "조용한 오답(U 아님)"). U 분류기가 원본 gold를 찾도록 프로세스 안에서
  ``compare._GOLD["pf1"]``에 문항(id ``pf1/NNN`` → ``NNN``)을 넣는다.
- 잘림(호출 ``done_reason == "length"``)은 따로 다시 돌리지 않고 그대로 채점(대개 오답)하며 건수만 센다.
판정(PROTOCOL_v4 6절 = v3 6절 + 지연): 문항 값 = k=8 표본 평균, d = 후보 − base, 95% CI = 문항 단위 쌍 bootstrap 10,000회(비교마다 새 ``default_rng(20261109)``,
``compute_gates.ci``와 같은 계산).
- 개선: 정답률 CI 하한 > 0, U CI 하한 ≤ 0, 조용한 오답 CI 하한 ≤ 0, 지연 비 ≤ 1.5 — 모두.
- 악화: 정답률 CI 상한 < 0, U CI 하한 > 0, 조용한 오답 CI 하한 > 0, 지연 비 > 1.5 — 하나라도.
- 차이 없음(이 셋·k에서 구분되지 않음): 그 밖.
지연 비 = 고정 30문항 순차 셀의 문항 모델 시간 중앙값(``compute_gates.latency``) 후보 / base.
함께 적는 것: 유형(8)·hard factor별 정답률, 거부(올바른 거부·과잉 거부), 잘림·서버 오류, vicinity 빠짐(PROTOCOL_v4 7절, ``analyze_fp8.vicinity``와 같은 정의),
생성 속도(tok/s), 요청 로그 요약, 안정 정답 문항 수.
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PFDIR = Path("/home/hwkim/sftdpo_work/protected_final_v1")
GOLD = PFDIR / "pf1_gold.yaml"
META = PFDIR / "pf1_items_meta.json"
CELLS = PFDIR / "cells"
K = 8
REFUSAL_OUTCOMES = ("unsupported", "needs_clarification")
LAT = {"base": "sft_dpo_inventory/pilot_007/latency/final/latF-base_s1.json", "cand": "sft_dpo_inventory/pilot_007/latency/final/latF-F_s1.json"}
LABELS = {"base": "pf_base", "cand": "pf_cand"}


def final_ok(is_refusal_item, grounding_ok, outcome, analysis_calls):
    """표본 하나의 정답 여부(결정 214). outcome: 파이프라인 결과 상태(answered·unsupported·needs_clarification·failed 등)."""
    refused = outcome in REFUSAL_OUTCOMES
    if is_refusal_item:
        return bool(refused and analysis_calls == 0)
    return bool(grounding_ok is True and not refused)


def classify(cells_by_item, meta):
    """{id: [표본 dict]} → 문항 × 표본 행렬들."""
    ids = sorted(cells_by_item)
    out = {f: np.zeros((len(ids), K)) for f in ("ok", "U", "silent", "truncated", "refused")}
    for x, i in enumerate(ids):
        for s, smp in enumerate(cells_by_item[i]):
            out["ok"][x, s] = smp["ok"]
            out["U"][x, s] = smp["U"]
            out["silent"][x, s] = smp["silent"]
            out["truncated"][x, s] = smp["truncated"] > 0
            out["refused"][x, s] = smp["refused"]
    return ids, out


def ci(d):
    sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
    import compute_gates as CG
    return CG.ci(d)


def judge(A, B, lat_ratio):
    """A·B: 문항 값(문항 × 지표 평균) dict. → 차이·CI·범주."""
    res = {}
    for f in ("ok", "U", "silent"):
        m, (lo, hi) = ci(B[f] - A[f])
        res[f] = {"base_pct": round(100 * float(A[f].mean()), 2), "cand_pct": round(100 * float(B[f].mean()), 2),
                  "diff_pp": round(100 * m, 2), "ci95_pp": [round(100 * lo, 2), round(100 * hi, 2)]}
    lo = {f: res[f]["ci95_pp"][0] for f in res}
    hi_ok = res["ok"]["ci95_pp"][1]
    improve = lo["ok"] > 0 and lo["U"] <= 0 and lo["silent"] <= 0 and lat_ratio is not None and lat_ratio <= 1.5
    worse = hi_ok < 0 or lo["U"] > 0 or lo["silent"] > 0 or (lat_ratio is not None and lat_ratio > 1.5)
    cat = "악화" if worse else ("개선" if improve else "차이 없음(구분 안 됨)")
    res["latency_ratio"] = lat_ratio
    res["conditions"] = {"improve": {"ok_lo_gt_0": lo["ok"] > 0, "U_lo_le_0": lo["U"] <= 0, "silent_lo_le_0": lo["silent"] <= 0,
                                     "latency_le_1.5": None if lat_ratio is None else lat_ratio <= 1.5},
                         "worse": {"ok_hi_lt_0": hi_ok < 0, "U_lo_gt_0": lo["U"] > 0, "silent_lo_gt_0": lo["silent"] > 0,
                                   "latency_gt_1.5": None if lat_ratio is None else lat_ratio > 1.5}}
    res["category"] = cat
    return res


def load_cells(arm, gold, meta):
    sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
    sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/post"))
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    A = CG.scorer()
    A.C.R.C._GOLD["pf1"] = {i.split("/", 1)[1]: it for i, it in gold.items()}
    per_item, info = defaultdict(list), []
    for k in range(1, K + 1):
        p = CELLS / f"{LABELS[arm]}_s{k}.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        A.RAW = Path(d["meta"]["hf"]["raw_out"]).parent
        _, scored = A.load_sample(p, gold)
        src = {r["id"]: r for r in d["rows"]}
        gen = sec = 0
        srv_err = 0
        for i, r in scored.items():
            s = src[i]
            outcome = s.get("outcome")
            analysis = sum(1 for c in (s.get("calls") or []) if c.get("tool") != "get_place_scope")
            refusal_item = meta[i]["refusal"]
            ok = final_ok(refusal_item, r["ok"] if not refusal_item else None, outcome, analysis)
            for c in s.get("hf_calls") or []:
                gen += c.get("eval_count") or c.get("generated_tokens") or 0
                sec += c.get("server_seconds") or 0
            exc = ((s.get("planner_trace") or {}).get("exception") or "")
            srv_err += s.get("error_code") == "UNHANDLED_EXCEPTION" and exc.split(":")[0] in ("URLError", "HTTPError", "ConnectionError", "ConnectionResetError",
                                                                                                "ConnectionRefusedError", "RemoteDisconnected", "TimeoutError")
            g = (s.get("grounding") or {}).get("factors") or {}
            gg = {}
            if not refusal_item:
                import evaluate_vendor100 as EV
                gg = ((EV.gold_grounding(gold[i]) or {}).get("factors") or {})
            per_item[i].append({"ok": ok, "U": r["class"] == A.CS.U_CLASS, "silent": r["class"] == A.CS.SILENT, "truncated": r["truncated"],
                                "refused": outcome in REFUSAL_OUTCOMES, "outcome": outcome, "vic_gold": bool(gg.get("vicinity")),
                                "vic_missing": bool(gg.get("vicinity")) and not g.get("vicinity")})
        v = d["meta"].get("vllm") or {}
        info.append({"k": k, "file_sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "rows": len(d["rows"]), "rows_equal_items": len(d["rows"]) == len(gold),
                     "raw_sha256_match": hashlib.sha256(Path(d["meta"]["hf"]["raw_out"]).read_bytes()).hexdigest() == d["meta"]["hf"]["raw_out_sha256"],
                     "truncated_calls": int(sum(r["truncated"] for r in scored.values())), "server_error_rows": int(srv_err),
                     "model": d["meta"]["model"], "prompt_sha256": d["meta"]["planner_prompt_sha256"][:8], "fingerprint": d["meta"]["code_fingerprint"][:8],
                     "code_commit": d["meta"]["code_commit"][:7], "concurrency": (v.get("concurrency") or {}).get("max_concurrent_requests"),
                     "kernels": v.get("kernels"), "request_log": v.get("request_log"), "gen_tokens": gen, "server_seconds": round(sec, 1),
                     "gen_tok_per_s(call sum)": round(gen / sec, 1) if sec else None})
    return per_item, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--items-out", required=True)
    a = ap.parse_args()
    import evaluate_vendor100 as EV
    gold = {i["id"]: i for i in EV.load_gold(GOLD)["items"]}
    meta = json.loads(META.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
    import compute_gates as CG
    data, info, mats = {}, {}, {}
    for arm in ("base", "cand"):
        per_item, info[arm] = load_cells(arm, gold, meta)
        ids, mats[arm] = classify(per_item, meta)
        data[arm] = per_item
    vals = {arm: {f: m.mean(axis=1) for f, m in mats[arm].items()} for arm in mats}
    lat = {arm: CG.latency(LAT[arm]) for arm in LAT} if all((ROOT / p).exists() for p in LAT.values()) else None
    ratio = round(lat["cand"] / lat["base"], 3) if lat else None
    out = {"judgment": judge(vals["base"], vals["cand"], ratio), "latency_median_model_seconds": lat, "cells": info,
           "gold_yaml_sha256": hashlib.sha256(GOLD.read_bytes()).hexdigest(), "items": len(ids), "k": K}
    # 유형·factor별
    by = {"type": defaultdict(list), "factor": defaultdict(list), "difficulty": defaultdict(list)}
    for x, i in enumerate(ids):
        by["type"][meta[i]["type"]].append(x)
        by["difficulty"][meta[i]["difficulty"]].append(x)
        for f in meta[i]["factors"]:
            by["factor"][f].append(x)
    out["breakdown"] = {g: {name: {"n": len(ix), "base_pct": round(100 * float(vals["base"]["ok"][ix].mean()), 2),
                                   "cand_pct": round(100 * float(vals["cand"]["ok"][ix].mean()), 2)} for name, ix in sorted(d.items())} for g, d in by.items()}
    ref = [x for x, i in enumerate(ids) if meta[i]["refusal"]]
    non = [x for x, i in enumerate(ids) if not meta[i]["refusal"]]
    out["refusal"] = {arm: {"refusal_items": len(ref), "correct_refusal_samples": int(mats[arm]["ok"][ref].sum()), "samples": len(ref) * K,
                            "correct_refusal_items_majority": int((mats[arm]["ok"][ref].mean(axis=1) >= 0.5).sum()),
                            "over_refusal_samples(non-refusal items)": int(mats[arm]["refused"][non].sum()), "non_refusal_samples": len(non) * K,
                            "over_refusal_items(any sample)": int((mats[arm]["refused"][non].sum(axis=1) > 0).sum())} for arm in mats}
    vic = {}
    for arm in data:
        vi = [i for i in ids if data[arm][i][0]["vic_gold"]]
        miss = sum(s["vic_missing"] for i in vi for s in data[arm][i])
        vic[arm] = {"gold_vicinity_items": len(vi), "missing_item_samples": int(miss), "rate_pct": round(100 * miss / (len(vi) * K), 2) if vi else None}
    vi = [x for x, i in enumerate(ids) if data["base"][i][0]["vic_gold"]]
    if vi:
        mb = np.array([[s["vic_missing"] for s in data["base"][ids[x]]] for x in vi], dtype=float).mean(axis=1)
        mc = np.array([[s["vic_missing"] for s in data["cand"][ids[x]]] for x in vi], dtype=float).mean(axis=1)
        m, (lo, hi) = ci(mc - mb)
        vic["cand_minus_base_pp"] = {"diff": round(100 * m, 2), "ci95": [round(100 * lo, 2), round(100 * hi, 2)]}
    out["vicinity_missing(PROTOCOL_v4 7절, 판정에 안 씀)"] = vic
    out["stable"] = {arm: {"all_k_correct_items": int((mats[arm]["ok"].mean(axis=1) == 1).sum()), "all_k_wrong_items": int((mats[arm]["ok"].mean(axis=1) == 0).sum())} for arm in mats}
    out["truncation"] = {arm: {"truncated_samples": int(mats[arm]["truncated"].sum()), "samples": len(ids) * K} for arm in mats}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    items = {meta[i]["number"]: {arm: {"ok": [int(v) for v in mats[arm]["ok"][x]], "U": [int(v) for v in mats[arm]["U"][x]], "silent": [int(v) for v in mats[arm]["silent"][x]],
                                       "truncated": [int(v) for v in mats[arm]["truncated"][x]], "refused": [int(v) for v in mats[arm]["refused"][x]]} for arm in mats}
             for x, i in enumerate(ids)}
    Path(a.items_out).write_text(json.dumps({"note": "문항 번호별 판정 값(k=8 표본 순서), 문장 없음(결정 215)", "items": items}, ensure_ascii=False) + "\n", encoding="utf-8")
    j = out["judgment"]
    print(json.dumps({"category": j["category"], "ok": j["ok"], "U": j["U"], "silent": j["silent"], "latency_ratio": j["latency_ratio"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
