# -*- coding: utf-8 -*-
"""HF-F(두 번)와 Ollama F를 같은 기준으로 비교한다(모델 호출 없음).

    python sft_dpo_inventory/pilot_prep_001/compare_hf_f.py

- 채점·분류·전이 표는 ``baseline_conditions_001/compare_cells.py``의 함수를 그대로 쓴다
  (``grounding_check`` 재채점, v4 축, grounding_v13 U1–U4, 첫 응답 층별 결과).
- HF-F 1·2회차의 첫 계획 응답을 바이트 단위로 비교한다.
- Ollama F: ``baseline_conditions_001/runs/F.json``(qwen3:8b 500a1f06 Q4_K_M, prompt 87048d0c, think=false, 조건 계층 켬,
  기준일 2026-09-25, 문항마다 모델 내림).
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

CELLS = {"Ollama-F": ROOT / "sft_dpo_inventory/baseline_conditions_001/runs/F.json",
         "HF-F1": HERE / "hf/HF-F_run1.json", "HF-F2": HERE / "hf/HF-F_run2.json"}


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
    for a, b, label in (("Ollama-F", "HF-F1", "실행 경로: Ollama Q4_K_M + Ollama template(think=false) ↔ HF BF16 + HF template"),
                        ("HF-F1", "HF-F2", "같은 조건 반복(HF)")):
        if a in cells and b in cells:
            out["pairs"][f"{a}→{b}"] = {"condition": label, **C.transition(cells[a], cells[b])}
    if {"HF-F1", "HF-F2"} <= set(cells):
        r1, r2 = first_responses(CELLS["HF-F1"]), first_responses(CELLS["HF-F2"])
        differ = sorted(k for k in r1 if r1[k] != r2.get(k))
        out["hf_repeat_first_response"] = {"items": len(r1), "byte_identical": len(r1) - len(differ),
                                           "differing_items": differ}
    if {"Ollama-F", "HF-F1"} <= set(cells):
        o, h = first_responses(CELLS["Ollama-F"]), first_responses(CELLS["HF-F1"])
        out["ollama_vs_hf_first_response_identical"] = sum(1 for k in o if o[k] == h.get(k))
    out["items"] = cells
    (HERE / "hf" / "comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "items"}, ensure_ascii=False, indent=1)[:12000])


if __name__ == "__main__":
    main()
