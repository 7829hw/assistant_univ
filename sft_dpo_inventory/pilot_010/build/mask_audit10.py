# -*- coding: utf-8 -*-
"""V4·V8 손실 token·마스크 audit(결정 250 빌드 검사). ``pilot_009/build/mask_audit9.py``(그대로)의 사본: 대상 변형·종류(근접 대조 teacher·r2 Jb013)·config만 바꿈. 학습 코드의 렌더
(``training.trainer_common.render_records``)를 그대로 써서 레코드마다 completion(손실 구간)을 확인. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_010/build/mask_audit10.py --variant V4|V8 [--root DIR] [--config CFG]   # -> build/<V>/mask_audit.json

- 종류별(teacher full_response / 8b json_only / r2 Jb011·Jb012·Jb013 / r2 teacher b011 / 근접 대조 teacher / 거부 S-1·teacher) 손실 token(중앙값·합),
  전체 손실 token 중 거부·근접 대조 teacher·나머지 몫(결정 250 보고 기준)과 teacher 몫.
- 근접 대조 teacher(full_response): completion이 ``<think>``로 시작하고 ``</think>`` 뒤가 canonical Full JSON(``render_full``), EOS로 끝남.
- 거부 S-1(json_only): completion이 ``{"unsupported": true}`` + EOS, thinking이 prompt 쪽.
- 거부 teacher(full_response): completion이 ``<think>``로 시작하고 ``</think>`` 뒤 JSON이 정확히 ``{"unsupported": true}``, EOS로 끝남, prompt에 ``</think>`` 없음.
- json_only: completion에 ``</think>``가 없는지. full_response: completion이 thinking으로 시작하는지.
"""
import argparse
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
    if m.get("contrast_source") == "teacher":
        return "contrast_teacher"
    if m["corpus_group"] == "batch013":
        return "r2_Jb013"
    if m["corpus_group"] == "batch011":
        return "r2_b011_teacher" if m["loss_scope"] == "full_response" else "r2_Jb011"
    if m["corpus_group"] == "batch012":
        return "r2_Jb012"
    return "teacher_full_response" if m["loss_scope"] == "full_response" else "8b_json_only"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=("V4", "V8"))
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--config", default=str(ROOT / "sft_dpo_inventory/pilot_009/train/configs_p9/P9-F-o43.yaml"))
    a = ap.parse_args()
    vdir = Path(a.root) / a.variant
    import hf_thinking as H
    from grounding.full_renderer import render_full
    from training.data.canonicalize import serialize_planner_target
    from training.trainer_common import render_records
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    recs = [json.loads(l) for l in (vdir / "full/sft_train.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = render_records(tok, recs, cfg, "sft")
    sems = {r["id"]: r["semantics"] for r in (json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}
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
        elif k == "contrast_teacher":
            body = comp[:-len(eos)] if comp.endswith(eos) else None
            ok = body is not None and body.lstrip().startswith("<think>") and "</think>" in body
            sem = sems.get(r["metadata"]["source_record_id"])
            if not ok or sem is None or body.split("</think>", 1)[1].strip() != serialize_planner_target(render_full(sem)).strip():
                problems.append((tid, "contrast_teacher_completion", comp[-80:]))
            if "</think>" in row["prompt"]:
                problems.append((tid, "contrast_teacher_think_in_prompt"))
        elif r["metadata"]["loss_scope"] == "json_only" and "</think>" in comp:
            problems.append((tid, "json_only_has_think"))
        elif r["metadata"]["loss_scope"] == "full_response" and not comp.lstrip().startswith("<think>"):
            problems.append((tid, "full_response_without_think"))
    total = sum(sum(v) for v in loss.values())
    teacher_kinds = ("teacher_full_response", "r2_b011_teacher", "refusal_teacher", "contrast_teacher")
    out = {"records": len(recs), "rendered": len(rows), "loss_tokens_total": total,
           "by_kind": {k: {"records": len(v), "loss_tokens_sum": sum(v), "median": statistics.median(v), "share_of_loss": round(sum(v) / total, 4)} for k, v in sorted(loss.items())},
           "refusal_loss_share": round(sum(sum(v) for k, v in loss.items() if k.startswith("refusal")) / total, 4),
           "loss_share_3way": {"refusal": round(sum(sum(v) for k, v in loss.items() if k.startswith("refusal")) / total, 4),
                               "contrast_teacher": round(sum(loss.get("contrast_teacher", [])) / total, 4),
                               "rest": round(sum(sum(v) for k, v in loss.items() if not k.startswith("refusal") and k != "contrast_teacher") / total, 4)},
           "teacher_loss_share": round(sum(sum(loss[k]) for k in teacher_kinds if k in loss) / total, 4),
           "teacher_record_share": round(sum(len(loss[k]) for k in teacher_kinds if k in loss) / len(recs), 4),
           "problems": problems, "ok": not problems and len(rows) == len(recs)}
    (vdir / "mask_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
