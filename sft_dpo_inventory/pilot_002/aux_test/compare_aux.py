# -*- coding: utf-8 -*-
"""aux_test_v1(51문항) 보고(PROTOCOL_v2 2.2절). 판정에 쓰지 않는다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_002/aux_test/compare_aux.py

- 업체 100과 같은 셀·지표로 보고한다: grounding_ok, b·c·McNemar p, 보고 분류, U·조용한 오답 순증과 문항 목록, 지연.
- Ollama 셀(``evaluate_vendor100.py --gold aux_test_gold.yaml`` 출력): 업체 100 판정과 같은 분류 코드
  (``evaluate_vendor100.axes_rows``의 v4 축, ``grounding_v13/report.unacceptable``의 U1–U4, ``compare_cells.report_class``).
  gold는 결과 meta의 ``gold_file``(aux_test_gold.yaml)이고, U 판정의 문항 조회는 원본 셋(at, final_v12) 파일이다.
- HF 셀(``pilot_prep_005/sets/eval_set.py`` 출력, base 기준값 27을 잰 것과 같은 스크립트): 결과에 호출·최종 답 기록이 없어
  v4 축과 U·조용한 오답을 셀 수 없다. grounding_ok, b·c·p, 결과 분류(outcome:error_code), 업체식 분류, 지연, 생성 상한 호출만 낸다.
- 비교 쌍: HF-E→HF-final(주)·HF-sft, E→Ollama-final(주)·Ollama-sft, 삼자(E→B-conv, B-conv→학습 모델).
- 결과: ``comparison.json``.
"""
import importlib.util
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("compare_cells", ROOT / "sft_dpo_inventory/baseline_conditions_001/compare_cells.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
C.R.C.GOLD_FILES["final_v12"] = "evaluation/grounding_v12/final_questions.yaml"
import evaluate_vendor100 as EV  # noqa: E402

HF_CELLS = {"HF-E": ROOT / "sft_dpo_inventory/pilot_prep_005/sets/runs/aux_test_base.json",
            "HF-sft": HERE / "HF-sft.json", "HF-final": HERE / "HF-final.json"}
OLLAMA_CELLS = {"E": HERE / "E.json", "B-conv": HERE / "B-conv.json",
                "Ollama-sft": HERE / "Ollama-sft.json", "Ollama-final": HERE / "Ollama-final.json"}
PAIRS = [("HF-E", "HF-final", "HF 경로 주 비교"), ("HF-E", "HF-sft", "HF 경로 참고 비교"),
         ("E", "Ollama-final", "운영 경로 주 비교"), ("E", "Ollama-sft", "운영 경로 참고 비교"),
         ("E", "B-conv", "삼자: 변환 효과"), ("B-conv", "Ollama-final", "삼자: 학습 효과(최종)"),
         ("B-conv", "Ollama-sft", "삼자: 학습 효과(SFT)")]
U_CLASS, SILENT = "용납할 수 없는 실패", "조용한 오답(U 아님)"


def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(max(b, c), n + 1)) / 2 ** n)


def load_hf(path):
    res = json.loads(path.read_text(encoding="utf-8"))
    return {r["id"]: {"grounding_ok": bool(r["grounding_ok"]), "report_class": None, "seconds": r["seconds"],
                      "outcome": f"{r['outcome']}:{r['error_code']}", "vendor_style": r["vendor_style_category"],
                      "truncated": sum(d == "length" for d in r["done_reasons"])} for r in res["rows"]}, res["meta"]


def load_ollama(path):
    meta, rows = EV.axes_rows(str(path))
    source = {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["rows"]}
    gold = {i["id"]: i for i in EV.load_gold(ROOT / meta["gold_file"])["items"]}
    out = {}
    for row in rows:
        key, src = row["id"], source[row["id"]]
        flags = C.R.unacceptable(key, row, src)
        regraded, _ = EV.grounding_check(gold[key], src.get("grounding"))
        out[key] = {"grounding_ok": bool(regraded), "grounding_ok_recorded": src.get("grounding_ok"),
                    "report_class": C.report_class(row, flags), "u_flags": flags, "v4": row["v4"],
                    "seconds": (row["cost"]["total_ms"] or 0) / 1000,
                    "outcome": f"{src.get('outcome')}:{src.get('error_code')}", "vendor_style": src.get("category"),
                    "truncated": sum((c.get("done_reason") == "length") for c in src.get("llm_calls") or [])}
    return out, meta


