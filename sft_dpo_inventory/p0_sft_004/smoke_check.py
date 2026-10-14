# -*- coding: utf-8 -*-
"""smoke hard-failure 판정(PLAN.md 7절, 결과 전 고정). 모델 호출 0.

hard failure(전체 평가를 시작하지 않음): 모델 파일 없음·행 수 18 아님(어댑터 load·생성 실패),
content 비어 있음 > 9/18, JSON parse 실패 > 9/18(malformed 대부분), UNPARSEABLE > 9/18.
thinking 비율은 모델 행동 결과라 hard failure가 아니다(기록만).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    out, fail = {}, []
    for m in ("base", "full154", "json154"):
        p = HERE / "smoke" / f"{m}.jsonl"
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()[1:] if x.strip()] if p.exists() else []
        s = {"n": len(rows), "thinking_emitted": sum(r["thinking_emitted"] for r in rows),
             "thinking_chars_median": sorted(r["thinking_chars"] for r in rows)[len(rows) // 2] if rows else None,
             "content_nonempty": sum(r["content_nonempty"] for r in rows), "json_parsed": sum(r["json_parsed"] for r in rows),
             "exact_train_recall": sum(r["category"] == "EXACT_OR_SEMANTIC_MATCH" for r in rows),
             "unparseable": sum(r["category"] == "UNPARSEABLE" for r in rows),
             "generated_tokens_median": sorted(r["generated_tokens"] for r in rows)[len(rows) // 2] if rows else None,
             "canonical_exact": sum(r["category"] == "EXACT_OR_SEMANTIC_MATCH" for r in rows if r["canonical"])}
        out[m] = s
        if s["n"] != 18 or s["content_nonempty"] < 9 or s["json_parsed"] < 9 or s["unparseable"] > 9:
            fail.append(m)
    doc = {"models": out, "hard_failure": fail, "pass": not fail}
    (HERE / "smoke" / "smoke_summary.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False))
    return 0 if not fail else 7


if __name__ == "__main__":
    sys.exit(main())
