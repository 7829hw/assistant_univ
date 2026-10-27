# -*- coding: utf-8 -*-
"""pilot_010 변형 V4·V8 데이터 구성 추정(결정 244 AA4, 지시 C3). **빌드가 아니다**(레코드 파일을 만들지 않음). 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_010/analysis/variants10.py   # -> analysis/variants10.json

가정(PLAN_DRAFT 1절의 공통 바탕):
- 답하는 바탕 = RC7 답하는 레코드 1,834(RC6 1,709 + batch012 r2 base 정답 표본 103 + batch011 r2 teacher 22) 그대로. 유형 상한 C-1은 다시 계산하지 않는다(밀림은 추정 밖).
- 근접 대조 teacher 레코드(``full_response``) = TEACH-C 대상 250질문(batch011 r2 40·batch012 r2 40·batch013 초안 77·승인 요금 지표 93)마다 min(4, 통과 trace 수).
  통과 trace 수 분포는 실제 TEACH-C가 없으면 **T-C 질문별 통과 수의 경험 분포**(20질문 × 8)로 대신한다(``source``에 적음). TEACH-C 원문이 있으면 그것을 쓴다.
  batch013은 모두 승인된다고 두는 상한(승인 수가 줄면 비례해 준다).
- batch013 base 정답 표본(json_only) = J-b013 표본에서 초안과 같은 grounding 표본 수 min(4, ·)(RC7의 batch012 r2와 같은 방식). J-b013이 없으면 0.
- 거부 레코드 R = ρ/(1−ρ)·N(N = 답하는 레코드 합), ρ = 4%(V4)·8%(V8). 구성은 RC7과 같게 S-1 10 + teacher 거부 trace(질문당 최대 4, 117질문).
- 레코드당 손실 token: RC7·RC6 ``mask_audit.json``의 종류별 평균(같은 렌더). 근접 대조 teacher 레코드는 T-C(또는 TEACH-C) 통과 trace를
  ``teacher_contrast10.to_arm_records``(Full) → ``training.trainer_common.render_records``로 렌더해 completion token을 센다(학습 렌더와 같음).
"""
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
ROOT = P10.parents[1]
for p in (ROOT, ROOT / "sft_dpo_inventory/thinking_prep_001", P10 / "teacher", ROOT / "sft_dpo_inventory/pilot_007/teacher"):
    sys.path.insert(0, str(p))
RC7_AUDIT = ROOT / "sft_dpo_inventory/pilot_009/build/RC7/mask_audit.json"
RC6_AUDIT = ROOT / "sft_dpo_inventory/pilot_008/build/RC6/mask_audit.json"
RC7_SUMMARY = ROOT / "sft_dpo_inventory/pilot_009/build/RC7/build_summary.json"
TC = ROOT / "training/generated/pilot_010/teacher_tc/traces.jsonl"
TEACHC = ROOT / "training/generated/pilot_010/teacher_teachc/traces.jsonl"
TARGETS = P10 / "teacher/teachc_targets.json"
JB013 = ROOT / "sft_dpo_inventory/batch013/jb013_draft_judgement.json"


def lines(p):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def contrast_tokens(rows, targets):
    """통과 trace → Full 레코드 completion token 수 목록."""
    import c2_edit as C2
    import hf_thinking as H
    import teacher_contrast10 as T
    from training.trainer_common import render_records
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = yaml.safe_load((ROOT / "sft_dpo_inventory/pilot_009/train/configs_p9/P9-F-o43.yaml").read_text(encoding="utf-8"))
    recs = []
    for r in rows:
        t = targets[r["id"]]
        th = C2.edit_thinking(r["thinking"] or "")[0]
        recs.append(T.to_arm_records({**r, "thinking": th}, t["semantics"], t["question"], r["id"])["full"])
    out = render_records(tok, recs, cfg, "sft")
    return [len(tok(x["completion"], add_special_tokens=False)["input_ids"]) for x in out]


