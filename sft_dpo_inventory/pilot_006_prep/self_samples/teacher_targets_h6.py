# -*- coding: utf-8 -*-
"""H6: 모든 8b 표본 판정(승인 gold) 뒤 teacher 필수 대상과 12,288 초과 정답 표본을 다시 센다. 모델 호출 없음.

    hfvenv/bin/python teacher_targets_h6.py   # -> r1/teacher_targets_h6.json

- teacher 필수 = 승인 corpus 질문(정규화 질문으로 합침, trunk 우선) 가운데 한 arm이라도 8b 자체 정답 표본이 없는 질문.
- TEACH는 T0' 불통과로 시작하지 않았으므로(결정 131) 전부 "추가 teacher 대상"(다음 세션 수집)이다. G2 범위(teacher 필수 ∪ trunk 131 ∪ 질문 변경)도 함께 적는다.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))


def main():
    import approved6 as AP
    from training.data.split import question_key
    corpus = AP.load()
    order = {"trunk": 0, "pg": 1, "aug300": 2, "batch007": 3, "batch008": 4}
    by_key, alias, qs = {}, {}, {}
    for cid, rec in sorted(corpus.items(), key=lambda kv: (order[kv[1]["corpus_group"]], kv[0])):
        k = question_key(rec["question"])
        if k in by_key:
            alias[cid] = by_key[k]
            continue
        by_key[k] = cid
        qs[cid] = rec
    correct = {"full": set(), "partial": set()}
    over, files = [], []
    for f in sorted((HERE / "r1").glob("*_approved.json")):
        if "first" in f.name:
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        files.append(f.name)
        for q in d["per_question"]:
            if q["status"] == "approved" and q["correct"] > 0:
                correct[d["arm"]].add(alias.get(q["id"], q["id"]))
        over += [{"file": f.name, **x} for x in d.get("correct_over_12288", [])]
    need = sorted(c for c in qs if c not in correct["full"] or c not in correct["partial"])
    inval = json.loads((AP.APPROVED / "invalidated_outputs.json").read_text(encoding="utf-8"))["questions"]
    g2 = sorted(set(need) | {c for c in qs if qs[c]["corpus_group"] == "trunk"} | {alias.get(i, i) for i in inval})
    out = {"judge_files": files, "questions": len(qs), "with_correct": {a: len(v & set(qs)) for a, v in correct.items()},
           "teacher_required": {"count": len(need), "both_arms_missing": sum(1 for c in need if c not in correct["full"] and c not in correct["partial"]),
                                "full_only_missing": sum(1 for c in need if c not in correct["full"] and c in correct["partial"]),
                                "partial_only_missing": sum(1 for c in need if c in correct["full"] and c not in correct["partial"]),
                                "by_group": {g: sum(1 for c in need if qs[c]["corpus_group"] == g) for g in order}, "ids": need},
           "additional_teacher_targets(next session, G2 scope)": {"count": len(g2), "ids": g2,
                                                                  "note": "TEACH 미실행(T0' 불통과). G2 범위 전체가 다음 세션 수집 대상"},
           "r1_teacher_required": 133, "correct_over_12288": over}
    (HERE / "r1/teacher_targets_h6.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: (v if k not in ("teacher_required", "additional_teacher_targets(next session, G2 scope)") else {kk: vv for kk, vv in v.items() if kk != "ids"})
                      for k, v in out.items() if k != "judge_files"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
