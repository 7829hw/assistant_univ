# -*- coding: utf-8 -*-
"""pilot_010 판정 단계 O4' 순서 파일 5개(결정 267 D2). V4 데이터 그대로, 예약된 PLAN_J 순서 seed 101·523·2029·31·20271027.

- 호출은 선택 단계와 같다: ``order7b.order_file({"full": V4 레코드}, seed)`` → ``build/V4/order_b2_o<seed>.json``.
- 재현 검사: 같은 호출로 seed 43을 만들어 선택 단계 ``build/V4/order_b2_o43.json``과 바이트 단위로 같은지 먼저 본다(다르면 멈춤).
- V4 학습 파일 sha256(``3575c7f0…``)·질문 목록 sha256(``d559b3e1…``)이 manifest와 같아야 하고, 같은 질문 연속 ≤ 4(넘으면 멈춤).
- 모델 호출 없음. 기존 파일은 고치지 않는다(새 seed 파일이 이미 있으면 내용이 같은지만 본다).

    python3 sft_dpo_inventory/pilot_010/build/make_orders_j.py
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INV = HERE.parents[1]
sys.path.insert(0, str(INV / "pilot_007/train_data"))
import order7b  # noqa: E402

V4 = HERE / "V4"
SEEDS = (101, 523, 2029, 31, 20271027)
TRAIN_SHA = "3575c7f06c2ee7baaf59233b01c926504589ec2fbf3136f255a45599ced10e3f"
QLIST_SHA = "d559b3e1acca8c8dbd3592d3e0c2302e1890b88801f5df5d160a35938ef54b98"


def text(o):
    return json.dumps(o, ensure_ascii=False, indent=1) + "\n"


def main():
    p = V4 / "full/sft_train.jsonl"
    if hashlib.sha256(p.read_bytes()).hexdigest() != TRAIN_SHA:
        raise SystemExit("V4 sft_train.jsonl sha256 differs")
    recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    chk = order7b.order_file({"full": recs}, 43)
    if text(chk) != (V4 / "order_b2_o43.json").read_text(encoding="utf-8"):
        raise SystemExit("order7b.order_file does not reproduce build/V4/order_b2_o43.json")
    out = {"reproduction_check": {"seed": 43, "byte_identical": True}, "orders": {}}
    for s in SEEDS:
        o = order7b.order_file({"full": recs}, s)
        if o["question_list_sha256"] != QLIST_SHA or not o["max_run_ok"] or o["slots_union"] != len(recs):
            raise SystemExit(f"order o{s}: question list / max_run / slot check failed")
        f = V4 / f"order_b2_o{s}.json"
        if f.exists() and f.read_text(encoding="utf-8") != text(o):
            raise SystemExit(f"{f.name} exists with different content")
        f.write_text(text(o), encoding="utf-8")
        out["orders"][f"o{s}"] = {"file": str(f.relative_to(INV.parent)), "file_sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                                  "order_sha256": o["order_sha256"], "run_stats": o["arms"]["full"]["run_stats"]}
    (HERE / "orders_j_summary.json").write_text(text(out), encoding="utf-8")
    print(text(out))


if __name__ == "__main__":
    main()
