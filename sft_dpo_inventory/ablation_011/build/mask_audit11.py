# -*- coding: utf-8 -*-
"""ablation_011 손실 token·마스크 audit(결정 261 빌드 검사). ``pilot_010/build/mask_audit10.py``(그대로)와 같은 검사를 arm마다, 학습 wrapper
``train_a11.py``의 손실 범위 표시(A1)를 켠 채로 학습 코드의 렌더(``training.trainer_common.render_records``)로 한다. 모델 호출 없음.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/build/mask_audit11.py   # -> build/mask_audit11.json

- 종류별 손실 token(합·중앙값)과 손실 비중 거부 / 근접 대조 teacher / 나머지(결정 250 보고 기준), 길이(prompt + completion + 1) 최대값과 12,288 초과 수.
- mask_audit10 검사: 거부 S-1 completion = ``{"unsupported": true}`` + EOS(추론은 prompt 쪽), 거부 teacher completion이 ``<think>``로 시작하고 ``</think>`` 뒤가
  정확히 ``{"unsupported": true}``, 근접 대조 teacher(full_response) ``</think>`` 뒤 = canonical Full JSON, json_only completion에 ``</think>`` 없음, full_response는 thinking으로 시작.
- A1 근접 대조 teacher(json_only 표시): completion = canonical Full JSON + EOS(``<think>`` 없음), prompt 끝이 ``</think>`` + 공백, 그리고 같은 레코드의 A0 렌더와
  **prompt + completion 문자열과 token 열이 같다**(입력 같음, 손실 경계만 다름). A1의 나머지 레코드는 A0 렌더와 prompt·completion이 모두 같다.
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
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/ablation_011/train"))
MAXLEN = 12288
ARMS = {"A0": "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl", "A1": "sft_dpo_inventory/ablation_011/build/A1/full/sft_train.jsonl",
        "A2": "sft_dpo_inventory/ablation_011/build/A2/full/sft_train.jsonl", "A3": "sft_dpo_inventory/ablation_011/build/A3/full/sft_train.jsonl"}


def kind(r):
    m = r["metadata"]
    if m.get("refusal_source"):
        return f"refusal_{m['refusal_source']}"
    if m.get("contrast_source") == "teacher":
        return "contrast_teacher_json_only" if m.get("a11_loss_scope_override") == "json_only" else "contrast_teacher"
    if m["corpus_group"] == "batch013":
        return "r2_Jb013"
    if m["corpus_group"] == "batch011":
        return "r2_b011_teacher" if m["loss_scope"] == "full_response" else "r2_Jb011"
    if m["corpus_group"] == "batch012":
        return "r2_Jb012"
    return "teacher_full_response" if m["loss_scope"] == "full_response" else "8b_json_only"


def rkey(r):
    return f"{r['metadata']['source_record_id']}|{r['metadata']['trace_id']}"


def main():
    import train_a11
    train_a11.install_override()
    import hf_thinking as H
    from grounding.full_renderer import render_full
    from training.data.canonicalize import serialize_planner_target
    from training.trainer_common import render_records
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = yaml.safe_load((ROOT / "sft_dpo_inventory/ablation_011/train/configs/A0-o1102.yaml").read_text(encoding="utf-8"))
    sems = {r["id"]: r["semantics"] for r in (json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
    eos = tok.eos_token
    out, a0_rows = {}, {}
    for arm, path in ARMS.items():
        recs = [json.loads(l) for l in (ROOT / path).read_text(encoding="utf-8").splitlines() if l.strip()]
        rows = render_records(tok, recs, cfg, "sft")
        loss, problems, lens = defaultdict(list), [], []
        for r, row in zip(recs, rows):
            k = kind(r)
            comp, prompt = row["completion"], row["prompt"]
            p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
            c_ids = tok(comp, add_special_tokens=False)["input_ids"]
            lens.append(len(p_ids) + len(c_ids) + 1)
            loss[k].append(len(c_ids))
            tid = r["metadata"]["trace_id"]
            body = comp[:-len(eos)] if comp.endswith(eos) else None
            if arm == "A0":
                a0_rows[rkey(r)] = (prompt, comp, p_ids + c_ids)
            elif arm == "A1":
                p0, c0, ids0 = a0_rows[rkey(r)]
                if prompt + comp != p0 + c0:
                    problems.append((tid, "a1_input_differs_from_a0"))
                if p_ids + c_ids != ids0:
                    problems.append((tid, "a1_tokens_differ_from_a0"))
                if k != "contrast_teacher_json_only" and (prompt, comp) != (p0, c0):
                    problems.append((tid, "a1_unmarked_render_differs"))
            if k == "refusal_S-1":
                try:
                    same = body is not None and json.loads(body) == {"unsupported": True}
                except Exception:  # noqa: BLE001
                    same = False
                if not same:
                    problems.append((tid, "s1_completion"))
                if "</think>" not in prompt:
                    problems.append((tid, "s1_thinking_not_in_prompt"))
            elif k == "refusal_teacher":
                ok = body is not None and body.lstrip().startswith("<think>") and "</think>" in body and body.split("</think>", 1)[1].strip() == '{"unsupported": true}'
                if not ok:
                    problems.append((tid, "teacher_refusal_completion"))
                if "</think>" in prompt:
                    problems.append((tid, "teacher_refusal_think_in_prompt"))
            elif k in ("contrast_teacher", "contrast_teacher_json_only"):
                sem = sems.get(r["metadata"]["source_record_id"])
                canon = serialize_planner_target(render_full(sem)).strip() if sem is not None else None
                if k == "contrast_teacher":
                    ok = body is not None and body.lstrip().startswith("<think>") and "</think>" in body and body.split("</think>", 1)[1].strip() == canon
                    if "</think>" in prompt:
                        problems.append((tid, "contrast_teacher_think_in_prompt"))
                else:
                    ok = body is not None and "<think>" not in body and "</think>" not in body and body.strip() == canon and prompt.rstrip().endswith("</think>")
                if not ok:
                    problems.append((tid, f"{k}_completion"))
            elif r["metadata"]["loss_scope"] == "json_only" and "</think>" in comp:
                problems.append((tid, "json_only_has_think"))
            elif r["metadata"]["loss_scope"] == "full_response" and not comp.lstrip().startswith("<think>"):
                problems.append((tid, "full_response_without_think"))
        total = sum(sum(v) for v in loss.values())
        con = sum(sum(v) for k, v in loss.items() if k.startswith("contrast_teacher"))
        ref = sum(sum(v) for k, v in loss.items() if k.startswith("refusal"))
        over = sum(1 for n in lens if n > MAXLEN)
        out[arm] = {"records": len(recs), "rendered": len(rows), "loss_tokens_total": total,
                    "by_kind": {k: {"records": len(v), "loss_tokens_sum": sum(v), "median": statistics.median(v), "share_of_loss": round(sum(v) / total, 4)} for k, v in sorted(loss.items())},
                    "loss_share_3way": {"refusal": round(ref / total, 4), "contrast_teacher": round(con / total, 4), "rest": round((total - ref - con) / total, 4)},
                    "max_len_tokens": max(lens), "over_12288": over, "problems": problems[:50], "problem_count": len(problems),
                    "ok": not problems and len(rows) == len(recs) and over == 0}
        print(arm, json.dumps({k: out[arm][k] for k in ("records", "loss_tokens_total", "loss_share_3way", "max_len_tokens", "over_12288", "problem_count", "ok")}, ensure_ascii=False), flush=True)
    (HERE / "mask_audit11.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
