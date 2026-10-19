# -*- coding: utf-8 -*-
"""c2 적용(결정 185 Q1, A3 S0). RC3 두 arm teacher 레코드의 thinking에 ``c2_edit``을 적용한다. 원본(RC3, ``teacher_v3/traces.jsonl``)은 고치지 않는다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/teacher/apply_c2.py
    # -> pilot_007/teacher/c2_records_{full,partial}.jsonl(편집 뒤 남은 teacher 레코드), c2_edits.jsonl(trace별 편집 기록), pilot_007/teacher_c2.json(요약)

- (b) 검사의 다섯 줄은 teacher 원 출력(``traces.jsonl``의 content), semantics는 ``teach3_targets.json``. 두 arm의 같은 trace는 thinking이 같다(arm마다 따로 적용하고 같은지 확인).
- 빠지는 이유: 내용 손실(C4 조건), (ii) 남음, (a)(b)(c) 불통과.
- 요약: 편집한 trace 수·지운 줄 수, 빠진 trace 수(이유별), teacher가 없어진 질문 수, 약점 부분집합 커버리지, RC3c와 비교. 보고 기준: 빠지는 trace가 RC3 teacher trace의 10% 초과면 보고.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (ROOT, HERE, ROOT / "sft_dpo_inventory/pilot_006_prep/analysis"):
    sys.path.insert(0, str(p))
RC3 = ROOT / "sft_dpo_inventory/pilot_006/build/RC3"
RC3C = HERE.parent / "build/RC3c"
TRACES = ROOT / "training/generated/pilot_006/teacher_v3/traces.jsonl"
TARGETS = ROOT / "sft_dpo_inventory/pilot_006/teacher/teach3_targets.json"
CORPUS = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v3.jsonl"


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    import c2_edit as E
    import coverage_h4 as H4
    traces = {t["trace_id"]: t for t in read_jsonl(TRACES)}
    targets = {t["id"]: t for t in json.loads(TARGETS.read_text(encoding="utf-8"))}
    corpus = {r["id"]: r for r in read_jsonl(CORPUS)}
    edits, by_trace, summary = [], {}, {}
    for arm in ("full", "partial"):
        recs = [r for r in read_jsonl(RC3 / arm / "sft_train.jsonl") if r["metadata"]["loss_scope"] == "full_response"]
        kept, drop = [], Counter()
        n_edit = n_lines = 0
        for r in recs:
            m = r["metadata"]
            t = traces[m["trace_id"]]
            head, th, tail = E.split_record(r["messages"][-1]["content"])
            new, gone, lost = E.edit_thinking(th)
            chk = E.check_after(new, t["content"], targets[t["id"]]["semantics"])
            reasons = (["content_loss"] if lost else []) + chk["reasons"]
            if gone:
                n_edit += 1
                n_lines += len(gone)
            prev = by_trace.get(m["trace_id"])
            if prev is not None:
                assert prev["thinking_sha256_before"] == E.sha(th) and prev["removed_lines"] == gone, m["trace_id"]
            else:
                by_trace[m["trace_id"]] = {"trace_id": m["trace_id"], "question": m["source_record_id"], "removed_lines": gone,
                                           "thinking_sha256_before": E.sha(th), "thinking_sha256_after": E.sha(new), "kept": not reasons, "drop_reasons": reasons}
            if reasons:
                drop[",".join(reasons)] += 1
                continue
            nr = json.loads(json.dumps(r))
            nr["messages"][-1]["content"] = head + new + tail
            nr["metadata"]["c2_edited"] = bool(gone)
            nr["metadata"]["c2_removed_lines"] = len(gone)
            nr["metadata"]["thinking_sha256_c2"] = E.sha(new)
            kept.append(nr)
        (HERE / f"c2_records_{arm}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in kept), encoding="utf-8")
        tq_before = {r["metadata"]["source_record_id"] for r in recs}
        tq_after = {r["metadata"]["source_record_id"] for r in kept}
        rc3c_tq = {r["metadata"]["source_record_id"] for r in read_jsonl(RC3C / arm / "sft_train.jsonl") if r["metadata"]["loss_scope"] == "full_response"}

        def subs(q):
            c = corpus.get(q)
            s = set(H4.subsets(c)) if c else set()
            if c and "소속" in c["question"]:
                s.add("소속")
            return s
        names = sorted(set().union(*(subs(q) for q in tq_before)))
        cov = {n: {"RC3": sum(n in subs(q) for q in tq_before), "c2": sum(n in subs(q) for q in tq_after), "RC3c": sum(n in subs(q) for q in rc3c_tq)} for n in names}
        summary[arm] = {"teacher_records_rc3": len(recs), "edited": n_edit, "lines_removed": n_lines, "dropped": sum(drop.values()), "dropped_by_reason": dict(drop),
                        "kept": len(kept), "dropped_pct": round(100 * sum(drop.values()) / len(recs), 2),
                        "teacher_questions": {"RC3": len(tq_before), "c2": len(tq_after), "RC3c": len(rc3c_tq), "lost_vs_RC3": sorted(tq_before - tq_after)},
                        "teacher_records_RC3c": sum(1 for r in read_jsonl(RC3C / arm / "sft_train.jsonl") if r["metadata"]["loss_scope"] == "full_response"),
                        "weak_subset_teacher_questions": cov}
    with (HERE / "c2_edits.jsonl").open("w", encoding="utf-8") as f:
        for v in by_trace.values():
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    out = {"decision": "185 (Q1)", "rule": "c2_edit: TYPE_II 줄 삭제(C4) → 내용 손실·(ii) 남음·(a)(b)(c) 불통과면 trace 뺌, 영어 생각 trace 그대로",
           "arms": summary, "report_needed(dropped > 10%)": any(v["dropped_pct"] > 10 for v in summary.values())}
    (HERE.parent / "teacher_c2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for arm, v in summary.items():
        print(arm, {k: v[k] for k in ("teacher_records_rc3", "edited", "lines_removed", "dropped", "dropped_by_reason", "kept", "dropped_pct", "teacher_records_RC3c")},
              {k: v["teacher_questions"][k] for k in ("RC3", "c2", "RC3c")})
    print("report_needed", out["report_needed(dropped > 10%)"])


if __name__ == "__main__":
    main()
