# -*- coding: utf-8 -*-
"""pilot_005 업체 100 판정과 aux_test_v1·valid98 보고(PROTOCOL_v5 5절 = v4 5–7절, 보정 없음). 모델 호출 없음.

    HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python sft_dpo_inventory/pilot_005/vendor100/judge5.py {vendor100|aux|valid98|all}

pilot_004 ``vendor100/judge4.py``의 사본이고, 바꾼 것은 셀·원문 위치(pilot_005)와 valid98 gold 위치(pilot_004의 것을 그대로 읽음), family 분리 파일
(pilot_004 ``data/overlap.json``: 학습 데이터가 같은 판이라 그대로 쓴다)뿐이다. "final"은 고른 후보(``../selection.json``)다.

- 셀 통계·비교는 ``pilot_003/vendor100/judge_v3.py``(analyze_cal 함수, U 키 연결)와 같은 계산이다. 비교마다 ``default_rng(20261109)``.
  셀마다 k가 다를 수 있다(27b k=4). 비교는 문항별 k표본 평균의 쌍 bootstrap이다.
- 업체 100 판정(PROTOCOL_v4 6절): A = vLLM-base, B = vLLM-최종(BF16, flashinfer, 동시 요청 8, k=8).
  개선: grounding_ok CI 하한 > 0, U CI 하한 ≤ 0, 조용한 오답 CI 하한 ≤ 0, 지연 조건 만족. 악화: grounding_ok CI 상한 < 0, U CI 하한 > 0, 조용한 오답 CI 하한 > 0,
  지연 조건 불만족 중 하나. 지연 조건: 고정 30문항 순차 측정(``latency/lat-{base,final}_s1.json``)의 문항 모델 시간 중앙값 비(최종/base) ≤ 1.5.
- 참고 비교(판정 없음): E → vLLM-base, E → vLLM-최종, 27b → vLLM-최종(27b는 운영 조건 greedy와 다름).
- 함께 적는 것: 셀별 평균·표본별 값, 안정 정답, 새로 생긴·사라진 U·조용한 오답 문항, 오류 유형, 잡음 폭, family 분리(결정 15, ``data/overlap.json``),
  vicinity 빠짐(결정 94·97), 실차 통행량 오독 문항, 표본별 장치·동시 요청·커널·요청 로그 요약.
- valid98: base·최종 k=4, 보조. 실차 h30(heldout_v9/h30)의 표본별 결과를 따로 적는다.
- 결과: ``vendor100/judgment.json``, ``aux_test/comparison.json``, ``valid98/comparison.json``.
"""
import json
import statistics
import sys
from itertools import product
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P4 = HERE.parent
ROOT = P4.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/vendor100"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/serving_vllm_fp8"))
import judge_v3 as J  # noqa: E402
import analyze_fp8 as F  # noqa: E402

A = J.A
A.C.R.C.GOLD_FILES.update({"stage_v7": "evaluation/grounding_v7/stage_contrast_questions.yaml",
                           "heldout_v8": "evaluation/grounding_v8/heldout_questions.yaml",
                           "heldout_v9": "evaluation/grounding_v9/heldout_questions.yaml"})
RAW = ROOT / "training/generated/pilot_005/raw"
P4DATA = ROOT / "sft_dpo_inventory/pilot_004"
SETS = {
    "vendor100": {"gold": ROOT / "evaluation/vendor100/gold.yaml", "dir": P4 / "vendor100/runs",
                  "cells": {"vLLM-base": ("v100-base", 8), "vLLM-final": ("v100-final", 8), "E": ("v100-E", 8), "27b": ("v100-27b", 4)},
                  "judged": ("vLLM-base", "vLLM-final"), "reference": [("E", "vLLM-base"), ("E", "vLLM-final"), ("27b", "vLLM-final")],
                  "out": P4 / "vendor100/judgment.json"},
    "aux": {"gold": ROOT / "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml", "dir": P4 / "aux_test/runs",
            "cells": {"vLLM-base": ("aux-base", 4), "vLLM-final": ("aux-final", 4), "E": ("aux-E", 4)}, "judged": None,
            "reference": [("vLLM-base", "vLLM-final"), ("E", "vLLM-base"), ("E", "vLLM-final")], "out": P4 / "aux_test/comparison.json"},
    "valid98": {"gold": P4DATA / "valid98/valid98_gold.yaml", "dir": P4 / "valid98/runs",
                "cells": {"vLLM-base": ("v98-base", 4), "vLLM-final": ("v98-final", 4)}, "judged": None,
                "reference": [("vLLM-base", "vLLM-final")], "out": P4 / "valid98/comparison.json"},
}


