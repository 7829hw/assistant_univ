# -*- coding: utf-8 -*-
"""SFT(json_only, 결정 24)의 손실 대상 token이 ``</think>`` 뒤의 JSON에만 있는지 레코드마다 확인한다. GPU를 쓰지 않는다.

    HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pilot_001/data/check_loss_tokens.py

- 학습과 같은 경로로 렌더링한다: ``trainer_common.load_records`` → ``render_records``(config의 ``thinking.loss_scope``).
- 손실 마스크는 TRL 0.23.1 ``SFTTrainer``의 prompt/completion 처리와 같게 만든다:
  ``prompt_ids = tok(prompt)``, ``ids = tok(prompt + completion)``, 마스크 = ``[0]*len(prompt_ids) + [1]*나머지``.
- 확인(하나라도 어긋나면 실패):
  - ``ids[:len(prompt_ids)] == prompt_ids``.
  - prompt가 ``</think>``(와 뒤 공백)로 끝난다.
  - 손실 token을 decode한 문자열이 JSON 본문 + EOS와 같다. ``<think>``·``</think>``가 없고, JSON으로 읽힌다.
  - 손실 token 수가 0보다 크다.
- 결과: ``loss_tokens.json``(레코드별 손실 token 수와 분포, 원문 없음).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
CONFIG = ROOT / "training/configs/qwen3_8b_t2pc_thinking_pilot001_sft.yaml"


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q / 100 * (len(values) - 1))))]


def main():
    from training.data import thinking
    from training.data.validation import assess  # noqa: F401
    from training.trainer_common import load_config, load_records, render_records, tokenizer_for
    from geoflow.planner import parse_planner_json
    config = load_config(CONFIG, "sft")
    if thinking.loss_scope(config) != "json_only":
        raise SystemExit("config loss_scope is not json_only")
    records, _ = load_records(config, "sft")
    tok = tokenizer_for(config)
    rows = render_records(tok, records["train"], config, "sft")
    out, failures = [], []
    for record, row in zip(records["train"], rows):
        tid = record["metadata"]["trace_id"]
        prompt_ids = tok(text=row["prompt"])["input_ids"]
        ids = tok(text=row["prompt"] + row["completion"])["input_ids"]
        loss_ids = ids[len(prompt_ids):]
        text = tok.decode(loss_ids)
        reasoning, answer = thinking.split_response(record["messages"][-1]["content"])
        problems = []
        if ids[:len(prompt_ids)] != prompt_ids:
            problems.append("prompt_prefix_mismatch")
        if not row["prompt"].rstrip().endswith("</think>"):
            problems.append("prompt_does_not_end_with_think_close")
        if text != answer + tok.eos_token:
            problems.append("loss_text_is_not_json_plus_eos")
        if "<think>" in text or "</think>" in text:
            problems.append("think_tag_in_loss")
        try:
            parse_planner_json(text[: -len(tok.eos_token)])
        except Exception:  # noqa: BLE001
            problems.append("loss_text_not_json")
        if not loss_ids:
            problems.append("no_loss_tokens")
        out.append({"trace_id": tid, "prompt_tokens": len(prompt_ids), "loss_tokens": len(loss_ids),
                    "total_tokens": len(ids), "problems": problems})
        if problems:
            failures.append({"trace_id": tid, "problems": problems})
    counts = [r["loss_tokens"] for r in out]
    summary = {"config": str(CONFIG.relative_to(ROOT)), "records": len(out), "failures": failures,
               "all_ok": not failures,
               "loss_tokens": {"min": min(counts), "p10": pct(counts, 10), "p50": pct(counts, 50), "p90": pct(counts, 90),
                               "max": max(counts), "sum": sum(counts)},
               "prompt_tokens_incl_reasoning": {"min": min(r["prompt_tokens"] for r in out),
                                                "max": max(r["prompt_tokens"] for r in out)},
               "total_tokens_max": max(r["total_tokens"] for r in out),
               "method": "TRL 0.23.1 SFTTrainer prompt/completion tokenization (non-conversational)", "rows": out}
    (HERE / "loss_tokens.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("records", "all_ok", "loss_tokens", "prompt_tokens_incl_reasoning",
                                              "total_tokens_max")}, ensure_ascii=False))
    print(json.dumps(failures[:10], ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
