# -*- coding: utf-8 -*-
"""TEACH 대상(결정 132 G2), 실행 전에 커밋. 모델 출력은 R1 판정 결과(정답 표본 유무)만 쓴다.

    hfvenv/bin/python select_teach.py   # -> teach_targets.json

대상 = R1 teacher 필수(``pilot_006_prep/self_samples/r1/r1_summary.json``: 승인 질문 가운데 한 arm이라도 J1·J6 정답 표본 없음)
     ∪ 질문이 바뀐 aug300(R0 통과분; 348은 보류라 뺌) ∪ trunk 131 전체.
- 미승인·G0 제외는 넣지 않는다(승인 corpus에 없는 id는 실패). 같은 정규화 질문(pg v005 ``pg:ann-…``와 trunk ``t2pc:ann-…``)은 하나로 합치고
  trunk id를 쓴다(``aliases``). semantics는 승인 corpus 것.
- 순서: teacher 필수 → 질문 변경 → trunk(각 묶음 안에서 id 순서). 수집이 세션 안에 끝나지 않으면 앞쪽부터 쓴다.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from training.data.split import question_key  # noqa: E402

corpus = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v1.jsonl").read_text(encoding="utf-8").splitlines()}
r1 = json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/self_samples/r1/r1_summary.json").read_text(encoding="utf-8"))
inval = json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/approved/invalidated_outputs.json").read_text(encoding="utf-8"))["questions"]
trunk_by_key = {question_key(r["question"]): rid for rid, r in corpus.items() if r["corpus_group"] == "trunk"}
groups = [("teacher_required_r1", sorted(r1["teacher_required_r1"]["ids"])), ("question_changed", sorted(inval)),
          ("trunk", sorted(rid for rid, r in corpus.items() if r["corpus_group"] == "trunk"))]
out, seen = [], {}
for name, ids in groups:
    for rid in ids:
        rec = corpus[rid]
        key = question_key(rec["question"])
        main = trunk_by_key.get(key, rid)
        if key in seen:
            if rid not in seen[key]["aliases"] and rid != seen[key]["id"]:
                seen[key]["aliases"].append(rid)
                seen[key]["groups"].append(name)
            continue
        t = {"id": main, "aliases": [rid] if rid != main else [], "groups": [name], "question": corpus[main]["question"], "semantics": corpus[main]["semantics"]}
        seen[key] = t
        out.append(t)
(HERE / "teach_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
from collections import Counter  # noqa: E402
print(len(out), Counter(t["groups"][0] for t in out), "with_alias", sum(bool(t["aliases"]) for t in out))
