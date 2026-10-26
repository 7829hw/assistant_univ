# -*- coding: utf-8 -*-
"""pilot_009 PLAN_DRAFT(결정 232 Y6) RC7 구성 선택지 계산 — 빌드가 아니다(RC7 빌드는 승인 뒤). 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_009/analysis/rc7_options.py   # -> analysis/rc7_options.json

가정(승인 전이라 추정):
- batch012 100이 모두 승인된다고 둔다(승인 결과에 따라 줄어듦). 유형 상한(C-1)으로 밀리는 레코드는 빼지 않은 값(빌드 때 다시 계산).
- 답하는 레코드 A = RC6 답하는 1,845 + batch012 r2 base 정답 표본(J-b012, 질문당 ≤ 4) + r2 teacher trace(TEACH-R v3b 통과, 질문당 ≤ 4).
- 거부 레코드 R: 8%면 round(0.08·A/0.92), 10%면 round(0.10·A/0.90). 거부 질문 = batch011 r1 60 + batch012 r1 60.
- 출처: S-1(base 순수 모델 거부 표본: batch011 10, batch012는 J-b012 표본 중 exact `{"unsupported": true}` 수), teacher 거부 trace(TEACH-R 통과, 질문당 ≤ 4, full_response),
  S-2(짧은 근거 target, json_only; batch012 S-2는 새로 만들어야 함).
  - **T(대체)**: R = S-1 + teacher(질문마다 고르게, ≤ 4). S-2 없음.
  - **S(유지)**: R = S-1 + S-2(질문당 1) + teacher(나머지, 고르게).
- 손실 token: 기존 RC6 값(`pilot_008/build/RC6/mask_audit.json`), teacher 거부 레코드 = 통과 trace의 eval_count 평균(생각 + 출력; 출력은 JSON으로 바뀌어 거의 같음),
  r2 teacher = v3b 통과 eval_count 평균 + JSON 근사(RC6 teacher 레코드 평균 − 생각 근사 대신 그대로 eval_count 사용), r2 base 표본 = RC6 r2_Jb011 평균, S-2·S-1 = 6.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GEN = ROOT / "training/generated/pilot_009"


def main():
    audit = json.loads((ROOT / "sft_dpo_inventory/pilot_008/build/RC6/mask_audit.json").read_text(encoding="utf-8"))
    k = audit["by_kind"]
    rows = [json.loads(l) for l in (GEN / "teacher_teachr/traces.jsonl").read_text(encoding="utf-8").splitlines()]
    tg = {t["id"]: t for t in json.loads((ROOT / "sft_dpo_inventory/pilot_009/teacher/teachr_targets.json").read_text(encoding="utf-8"))}
    passed = Counter(r["id"] for r in rows if r["pass"])
    ref_q = [i for i, t in tg.items() if t["variant"] == "refusal_v1"]
    r2_q = [i for i, t in tg.items() if t["variant"] == "v3b"]
    ref_tok = [r["eval_count"] for r in rows if r["pass"] and r["variant"] == "refusal_v1"]
    r2_tok = [r["eval_count"] for r in rows if r["pass"] and r["variant"] == "v3b"]
    teacher_avail = {i: min(4, passed[i]) for i in ref_q}
    r2_teacher = sum(min(4, passed[i]) for i in r2_q)
    jb = json.loads((ROOT / "sft_dpo_inventory/batch012/jb012_draft_judgement.json").read_text(encoding="utf-8"))["base_samples"]
    cands = {c["id"]: c for c in json.loads((ROOT / "sft_dpo_inventory/batch012/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    r2_base = sum(min(4, jb.get(i, {}).get("match", 0)) for i, c in cands.items() if c["kind"] == "r2_contrast")
    s1_b012 = sum(jb.get(i, {}).get("model_refusal", 0) for i, c in cands.items() if c["kind"] == "r1_refusal")  # 상한: exact 형식은 빌드 때 다시 셈
    s1 = 10 + min(s1_b012, 7)
    A = 1845 + r2_base + r2_teacher
    avg = lambda xs: sum(xs) / len(xs)  # noqa: E731
    base_tok = {"answered_8b": k["8b_json_only"]["loss_tokens_sum"] + k["r2_Jb011"]["loss_tokens_sum"], "teacher_full_response": k["teacher_full_response"]["loss_tokens_sum"]}
    add_r2_base_tok = r2_base * k["r2_Jb011"]["loss_tokens_sum"] / k["r2_Jb011"]["records"]
    add_r2_teacher_tok = r2_teacher * avg(r2_tok)
    out = {"assumptions": __doc__.split("가정(승인 전이라 추정):")[1].strip(), "answered_records_A": A,
           "parts": {"rc6_answered": 1845, "batch012_r2_base_samples(≤4/q)": r2_base, "r2_teacher_traces(≤4/q)": r2_teacher,
                     "refusal_questions": len(ref_q), "teacher_refusal_available(≤4/q)": sum(teacher_avail.values()),
                     "questions_with_teacher_refusal≥4": sum(v == 4 for v in teacher_avail.values()), "s1_records(est.)": s1},
           "tokens": {"teacher_refusal_trace_mean": round(avg(ref_tok), 1), "r2_teacher_trace_mean": round(avg(r2_tok), 1),
                      "rc6_teacher_record_mean": round(k["teacher_full_response"]["loss_tokens_sum"] / k["teacher_full_response"]["records"], 1)},
           "options": {}}
    for share in (0.08, 0.10):
        R = round(share * A / (1 - share))
        for opt in ("T", "S"):
            s2 = 0 if opt == "T" else len(ref_q)
            teacher = max(0, min(R - s1 - s2, sum(teacher_avail.values())))
            refusal = s1 + s2 + teacher
            teacher_tok = base_tok["teacher_full_response"] + add_r2_teacher_tok + teacher * avg(ref_tok)
            total_tok = base_tok["answered_8b"] + base_tok["teacher_full_response"] + add_r2_base_tok + add_r2_teacher_tok + teacher * avg(ref_tok) + 6 * (s1 + s2)
            teacher_recs = 747 + r2_teacher + teacher
            out["options"][f"{int(share * 100)}%_{opt}"] = {
                "R_target": R, "refusal_records": refusal, "s1": s1, "s2": s2, "teacher_refusal": teacher,
                "per_question_teacher": round(teacher / len(ref_q), 2), "records_total": A + refusal, "refusal_share": round(refusal / (A + refusal), 4),
                "teacher_records": teacher_recs, "teacher_record_share": round(teacher_recs / (A + refusal), 4),
                "teacher_loss_share": round(teacher_tok / total_tok, 4), "refusal_loss_share": round((teacher * avg(ref_tok) + 6 * (s1 + s2)) / total_tok, 4),
                "steps_1epoch": A + refusal}
    out["rc6_reference"] = {"records": 2005, "teacher_records": 747, "teacher_record_share": round(747 / 2005, 4), "teacher_loss_share": k["teacher_full_response"]["share_of_loss"],
                            "refusal_records": 160, "refusal_loss_share": audit["refusal_loss_share"]}
    (HERE / "rc7_options.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "assumptions"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
