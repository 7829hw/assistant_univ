# -*- coding: utf-8 -*-
"""A2 정리 규칙 제안: RC3 teacher trace(836)에 규칙 후보를 적용했을 때 빠지는 trace·문항, 약점 부분집합 coverage. 모델 호출 없음, 데이터 파일은 고치지 않는다.

    hfvenv/bin/python a2_cleaning.py   # -> a2_cleaning.json

규칙 후보(제안일 뿐, pilot_007에서 고를 일):
- C1 drop-ii: (ii) 숨은 결론 암시 문장이 있는 trace를 뺀다.
- C2 drop-any: ``teacher6v3.EXPOSURE_V3C``(결론·conclusion·일치한다·대조 포함) 어느 것이든 있으면 뺀다(v3c (c) 검사와 같다).
- C3 strip: thinking에서 결론|conclusion|일치한다|대조가 든 줄을 지운다. 지운 줄에 다섯 판단 줄(측정/끝/묶음/집계/주변 + 값)이 들어 있거나
  지운 줄이 4줄 이상이면 내용 손실로 보고 뺀다. 나머지는 지운 채 남긴다(teacher 원문을 고치는 규칙이라 기록용 diff가 필요).
- C4 strip-ii: C3과 같되 (ii)에 걸리는 줄만 지운다.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/teacher"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/analysis"))
import coverage_h4 as H4  # noqa: E402
from itemdata import TYPE_II, concl_types  # noqa: E402
from teacher6v3 import EXPOSURE_V3C  # noqa: E402

RC3 = ROOT / "sft_dpo_inventory/pilot_006/build/RC3"
HIT = re.compile(r"결론|conclusion|일치한다|대조", re.I)
FIELD = re.compile(r"(측정|끝|묶음|집계|주변)\s*[:：]\s*\S")


def strip(th, only_ii):
    keep, gone = [], []
    for line in th.splitlines():
        bad = bool(TYPE_II.search(line)) if only_ii else bool(HIT.search(line))
        (gone if bad else keep).append(line)
    lost = len(gone) >= 4 or any(FIELD.search(g) for g in gone)
    return gone, lost


def main():
    corpus = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl").read_text(encoding="utf-8").splitlines()}
    out = {"rules": {}}
    for arm in ("full", "partial"):
        recs = [json.loads(l) for l in (RC3 / arm / "sft_train.jsonl").read_text(encoding="utf-8").splitlines()]
        teach = [r for r in recs if r["metadata"]["loss_scope"] == "full_response"]
        qs = defaultdict(list)
        for r in teach:
            qs[r["metadata"]["source_record_id"]].append(r)
        sub_all = Counter()
        for q in qs:
            if q in corpus:
                sub_all.update(H4.subsets(corpus[q]))
        res = {"teacher_traces": len(teach), "teacher_questions": len(qs)}
        for rule in ("C1", "C2", "C3", "C4"):
            dropped, modified, lines_removed = set(), 0, 0
            for i, r in enumerate(teach):
                th = r["messages"][-1]["content"].split("</think>")[0]
                if rule == "C1":
                    bad = "ii" in concl_types(th)
                elif rule == "C2":
                    bad = any(w in r["messages"][-1]["content"] for w in EXPOSURE_V3C)
                else:
                    gone, bad = strip(th, rule == "C4")
                    if gone and not bad:
                        modified += 1
                        lines_removed += len(gone)
                if bad:
                    dropped.add(i)
            left = defaultdict(int)
            for i, r in enumerate(teach):
                if i not in dropped:
                    left[r["metadata"]["source_record_id"]] += 1
            lost_q = [q for q in qs if left[q] == 0]
            sub_lost = Counter()
            for q in lost_q:
                if q in corpus:
                    sub_lost.update(H4.subsets(corpus[q]))
            res[rule] = {"traces_dropped": len(dropped), "traces_modified(strip)": modified, "lines_removed": lines_removed,
                         "traces_left": len(teach) - len(dropped), "questions_without_teacher": len(lost_q),
                         "weak_subsets_questions_lost": {k: f"{sub_lost[k]}/{sub_all[k]}" for k in sorted(sub_all) if sub_lost[k]}}
        out["rules"][arm] = res
    (HERE / "a2_cleaning.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
