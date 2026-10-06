# -*- coding: utf-8 -*-
"""HF-E(두 번, thinking 켬)와 Ollama E를 같은 기준으로 비교한다(모델 호출 없음).

    python sft_dpo_inventory/thinking_prep_001/compare_hf_e.py

- 채점·분류·전이 표는 ``baseline_conditions_001/compare_cells.py``의 함수를 그대로 쓴다
  (``grounding_check`` 재채점, v4 축, grounding_v13 U1–U4, 첫 응답 층별 결과).
- HF-E 1·2회차의 첫 계획 원문(thinking 포함) sha256과 본문을 비교한다. thinking 길이·지연·생성 상한 잘림을 함께 센다.
- Ollama E: ``baseline_conditions_001/runs/E.json``(qwen3:8b 500a1f06 Q4_K_M, prompt 87048d0c, think 미지정 = thinking 켬,
  조건 계층 켬, 기준일 2026-09-25, 문항마다 모델 내림).
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("compare_cells", ROOT / "sft_dpo_inventory/baseline_conditions_001/compare_cells.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

CELLS = {"Ollama-E": ROOT / "sft_dpo_inventory/baseline_conditions_001/runs/E.json",
         "HF-E1": HERE / "hf_e/HF-E_run1.json", "HF-E2": HERE / "hf_e/HF-E_run2.json"}


def first_responses(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["rows"]
    return {r["id"]: next((c.get("content") for c in r.get("llm_calls") or []
                           if c.get("kind") == "plan" and not c.get("failed")), None) for r in rows}


def main():
    empty = HERE / ".empty_arm"
    empty.mkdir(exist_ok=True)
    cells = {name: C.load_cell(path, empty) for name, path in CELLS.items() if Path(path).is_file()}
    empty.rmdir()
    out = {"cells": {name: {"source": str(CELLS[name].relative_to(ROOT)), **C.summary(items)}
                     for name, items in cells.items()}, "pairs": {}}
    for a, b, label in (("Ollama-E", "HF-E1", "실행 경로: Ollama Q4_K_M + Ollama template(think 미지정 = 켬, ' /think') ↔ HF BF16 + HF template(enable_thinking=True)"),
                        ("HF-E1", "HF-E2", "같은 조건 반복(HF)")):
        if a in cells and b in cells:
            out["pairs"][f"{a}→{b}"] = {"condition": label, **C.transition(cells[a], cells[b])}
    if {"HF-E1", "HF-E2"} <= set(cells):
        r1, r2 = first_responses(CELLS["HF-E1"]), first_responses(CELLS["HF-E2"])
        differ = sorted(k for k in r1 if r1[k] != r2.get(k))
        out["hf_repeat_first_response"] = {"items": len(r1), "byte_identical": len(r1) - len(differ),
                                           "differing_items": differ}
    if {"Ollama-E", "HF-E1"} <= set(cells):
        o, h = first_responses(CELLS["Ollama-E"]), first_responses(CELLS["HF-E1"])
        out["ollama_vs_hf_first_response_identical"] = sum(1 for k in o if o[k] == h.get(k))
    for name in ("HF-E1", "HF-E2"):
        if name in cells:
            rows = json.loads(Path(CELLS[name]).read_text(encoding="utf-8"))["rows"]
            calls = [c for r in rows for c in r.get("hf_calls") or []]
            out[f"{name}_generation"] = {"calls": len(calls), "truncated_calls": sum(c["done_reason"] == "length" for c in calls),
                                        "items_with_truncation": sum(any(c["done_reason"] == "length" for c in r.get("hf_calls") or [])
                                                                     for r in rows),
                                        "think_not_closed": sum(not c["think_closed"] for c in calls),
                                        "generated_tokens_median": sorted(c["generated_tokens"] for c in calls)[len(calls) // 2] if calls else None,
                                        "generated_tokens_max": max((c["generated_tokens"] for c in calls), default=None)}
    if {"HF-E1", "HF-E2"} <= set(cells):
        h1 = {r["id"]: [c["raw_sha256"] for c in r["hf_calls"]] for r in json.loads(Path(CELLS["HF-E1"]).read_text())["rows"]}
        h2 = {r["id"]: [c["raw_sha256"] for c in r["hf_calls"]] for r in json.loads(Path(CELLS["HF-E2"]).read_text())["rows"]}
        differ = sorted(k for k in h1 if h1[k][:1] != h2.get(k, [])[:1])
        out["hf_repeat_first_raw_including_thinking"] = {"items": len(h1), "byte_identical": len(h1) - len(differ),
                                                         "differing_items": differ}
    out["items"] = cells
    (HERE / "hf_e" / "comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "items"}, ensure_ascii=False, indent=1)[:12000])


if __name__ == "__main__":
    main()
