# -*- coding: utf-8 -*-
"""batch010 결정 1단계(결정 175 P1): 받아들일 목록을 만들고 원본 검토 시트와 대조한다. 기록하지 않는다. 모델 호출 없음.
``pilot_006_prep/review/p1/p1_plan.py``와 같은 방식.

    python3 sft_dpo_inventory/pilot_007/review/b010/b010_plan.py   # -> b010_accept_list.json, b010_accept_list.md

- 결정 파일 ``batch010/review/batch010_review_decisions_v1.xlsx`` sha256 = ``23487fcf…``, 원본 ``batch010_review_v1.xlsx`` sha256 = ``4845cbee…``.
- 결정 파일 ``batch010`` 시트 50행은 원본과 id·질문·초안 grounding·근거·신호·결정 120 분류 열이 같아야 한다(원본 열 이름 "Claude 2차 검토 권고"는 결정 파일에서
  "작성자(Claude Code) 의견"으로 바뀌었다 — 값이 같아야 함).
- 결정: "결정(승인/수정/보류/제외)" 칸 그대로(P1: 승인 48, 수정 2). 수정은 "수정 grounding(JSON)" 칸. 검토자 칸 = "사용자(이름 기록 안 함)".
- 작성자 의견 "수정(측정 span)" 7건은 측정 text를 비운 채 승인으로 받아들인다(결정 175) — 결정 칸이 승인이어야 함.
- 하나라도 어긋나면 exit 2.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INV = HERE.parents[2]
sys.path.insert(0, str(INV / "batch004"))
from sheet_to_commands import read_sheets  # noqa: E402

FD = INV / "batch010/review/batch010_review_decisions_v1.xlsx"
F1 = INV / "batch010/review/batch010_review_v1.xlsx"
SHAD, SHA1 = "23487fcfe80bbd4f2e8cb2ebee2d37ea38e5ba722649ae83382756bfbe4c27af", "4845cbee"
SHARED = ("id", "우선순위", "약점", "질문", "초안 grounding", "근거", "J-b010 첫 응답", "J-b010 Full 일치(9개 중)", "J-b010 Partial 일치(9개 중)", "결정 120 분류")
DEC = "결정(승인/수정/보류/제외)"
SPAN7 = ["b010-21", "b010-23", "b010-24", "b010-26", "b010-27", "b010-28", "b010-30"]


def main():
    if hashlib.sha256(FD.read_bytes()).hexdigest() != SHAD or not hashlib.sha256(F1.read_bytes()).hexdigest().startswith(SHA1):
        print("sha256 mismatch", file=sys.stderr)
        raise SystemExit(2)
    d = {r["id"]: r for r in read_sheets(FD)["batch010"]}
    o = {r["id"]: r for r in read_sheets(F1)["batch010"]}
    problems = []
    if set(d) != set(o) or len(d) != 50:
        problems.append(f"id sets differ: {len(d)} vs {len(o)}")
    rows = []
    for i in sorted(o):
        a, b = d.get(i, {}), o[i]
        for k in SHARED:
            if str(a.get(k) or "") != str(b.get(k) or ""):
                problems.append(f"{i}: column {k} differs")
        if str(a.get("작성자(Claude Code) 의견") or "") != str(b.get("Claude 2차 검토 권고") or ""):
            problems.append(f"{i}: 작성자 의견 differs from original recommendation")
        dec = a.get(DEC)
        if dec not in ("승인", "수정"):
            problems.append(f"{i}: decision {dec!r} not in 승인/수정")
        if a.get("검토자") != "사용자(이름 기록 안 함)":
            problems.append(f"{i}: reviewer {a.get('검토자')!r}")
        corrected = None
        if dec == "수정":
            try:
                corrected = json.loads(a.get("수정 grounding(JSON)") or "")
            except ValueError:
                problems.append(f"{i}: 수정 grounding not JSON")
        if i in SPAN7 and dec != "승인":
            problems.append(f"{i}: measure-span item must be 승인 (결정 175)")
        rows.append({"id": i, "gap": b["약점"], "question": b["질문"], "decision": {"승인": "approve", "수정": "modify"}.get(dec, dec),
                     "corrected_grounding": corrected, "measure_text_empty": i in SPAN7, "second_review": a.get("2차 검토 권고"),
                     "second_review_reason": a.get("2차 검토 근거"), "memo": a.get("메모"), "review_date": a.get("검토일")})
    out = {"decision": "175 (P1)", "decision_file": {"path": str(FD.relative_to(INV.parent)), "sha256": SHAD}, "original_sheet_sha256_prefix": SHA1,
           "counts": dict(Counter(r["decision"] for r in rows)), "measure_text_empty_approved": SPAN7, "rows": rows, "problems": problems}
    (HERE / "b010_accept_list.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md = ["# batch010 받아들일 목록(결정 175 P1, 기록 전)", "", f"결정 파일 sha256 `{SHAD}`, 원본 `{SHA1}…`. 수: {dict(Counter(r['decision'] for r in rows))}.", "",
          "| id | 약점 | 결정 | 메모 |", "|---|---|---|---|"]
    md += [f"| {r['id']} | {r['gap']} | {r['decision']}{' (측정 text 비움)' if r['measure_text_empty'] else ''} | {r['memo'] or ''} |" for r in rows]
    (HERE / "b010_accept_list.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"counts": out["counts"], "problems": problems}, ensure_ascii=False))
    raise SystemExit(2 if problems else 0)


if __name__ == "__main__":
    main()
