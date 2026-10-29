# -*- coding: utf-8 -*-
"""빌드 옵션(결정 168 O4): RC 두 arm의 질문 목록이 같은지 확인하고 순서 seed마다 질문 순서 파일을 쓴다. 모델 호출 없음.

    python3 make_order7.py --rc sft_dpo_inventory/pilot_007/build/RC4 --seeds 43 20261016 7   # -> <rc>/order_o<seed>.json

B단계 config는 ``training.shared_order_seed``와 ``training.shared_order_file``(이 파일)을 준다 → ``train_b7.py``가 같은 순서인지 확인하고 순서대로 학습.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import order7  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--rc", required=True)
p.add_argument("--seeds", type=int, nargs="+", required=True)
a = p.parse_args()
rc = Path(a.rc)
qids = {arm: [r["metadata"]["source_record_id"] for r in order7.load_jsonl(rc / arm / "sft_train.jsonl")] for arm in ("full", "partial")}
for s in a.seeds:
    d = order7.order_file(qids, s)
    for arm in ("full", "partial"):
        seq = order7.question_sequence(order7.order_records(order7.load_jsonl(rc / arm / "sft_train.jsonl"), s))
        assert seq == d["order"], arm
    (rc / f"order_o{s}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(s, d["questions"], d["order_sha256"][:12])