def cell_summary(items, meta, path):
    classes = Counter(i["report_class"] for i in items.values()) if all(i["report_class"] for i in items.values()) else None
    return {"source": str(path.relative_to(ROOT)), "items": len(items),
            "grounding_ok": sum(i["grounding_ok"] for i in items.values()),
            "report_class": dict(classes) if classes else "기록 형식에 없음(HF eval_set 출력)",
            "U": classes.get(U_CLASS, 0) if classes else None, "silent": classes.get(SILENT, 0) if classes else None,
            "outcomes": dict(Counter(i["outcome"] for i in items.values())),
            "vendor_style": dict(Counter(i["vendor_style"] for i in items.values())),
            "latency_median_s": round(statistics.median(i["seconds"] for i in items.values()), 2),
            "truncated_calls": sum(i["truncated"] for i in items.values()),
            "model": meta.get("model"), "adapter": meta.get("adapter"), "ollama_version": meta.get("ollama_version"),
            "device_uuid": meta.get("device_uuid")}


def pair(A, B):
    keys = sorted(set(A) & set(B))
    gained = [k for k in keys if not A[k]["grounding_ok"] and B[k]["grounding_ok"]]
    lost = [k for k in keys if A[k]["grounding_ok"] and not B[k]["grounding_ok"]]
    out = {"common": len(keys), "grounding_ok": [sum(A[k]["grounding_ok"] for k in keys), sum(B[k]["grounding_ok"] for k in keys)],
           "b": len(gained), "c": len(lost), "mcnemar_p": round(mcnemar(len(gained), len(lost)), 4),
           "gained": gained, "lost": lost}
    if all(A[k]["report_class"] and B[k]["report_class"] for k in keys):
        for name, cls in (("U", U_CLASS), ("silent", SILENT)):
            a = {k for k in keys if A[k]["report_class"] == cls}
            b = {k for k in keys if B[k]["report_class"] == cls}
            out[name] = [len(a), len(b)]
            out[f"{name}_net"] = len(b) - len(a)
            out[f"{name}_new"], out[f"{name}_gone"] = sorted(b - a), sorted(a - b)
    la = statistics.median(A[k]["seconds"] for k in keys)
    lb = statistics.median(B[k]["seconds"] for k in keys)
    out["latency_median_s"] = [round(la, 2), round(lb, 2)]
    out["latency_ratio"] = round(lb / la, 3) if la else None
    return out


def main():
    cells, out = {}, {"note": "보고용. 판정은 업체 100으로만 한다(PROTOCOL_v2 2.2절).", "cells": {}, "pairs": {}}
    for name, path in HF_CELLS.items():
        if path.exists():
            items, meta = load_hf(path)
            cells[name] = items
            out["cells"][name] = cell_summary(items, meta, path)
    for name, path in OLLAMA_CELLS.items():
        if path.exists():
            items, meta = load_ollama(path)
            cells[name] = items
            out["cells"][name] = cell_summary(items, meta, path)
            out["cells"][name]["grounding_ok_recorded_differs"] = sorted(
                k for k, i in items.items() if i["grounding_ok_recorded"] is not None and bool(i["grounding_ok_recorded"]) != i["grounding_ok"])
    for a, b, label in PAIRS:
        if a in cells and b in cells:
            out["pairs"][label] = {"pair": f"{a}→{b}", **pair(cells[a], cells[b])}
    (HERE / "comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, c in out["cells"].items():
        print(name, c["grounding_ok"], "U", c["U"], "silent", c["silent"], "lat", c["latency_median_s"], "trunc", c["truncated_calls"])
    for label, p in out["pairs"].items():
        print(label, p["pair"], p["grounding_ok"], "b", p["b"], "c", p["c"], "p", p["mcnemar_p"], "U", p.get("U"),
              "silent", p.get("silent"), "lat", p["latency_ratio"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
