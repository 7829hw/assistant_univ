# -*- coding: utf-8 -*-
"""(pilot_006 C6) integration/check_loss_tokens_w4.py의 사본. 바꾼 것: config·출력 경로를 인자로 받는다(python check_loss_tokens6.py CONFIG OUT). Partial arm(grounding_target partial) config에도 같은 검사.

pilot_004 SFT 손실 token 검사(결정 86, by_source). GPU를 쓰지 않는다.

    HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pilot_004/data/check_loss_tokens.py

- 학습과 같은 경로로 렌더링한다: pilot_004 SFT config(``thinking.loss_scope: by_source``) → ``trainer_common.load_records`` → ``render_records``.
- 손실 마스크는 TRL SFTTrainer prompt/completion 처리와 같다(pilot_003 check_loss_tokens.py와 같은 방법).
- 확인(하나라도 어긋나면 실패):
  - 레코드에 ``metadata.loss_scope``가 있고 출처와 맞다(teacher → full_response, 8b 자체 → json_only).
  - ``ids[:len(prompt_ids)] == prompt_ids``. prompt는 추론 때 렌더링으로 시작한다.
  - teacher: prompt == 추론 렌더링, 손실 문자열 == 응답 전체 + EOS(thinking과 JSON 모두).
  - 8b 자체: prompt == 추론 렌더링 + 추론 부분, 손실 문자열 == JSON + EOS(think 태그 없음).
- 결과: ``loss_tokens.json``(출처별 손실 token 수, 실패 목록. 원문 없음).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
CONFIG = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(q / 100 * (len(v) - 1))))]


def main():
    from training.data import thinking
    from training.trainer_common import load_config, load_records, render_prompt, render_records, tokenizer_for
    config = load_config(CONFIG, "sft")
    if thinking.loss_scope(config) != "by_source":
        raise SystemExit("config loss_scope is not by_source")
    records, _ = load_records(config, "sft")
    tok = tokenizer_for(config)
    rows = render_records(tok, records["train"], config, "sft")
    per, failures = defaultdict(list), []
    for rec, row in zip(records["train"], rows):
        src = thinking.record_source(rec)
        content = rec["messages"][-1]["content"]
        reasoning, answer = thinking.split_response(content)
        inference = render_prompt(tok, rec["messages"][:2], config)
        pids = tok(text=row["prompt"])["input_ids"]
        ids = tok(text=row["prompt"] + row["completion"])["input_ids"]
        text = tok.decode(ids[len(pids):])
        p = []
        if rec["metadata"].get("loss_scope") != thinking.SOURCE_LOSS_SCOPES[src]:
            p.append("loss_scope_mark_mismatch")
        if ids[:len(pids)] != pids:
            p.append("prompt_prefix_mismatch")
        if src == "teacher":
            if row["prompt"] != inference:
                p.append("teacher_prompt_not_inference")
            if text != content + tok.eos_token or "</think>" not in text:
                p.append("teacher_loss_not_full_response")
        else:
            if row["prompt"] != inference + reasoning:
                p.append("self_prompt_not_inference_plus_reasoning")
            if text != answer + tok.eos_token or "<think>" in text or "</think>" in text:
                p.append("self_loss_not_json_only")
        if len(ids) > config["training"]["max_seq_length"]:
            p.append("over_max_seq_length")
        per[src].append({"loss": len(ids) - len(pids), "total": len(ids)})
        if p:
            failures.append({"trace_id": rec["metadata"]["trace_id"], "source": src, "problems": p})
    total = sum(x["loss"] for v in per.values() for x in v)
    out = {"config": str(CONFIG.relative_to(ROOT)) if ROOT in CONFIG.parents else str(CONFIG), "records": len(rows), "all_ok": not failures, "failures": failures,
           "by_source": {("teacher" if s == "teacher" else "self(8b)"): {
               "records": len(v), "scope": thinking.SOURCE_LOSS_SCOPES[s], "loss_tokens_sum": sum(x["loss"] for x in v),
               "loss_token_share": round(sum(x["loss"] for x in v) / total, 4),
               "loss_tokens": {"min": min(x["loss"] for x in v), "p50": pct([x["loss"] for x in v], 50), "max": max(x["loss"] for x in v)},
               "total_tokens_max": max(x["total"] for x in v)} for s, v in sorted(per.items())},
           "method": "TRL SFTTrainer prompt/completion tokenization (non-conversational)"}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("records", "all_ok", "by_source")}, ensure_ascii=False, indent=1))
    sys.exit(0 if out["all_ok"] else 1)


if __name__ == "__main__":
    main()