def main():
    a7, a6 = json.loads(RC7_AUDIT.read_text(encoding="utf-8")), json.loads(RC6_AUDIT.read_text(encoding="utf-8"))
    mean7 = {k: v["loss_tokens_sum"] / v["records"] for k, v in a7["by_kind"].items()}
    targets = {t["id"]: t for t in json.loads(TARGETS.read_text(encoding="utf-8"))}
    tct = {t["id"]: t for t in json.loads((P10 / "teacher/tc_targets.json").read_text(encoding="utf-8"))}
    if TEACHC.exists():
        rows, src = lines(TEACHC), "TEACH-C 원문"
        per_q = Counter()
        for r in rows:
            per_q[r["id"]] += r["pass"]
        rec_per_q = {i: min(4, per_q.get(i, 0)) for i in targets}
        tok_rows, tok_targets = [r for r in rows if r["pass"]], targets
    else:
        rows, src = lines(TC), "T-C 질문별 통과 수 경험 분포(TEACH-C 없음)"
        per_q = Counter()
        for r in rows:
            per_q[r["id"]] += r["pass"]
        dist = [min(4, per_q.get(i, 0)) for i in tct]
        mean_r = sum(dist) / len(dist)
        rec_per_q = {i: mean_r for i in targets}
        tok_rows, tok_targets = [r for r in rows if r["pass"]], tct
    toks = contrast_tokens(tok_rows, tok_targets) if tok_rows else []
    c_tok = statistics.mean(toks) if toks else None
    by_set = defaultdict(float)
    for i, v in rec_per_q.items():
        by_set[targets[i]["set"]] += v
    contrast_records = sum(rec_per_q.values())
    b013_hf = 0
    if JB013.exists():
        bs = json.loads(JB013.read_text(encoding="utf-8"))["base_samples"]
        b013_hf = sum(min(4, v.get("match", 0)) for v in bs.values())
    s7 = json.loads(RC7_SUMMARY.read_text(encoding="utf-8"))["composition"]
    answered_base = s7["answered_records_N"]
    hf_tok = {"rc6_8b_json_only": mean7["8b_json_only"], "r2_Jb011": mean7["r2_Jb011"], "r2_Jb012": mean7["r2_Jb012"]}
    base_loss = a7["by_kind"]["8b_json_only"]["loss_tokens_sum"] + a7["by_kind"]["r2_Jb011"]["loss_tokens_sum"] + a7["by_kind"]["r2_Jb012"]["loss_tokens_sum"]
    teacher_ans_loss = a7["by_kind"]["teacher_full_response"]["loss_tokens_sum"] + a7["by_kind"]["r2_b011_teacher"]["loss_tokens_sum"]
    ref_t, s1_t = mean7["refusal_teacher"], mean7["refusal_S-1"]
    variants = {}
    for name, rho in (("V4", 0.04), ("V8", 0.08)):
        N = answered_base + contrast_records + b013_hf
        R = round(rho / (1 - rho) * N)
        r_s1, r_t = 10, R - 10
        loss = {"answered_hf_json_only": base_loss + b013_hf * mean7["r2_Jb012"], "answered_teacher(v3b)": teacher_ans_loss,
                "contrast_teacher": contrast_records * (c_tok or 0), "refusal_teacher": r_t * ref_t, "refusal_S-1": r_s1 * s1_t}
        tot = sum(loss.values())
        variants[name] = {"records": {"total": round(N + R), "answered_base(RC7)": answered_base, "contrast_teacher": round(contrast_records, 1),
                                      "contrast_teacher_by_set": {k: round(v, 1) for k, v in by_set.items()}, "batch013_base_json_only": b013_hf,
                                      "refusal": R, "refusal_S-1": r_s1, "refusal_teacher": r_t, "refusal_share": round(R / (N + R), 4),
                                      "refusal_teacher_per_question_mean(117q)": round(r_t / 117, 2)},
                          "loss_tokens_est": {k: round(v) for k, v in loss.items()}, "loss_share": {k: round(v / tot, 4) for k, v in loss.items()},
                          "loss_share_3way": {"refusal": round((loss["refusal_teacher"] + loss["refusal_S-1"]) / tot, 4),
                                              "contrast_teacher": round(loss["contrast_teacher"] / tot, 4),
                                              "rest": round((loss["answered_hf_json_only"] + loss["answered_teacher(v3b)"]) / tot, 4)},
                          "teacher_record_share": round((a7["by_kind"]["teacher_full_response"]["records"] + 22 + contrast_records + r_t) / (N + R), 4),
                          "steps(=records)": round(N + R)}
    ref6 = a6["by_kind"]
    compare = {"pilot_008 RC6": {"records": a6["records"], "refusal": 160, "refusal_share": round(160 / a6["records"], 4), "contrast_teacher": 0,
                                 "loss_share_3way": {"refusal": a6["refusal_loss_share"], "contrast_teacher": 0.0, "rest": round(1 - a6["refusal_loss_share"], 4)}},
               "pilot_009 RC7": {"records": a7["records"], "refusal": 159, "refusal_share": 0.0798, "contrast_teacher": 0,
                                 "loss_share_3way": {"refusal": a7["refusal_loss_share"], "contrast_teacher": 0.0, "rest": round(1 - a7["refusal_loss_share"], 4)},
                                 "note": "batch011 r2 teacher 22(v3b, 근접 대조 문장의 일반 teacher)는 rest에 넣음"}}
    out = {"source_pass_distribution": src, "contrast_records_per_question_mean": round(contrast_records / len(targets), 3),
           "contrast_teacher_loss_tokens": {"n": len(toks), "mean": round(c_tok, 1) if c_tok else None, "median": statistics.median(toks) if toks else None},
           "loss_tokens_per_record_rc7": {k: round(v, 1) for k, v in mean7.items()}, "teachc_targets": len(targets), "variants": variants, "compare": compare,
           "rc6_kinds": {k: v["records"] for k, v in ref6.items()}}
    (HERE / "variants10.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
