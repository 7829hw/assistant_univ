# -*- coding: utf-8 -*-
"""결정 86(AA) 확인: 출처별 SFT 손실 범위(teacher full_response, HF json_only)를 pilot_003 SFT 레코드에 적용해 렌더링한다.
학습하지 않는다. 데이터 파일을 쓰지 않는다(메모리 안에서 ``assign_loss_scope``만 적용). GPU를 쓰지 않는다.

    HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python sft_dpo_inventory/pilot_004_prep/loss_scope_check.py

- 렌더링은 학습과 같은 ``trainer_common.render_records``이고, config는 pilot_003 SFT config에서 ``thinking.loss_scope``만 ``by_source``로 바꾼 사본(메모리)이다.
- 손실 마스크는 TRL SFTTrainer prompt/completion 처리와 같다(pilot_003 ``data/check_loss_tokens.py``와 같은 방법).
- 확인(레코드마다, 하나라도 어긋나면 실패):
  - 공통: ``ids[:len(prompt_ids)] == prompt_ids``, prompt가 추론 때 렌더링(``render_prompt``, enable_thinking)으로 시작한다.
  - teacher: prompt == 추론 렌더링, 손실 문자열 == 응답 전체 + EOS(``<think>``·``</think>`` 포함).
  - HF: prompt == 추론 렌더링 + 추론 부분(``</think>``까지), 손실 문자열 == JSON + EOS(think 태그 없음).
  - 전체 token 수 ≤ max_seq_length.
- 결과: ``loss_scope_check.json``(출처별 손실 token 수 분포, 실패 목록. 원문 없음).
"""
import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
CONFIG = ROOT / "training/configs/qwen3_8b_t2pc_thinking_pilot003_sft.yaml"


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q / 100 * (len(values) - 1))))]


def main():
    from training.data import thinking
    from training.trainer_common import load_config, load_records, render_prompt, render_records, tokenizer_for
    config = copy.deepcopy(load_config(CONFIG, "sft"))
    config["thinking"]["loss_scope"] = "by_source"
    records, _ = load_records(config, "sft")
    marked = [thinking.assign_loss_scope(r) for r in records["train"]]
    tok = tokenizer_for(config)
    rows = render_records(tok, marked, config, "sft")
    limit = config["training"]["max_seq_length"]
    per, failures = defaultdict(list), []
    for record, row in zip(marked, rows):
        source = thinking.record_source(record)
        content = record["messages"][-1]["content"]
        reasoning, answer = thinking.split_response(content)
        inference = render_prompt(tok, record["messages"][:2], config)
        prompt_ids = tok(text=row["prompt"])["input_ids"]
        ids = tok(text=row["prompt"] + row["completion"])["input_ids"]
        text = tok.decode(ids[len(prompt_ids):])
        problems = []
        if ids[:len(prompt_ids)] != prompt_ids:
            problems.append("prompt_prefix_mismatch")
        if not row["prompt"].startswith(inference):
            problems.append("prompt_not_inference_rendering")
        if source == "teacher":
            if row["prompt"] != inference:
                problems.append("teacher_prompt_has_extra")
            if text != content + tok.eos_token:
                problems.append("teacher_loss_is_not_full_response")
            if "<think>" not in text or "</think>" not in text:
                problems.append("teacher_loss_lacks_thinking")
        else:
            if row["prompt"] != inference + reasoning:
                problems.append("hf_prompt_is_not_inference_plus_reasoning")
            if text != answer + tok.eos_token:
                problems.append("hf_loss_is_not_json_plus_eos")
            if "<think>" in text or "</think>" in text:
                problems.append("hf_think_tag_in_loss")
        if len(ids) > limit:
            problems.append("over_max_seq_length")
        per[source].append({"loss": len(ids) - len(prompt_ids), "total": len(ids)})
        if problems:
            failures.append({"trace_id": record["metadata"]["trace_id"], "source": source, "problems": problems})
    out = {"config": str(CONFIG.relative_to(ROOT)) + " (thinking.loss_scope → by_source, 메모리 사본)",
           "records": len(rows), "all_ok": not failures, "failures": failures, "max_seq_length": limit,
           "by_source": {s: {"records": len(v), "scope": thinking.SOURCE_LOSS_SCOPES[s],
                             "loss_tokens": {"min": min(x["loss"] for x in v), "p50": pct([x["loss"] for x in v], 50),
                                             "p90": pct([x["loss"] for x in v], 90), "max": max(x["loss"] for x in v),
                                             "sum": sum(x["loss"] for x in v)},
                             "total_tokens_max": max(x["total"] for x in v)} for s, v in sorted(per.items())},
           "method": "TRL SFTTrainer prompt/completion tokenization (non-conversational), pilot_003 check_loss_tokens.py와 같음"}
    (HERE / "loss_scope_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0 if out["all_ok"] else 1)


if __name__ == "__main__":
    main()
