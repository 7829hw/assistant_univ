# -*- coding: utf-8 -*-
"""R1 요약: 초안 기준 판정(C2·C3: j1/j6_judgement.json)과 승인 gold 판정(r1/j1·j6_approved.json) 비교. 모델 호출 없음.

    python3 r1_compare.py   # -> r1/r1_summary.json

- 질문별 "정답 표본 있음"이 바뀐 질문, 정답 표본 수가 바뀐 질문.
- teacher 필수 대상(결정 132 G2의 첫 항): 승인 train 질문 가운데 한 arm이라도 정답 표본이 없는 질문(J1·J6 대상 질문만; trunk 131·batch008은 J1·J6 대상이 아님).
- 보강 대상(결정 133 G3, H2): arm마다 그 arm에 정답 표본이 없는 승인 질문.
- 12,288 초과 정답 표본.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import approved6 as AP  # noqa: E402


def main():
    old = {arm: {AP.corpus_id(q["id"]): q for q in json.loads((HERE / f"{j}_judgement.json").read_text(encoding="utf-8"))["per_question"]}
           for arm, j in (("full", "j1"), ("partial", "j6"))}
    new = {arm: {q["id"]: q for q in json.loads((HERE / f"r1/{j}_approved.json").read_text(encoding="utf-8"))["per_question"]}
           for arm, j in (("full", "j1"), ("partial", "j6"))}
    out = {"arms": {}}
    for arm in ("full", "partial"):
        changed_has, changed_n = [], []
        for cid, q in new[arm].items():
            if q["status"] != "approved":
                continue
            o = old[arm].get(cid)
            if o is None:
                continue
            if (o["correct"] > 0) != (q["correct"] > 0):
                changed_has.append({"id": cid, "draft_correct": o["correct"], "approved_correct": q["correct"]})
            elif o["correct"] != q["correct"]:
                changed_n.append({"id": cid, "draft_correct": o["correct"], "approved_correct": q["correct"]})
        no_corr = sorted(cid for cid, q in new[arm].items() if q["status"] == "approved" and q["correct"] == 0)
        old_no = sorted(AP.corpus_id(i) for i in json.loads((HERE / ("j1_judgement.json" if arm == "full" else "j6_judgement.json"))
                                                             .read_text(encoding="utf-8"))["no_correct_questions(teacher priority)"])
        out["arms"][arm] = {"approved_questions_judged": sum(q["status"] == "approved" for q in new[arm].values()),
                            "with_correct": sum(q["status"] == "approved" and q["correct"] > 0 for q in new[arm].values()),
                            "has_correct_changed": changed_has, "count_changed_only": len(changed_n),
                            "no_correct_approved(S32 target)": no_corr, "no_correct_draft_basis": len(old_no),
                            "over_12288": [x for q in new[arm].values() for x in ([{"id": q["id"], **y} for y in q["correct_over_12288"]])]}
    union = sorted(set(out["arms"]["full"]["no_correct_approved(S32 target)"]) | set(out["arms"]["partial"]["no_correct_approved(S32 target)"]))
    inter = sorted(set(out["arms"]["full"]["no_correct_approved(S32 target)"]) & set(out["arms"]["partial"]["no_correct_approved(S32 target)"]))
    old_union = set()
    for j in ("j1", "j6"):
        old_union |= {AP.corpus_id(i) for i in json.loads((HERE / f"{j}_judgement.json").read_text(encoding="utf-8"))["no_correct_questions(teacher priority)"]}
    out["teacher_required_r1"] = {"count": len(union), "both_arms_no_correct": len(inter), "ids": union,
                                  "draft_basis_count": len(old_union), "added_vs_draft": sorted(set(union) - old_union),
                                  "removed_vs_draft": sorted(old_union - set(union))}
    (HERE / "r1/r1_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"full": {k: (v if not isinstance(v, list) else len(v)) for k, v in out["arms"]["full"].items()},
                      "partial": {k: (v if not isinstance(v, list) else len(v)) for k, v in out["arms"]["partial"].items()},
                      "teacher": {k: (v if not isinstance(v, list) else len(v)) for k, v in out["teacher_required_r1"].items()}}, ensure_ascii=False, indent=1))
    for arm in ("full", "partial"):
        print(arm, out["arms"][arm]["has_correct_changed"], out["arms"][arm]["over_12288"])


if __name__ == "__main__":
    main()
