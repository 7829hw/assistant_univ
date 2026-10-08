# -*- coding: utf-8 -*-
"""pilot_002 업체 100 판정(PROTOCOL_v2: PROTOCOL 7절 + v2 2.1절)과 삼자 비교(ADDENDUM_three_way, 보조 분석). 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_002/vendor100/judge.py

pilot_001 ``judge.py``의 사본이다. 다른 것:
- 개선·악화 기준이 PROTOCOL_v2 2.1절이다(U 순증 ≤ 2 / ≥ 3, 조용한 오답 순증 ≤ 2 / ≥ 3).
- 결정 15 family 분리의 학습 질문은 pilot_002 데이터(``thinking_pilot002_t2pc``의 SFT·DPO 질문, gold ``reviewed_gold_v005_t2pc``)다.
  결정 54의 겹침 문항(``data/overlap.json``의 업체 100 template·family 겹침)을 따로 적는다.

- 채점·분류: ``baseline_conditions_001/compare_cells.py``(grounding_check 재채점, v4 축, grounding_v13 U1–U4, 보고 분류).
- PROTOCOL 판정(주 비교 = 최종, SFT는 참고):
  - HF 경로: HF-E → HF-최종(주), HF-E → HF-SFT(참고).
  - 운영 경로: E → Ollama-최종(주), E → Ollama-SFT(참고).
  - 개선: b > c, McNemar 양측 p < 0.05, U 순증 ≤ 2, 조용한 오답 순증 ≤ 2.
  - 악화: c > b이고 p < 0.05, 또는 U 순증 ≥ 3, 또는 조용한 오답 순증 ≥ 3, 또는(운영 셀만) 지연 중앙값 > 기준 × 1.5.
  - 그 밖은 차이 없음("이 크기의 셋에서 구분되지 않는다").
  - 정책·모호 라벨(label_audit, dev_report.policy_ambiguous)의 업체 100 문항은 없어서, 뺀 값은 전체 값과 같다(확인해 적는다).
- 삼자 비교(판정에 쓰지 않음): 학습 모델마다 E·B-conv·학습 모델. 쌍 3개, 8가지 O/X 조합별 문항 id, U 조합, family 분리.
- 기준 셀 선택(결정 31): ``vendor100/E.json``·``B-conv.json``(버전이 바뀌어 다시 쟀으면)이 있으면 그것, 없으면 pilot_prep_003의 기록.
"""
import importlib.util
import json
import math
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("compare_cells", ROOT / "sft_dpo_inventory/baseline_conditions_001/compare_cells.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

PREP = ROOT / "sft_dpo_inventory/pilot_prep_003/ollama"
CELLS = {
    "HF-E": ROOT / "sft_dpo_inventory/thinking_prep_001/hf_e/HF-E_run1.json",
    "HF-sft": HERE / "HF-sft.json", "HF-final": HERE / "HF-final.json",
    "E": HERE / "E.json" if (HERE / "E.json").exists() else PREP / "E.json",
    "B-conv": HERE / "B-conv.json" if (HERE / "B-conv.json").exists() else PREP / "B-conv.json",
    "Ollama-sft": HERE / "Ollama-sft.json", "Ollama-final": HERE / "Ollama-final.json",
}
JUDGED = [("HF-E", "HF-final", "HF 경로 주 비교", False), ("HF-E", "HF-sft", "HF 경로 참고 비교", False),
          ("E", "Ollama-final", "운영 경로 주 비교", True), ("E", "Ollama-sft", "운영 경로 참고 비교", True)]
DATA = ROOT / "training/generated/thinking_pilot002_t2pc"
GOLD_V005 = ROOT / "training/generated/reviewed_gold_v005_t2pc/sft_train.jsonl"
OVERLAP = HERE.parent / "data/overlap.json"
U_CLASS, SILENT = "용납할 수 없는 실패", "조용한 오답(U 아님)"


def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(max(b, c), n + 1)) / 2 ** n)


def median(values):
    values = sorted(values)
    n = len(values)
    return (values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2) if n else None