def latency_condition():
    out = {}
    for m in ("base", "final"):
        d = json.loads((P4 / f"latency/lat-{m}_s1.json").read_text(encoding="utf-8"))
        secs = [sum((c.get("duration_ms") or 0) for c in r.get("llm_calls") or []) / 1000 for r in d["rows"]]
        rates = [c["eval_count"] / (c["duration_ms"] / 1000) for r in d["rows"] for c in r.get("llm_calls") or []
                 if c.get("eval_count") and c.get("duration_ms")]
        out[m] = {"items": len(secs), "item_model_seconds_median": round(statistics.median(secs), 2),
                  "gen_tokens_per_s_median": round(statistics.median(rates), 1)}
    e = P4 / "latency/lat-E_s1.json"
    if e.exists():
        d = json.loads(e.read_text(encoding="utf-8"))
        secs = [sum((c.get("duration_ms") or 0) for c in r.get("llm_calls") or []) / 1000 for r in d["rows"]]
        rates = [c["eval_count"] / ((c.get("eval_duration_ms") or ((c.get("duration_ms") or 0) - (c.get("load_duration_ms") or 0))) / 1000)
                 for r in d["rows"] for c in r.get("llm_calls") or [] if c.get("eval_count")]
        out["E(reference)"] = {"items": len(secs), "item_model_seconds_median": round(statistics.median(secs), 2),
                               "gen_tokens_per_s_median": round(statistics.median(rates), 1)}
    ratio = out["final"]["item_model_seconds_median"] / out["base"]["item_model_seconds_median"]
    out["ratio_final_over_base"] = round(ratio, 3)
    out["condition_ok(<=1.5)"] = ratio <= 1.5
    return out


def verdict(r, lat_ok, lat_ratio):
    lo, hi = r["ci95_pct"]
    worse = [why for cond, why in ((hi < 0, "grounding_ok CI 상한 < 0"), (r["U_ci95_pct"][0] > 0, "U 비율 CI 하한 > 0"),
                                   (r["silent_ci95_pct"][0] > 0, "조용한 오답 비율 CI 하한 > 0"),
                                   (not lat_ok, f"지연 중앙값 비 {lat_ratio} > 1.5(고정 30문항 순차)")) if cond]
    if worse:
        return "악화", worse
    if lo > 0 and r["U_ci95_pct"][0] <= 0 and r["silent_ci95_pct"][0] <= 0 and lat_ok:
        return "개선", ["grounding_ok CI 하한 > 0, U·조용한 오답 CI 하한 ≤ 0, 지연 비 ≤ 1.5"]
    return "차이 없음", ["개선·악화 조건 모두 아님(이 셋·k에서 구분되지 않음)"]


