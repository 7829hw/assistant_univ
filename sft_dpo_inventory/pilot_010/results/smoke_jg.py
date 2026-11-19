# -*- coding: utf-8 -*-
"""pilot_010 JG smoke 판정(결정 270, PLAN_JG 1절). 측정 전에 커밋한다. 모델 호출 없음. **판정 뒤 추가(사후).**

    python3 sft_dpo_inventory/pilot_010/results/smoke_jg.py --out sft_dpo_inventory/pilot_010/results/jg_smoke.json

- 셀 3개(G0, H-dev 앞 300문항): ``cells/JG/smoke/hdev300g0_{base,b2f_o43,v4_o101}_s1.json``.
- 잘림 비율 = 잘린 호출 수 / 호출 수(행의 ``hf_calls`` 중 ``finish_reason == "length"``, ``validity_j``·``completeness_B``와 같은 호출 단위), 반올림 없이 비교.
- 비교 기준(같은 모델의 기존 sampling 셀, PLAN_JG 1절):
  - base = ``ablation_012/cells/hdev_base_s1·s2``의 같은 300문항(두 회차 호출을 합친 비율).
  - SFT ``o43``·RR+NM4 ``o101``: 같은 300문항의 H-dev sampling 셀이 저장소에 없다. 대신 같은 어댑터의 H-final sampling 셀
    (``cells/J/hfinal_b2f_o43_s1``·``hfinal_v4_o101_s1``, 3,000문항, 같은 하네스·동시 32)의 비율을 쓴다(PLAN_JG 1절, smoke 전에 고정).
- 규칙: 세 셀 중 하나라도 (G0 비율 > 3%) 또는 (G0 비율 > 2 × 기준 비율)이면 G0를 버리고 G1. 아니면 G0.
  **정답률·거부율은 판단에 쓰지 않는다**: 판단을 먼저 계산해 적은 뒤, 보고용으로만 300문항 정답률·과잉 거부율을 덧붙인다.
- 셀이 300행이 아니거나 하나라도 없으면 멈춘다(판단하지 않음).
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
INV = P10.parent
ROOT = INV.parent
SMOKE = P10 / "cells/JG/smoke"
CELLS = {"base": SMOKE / "hdev300g0_base_s1.json", "SFT o43": SMOKE / "hdev300g0_b2f_o43_s1.json", "RR+NM4 o101": SMOKE / "hdev300g0_v4_o101_s1.json"}
REF = {"base": ([INV / "ablation_012/cells/hdev_base_s1.json", INV / "ablation_012/cells/hdev_base_s2.json"], "same300"),
       "SFT o43": ([P10 / "cells/J/hfinal_b2f_o43_s1.json"], "all"), "RR+NM4 o101": ([P10 / "cells/J/hfinal_v4_o101_s1.json"], "all")}
REFUSAL_OUTCOMES = ("unsupported", "needs_clarification")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def trunc(rows):
    calls = [c for r in rows for c in (r.get("hf_calls") or [])]
    t = sum(1 for c in calls if c.get("finish_reason") == "length")
    return {"calls": len(calls), "truncated_calls": t, "pct": 100.0 * t / max(1, len(calls))}


def report_only(rows):
    n = len(rows)
    refused = sum(1 for r in rows if r.get("outcome") in REFUSAL_OUTCOMES and not any(x.get("tool") != "get_place_scope" for x in (r.get("calls") or [])))
    return {"accuracy_pct": round(100 * sum(r.get("category") == "match" for r in rows) / n, 2), "over_refusal_pct": round(100 * refused / n, 2), "items": n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = {}
    for k, p in CELLS.items():
        if not p.exists():
            raise SystemExit(f"missing smoke cell {p}")
        d = json.loads(p.read_text(encoding="utf-8"))
        if len(d["rows"]) != 300:
            raise SystemExit(f"{p.name}: {len(d['rows'])} rows != 300")
        data[k] = d
    ids = [r["id"] for r in data["base"]["rows"]]
    if any([r["id"] for r in d["rows"]] != ids for d in data.values()):
        raise SystemExit("smoke cells differ in items")
    # ---- 판단(잘림만) ----
    decision = {}
    for k, d in data.items():
        g = trunc(d["rows"])
        refs, scope = REF[k]
        rr = []
        for p in refs:
            rows = json.loads(p.read_text(encoding="utf-8"))["rows"]
            rr += [r for r in rows if r["id"] in set(ids)] if scope == "same300" else rows
        ref = trunc(rr)
        over3, over2x = g["pct"] > 3.0, g["pct"] > 2.0 * ref["pct"]
        decision[k] = {"g0": {**g, "pct": round(g["pct"], 4)}, "reference": {**ref, "pct": round(ref["pct"], 4), "cells": [str(p.relative_to(ROOT)) for p in refs],
                                                                            "cells_sha256": [sha(p) for p in refs], "scope": scope},
                       "g0_over_3pct": over3, "g0_over_2x_reference": over2x, "reject_g0": over3 or over2x}
    chosen = "G1" if any(v["reject_g0"] for v in decision.values()) else "G0"
    res = {"decision": 270, "plan": "sft_dpo_inventory/pilot_010/PLAN_JG.md", "label": "판정 뒤 추가(사후); smoke = 개발 셋 H-dev 앞 300문항",
           "rule": "any cell: g0 truncation pct > 3 or > 2 x reference pct -> G1, else G0 (accuracy/refusal not used)",
           "chosen_condition": chosen, "cells": {k: {"file": str(CELLS[k].relative_to(ROOT)), "sha256": sha(CELLS[k]),
                                                      "decoding": data[k]["meta"]["hf"]["decoding"], "wall_s": data[k]["meta"]["vllm"].get("wall_seconds")} for k in CELLS},
           "truncation": decision}
    # ---- 보고용(판단 뒤) ----
    base_ref = [r for p in REF["base"][0] for r in json.loads(p.read_text(encoding="utf-8"))["rows"] if r["id"] in set(ids)]
    res["report_only_not_used_for_decision"] = {"g0": {k: report_only(d["rows"]) for k, d in data.items()},
                                                "base_sampling_same300_two_runs_pooled": report_only(base_ref)}
    res["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    res["script_sha256"] = sha(__file__)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"chosen": chosen, **{k: (v["g0"]["pct"], v["reference"]["pct"], v["reject_g0"]) for k, v in decision.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
