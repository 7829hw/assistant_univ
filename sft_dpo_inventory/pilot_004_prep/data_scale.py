# -*- coding: utf-8 -*-
"""pilot_004 데이터 규모 계산(결정 86·88·92). 데이터 파일은 만들지 않는다. GPU를 쓰지 않는다.

    HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python sft_dpo_inventory/pilot_004_prep/data_scale.py

- 입력: pilot_003 데이터(``thinking_pilot003_t2pc``). 결정 92: 결정 66 실차 통행량 대조 묶음 질문은 결정 88 상한의 예외, 나머지에는 상한(τ 0.09)을 그대로 둔다.
  상한 계산은 ``type_caps.scenarios``(A: 레코드 상한, B: 질문 → 레코드 상한)와 같다.
- 시나리오마다: SFT·DPO 레코드 수와 질문 수, 세 TV(전체, 그리고 예외를 뺀 나머지만), 실차 대조 묶음 레코드 수,
  결정 86(``by_source``) 손실 token의 출처별 합과 비중(렌더링은 학습과 같은 ``render_records``, TRL prompt/completion 경계).
- 결과: ``data_scale.json``.
"""
import copy
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import type_caps as T  # noqa: E402

CONFIG = ROOT / "training/configs/qwen3_8b_t2pc_thinking_pilot003_sft.yaml"


def loss_tokens(records):
    from training.data import thinking
    from training.trainer_common import load_config, render_records, tokenizer_for
    config = copy.deepcopy(load_config(CONFIG, "sft"))
    config["thinking"]["loss_scope"] = "by_source"
    tok = tokenizer_for(config)
    marked = [thinking.assign_loss_scope(r) for r in records]
    rows = render_records(tok, marked, config, "sft")
    out = defaultdict(lambda: {"records": 0, "loss_tokens": 0})
    for rec, row in zip(marked, rows):
        n = len(tok(text=row["prompt"] + row["completion"])["input_ids"]) - len(tok(text=row["prompt"])["input_ids"])
        s = thinking.record_source(rec)
        out[s]["records"] += 1
        out[s]["loss_tokens"] += n
    total = sum(v["loss_tokens"] for v in out.values())
    return {s: {**v, "scope": thinking.SOURCE_LOSS_SCOPES[s], "share": round(v["loss_tokens"] / total, 4)} for s, v in sorted(out.items())}


def main():
    cell, sft, dpo, variant = T.load()
    exempt = frozenset(variant)
    records = {r["metadata"]["trace_id"]: r for r in T.read(T.DATA / "sft_train.jsonl")}
    summary, kept = T.scenarios(sft, dpo, cell, variant, 0.09, exempt)
    out = {"tau": 0.09, "exempt_questions(decision 92)": sorted(exempt), "data": str(T.DATA.relative_to(ROOT)), "scenarios": {}}
    for name, (sft_k, dpo_k) in kept.items():
        s = summary[name]
        rest_sft = [r for r in sft_k if r["sid"] not in exempt]
        rest_dpo = [r for r in dpo_k if r["sid"] not in exempt]
        rest = T.describe(rest_sft, rest_dpo, cell, variant)
        out["scenarios"][name] = {
            "sft_records": s["sft_records"], "sft_questions": s["sft_questions"], "dpo_pairs": s["dpo_pairs"], "dpo_questions": s["dpo_questions"],
            "tv_vs_dev(all)": s["tv_vs_dev"], "tv_vs_dev(non-exempt only)": rest["tv_vs_dev"],
            "tv_over_0.09": {k: v > 0.09 for k, v in s["tv_vs_dev"].items()},
            "passage_status_contrast": s["passage_status_contrast"],
            "dropped": {"sft_records": len(sft) - s["sft_records"], "dpo_pairs": len(dpo) - s["dpo_pairs"],
                        "questions": s.get("dropped_questions", [])},
            "loss_tokens_by_source(decision 86)": loss_tokens([records[r["trace"]] for r in sft_k])}
    (HERE / "data_scale.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, s in out["scenarios"].items():
        print(name, {k: s[k] for k in ("sft_records", "sft_questions", "dpo_pairs", "dpo_questions", "tv_vs_dev(all)", "tv_vs_dev(non-exempt only)")},
              s["passage_status_contrast"], s["loss_tokens_by_source(decision 86)"], s["dropped"]["sft_records"])


if __name__ == "__main__":
    main()
