# -*- coding: utf-8 -*-
"""실차 오독 문항(selection_v2 old44/g02·g04·indepv2/n33)의 첫 계획 thinking을 pilot_003 후속 분석과 같은 정규식으로 센다(보고용). 모델 호출 없음.

    python sft_dpo_inventory/pilot_004/selection/real_trip_thinking.py

셀: vLLM-base·pilot_003 최종(pilot_prep_007, 동시 요청 8), pilot_004 SFT 934·최종 DPO 385. 원문은 ignore 경로에서 읽고 수만 남긴다 → ``real_trip_thinking.json``.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003_followup"))
import analyze_followup as AF  # noqa: E402  (REAL_TRIP, TRIP_READ, OCCUPIED, PASSAGE_MENTION, answer_json, thinking_of)

CELLS = {"vLLM-base": ROOT / "training/generated/serving_vllm_fp8/raw/vllm-bf16-base", "pilot003-final": ROOT / "training/generated/serving_vllm_fp8/raw/vllm-bf16-final",
         "pilot004-sft934": ROOT / "training/generated/pilot_004/raw/sft_step934", "pilot004-final(dpo385)": ROOT / "training/generated/pilot_004/raw/dpo_step385"}


def main():
    out = {}
    for cell, prefix in CELLS.items():
        for item in AF.REAL_TRIP_SEL:
            rec = Counter()
            for k in range(1, 5):
                rows = [json.loads(line) for line in Path(f"{prefix}_s{k}_raw.jsonl").read_text(encoding="utf-8").splitlines()]
                first = min((r for r in rows if r["id"] == item), key=lambda r: r.get("call", 0))
                t = AF.thinking_of(first)
                ans = AF.answer_json(first.get("raw_text") or "")
                measure = next((c.get("subtype") for c in (ans or {}).get("concepts", []) if c.get("role") == "MEASURE"), None)
                rec["samples"] += 1
                rec["thinking_translates_real_trip"] += bool(AF.REAL_TRIP.search(t))
                rec["thinking_links_silcha_to_trip_count"] += bool(AF.TRIP_READ.search(t))
                rec["thinking_mentions_occupied"] += bool(AF.OCCUPIED.search(t))
                rec[f"first_plan_measure:{measure}"] += 1
                rec["first_plan_taxi_status_occupied"] += ((ans or {}).get("factors") or {}).get("taxi_status") == "occupied"
            out.setdefault(item, {})[cell] = dict(rec)
    (HERE / "real_trip_thinking.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
