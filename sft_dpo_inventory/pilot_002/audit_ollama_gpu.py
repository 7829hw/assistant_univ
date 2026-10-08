# -*- coding: utf-8 -*-
"""결정 55 감사: 판정에 쓰인 기존 Ollama 기록이 GPU에서 측정됐는지 기록된 생성 속도로만 본다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_002/audit_ollama_gpu.py

- 평가 기록(``evaluate_vendor100.py``의 ``*.jsonl``)은 ``eval_duration``을 남기지 않는다. 그래서 호출마다
  ``eval_count / (duration_ms - load_duration_ms)``를 생성 속도(tok/s)로 쓴다. 분모에 prompt 처리 시간이 들어가므로
  실제 생성 속도보다 조금 낮게 나온다(GPU에서 7k token prompt 처리는 1–2초, CPU에서는 수십 초).
- teacher 기록은 ``eval_count / seconds``(호출 전체 시간)다.
- 같은 장애에서 CPU로 돈 것이 확실한 ``ABORTED_cpu_E``를 비교용으로 함께 센다.
- 의심 기준: 호출 속도가 그 셀 중앙값의 절반 미만이거나, 셀 중앙값이 같은 모델 다른 셀 중앙값의 절반 미만.
  CPU 실행(약 4 tok/s)은 GPU 실행(qwen3:8b 30 tok/s 이상)과 열 배 가까이 차이 나므로 이 기준으로 가려진다.
- 출력: ``ollama_gpu_audit.json``(셀마다 호출 수, 속도 분포, 의심 호출 id).
"""
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INV = ROOT / "sft_dpo_inventory"
EVAL_CELLS = {
    "vendor100/E (qwen3:8b)": INV / "pilot_prep_003/ollama/E.jsonl",
    "vendor100/B-conv": INV / "pilot_prep_003/ollama/B-conv.jsonl",
    "vendor100/pilot_001 Ollama-sft": INV / "pilot_001/vendor100/Ollama-sft.jsonl",
    "vendor100/pilot_001 Ollama-final": INV / "pilot_001/vendor100/Ollama-final.jsonl",
    "valid98/B-conv (결정 43)": INV / "pilot_001_analysis/decision43/valid98_B-conv.jsonl",
    "valid98/pilot_001 Ollama-final (결정 43)": INV / "pilot_001_analysis/decision43/valid98_Ollama-final.jsonl",
    "참고: aux_test ABORTED_cpu_E(CPU 확정)": HERE / "aux_test/ABORTED_cpu_E.jsonl",
}
TEACHER = ROOT / "training/generated/thinking_traces/teacher_qwen3.8_27b"


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize(rates):
    values = sorted(r for _, r in rates)
    q = lambda p: values[min(len(values) - 1, int(p * (len(values) - 1) + 0.5))]  # noqa: E731
    median = statistics.median(values)
    return {"calls": len(values), "min": round(values[0], 1), "p05": round(q(0.05), 1), "median": round(median, 1),
            "max": round(values[-1], 1),
            "below_half_median": [i for i, r in rates if r < median / 2]}


def eval_cell(path):
    rates, skipped = [], 0
    for record in read(path):
        for k, call in enumerate(record.get("llm_calls") or []):
            gen_ms = (call.get("duration_ms") or 0) - (call.get("load_duration_ms") or 0)
            if call.get("failed") or call.get("replayed") or not call.get("eval_count") or gen_ms <= 0:
                skipped += 1
                continue
            rates.append((f"{record['id']}#{k}", call["eval_count"] / (gen_ms / 1000)))
    out = summarize(rates)
    out["skipped_calls"] = skipped
    out["items"] = len(read(path))
    return out


def teacher_cell(path):
    rates = [(r["trace_id"], r["eval_count"] / r["seconds"]) for r in read(path) if r.get("eval_count") and r.get("seconds")]
    out = summarize(rates)
    out["ollama_version"] = sorted({r.get("ollama_version") for r in read(path)})
    return out


def main():
    cells = {name: {"path": str(p.relative_to(ROOT)), "metric": "eval_count/(duration-load)", **eval_cell(p)}
             for name, p in EVAL_CELLS.items()}
    for d in sorted(TEACHER.iterdir()):
        p = d / "traces.jsonl"
        if p.exists():
            cells[f"teacher qwen3.8:27b/{d.name}"] = {"path": str(p.relative_to(ROOT)), "metric": "eval_count/seconds",
                                                      **teacher_cell(p)}
    out = {"cells": cells}
    (HERE / "ollama_gpu_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, c in cells.items():
        print(f"{name}: calls={c['calls']} min={c['min']} p05={c['p05']} median={c['median']} max={c['max']} "
              f"below_half={len(c['below_half_median'])} {c['below_half_median'][:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