def pair(a, b, cells, latency, in_family, ops):
    A, B = cells[a], cells[b]
    keys = sorted(set(A) & set(B))
    gained = [k for k in keys if not A[k]["grounding_ok"] and B[k]["grounding_ok"]]
    lost = [k for k in keys if A[k]["grounding_ok"] and not B[k]["grounding_ok"]]
    bb, cc = len(gained), len(lost)
    p = mcnemar(bb, cc)
    u_a = {k for k in keys if A[k]["report_class"] == U_CLASS}
    u_b = {k for k in keys if B[k]["report_class"] == U_CLASS}
    s_a = {k for k in keys if A[k]["report_class"] == SILENT}
    s_b = {k for k in keys if B[k]["report_class"] == SILENT}
    ratio = round(latency[b] / latency[a], 3)
    out = {"pair": f"{a}→{b}", "common": len(keys),
           "grounding_ok": [sum(A[k]["grounding_ok"] for k in keys), sum(B[k]["grounding_ok"] for k in keys)],
           "transitions": {f"{x}→{y}": sum(1 for k in keys if ("O" if A[k]["grounding_ok"] else "X") == x
                                          and ("O" if B[k]["grounding_ok"] else "X") == y) for x in "OX" for y in "OX"},
           "b": bb, "c": cc, "mcnemar_p": round(p, 4), "gained": gained, "lost": lost,
           "U": [len(u_a), len(u_b)], "U_net": len(u_b) - len(u_a), "U_new": sorted(u_b - u_a), "U_gone": sorted(u_a - u_b),
           "silent": [len(s_a), len(s_b)], "silent_net": len(s_b) - len(s_a), "silent_new": sorted(s_b - s_a),
           "silent_gone": sorted(s_a - s_b),
           "classes": {name: {cls: sum(1 for k in keys if cells[name][k]["report_class"] == cls)
                              for cls in ("정상 답변", "안전한 실패", SILENT, U_CLASS)} for name in (a, b)},
           "latency_median_s": [latency[a], latency[b]], "latency_ratio": ratio,
           "family_split": {part: {"b": sum(1 for k in gained if (k in in_family) == (part == "in_family")),
                                   "c": sum(1 for k in lost if (k in in_family) == (part == "in_family")),
                                   "items": sum(1 for k in keys if (k in in_family) == (part == "in_family")),
                                   "grounding_ok": [sum(A[k]["grounding_ok"] for k in keys if (k in in_family) == (part == "in_family")),
                                                    sum(B[k]["grounding_ok"] for k in keys if (k in in_family) == (part == "in_family"))]}
                            for part in ("in_family", "outside")}}
    improve = bb > cc and p < 0.05 and out["U_net"] <= 2 and out["silent_net"] <= 2
    worse_reasons = []
    if cc > bb and p < 0.05:
        worse_reasons.append("grounding_ok 감소(McNemar p<0.05)")
    if out["U_net"] >= 3:
        worse_reasons.append(f"U 순증 {out['U_net']}")
    if out["silent_net"] >= 3:
        worse_reasons.append(f"조용한 오답 순증 {out['silent_net']}")
    if ops and ratio > 1.5:
        worse_reasons.append(f"지연 중앙값 {ratio}배 > 1.5")
    out["verdict"] = "악화" if worse_reasons else "개선" if improve else "차이 없음"
    out["verdict_reasons"] = worse_reasons if worse_reasons else (
        ["b > c, p < 0.05, U·조용한 오답 순증 ≤ 2"] if improve else ["개선·악화 조건 모두 아님(이 크기의 셋에서 구분되지 않음)"])
    return out


