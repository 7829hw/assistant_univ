# -*- coding: utf-8 -*-
"""RC6 손실 token·마스크 audit(결정 223 빌드 검사). 학습 코드의 렌더(``training.trainer_common.render_records``)를 그대로 써서 레코드마다 completion(손실 구간)을 확인. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_008/build/mask_audit8.py   # -> build/RC6/mask_audit.json

- 출처별(teacher full_response / 8b json_only / r2 Jb011 / 거부 S-1·S-2) 손실 token 수(중앙값·합), 전체 손실 token 중 거부 몫.
- 거부 레코드: completion이 ``{"unsupported": true}``(JSON으로 같음) + EOS인지(다른 줄바꿈 형식은 따로 셈), thinking이 prompt 쪽(손실 밖)에 있는지.
- json_only: completion에 ``</think>``가 없는지. full_response: completion이 thinking으로 시작하는지.
"""
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))


def kind(r):
    m = r["metadata"]
    if m.get("refusal_source"):
        return f"refusal_{m['refusal_source']}"
    if m["corpus_group"] == "batch011":
        return "r2_Jb011"
    return "teacher_full_response" if m["loss_scope"] == "full_response" else "8b_json_only"


def main():
    import hf_thinking as H
    from training.trainer_common import render_records
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = yaml.safe_load((ROOT / "sft_dpo_inventory/pilot_008/train/configs_p8/P8-F-o43.yaml").read_text(encoding="utf-8"))
    recs = [json.loads(l) for l in (HERE / "RC6/full/sft_train.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = render_records(tok, recs, cfg, "sft")
    loss, problems, formats = defaultdict(list), [], {}
    for r, row in zip(recs, rows):
        k = kind(r)
        comp = row["completion"]
        n = len(tok(comp, add_special_tokens=False)["input_ids"])
        loss[k].append(n)
        if k.startswith("refusal"):
            body = comp[:-len(tok.eos_token)] if comp.endswith(tok.eos_token) else None
            try:
                same = body is not None and json.loads(body) == {"unsupported": True}
            except Exception:  # noqa: BLE001
                same = False
            if not same:
                problems.append((r["metadata"]["trace_id"], "refusal_completion", comp[:60]))
            elif body != '{"unsupported": true}':
                formats[r["metadata"]["trace_id"]] = body
            if "</think>" not in row["prompt"]:
                problems.append((r["metadata"]["trace_id"], "refusal_thinking_not_in_prompt"))
        elif r["metadata"]["loss_scope"] == "json_only" and "</think>" in comp:
            problems.append((r["metadata"]["trace_id"], "json_only_has_think"))
        elif r["metadata"]["loss_scope"] == "full_response" and not comp.lstrip().startswith("<think>"):
            problems.append((r["metadata"]["trace_id"], "full_response_without_think"))
    total = sum(sum(v) for v in loss.values())
    out = {"records": len(recs), "rendered": len(rows), "loss_tokens_total": total,
           "by_kind": {k: {"records": len(v), "loss_tokens_sum": sum(v), "median": statistics.median(v), "share_of_loss": round(sum(v) / total, 4)} for k, v in sorted(loss.items())},
           "refusal_loss_share": round(sum(sum(v) for k, v in loss.items() if k.startswith("refusal")) / total, 4),
           "refusal_json_other_format(same JSON)": formats, "problems": problems, "ok": not problems and len(rows) == len(recs)}
    (HERE / "RC6/mask_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
