# -*- coding: utf-8 -*-
"""결정 40-D 2단계: 고정한 루프 기준(``CRITERIA.md``, 커밋 db1dab6)을 trace pool에 적용해 빠지는 수를 센다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_004/loop_filter/apply_filter.py

- pool: v004 trace(``combined_traces.jsonl``)와 teacher trace. 학습에 실제로 쓰인 r1 SFT 레코드·DPO 쌍에 대한 영향도 센다.
- 기준: L1 ``tail_repeats ≥ 3``, L2 ``zlib_ratio ≤ 0.086``, L3 ``top_line_repeats ≥ 21``(하나라도 해당하면 루프).
- 결과: ``applied.json``(trace별 지표는 걸린 trace만, 나머지는 수만).
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_001_analysis"))

from analyze import loop_metrics, split_think  # noqa: E402

GEN = ROOT / "training/generated"
L1_TAIL, L2_ZLIB, L3_LINE = 3, 0.086, 21


def is_loop(m):
    reasons = []
    if m["tail_repeats"] >= L1_TAIL:
        reasons.append("L1")
    if m["zlib_ratio"] <= L2_ZLIB:
        reasons.append("L2")
    if m["top_line_repeats"] >= L3_LINE:
        reasons.append("L3")
    return reasons


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    pool = {}
    for r in read(GEN / "pilot_prep_003/combined_traces.jsonl"):
        pool[r["trace_id"]] = ("v004", r.get("thinking") or split_think(r["raw_text"])[0])
    for path in sorted((GEN / "thinking_traces/teacher_qwen3.8_27b").glob("*/traces.jsonl")):
        for r in read(path):
            pool[r["trace_id"]] = ("teacher", r["thinking"])
    flagged, counts = {}, Counter()
    for tid, (origin, thinking) in pool.items():
        counts[f"{origin}:traces"] += 1
        m = loop_metrics(thinking)
        reasons = is_loop(m) if m else ["empty_thinking"]
        if reasons:
            counts[f"{origin}:loop"] += 1
            flagged[tid] = {"origin": origin, "reasons": reasons,
                            **{k: m[k] for k in ("chars", "zlib_ratio", "top_line_repeats", "tail_period", "tail_repeats")}}
    sft = read(GEN / "thinking_v004_t2pc_r1/sft_train.jsonl")
    dpo = read(GEN / "thinking_v004_t2pc_r1/dpo_train.jsonl")
    sft_hit = [r["metadata"]["trace_id"] for r in sft if r["metadata"]["trace_id"] in flagged]
    dpo_hit = [(r["metadata"]["chosen_trace_id"], r["metadata"]["rejected_trace_id"]) for r in dpo
               if r["metadata"]["chosen_trace_id"] in flagged or r["metadata"]["rejected_trace_id"] in flagged]
    out = {"criteria": {"L1_tail_repeats>=": L1_TAIL, "L2_zlib_ratio<=": L2_ZLIB, "L3_top_line_repeats>=": L3_LINE,
                        "fixed_in": "CRITERIA.md (commit db1dab6)"},
           "pool": dict(counts), "flagged": flagged,
           "r1_training_effect": {"sft_records": len(sft), "sft_records_excluded": len(sft_hit),
                                  "dpo_pairs": len(dpo), "dpo_pairs_excluded": len(dpo_hit)}}
    (HERE / "applied.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "flagged"}, ensure_ascii=False, indent=1), len(flagged))


if __name__ == "__main__":
    main()