def main():
    import evaluate_vendor100 as EV
    from training.annotations.inventory import family_key
    from training.data.common import read_jsonl
    sys.path.insert(0, str(ROOT / "sft_dpo_inventory"))
    from policy_scale import exclusion_keys
    present = {n: p for n, p in CELLS.items() if p.exists()}
    empty = HERE / ".empty_arm"
    empty.mkdir(exist_ok=True)
    cells = {n: C.load_cell(p, empty) for n, p in present.items()}
    empty.rmdir()
    latency = {n: round(median([(i["total_ms"] or 0) / 1000 for i in items.values()]), 2) for n, items in cells.items()}
    # 결정 15: pilot_002 학습 데이터(SFT·DPO)에 실제로 들어간 질문의 gold family
    train_ids = {r["metadata"]["source_record_id"] for name in ("sft_train.jsonl", "dpo_train.jsonl")
                 for r in read_jsonl(DATA / name)}
    families = {family_key(json.loads(r["messages"][-1]["content"])) for r in read_jsonl(GOLD_V005)
                if r["metadata"]["source_record_id"] in train_ids}
    in_family = {it["id"] for it in EV.load_gold(None)["items"]
                 if EV.gold_grounding(it) is not None and family_key(EV.gold_grounding(it)) in families}
    policy = sorted(k.split("/", 1)[1] for k in exclusion_keys() if k.startswith("dev/"))
    meta = {}
    for n, p in present.items():
        m = json.loads(p.read_text(encoding="utf-8"))["meta"]
        meta[n] = {k: m.get(k) for k in ("model", "model_digest", "ollama_version", "planner_prompt_sha256", "code_commit",
                                         "reference_date")}
        fp = m.get("code_fingerprint")
        meta[n]["code_fingerprint"] = fp.get("sha256") if isinstance(fp, dict) else fp
        meta[n]["source"] = str(p.relative_to(ROOT))
    out = {"cells": {n: {**C.summary(cells[n]), "latency_median_s": latency[n], "meta": meta[n],
                         "U": sum(i["report_class"] == U_CLASS for i in cells[n].values()),
                         "silent": sum(i["report_class"] == SILENT for i in cells[n].values())} for n in cells},
           "policy_ambiguous_vendor_items": policy,
           "family(decision 15)": {"train_questions": len(train_ids), "train_families": len(families),
                                   "vendor_items_in_family": sorted(in_family)},
           "overlap(decision 54)": {kind: sorted({h["eval_id"] for h in hits}) for kind, hits in
                                    json.loads(OVERLAP.read_text(encoding="utf-8"))["sets"]["vendor100"].items()
                                    if kind in ("template", "family")},
           "protocol": {}, "three_way(not used for judgment)": {}}
    for a, b, label, ops in JUDGED:
        if a in cells and b in cells:
            out["protocol"][label] = pair(a, b, cells, latency, in_family, ops)
            if policy:
                out["protocol"][label]["policy_excluded"] = "see policy_ambiguous_vendor_items"
            else:
                out["protocol"][label]["policy_excluded"] = "업체 100에 정책·모호 라벨 문항 없음: 뺀 값 = 전체 값"
    for stage in ("sft", "final"):
        model = f"Ollama-{stage}"
        if not all(x in cells for x in ("E", "B-conv", model)):
            out["three_way(not used for judgment)"][stage] = {"status": "not available",
                                                               "missing": [x for x in ("E", "B-conv", model) if x not in cells]}
            continue
        names = ("E", "B-conv", model)
        keys = sorted(set(cells["E"]) & set(cells["B-conv"]) & set(cells[model]))
        combos = {}
        for combo in product("OX", repeat=3):
            ids = [k for k in keys if all(("O" if cells[n][k]["grounding_ok"] else "X") == c for n, c in zip(names, combo))]
            combos[" ".join(combo)] = {"n": len(ids), "ids": ids}
        ucombos = {}
        for combo in product("UN", repeat=3):
            ids = [k for k in keys if all(("U" if cells[n][k]["report_class"] == U_CLASS else "N") == c
                                          for n, c in zip(names, combo))]
            if ids:
                ucombos[" ".join(combo)] = {"n": len(ids), "ids": ids}
        out["three_way(not used for judgment)"][stage] = {
            "cells": names, "versions": {n: meta[n].get("ollama_version") for n in names},
            "pairs": {"E→B-conv(변환 효과)": pair("E", "B-conv", cells, latency, in_family, True),
                      f"B-conv→{model}(학습 효과)": pair("B-conv", model, cells, latency, in_family, True),
                      f"E→{model}(PROTOCOL 쌍 재표시)": pair("E", model, cells, latency, in_family, True)},
            "grounding_ok_combinations(E B-conv model)": combos, "U_combinations(E B-conv model)": ucombos}
        for p in out["three_way(not used for judgment)"][stage]["pairs"].values():
            p.pop("verdict", None)
            p.pop("verdict_reasons", None)
    (HERE / "judgment.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for label, r in out["protocol"].items():
        print(label, r["pair"], r["grounding_ok"], "b", r["b"], "c", r["c"], "p", r["mcnemar_p"], "U", r["U"], "silent",
              r["silent"], "lat", r["latency_ratio"], "=>", r["verdict"], r["verdict_reasons"])
    for stage, t in out["three_way(not used for judgment)"].items():
        print("three-way", stage, t.get("status", ""), {k: v["n"] for k, v in t.get("grounding_ok_combinations(E B-conv model)", {}).items()})


if __name__ == "__main__":
    main()
