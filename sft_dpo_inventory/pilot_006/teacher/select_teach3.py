# -*- coding: utf-8 -*-
"""TEACH 대상(결정 145 K8), 실행 전에 커밋. 모델 출력은 판정 결과(정답 표본 유무)만 쓴다.

    hfvenv/bin/python select_teach3.py   # -> teach3_targets.json

대상 = teacher 필수(P2 ``pilot_006_prep/self_samples/r1/teacher_targets_p2.json``: 승인 corpus v2에서 한 arm이라도 8b 정답 표본 없음)
     ∪ trunk 131 ∪ 질문이 바뀐 aug300 3(R0) ∪ batch009 승인분 51(K2 42 + K3 w1 9) ∪ K4 복원 5. 제외·미승인은 넣지 않는다.
- 같은 정규화 질문은 trunk id로 합친다(``aliases``). semantics는 승인 corpus v2.
- 순서: teacher 필수 → batch009 → 복원 → 질문 변경 → trunk(각 묶음 안 id 순서). 세션 안에 끝나지 않으면 앞쪽부터 쓴다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from training.data.split import question_key  # noqa: E402

corpus = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl").read_text(encoding="utf-8").splitlines()}
p2 = json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/self_samples/r1/teacher_targets_p2.json").read_text(encoding="utf-8"))
inval = json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/approved/invalidated_outputs.json").read_text(encoding="utf-8"))["questions"]
K4 = ["aug300-366", "aug300-369", "aug300-389", "aug300-397", "aug300-398"]
trunk_by_key = {question_key(r["question"]): rid for rid, r in corpus.items() if r["corpus_group"] == "trunk"}
groups = [("teacher_required_p2", sorted(p2["teacher_required"]["ids"])),
          ("batch009", sorted(rid for rid, r in corpus.items() if r["corpus_group"] == "batch009")),
          ("restored_k4", K4), ("question_changed", sorted(inval)),
          ("trunk", sorted(rid for rid, r in corpus.items() if r["corpus_group"] == "trunk"))]
out, seen = [], {}
for name, ids in groups:
    for rid in ids:
        rec = corpus[rid]
        key = question_key(rec["question"])
        main = trunk_by_key.get(key, rid)
        if key in seen:
            if rid != seen[key]["id"] and rid not in seen[key]["aliases"]:
                seen[key]["aliases"].append(rid)
            if name not in seen[key]["groups"]:
                seen[key]["groups"].append(name)
            continue
        t = {"id": main, "aliases": [rid] if rid != main else [], "groups": [name], "question": corpus[main]["question"],
             "semantics": corpus[main]["semantics"], "k3_scope_name_family": corpus[main].get("k3_scope_name_family", False)}
        seen[key] = t
        out.append(t)
(HERE / "teach3_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(out), Counter(t["groups"][0] for t in out), "with_alias", sum(bool(t["aliases"]) for t in out))
