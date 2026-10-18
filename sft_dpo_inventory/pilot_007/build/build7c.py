# -*- coding: utf-8 -*-
"""RC3c 빌드(결정 166 O2, A단계 S0·S1). RC3에 teacher 정리만 적용한다. 모델 호출 없음. pilot_006 파일은 읽기만 한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/build/build7c.py   # -> pilot_007/build/RC3c/, pilot_007/teacher_cleanup.json

1. TEACH 원 trace 전부(``training/generated/pilot_006/teacher_v3/traces.jsonl``, 1,960)에 (a)–(e)·(ii)(``teacher/teacher_checks7.check_all``)를 적용해 요약한다.
2. RC3 두 arm의 teacher 레코드(``full_response``)를 ``trace_id``로 원 trace에 이어, keep이 아니면 레코드를 뺀다(문장 편집 없음, 다른 trace로 채우지 않음).
   8b 자체 레코드(``json_only``)·유형 상한·길이·겹침 규칙은 RC3 그대로(RC3에서 고른 레코드를 그대로 씀).
3. teacher가 모두 빠진 질문은 그 arm의 8b 레코드가 있으면 그것으로 남는다. 한 arm이라도 레코드가 0이 되면 두 arm 모두에서 뺀다(두 arm 질문 목록 같음).
4. 레코드 순서는 RC3 순서를 유지한다(빠진 것만 없앰). manifest는 RC3 manifest에서 개수·질문·출처·해시만 새로 쓴다.
보고: 빠진 trace(이유별), teacher가 없어진 질문(8b로 남음/학습에서 빠짐), 약점 부분집합 커버리지(teacher 질문 수, 레코드 있는 질문 수) 전후.
약점 부분집합 = ``coverage_h4.subsets`` + "소속"(질문에 "소속") + 장소 이름 조회(결정 140 family ``k3_scope_name_family``).
"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (ROOT, HERE.parent / "teacher", ROOT / "sft_dpo_inventory/pilot_006_prep/analysis"):
    sys.path.insert(0, str(p))
RC3 = ROOT / "sft_dpo_inventory/pilot_006/build/RC3"
OUT = HERE / "RC3c"
TRACES = ROOT / "training/generated/pilot_006/teacher_v3/traces.jsonl"
TARGETS = ROOT / "sft_dpo_inventory/pilot_006/teacher/teach3_targets.json"
CORPUS = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl"
HALF_WATCH = ("implicit_endpoint", "scope_name_family", "소속")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import coverage_h4 as H4
    from teacher_checks7 import check_all
    targets = {t["id"]: t for t in json.loads(TARGETS.read_text(encoding="utf-8"))}
    traces = [json.loads(l) for l in TRACES.read_text(encoding="utf-8").splitlines()]
    checks = {}
    for t in traces:
        checks[t["trace_id"]] = check_all(t["thinking"], t["content"], targets[t["id"]]["semantics"])
    all_summary = {"traces": len(traces), "originally_pass(a,b,c)": sum(t["pass"] for t in traces),
                   "fail_by_check": dict(Counter(r for c in checks.values() for r in c["reasons"])),
                   "keep": sum(c["keep"] for c in checks.values())}
    corpus = {json.loads(l)["id"]: json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines()}
    qinfo = {q["id"]: q for q in json.loads((RC3 / "questions.json").read_text(encoding="utf-8"))}
    arms = {}
    for arm in ("full", "partial"):
        arms[arm] = [json.loads(l) for l in (RC3 / arm / "sft_train.jsonl").read_text(encoding="utf-8").splitlines()]
    dropped_records = {}
    kept = {}
    for arm, recs in arms.items():
        k, d = [], Counter()
        for r in recs:
            m = r["metadata"]
            if m["loss_scope"] == "full_response":
                c = checks.get(m["trace_id"])
                if c is None:
                    raise SystemExit(f"trace not found: {m['trace_id']}")
                if not c["keep"]:
                    d[",".join(c["reasons"])] += 1
                    continue
            k.append(r)
        kept[arm] = k
        dropped_records[arm] = {"teacher_records_before": sum(r["metadata"]["loss_scope"] == "full_response" for r in recs),
                                "teacher_records_dropped": sum(d.values()), "by_reasons": dict(d.most_common())}
    count = {arm: Counter(r["metadata"]["source_record_id"] for r in recs) for arm, recs in kept.items()}
    before_q = {arm: set(r["metadata"]["source_record_id"] for r in recs) for arm, recs in arms.items()}
    both = before_q["full"] & before_q["partial"]
    lost_q = sorted(q for q in both if count["full"][q] == 0 or count["partial"][q] == 0)
    final = {arm: [r for r in kept[arm] if r["metadata"]["source_record_id"] not in lost_q] for arm in kept}
    qset = sorted(set(r["metadata"]["source_record_id"] for r in final["full"]))
    assert qset == sorted(set(r["metadata"]["source_record_id"] for r in final["partial"]))

    def teacher_q(recs):
        return set(r["metadata"]["source_record_id"] for r in recs if r["metadata"]["loss_scope"] == "full_response")

    def subs(q):
        c = corpus.get(q)
        s = set(H4.subsets(c)) if c else set()
        if c and "소속" in c["question"]:
            s.add("소속")
        if (qinfo.get(q) or {}).get("k3_scope_name_family"):
            s.add("scope_name_family")
        return s

    tq_before = {arm: teacher_q(arms[arm]) for arm in arms}
    tq_after = {arm: teacher_q(final[arm]) for arm in final}
    teacher_lost = {arm: sorted(tq_before[arm] - tq_after[arm]) for arm in arms}
    cov = {}
    names = sorted(set().union(*(subs(q) for q in before_q["full"])))
    for name in names:
        row = {}
        for arm in ("full", "partial"):
            row[arm] = {"questions_before": sum(name in subs(q) for q in before_q[arm]), "questions_after": sum(name in subs(q) for q in qset),
                        "teacher_q_before": sum(name in subs(q) for q in tq_before[arm]), "teacher_q_after": sum(name in subs(q) for q in tq_after[arm])}
        tb, ta = row["partial"]["teacher_q_before"], row["partial"]["teacher_q_after"]
        row["teacher_q_lost_share(partial)"] = round((tb - ta) / tb, 3) if tb else None
        cov[name] = row
    watch = {n: cov[n]["teacher_q_lost_share(partial)"] for n in HALF_WATCH if n in cov}
    OUT.mkdir(parents=True, exist_ok=True)
    built = {}
    for arm in ("full", "partial"):
        d = OUT / arm
        d.mkdir(exist_ok=True)
        with (d / "sft_train.jsonl").open("w", encoding="utf-8") as f:
            for r in final[arm]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
        man = json.loads((RC3 / arm / "manifest.json").read_text(encoding="utf-8"))
        s = man["sft"]
        s.update(generated_at=datetime.now(timezone.utc).isoformat(), release_candidate="RC3c",
                 note=f"pilot_007 RC3c = RC3({arm}) + teacher 정리(결정 166: (a)–(e)·(ii) 불통과 teacher 레코드 제외, 문장 편집 없음). build7c.py",
                 train_count=len(final[arm]), validation_count=0, questions=len(qset),
                 question_list_sha256=hashlib.sha256("\n".join(qset).encode()).hexdigest(),
                 by_source=dict(Counter(r["metadata"]["loss_scope"] for r in final[arm])),
                 output_hashes={"sft_train.jsonl": sha(d / "sft_train.jsonl"), "sft_valid.jsonl": sha(d / "sft_valid.jsonl")})
        (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        built[arm] = {"records": len(final[arm]), "by_source": s["by_source"], "sft_train_sha256": s["output_hashes"]["sft_train.jsonl"]}
    (OUT / "questions.json").write_text(json.dumps([{"id": q, "records": {a: count[a][q] for a in count},
                                                      "teacher_records": {a: sum(1 for r in final[a] if r["metadata"]["source_record_id"] == q and r["metadata"]["loss_scope"] == "full_response") for a in final}}
                                                     for q in qset], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    report = {"decision": "166 (O2)", "rule": "teacher_checks7.check_all: (a)(b)(c) pilot_006 + (d) 한글 비율 ≥ 0.5 + (e) 영어 노출·메타 + (ii) 없음 → keep",
              "all_teach_traces": all_summary,
              "rc3_teacher_records": dropped_records,
              "questions": {"rc3": len(both), "rc3c": len(qset), "dropped_from_training": lost_q,
                            "teacher_lost_but_kept_by_8b": {a: [q for q in teacher_lost[a] if q not in lost_q] for a in teacher_lost},
                            "teacher_lost_count": {a: len(v) for a, v in teacher_lost.items()}},
              "weak_subset_coverage": cov, "watch_teacher_lost_share(stop rule: report if > 0.5)": watch,
              "report_needed": any(v is not None and v > 0.5 for v in watch.values()), "built": built}
    (HERE.parent / "teacher_cleanup.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (OUT / "build_summary.json").write_text(json.dumps({"label": "RC3c", "source": "RC3", "built": built, "questions": len(qset),
                                                        "question_list_sha256": hashlib.sha256("\n".join(qset).encode()).hexdigest(),
                                                        "dropped_questions": lost_q}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("all_teach_traces", "rc3_teacher_records", "built", "watch_teacher_lost_share(stop rule: report if > 0.5)", "report_needed")}, ensure_ascii=False, indent=1))
    print("questions", len(both), "->", len(qset), "dropped", lost_q, "teacher lost", {a: len(v) for a, v in teacher_lost.items()})


if __name__ == "__main__":
    main()