def run(name):
    cfg = SETS[name]
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    data = {}
    for cell, (label, k) in cfg["cells"].items():
        # vLLM 셀은 <set>/runs, Ollama 셀(run_vendor5.sh ollama_cell)은 <set>/에 쓴다. 둘 다 본다(2026-10-15 판정 전 수정).
        cdir = next((d for d in (cfg["dir"], cfg["dir"].parent) if (d / f"{label}_s1.json").exists()), None)
        if cdir is None:
            continue
        A.RAW = RAW
        samples, metas = J.load_cell({"runs": cdir, "prefix": "", "k": k}, label, gold)
        if samples is None:
            continue
        data[cell] = {"samples": samples, "meta": metas, "label": label, "k": k, "dir": cdir}
    common = set.intersection(*[set(s) for c in data.values() for s in c["samples"]])
    ids = [i for i in gold if i in common]
    for cell, d in data.items():
        d["m"] = J.mats(d["samples"], ids)
        d["stats"] = J.cell_summary(d["samples"], d["m"], ids, d["k"])
        d["stats"]["vicinity_missing(decision 94·97)"], d["m"]["vic"] = F.vicinity(d["dir"], d["label"], ids, gold, d["k"])
        d["stats"]["run_meta"] = F.run_meta(d["dir"], d["label"]) if d["label"].split("-")[-1] in ("base", "final") else None
    out = {"set": name, "items": len(ids), "cells": {c: {"k": d["k"], "stats": d["stats"], "samples": d["meta"]} for c, d in data.items()},
           "missing_cells": [c for c in cfg["cells"] if c not in data], "comparisons": {}}
    pairs = ([cfg["judged"]] if cfg["judged"] else []) + cfg["reference"]
    for a, b in pairs:
        if a in data and b in data:
            r = J.versus(a, b, data[a]["m"], data[b]["m"], data[a]["stats"], data[b]["stats"], ids)
            dv = data[b]["m"]["vic"].mean(axis=1) - data[a]["m"]["vic"].mean(axis=1)
            r["vicinity_missing_diff_pct"] = round(100 * float(dv.mean()), 2)
            r["vicinity_missing_ci95_pct"] = [round(100 * x, 2) for x in A.boot_ci(dv, np.random.default_rng(J.SEED))]
            out["comparisons"][f"{a}→{b}"] = r
    if cfg["judged"]:
        lat = latency_condition()
        out["latency(sequential 30)"] = lat
        r = out["comparisons"]["vLLM-base→vLLM-final"]
        r["verdict"], r["verdict_reasons"] = verdict(r, lat["condition_ok(<=1.5)"], lat["ratio_final_over_base"])
        out["judgment"] = {"pair": r["pair"], "verdict": r["verdict"], "reasons": r["verdict_reasons"]}
        ov = json.loads((P4DATA / "data/overlap.json").read_text(encoding="utf-8"))["sets"]["vendor100"]
        in_family = sorted({h["eval_id"] for h in ov["family"]})
        fam = {"in_family_items": in_family}
        a, b = cfg["judged"]
        for part, sel in (("in_family", [i in in_family for i in ids]), ("outside", [i not in in_family for i in ids])):
            idx = np.array(sel)
            ma, mb = J.subset(data[a]["m"], idx), J.subset(data[b]["m"], idx)
            fam[part] = {"items": int(idx.sum()), "A_mean_pct": round(100 * float(ma["ok"].mean()), 2),
                         "B_mean_pct": round(100 * float(mb["ok"].mean()), 2), **J.diff_ci(ma, mb)}
        out["family(decision 15, no judgment)"] = fam
        if all(c in data for c in ("E", "vLLM-base", "vLLM-final")):
            names = ("E", "vLLM-base", "vLLM-final")
            o = {n: {i: v >= 0.5 for i, v in zip(ids, data[n]["m"]["ok"].mean(axis=1))} for n in names}
            out["three_way(E vLLM-base vLLM-final, item mean ≥ 0.5 = O, no judgment)"] = {
                " ".join(c): {"n": len(s), "ids": s} for c in product("OX", repeat=3)
                for s in [[i for i in ids if all(("O" if o[n][i] else "X") == x for n, x in zip(names, c))]]}
    if name == "valid98":
        h = "heldout_v9/h30"
        out["h30(real-trip, protected form)"] = {c: [{"ok": s[h]["ok"], "class": s[h]["class"], "outcome": s[h]["outcome"],
                                                       "occupied_misread": bool(s[h]["occupied_misread"])} for s in d["samples"]]
                                                  for c, d in data.items() if h in ids}
    cfg["out"].parent.mkdir(parents=True, exist_ok=True)
    cfg["out"].write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n", encoding="utf-8")
    for c, d in data.items():
        s = d["stats"]
        print(f"{name} {c:10s} k{d['k']} mean {s['mean_pct']:6.2f} U {s['u_pct']:5.2f} silent {s['silent_pct']:5.2f} stable {s['stable_correct']} "
              f"cap {s['length_capped_calls']} loop {s['loop_calls']} occ {s['occupied_misread_items']} vic {s['vicinity_missing(decision 94·97)']}")
    for k, r in out["comparisons"].items():
        print(f"{name} {k:22s} d {r['diff_pct']} CI {r['ci95_pct']} | U {r['U_diff_pct']} CI {r['U_ci95_pct']} | silent {r['silent_diff_pct']} "
              f"CI {r['silent_ci95_pct']} | vic {r['vicinity_missing_diff_pct']} {r.get('verdict', '')}")
    if "latency(sequential 30)" in out:
        print("latency", out["latency(sequential 30)"])
    if "h30(real-trip, protected form)" in out:
        print("h30", out["h30(real-trip, protected form)"])


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    for n in (["vendor100", "aux", "valid98"] if what == "all" else [what]):
        run(n)
