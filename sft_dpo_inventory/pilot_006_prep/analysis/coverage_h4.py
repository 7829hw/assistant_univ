# -*- coding: utf-8 -*-
"""H4: 약점 부분집합별 학습 재료 집계. 모델 호출 없음. 판정 파일이 늘면 다시 돌린다.

    hfvenv/bin/python coverage_h4.py   # -> coverage_h4.json, coverage_h4.md

- 대상: 승인 corpus 전체(R0: trunk 131, pg 154, aug300 train 승인, batch007 27, batch008 10; 같은 정규화 질문은 하나로, trunk 우선). batch009는 후보로 따로 센다.
- 부분집합(승인 semantics에서, 질문 표현이 필요한 것만 질문 문장 규칙):
  dt(dimension_target 있음), od≠dt(장소 od_role이 있고 그 집합이 {dimension_target}과 다름), implicit endpoint(od_role 또는 dt가 있고 질문에
  "승차·하차·출발·도착"이 없고 "태운·태워·탄·내린·내려·오른" 같은 동사가 있음), value 없는 장소(측정값이 장소 이름), 실차(trip_count 또는 운행 상태 occupied),
  scope 역조회(scope 노드가 있고 측정값이 장소 이름), vicinity, bucket(기간 단위)·dimension(묶음 단위)과 둘의 대조(bucket 또는 dimension).
- 항목: 질문 수, arm별 8b 자체 정답 표본이 있는 질문 수(승인 gold 판정 ``self_samples/r1/*_approved.json`` 전부), teacher 통과 trace가 있는 질문 수
  (TEACH, 없으면 0), 두 arm 모두 재료(teacher 또는 8b 정답)가 있는 질문 수.
- 최소 질문 수 제안: 30(두 arm 모두 재료가 있는 질문 기준). 모자란 부분집합을 목록으로.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREP = ROOT / "sft_dpo_inventory/pilot_006_prep"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PREP / "self_samples"))
MIN_Q = 30
EXPLICIT = re.compile(r"승차|하차|출발|도착")
VERB = re.compile(r"태운|태워|태우|탄 |탄곳|내린|내려|오른|올라")


def subsets(rec):
    from grounding.canonical import view
    s = rec["semantics"]
    f = s.get("factors") or {}
    v = view(s)
    m = (v.get("measure") or {}).get("subtype")
    roles = {(n.get("attributes") or {}).get("od_role") for n in s["nodes"] if n.get("subtype") in ("place", "scope")} - {None}
    dt = f.get("dimension_target")
    q = rec["question"]
    out = {"dt": bool(dt), "od_ne_dt": bool(dt and roles and roles != {dt}),
           "implicit_endpoint": bool((roles or dt) and not EXPLICIT.search(q) and VERB.search(q)),
           "valueless_place": m in ("place", "scope"), "silcha": m == "trip_count" or f.get("taxi_status") == "occupied",
           "scope_reverse": m in ("place", "scope") and any(n.get("subtype") == "scope" for n in s["nodes"]),
           "vicinity": bool(f.get("vicinity")), "bucket": bool(f.get("bucket")), "dimension": bool(f.get("dimension")),
           "bucket_or_dimension": bool(f.get("bucket") or f.get("dimension"))}
    return [k for k, x in out.items() if x]


def main():
    import approved6 as AP
    from training.data.split import question_key
    corpus = AP.load()
    order = {"trunk": 0, "pg": 1, "aug300": 2, "batch007": 3, "batch008": 4, "batch009": 5}
    by_key, alias, qs = {}, {}, {}
    for cid, rec in sorted(corpus.items(), key=lambda kv: (order[kv[1]["corpus_group"]], kv[0])):
        k = question_key(rec["question"])
        if k in by_key:
            alias[cid] = by_key[k]
            continue
        by_key[k] = cid
        qs[cid] = rec
    correct = {"full": set(), "partial": set()}
    used = []
    for f in sorted(x for x in (PREP / "self_samples/r1").glob("*_approved.json") if "first" not in x.name):
        d = json.loads(f.read_text(encoding="utf-8"))
        used.append(f.name)
        for q in d["per_question"]:
            if q["status"] == "approved" and q["correct"] > 0:
                correct[d["arm"]].add(alias.get(q["id"], q["id"]))
    teacher = set()
    teach = ROOT / "training/generated/pilot_006/teacher_v2/traces.jsonl"
    if teach.exists():
        for line in teach.read_text(encoding="utf-8").splitlines():
            t = json.loads(line)
            if t.get("pass"):
                teacher.add(alias.get(t["id"], t["id"]))
    table = defaultdict(Counter)
    lacking = defaultdict(list)
    for cid, rec in qs.items():
        for s in subsets(rec):
            t = table[s]
            t["questions"] += 1
            t["full_self_correct"] += cid in correct["full"]
            t["partial_self_correct"] += cid in correct["partial"]
            t["teacher_pass"] += cid in teacher
            both = (cid in teacher) or (cid in correct["full"] and cid in correct["partial"])
            t["both_arms_material"] += both
            if not both:
                lacking[s].append(cid)
    b9 = json.loads((ROOT / "sft_dpo_inventory/batch009/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    b9_sub = Counter()
    for c in b9:
        from grounding.canonical import semantics_from_full
        for s in subsets({"semantics": semantics_from_full(c["draft_grounding"]), "question": c["question"]}):
            b9_sub[s] += 1
    short = {s: {"both_arms_material": t["both_arms_material"], "need": MIN_Q - t["both_arms_material"], "batch009_candidates": b9_sub.get(s, 0)}
             for s, t in table.items() if t["both_arms_material"] < MIN_Q}
    for s in ("valueless_place", "scope_reverse", "implicit_endpoint", "od_ne_dt"):
        if s not in table:
            short[s] = {"both_arms_material": 0, "need": MIN_Q, "batch009_candidates": b9_sub.get(s, 0)}
    out = {"questions_after_merge": len(qs), "judge_files": used, "teacher_traces": teach.exists(), "min_questions_proposed": MIN_Q,
           "subsets": {s: dict(t) for s, t in sorted(table.items())}, "batch009_candidates_by_subset": dict(b9_sub), "shortfall": short,
           "lacking_ids": {s: sorted(v) for s, v in lacking.items()}}
    (HERE / "coverage_h4.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    lines = [f"# H4 약점별 학습 재료(승인 corpus {len(qs)}질문, 판정 {len(used)}개 파일, TEACH {'있음' if teach.exists() else '없음'})", "",
             "| 부분집합 | 질문 | Full 8b 정답 | Partial 8b 정답 | teacher 통과 | 두 arm 재료 | batch009 후보 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for s, t in sorted(table.items()):
        lines.append(f"| {s} | {t['questions']} | {t['full_self_correct']} | {t['partial_self_correct']} | {t['teacher_pass']} | {t['both_arms_material']} | {b9_sub.get(s, 0)} |")
    lines += ["", f"최소 제안 {MIN_Q}질문(두 arm 재료 기준). 모자란 곳: " + ", ".join(f"{s} {v['both_arms_material']}(−{v['need']})" for s, v in short.items())]
    (HERE / "coverage_h4.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
