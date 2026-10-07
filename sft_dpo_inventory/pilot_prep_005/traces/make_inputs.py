# -*- coding: utf-8 -*-
"""batch005 승인 58문항의 trace 수집 입력을 만든다(작업 지시 3). 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_005/traces/make_inputs.py

- ``reviewed_gold_v005_t2pc/sft_train.jsonl``에서 batch005 출처 레코드만 id 순서(b005-01 → 60)로 옮긴다.
  b005-12·14는 고친 문장 그대로다(결정 47). ``collect_traces.py``의 seed는 이 순서의 순번으로 정해진다(seed = 20261006 + 순번).
- 출력: ``training/generated/pilot_prep_005/trace_inputs/batch005/sft_train.jsonl``(pilot_prep_003의 batch004 입력과 같은 형식).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from training.data.common import read_jsonl, sha256, write_jsonl  # noqa: E402

SRC = ROOT / "training/generated/reviewed_gold_v005_t2pc/sft_train.jsonl"
OUT = ROOT / "training/generated/pilot_prep_005/trace_inputs/batch005"


def main():
    rows = sorted((r for r in read_jsonl(SRC) if r["metadata"]["corpus_origin_v005"] == "batch005"),
                  key=lambda r: r["metadata"]["source_record_id"])
    if len(rows) != 58 or OUT.exists():
        raise SystemExit("batch005 승인 레코드가 58이 아니거나 출력이 이미 있다")
    OUT.mkdir(parents=True)
    write_jsonl(OUT / "sft_train.jsonl", rows)
    print(json.dumps({"records": len(rows), "source_sha256": sha256(SRC), "sft_train_sha256": sha256(OUT / "sft_train.jsonl"),
                      "ids": [r["metadata"]["source_record_id"] for r in rows]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
