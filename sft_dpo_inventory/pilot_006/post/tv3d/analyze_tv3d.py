# -*- coding: utf-8 -*-
"""T-v3d 분석(판정 아님). 검사 (a)(b)(c) 통과율, A2 유형 (i)–(iv) 비율, v3c(T0c)와 나란히, 읽기용 통과 trace 10개(결정적 선택).

    hfvenv/bin/python analyze_tv3d.py --main /home/hwkim/assistant_univ   # -> post/tv3d/tv3d_analysis.json, tv3d_read_sample.json

- 읽기 표본: 통과 trace를 질문 순번 → 표본 번호로 정렬하고, 질문마다 첫 통과 하나씩 앞에서부터 10개(질문이 10개 미만이면 남은 자리를 다음 통과로).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))


def rates(rows, typed):
    n = len(rows) or 1
    c = Counter(x for r in rows for x in typed(r))
    return {"traces": len(rows), "pass": sum(r["pass"] for r in rows), "pass_pct": round(100 * sum(r["pass"] for r in rows) / n, 1),
            "a_pct": round(100 * sum(r["check_a"]["pass"] for r in rows) / n, 1), "b_pct": round(100 * sum(r["check_b"]["pass"] for r in rows) / n, 1),
            "c_exposed_pct": round(100 * sum(r["check_c"]["exposed"] for r in rows) / n, 1),
            "a2_any_pct": round(100 * sum(bool(typed(r)) for r in rows) / n, 1), "a2_types_pct": {x: round(100 * c[x] / n, 1) for x in ("i", "ii", "iii", "iv")},
            "exposure_words": dict(Counter(w for r in rows for w in r["check_c"]["found"]).most_common(12)),
            "eval_tokens_median": sorted(r.get("eval_count") or 0 for r in rows)[len(rows) // 2] if rows else None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    a = p.parse_args()
    m = Path(a.main)
    from itemdata import concl_types
    v3d = [json.loads(l) for l in (m / "training/generated/pilot_006/teacher_tv3d/traces.jsonl").read_text(encoding="utf-8").splitlines()]
    v3c = [json.loads(l) for l in (m / "training/generated/pilot_006/teacher_t0v3c/traces.jsonl").read_text(encoding="utf-8").splitlines()]
    out = {"note": "판정 아님(결정 164). v3c는 T0c(0.40.3, 다른 20문항)라 직접 비교가 아니라 참고.",
           "v3d": rates(v3d, lambda r: r["a2_types"]), "v3c_T0c_reference": rates(v3c, lambda r: sorted(concl_types(r["thinking"])))}
    seen, pick = set(), []
    passed = sorted((r for r in v3d if r["pass"]), key=lambda r: (r["question_index"], r["sample_index"]))
    for r in passed:
        if r["id"] not in seen and len(pick) < 10:
            pick.append(r)
            seen.add(r["id"])
    for r in passed:
        if len(pick) < 10 and r not in pick:
            pick.append(r)
    out["read_sample"] = [r["trace_id"] for r in pick]
    (HERE / "tv3d_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "tv3d_read_sample.json").write_text(json.dumps([{k: r[k] for k in ("trace_id", "id", "thinking", "content", "a2_types")} for r in pick],
                                                         ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "read_sample"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
