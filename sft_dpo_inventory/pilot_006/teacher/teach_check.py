# -*- coding: utf-8 -*-
"""P4: TEACH(v3b, 결정 151·152) 검사. 모델 호출 없음.

    hfvenv/bin/python teach_check.py   # -> teach_check.json

- trace 검사((a)(b)(c)): 수집 때 붙인 결과를 센다(질문별 통과 trace 수, 통과 trace가 없는 질문).
- 두 arm 레코드: 질문마다 통과 trace 하나에 Full JSON(``render_full``)·Partial JSON(``render_partial``)을 붙여(``teacher6v3.to_arm_records``) 학습 계약
  (``target_ok``, Partial은 completion 뒤)과 W5 검증 사슬(``validate_semantics``, 승인 corpus 정답 호출)을 확인한다.
- 부분집합별 통과율: ``analysis/coverage_h4.subsets``와 같은 정의.
- 결론 의식 표현(판정 밖 관찰, V3B_READ.md): 통과 trace의 thinking에 "결론" 또는 영어 "conclusion"이 있는 비율, 영어로 시작한 비율.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/analysis"))


def main():
    import coverage_h4 as H4
    import teacher6v3 as T
    from grounding.completion import complete_grounding_payload
    from grounding.validation import validate_semantics
    from training.data import thinking as TH
    from training.data.validation import assess, target_ok
    targets = {t["id"]: t for t in json.loads((HERE / "teach3_targets.json").read_text(encoding="utf-8"))}
    corpus = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl").read_text(encoding="utf-8").splitlines()}
    rows = [json.loads(l) for l in (ROOT / "training/generated/pilot_006/teacher_v3/traces.jsonl").read_text(encoding="utf-8").splitlines()]
    per = defaultdict(lambda: Counter())
    aware = Counter()
    for r in rows:
        q = per[r["id"]]
        q["traces"] += 1
        q["a"] += r["check_a"]["pass"]
        q["b"] += r["check_b"]["pass"]
        q["c_exposed"] += r["check_c"]["exposed"]
        q["pass"] += r["pass"]
        if r["pass"]:
            aware["pass_traces"] += 1
            aware["thinking_mentions_결론"] += "결론" in r["thinking"]
            aware["thinking_mentions_conclusion"] += bool(re.search(r"conclusion", r["thinking"], re.I))
            aware["thinking_starts_english"] += r["thinking"].lstrip()[:20].isascii()
    arm_check, sub = {}, defaultdict(Counter)
    for qid, t in targets.items():
        rec = corpus.get(qid)
        sem, question = t["semantics"], t["question"]
        ok_trace = next((r for r in rows if r["id"] == qid and r["pass"]), None)
        res = {"has_pass_trace": ok_trace is not None}
        if ok_trace:
            recs = T.to_arm_records({"trace_id": ok_trace["trace_id"], "thinking": ok_trace["thinking"]}, sem, question, qid, "v3b")
            for arm, r in recs.items():
                tgt = TH.response_json(r["messages"][2]["content"])
                tgt = complete_grounding_payload(tgt) if arm == "partial" else tgt
                res[f"{arm}_contract_ok"] = bool(target_ok(assess(tgt, question), {}))
            v = validate_semantics(sem, question, rec.get("execution") if rec else None)
            res["validation_chain_ok"] = bool(v["ok"])
        arm_check[qid] = res
        for s in H4.subsets({"semantics": sem, "question": question}):
            sub[s]["questions"] += 1
            sub[s]["with_pass_trace"] += res["has_pass_trace"]
            sub[s]["traces"] += per[qid]["traces"]
            sub[s]["pass_traces"] += per[qid]["pass"]
    total = Counter()
    for q in per.values():
        total.update(q)
    out = {"traces": len(rows), "questions_collected": len(per), "questions_target": len(targets), "totals": dict(total),
           "questions_without_pass": sorted(q for q in targets if per[q]["pass"] == 0),
           "pass_trace_dist": dict(Counter(min(per[q]["pass"], 8) for q in targets)),
           "both_arm_records": {"checked": sum(1 for v in arm_check.values() if v["has_pass_trace"]),
                                "full_contract_fail": [q for q, v in arm_check.items() if v.get("full_contract_ok") is False],
                                "partial_contract_fail": [q for q, v in arm_check.items() if v.get("partial_contract_ok") is False],
                                "validation_chain_fail": [q for q, v in arm_check.items() if v.get("validation_chain_ok") is False]},
           "subsets": {s: {**dict(c), "pass_rate": round(c["pass_traces"] / max(1, c["traces"]), 3)} for s, c in sorted(sub.items())},
           "awareness(observed, not a criterion)": dict(aware), "per_question": {q: dict(c) for q, c in per.items()}}
    (HERE / "teach_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("per_question", "subsets")}, ensure_ascii=False, indent=1)[:3000])
    print(json.dumps(out["subsets"], ensure_ascii=False))


if __name__ == "__main__":
    main()
