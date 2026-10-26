# -*- coding: utf-8 -*-
"""pilot_009 S1(결정 235 Z3): teacher trace 거르기 — 지시문 절 이름 인용. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_009/build/teacher_filter9.py   # -> build/teacher_filter9.json, build/teacher_filter9_rule.json

규칙(결과 전에 고정, 테스트 ``tests/test_teacher_filter9.py``):
1. 절 이름 = teacher 지시 파일에서 한 줄 전체가 ``[이름]``인 줄의 이름(거부: ``teacher_refusal_v1.md``, r2: ``teacher_neutral_v3b.md``).
2. 허용 = 그 이름(괄호 뺀 글자)이 학생 모델 system prompt(Full, 87048d0c)에 같은 문구로 있는 것. 학생도 그 문구를 본다.
3. 금지 = 나머지. trace의 생각(c2 정리 뒤)에 금지 이름의 글자가 하나라도 있으면(괄호 유무 무관) **그 trace를 통째로 뺀다**.
4. 보완: 빼고 나서 쓸 trace가 0인 질문만, TEACH-R 통과 trace에서 금지 이름이 든 줄을 줄 단위로 지운다(결정 185 c2 방식: 다른 줄은 바이트 그대로,
   내용 손실 = 지운 줄 ≥ 4 또는 판단 줄(``c2_edit.FIELD``)을 지움). 지운 뒤 같은 검사(거부: ``teacher_refusal9.checks_refusal``, r2: ``checks_v3b``)를 다시 하고
   통과·손실 없음이면 쓴다. 지운 줄을 기록한다.
5. 질문을 고친 문항(b012-001·021·039, 결정 233)의 TEACH-R trace는 원래 질문 문장을 인용하므로 쓰지 않는다.
"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_009/teacher", ROOT / "sft_dpo_inventory/pilot_007/teacher", ROOT / "sft_dpo_inventory/pilot_006/teacher",
          ROOT / "sft_dpo_inventory/pilot_006/post"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
PROMPTS = {"refusal_v1": ROOT / "grounding/prompts/teacher_refusal_v1.md", "v3b": ROOT / "grounding/prompts/teacher_neutral_v3b.md"}
TRACES = ROOT / "training/generated/pilot_009/teacher_teachr/traces.jsonl"
MODIFIED = frozenset({"b012:b012-001", "b012:b012-021", "b012:b012-039"})
SECTION = re.compile(r"^\[([^\]\n]+)\]\s*$")


def section_names(text):
    return [m.group(1).strip() for m in (SECTION.match(l) for l in text.splitlines()) if m]


def rule(student_prompt, prompts=None):
    """→ {variant: {"names": [...], "allowed": [...], "forbidden": [...]}}"""
    out = {}
    for v, p in (prompts or PROMPTS).items():
        names = section_names(Path(p).read_text(encoding="utf-8") if isinstance(p, Path) else p)
        out[v] = {"names": names, "allowed": [n for n in names if n in student_prompt], "forbidden": [n for n in names if n not in student_prompt]}
    return out


def cites(thinking, forbidden):
    return sorted({n for n in forbidden if n in (thinking or "")})


def strip_lines(thinking, forbidden):
    """금지 이름이 든 줄만 지운다 → (새 thinking, 지운 줄, 내용 손실)."""
    import c2_edit as C2
    keep, gone = [], []
    for ln in thinking.splitlines(keepends=True):
        (gone if any(n in ln for n in forbidden) else keep).append(ln)
    lost = len(gone) >= 4 or any(C2.FIELD.search(g) for g in gone)
    return "".join(keep), [g.rstrip("\n") for g in gone], lost


def main():
    import teacher_refusal9 as TR
    from training.trainer_common import expected_system_prompt
    student = expected_system_prompt("full")
    R = rule(student)
    targets = {t["id"]: t for t in json.loads((ROOT / "sft_dpo_inventory/pilot_009/teacher/teachr_targets.json").read_text(encoding="utf-8"))}
    rows = [json.loads(l) for l in TRACES.read_text(encoding="utf-8").splitlines() if l.strip()]
    usable, per_q, stats = defaultdict(list), {}, Counter()
    passed = defaultdict(list)
    for r in rows:
        t = targets[r["id"]]
        ev = TR.evaluate(t, r["thinking"], r["content"])
        if str(ev["pass"]) != str(r["pass"]):
            raise SystemExit(f"pass mismatch {r['trace_id']}")
        if not ev["pass"]:
            continue
        stats[f"{t['variant']}:pass"] += 1
        if r["id"] in MODIFIED:
            stats[f"{t['variant']}:modified_question_skipped"] += 1
            continue
        th = ev["thinking_after_c2"]
        hit = cites(th, R[t["variant"]]["forbidden"])
        passed[r["id"]].append((r, ev, hit))
        if hit:
            stats[f"{t['variant']}:excluded_citation"] += 1
            continue
        usable[r["id"]].append({"trace_id": r["trace_id"], "thinking": th, "edit": "none", "c2_removed": ev["c2"]["removed_lines"]})
    supplemented = {}
    for qid, lst in passed.items():
        if usable[qid]:
            continue
        t = targets[qid]
        for r, ev, hit in lst:
            new, gone, lost = strip_lines(ev["thinking_after_c2"], R[t["variant"]]["forbidden"])
            chk = TR.checks_refusal(new, r["content"]) if t["variant"] == "refusal_v1" else TR.checks_v3b(new, r["content"], t["semantics"])
            ok = chk["pass"] and not lost and not cites(new, R[t["variant"]]["forbidden"])
            supplemented.setdefault(qid, []).append({"trace_id": r["trace_id"], "removed_lines": gone, "content_lost": lost, "checks_after": chk.get("reasons"), "usable": ok})
            if ok:
                usable[qid].append({"trace_id": r["trace_id"], "thinking": new, "edit": "section_line_strip", "c2_removed": ev["c2"]["removed_lines"],
                                    "section_removed": gone})
    for qid, t in sorted(targets.items()):
        n_pass = len(passed.get(qid, [])) if qid not in MODIFIED else 0
        per_q[qid] = {"variant": t["variant"], "gap": t.get("gap"), "passed": sum(1 for r in rows if r["id"] == qid and str(r["pass"]) == "True"),
                      "citation_excluded": sum(1 for _, _, h in passed.get(qid, []) if h), "usable": len(usable.get(qid, [])),
                      "supplemented": qid in supplemented, "modified_question": qid in MODIFIED}
    out = {"rule": R, "traces_sha256": hashlib.sha256(TRACES.read_bytes()).hexdigest(), "stats": dict(stats),
           "questions_usable_by_count": {v: dict(sorted(Counter(min(4, q["usable"]) for q in per_q.values() if q["variant"] == v and not q["modified_question"]).items()))
                                         for v in ("refusal_v1", "v3b")},
           "questions_zero_usable": sorted(q for q, v in per_q.items() if v["usable"] == 0), "supplemented": supplemented, "per_question": per_q,
           "usable": {q: v for q, v in sorted(usable.items())}}
    (HERE / "teacher_filter9.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("rule", "stats", "questions_usable_by_count", "questions_zero_usable")}, ensure_ascii=False, indent=1))
    print("supplemented:", {q: [(s["trace_id"].split(":")[-1], s["usable"], len(s["removed_lines"])) for s in v] for q, v in supplemented.items()})


if __name__ == "__main__":
    main()
