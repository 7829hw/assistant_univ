# -*- coding: utf-8 -*-
"""pilot_010 JQ(결정 269) RR+NM8(V8) 새 순서 seed 4개의 O4' 순서 파일. V8 데이터 그대로(선택 단계와 같은 파일·sha256).

- 호출은 선택·판정 단계와 같다: ``order7b.order_file({"full": V8 레코드}, seed)`` → ``build/V8/order_b2_o<seed>.json``.
- 재현 검사: 같은 호출로 seed 43을 만들어 선택 단계 ``build/V8/order_b2_o43.json``과 바이트 단위로 같은지 먼저 본다(다르면 멈춤).
- V8 학습 파일 sha256(``5f830f36…``)·질문 목록 sha256(``3878a2e7…``) 확인, 같은 질문 연속 ≤ 4(넘으면 멈춤). seed는 ``build/seeds_jq.json``.
- 모델 호출 없음. 기존 파일은 고치지 않는다.

    python3 sft_dpo_inventory/pilot_010/build/make_orders_jq.py
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INV = HERE.parents[1]
sys.path.insert(0, str(INV / "pilot_007/train_data"))
import order7b  # noqa: E402

V8 = HERE / "V8"
SEEDS = tuple(json.loads((HERE / "seeds_jq.json").read_text(encoding="utf-8"))["order_seeds"])
TRAIN_SHA = "5f830f36f8c8291a0d1dcbca6c402de76b81d8d52aa830196666bc7c8155167b"
QLIST_SHA = "3878a2e79c1eeaecd47c94ac8dd0e8ab3404e452e272759b0cf453c797569307"


def text(o):
    return json.dumps(o, ensure_ascii=False, indent=1) + "\n"


def main():
    assert len(SEEDS) == 4
    p = V8 / "full/sft_train.jsonl"
    if hashlib.sha256(p.read_bytes()).hexdigest() != TRAIN_SHA:
        raise SystemExit("V8 sft_train.jsonl sha256 differs")
    recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    chk = order7b.order_file({"full": recs}, 43)
    if text(chk) != (V8 / "order_b2_o43.json").read_text(encoding="utf-8"):
        raise SystemExit("order7b.order_file does not reproduce build/V8/order_b2_o43.json")
    out = {"decision": 269, "reproduction_check": {"seed": 43, "byte_identical": True}, "train_sha256": TRAIN_SHA, "orders": {}}
    for s in SEEDS:
        o = order7b.order_file({"full": recs}, s)
        if o["question_list_sha256"] != QLIST_SHA or not o["max_run_ok"] or o["slots_union"] != len(recs):
            raise SystemExit(f"order o{s}: question list / max_run / slot check failed")
        f = V8 / f"order_b2_o{s}.json"
        if f.exists():
            raise SystemExit(f"{f.name} already exists")
        f.write_text(text(o), encoding="utf-8")
        out["orders"][f"o{s}"] = {"file": str(f.relative_to(INV.parent)), "file_sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                                  "order_sha256": o["order_sha256"], "run_stats": o["arms"]["full"]["run_stats"]}
    (HERE / "orders_jq_summary.json").write_text(text(out), encoding="utf-8")
    print(text(out))


if __name__ == "__main__":
    main()
