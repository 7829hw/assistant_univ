# -*- coding: utf-8 -*-
"""RC7 손실 token·마스크 audit(결정 235 빌드 검사). ``pilot_008/build/mask_audit8.py``의 사본(대상 RC7·종류 이름만 바꿈). 학습 코드의 렌더
(``training.trainer_common.render_records``)를 그대로 써서 레코드마다 completion(손실 구간)을 확인. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_009/build/mask_audit9.py   # -> build/RC7/mask_audit.json

- 종류별(teacher full_response / 8b json_only / r2 Jb011·Jb012 / r2 teacher b011 / 거부 S-1·teacher) 손실 token(중앙값·합), 전체 손실 token 중 거부·teacher 몫.
- 거부 S-1(json_only): completion이 ``{"unsupported": true}`` + EOS, thinking이 prompt 쪽.
- 거부 teacher(full_response): completion이 ``<think>``로 시작하고 ``</think>`` 뒤 JSON이 정확히 ``{"unsupported": true}``, EOS로 끝남, prompt에 ``</think>`` 없음.
- json_only: completion에 ``</think>``가 없는지. full_response: completion이 thinking으로 시작하는지.
"""
import json
import statistics
import sys
from collections import defaultdict
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
        return "r2_b011_teacher" if m["loss_scope"] == "full_response" else "r2_Jb011"
    if m["corpus_group"] == "batch012":
        return "r2_Jb012"
    return "teacher_full_response" if m["loss_scope"] == "full_response" else "8b_json_only"


def main():
    import hf_thinking as H
    from training.trainer_common import render_records
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = yaml.safe_load((ROOT / "sft_dpo_inventory/pilot_009/train/configs_p9/P9-F-o43.yaml").read_text(encoding="utf-8"))
    recs = [json.loads(l) for l in (HERE / "RC7/full/sft_train.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = render_records(tok, recs, cfg, "sft")
    loss, problems = defaultdict(list), []
    eos = tok.eos_token
    for r, row in zip(recs, rows):
        k = kind(r)
        comp = row["completion"]
        n = len(tok(comp, add_special_tokens=False)["input_ids"])
        loss[k].append(n)
        tid = r["metadata"]["trace_id"]
        if k == "refusal_S-1":
            body = comp[:-len(eos)] if comp.endswith(eos) else None
            try:
                same = body is not None and json.loads(body) == {"unsupported": True}
            except Exception:  # noqa: BLE001
                same = False
            if not same:
                problems.append((tid, "s1_completion", comp[:60]))
            if "</think>" not in row["prompt"]:
                problems.append((tid, "s1_thinking_not_in_prompt"))
        elif k == "refusal_teacher":
            body = comp[:-len(eos)] if comp.endswith(eos) else None
            ok = body is not None and body.lstrip().startswith("<think>") and "</think>" in body and body.split("</think>", 1)[1].strip() == '{"unsupported": true}'
            if not ok:
                problems.append((tid, "teacher_refusal_completion", comp[-80:]))
            if "</think>" in row["prompt"]:
                problems.append((tid, "teacher_refusal_think_in_prompt"))
        elif r["metadata"]["loss_scope"] == "json_only" and "</think>" in comp:
            problems.append((tid, "json_only_has_think"))
        elif r["metadata"]["loss_scope"] == "full_response" and not comp.lstrip().startswith("<think>"):
            problems.append((tid, "full_response_without_think"))
    total = sum(sum(v) for v in loss.values())
    teacher_kinds = ("teacher_full_response", "r2_b011_teacher", "refusal_teacher")
    out = {"records": len(recs), "rendered": len(rows), "loss_tokens_total": total,
           "by_kind": {k: {"records": len(v), "loss_tokens_sum": sum(v), "median": statistics.median(v), "share_of_loss": round(sum(v) / total, 4)} for k, v in sorted(loss.items())},
           "refusal_loss_share": round(sum(sum(v) for k, v in loss.items() if k.startswith("refusal")) / total, 4),
           "teacher_loss_share": round(sum(sum(loss[k]) for k in teacher_kinds if k in loss) / total, 4),
           "teacher_record_share": round(sum(len(loss[k]) for k in teacher_kinds if k in loss) / len(recs), 4),
           "problems": problems, "ok": not problems and len(rows) == len(recs)}
    (HERE / "RC7/mask_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
