# -*- coding: utf-8 -*-
"""pilot_002 보고용 루프·생성 상한·지연 집계(REPORT 6절). 모델을 부르지 않는다. 판정에 쓰지 않는다.

    python sft_dpo_inventory/pilot_002/analysis/loops_latency.py

- HF 셀: 결과 meta의 원문(``raw_out``)에 결정 40-D ``is_loop``(L1 tail_repeats ≥ 3, L2 zlib ≤ 0.086, L3 top_line ≥ 21)를
  모든 호출의 thinking에 적용한다. 생성 상한 호출은 원문 ``done_reason == "length"``다.
- Ollama 셀: 평가 기록에 thinking 원문이 없어(``thinking_chars``만 있음) 루프는 셀 수 없다.
  생성 상한 호출(``llm_calls[].done_reason == "length"``)과 첫 plan 호출 thinking 글자 수만 낸다.
- 지연: HF는 결과 행의 ``seconds``(업체 100 HF 결과에는 없어 ``judgment.json``의 값을 쓴다), Ollama는 호출 ``duration_ms`` 합(모델 시간).
- 셀: 업체 100(기준, pilot_001, pilot_002), aux_test_v1(기준, pilot_002), valid98(pilot_001, pilot_002).
결과: ``loops_latency.json``.
"""
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P2 = HERE.parent
ROOT = P2.parents[1]
INV = ROOT / "sft_dpo_inventory"
sys.path.insert(0, str(INV / "pilot_prep_004/loop_filter"))
from apply_filter import is_loop, loop_metrics, split_think  # noqa: E402

HF = {
    "vendor100": {"HF-E": INV / "thinking_prep_001/hf_e/HF-E_run1.json",
                  "pilot_001 HF-SFT": INV / "pilot_001/vendor100/HF-sft.json",
                  "pilot_001 HF-최종": INV / "pilot_001/vendor100/HF-final.json",
                  "pilot_002 HF-SFT": P2 / "vendor100/HF-sft.json", "pilot_002 HF-최종": P2 / "vendor100/HF-final.json"},
    "aux_test_v1": {"HF-E": INV / "pilot_prep_005/sets/runs/aux_test_base.json",
                    "pilot_002 HF-SFT": P2 / "aux_test/HF-sft.json", "pilot_002 HF-최종": P2 / "aux_test/HF-final.json"},
    "valid98": {"pilot_001 SFT": INV / "pilot_001/valid98/runs/sft_step124.json",
                "pilot_001 최종": INV / "pilot_001/valid98/runs/dpo_step212.json",
                "pilot_002 SFT": P2 / "valid98/valid98_sft.json", "pilot_002 최종": P2 / "valid98/valid98_final.json"},
}
OLLAMA = {
    "vendor100": {"E": INV / "pilot_prep_003/ollama/E.json", "B-conv": INV / "pilot_prep_003/ollama/B-conv.json",
                  "pilot_001 Ollama-SFT": INV / "pilot_001/vendor100/Ollama-sft.json",
                  "pilot_001 Ollama-최종": INV / "pilot_001/vendor100/Ollama-final.json",
                  "pilot_002 Ollama-SFT": P2 / "vendor100/Ollama-sft.json",
                  "pilot_002 Ollama-최종": P2 / "vendor100/Ollama-final.json"},
    "aux_test_v1": {"E": P2 / "aux_test/E.json", "B-conv": P2 / "aux_test/B-conv.json",
                    "pilot_002 Ollama-SFT": P2 / "aux_test/Ollama-sft.json",
                    "pilot_002 Ollama-최종": P2 / "aux_test/Ollama-final.json"},
}


def rel(path):
    return str(Path(path).relative_to(ROOT))


def q(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p * (len(values) - 1))))]


def raw_path(meta):
    return (meta.get("hf") or {}).get("raw_out") or meta.get("raw_out")


def hf_cell(path):
    res = json.loads(path.read_text(encoding="utf-8"))
    raw = Path(raw_path(res["meta"]))
    rows = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines() if line.strip()]
    hits = []
    for r in rows:
        m = loop_metrics(split_think(r["raw_text"])[0])
        reasons = (is_loop(m) if m else ["empty_thinking"]) or []
        if reasons:
            hits.append({"id": r["id"], "call": r["call"], "reasons": reasons, "done_reason": r.get("done_reason")})
    # 업체 100 HF 결과에는 문항 초가 없다(지연은 judgment.json의 cost.total_ms 중앙값을 쓴다).
    seconds = [r["seconds"] for r in res["rows"]] if "seconds" in res["rows"][0] else None
    return {"source": rel(path), "raw": rel(raw), "calls": len(rows),
            "truncated_calls": sum(r.get("done_reason") == "length" for r in rows),
            "loop_calls": len(hits), "loop_items": sorted({h["id"] for h in hits}), "loop_hits": hits,
            "latency_median_s": round(statistics.median(seconds), 2) if seconds else "judgment.json",
            "latency_p90_s": round(q(seconds, 0.9), 2) if seconds else None}


def ollama_cell(path):
    res = json.loads(path.read_text(encoding="utf-8"))
    calls = [c for r in res["rows"] for c in r.get("llm_calls") or []]
    trunc = sorted({r["id"] for r in res["rows"] for c in r.get("llm_calls") or [] if c.get("done_reason") == "length"})
    seconds = [sum(c.get("duration_ms") or 0 for c in r.get("llm_calls") or []) / 1000 for r in res["rows"]]
    first_plan = [next((c.get("thinking_chars") for c in r.get("llm_calls") or [] if c.get("kind") == "plan"), None)
                  for r in res["rows"]]
    first_plan = [t for t in first_plan if t is not None]
    return {"source": rel(path), "calls": len(calls),
            "truncated_calls": sum(c.get("done_reason") == "length" for c in calls), "truncated_items": trunc,
            "loop_calls": "기록 없음(thinking 원문 미저장)",
            "model_seconds_median": round(statistics.median(seconds), 2), "model_seconds_p90": round(q(seconds, 0.9), 2),
            "first_plan_thinking_chars": {"median": statistics.median(first_plan), "max": max(first_plan)} if first_plan else None}


def main():
    out = {"note": "보고용. 판정은 vendor100/judgment.json(PROTOCOL_v2)만 쓴다.", "hf": {}, "ollama": {}}
    for group, cells in HF.items():
        out["hf"][group] = {name: hf_cell(p) for name, p in cells.items() if p.exists()}
    for group, cells in OLLAMA.items():
        out["ollama"][group] = {name: ollama_cell(p) for name, p in cells.items() if p.exists()}
    (HERE / "loops_latency.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for kind in ("hf", "ollama"):
        for group, cells in out[kind].items():
            for name, c in cells.items():
                print(kind, group, name, "calls", c["calls"], "trunc", c["truncated_calls"], "loops", c["loop_calls"],
                      c.get("loop_items", c.get("truncated_items")), c.get("latency_median_s", c.get("model_seconds_median")),
                      c.get("first_plan_thinking_chars", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
