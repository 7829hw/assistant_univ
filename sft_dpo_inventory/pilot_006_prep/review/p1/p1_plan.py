# -*- coding: utf-8 -*-
"""P1 1단계(결정 139–142): 받아들일 목록을 만들고 원본과 대조한다. 기록하지 않는다. 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_006_prep/review/p1/p1_plan.py   # -> p1_accept_list.json, p1_accept_list.md

- 2차 검토 파일 sha256 = ``86449a69…``. ``batch009`` 시트 43행은 원본 ``batch009_review_v1.xlsx``(``82c93c34…``)와 id·초안 열이 같아야 하고,
  ``w1_예외_9`` 시트 9행은 ``batch009/excluded.json``의 같은 id 초안(질문, 초안 grounding)과 같아야 한다.
- 결정: batch009 시트는 "2차 검토 권고"(K2), w1 시트는 "승인(예외 채택 시)" → 승인(K3), aug300 5건 복원(K4), aug300-348 원래 문구 승인(K5).
- 하나라도 어긋나면 exit 2.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
INV = HERE.parents[2]
sys.path.insert(0, str(INV / "pilot_006_prep/aug300"))
from xlsx_read import read_workbook  # noqa: E402

F2 = INV / "batch009/review/batch009_review_v2_2nd.xlsx"
F1 = INV / "batch009/review/batch009_review_v1.xlsx"
SHA2, SHA1 = "86449a69a3ddf6a9ccc7cbd86811a07d2d27f9c599b7fd4b079b1cc96dba97d6", "82c93c34"
SHARED = ("id", "우선순위", "약점", "질문", "초안 grounding", "근거", "J11 첫 응답", "J12 Full 일치(9개 중)", "J12 Partial 일치(9개 중)", "결정 120 분류")
K4 = ["aug300-366", "aug300-369", "aug300-389", "aug300-397", "aug300-398"]


def table(sheet):
    rows = sheet["rows"]
    head = [str(c or "") for c in rows[0]]
    return [dict(zip(head, r)) for r in rows[1:] if r and r[0]]


def main():
    problems = []
    if hashlib.sha256(F2.read_bytes()).hexdigest() != SHA2 or not hashlib.sha256(F1.read_bytes()).hexdigest().startswith(SHA1):
        print("sha256 mismatch", file=sys.stderr)
        raise SystemExit(2)
    w2, w1 = read_workbook(F2), read_workbook(F1)
    orig = {r["id"]: r for r in table(w1["batch009"])}
    excl = {r["id"]: r for r in json.loads((INV / "batch009/excluded.json").read_text(encoding="utf-8"))}
    rows = []
    for r in table(w2["batch009"]):
        o = orig.get(r["id"])
        if o is None:
            problems.append({"id": r["id"], "problem": "not in v1"})
            continue
        diff = [c for c in SHARED if (r.get(c) or "") != (o.get(c) or "")]
        if diff:
            problems.append({"id": r["id"], "problem": "draft differs", "cols": diff})
        rec = r["2차 검토 권고"]
        dec = {"승인": "approve", "수정": "modify", "제외": "exclude"}.get(rec)
        if dec is None:
            problems.append({"id": r["id"], "problem": f"unknown {rec}"})
        if dec == "modify" and not (r.get("2차 검토 수정안") or "").strip():
            problems.append({"id": r["id"], "problem": "modify without JSON"})
        rows.append({"group": "batch009", "id": r["id"], "decision": dec, "decision_source": "K2(139)", "corrected_grounding": r.get("2차 검토 수정안") or None,
                     "reason": r.get("2차 검토 근거")})
    if len(rows) != len(orig):
        problems.append({"problem": f"batch009 rows {len(rows)} != v1 {len(orig)}"})
    for r in table(w2["w1_예외_9"]):
        e = excl.get(r["id"])
        if e is None:
            problems.append({"id": r["id"], "problem": "not in excluded.json"})
            continue
        if r["질문"] != e["question"] or json.loads(r["초안 grounding"]) != e["draft_grounding"]:
            problems.append({"id": r["id"], "problem": "w1 draft differs from excluded.json"})
        if r["2차 검토 권고"] != "승인(예외 채택 시)":
            problems.append({"id": r["id"], "problem": f"unexpected {r['2차 검토 권고']}"})
        rows.append({"group": "batch009_w1", "id": r["id"], "decision": "approve", "decision_source": "K3(140) 결정 120 예외", "corrected_grounding": None,
                     "reason": r.get("2차 검토 근거")})
    for i in K4:
        rows.append({"group": "aug300", "id": i, "decision": "approve", "decision_source": "K4(141) 결정 130 제외를 뒤집음", "corrected_grounding": None,
                     "reason": "Partial 8b 0/5 확인 뒤 표현이 다양한 SCOPE_NAME 예가 필요"})
    rows.append({"group": "aug300", "id": "aug300-348", "decision": "approve", "decision_source": "K5(142) 질문 수정 철회, 원래 문구 승인",
                 "corrected_grounding": None, "reason": "새 문구는 aux_test_v1·valid98과 겹침, 원래 문구는 W6 통과"})
    out = {"files": {"2nd": {"path": str(F2.relative_to(INV)), "sha256": SHA2}, "v1": {"path": str(F1.relative_to(INV)), "sha256_prefix": SHA1}},
           "counts": {g: dict(Counter(r["decision"] for r in rows if r["group"] == g)) for g in ("batch009", "batch009_w1", "aug300")},
           "rows": rows, "problems": problems}
    (HERE / "p1_accept_list.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md = ["# P1 받아들일 목록(결정 139–142, 기록 전 고정)", "", f"대조 문제 {len(problems)}건. " + json.dumps(out["counts"], ensure_ascii=False), "",
          "| 묶음 | id | 결정 | 근거 결정 |", "|---|---|---|---|"] + [f"| {r['group']} | {r['id']} | {r['decision']} | {r['decision_source']} |" for r in rows]
    (HERE / "p1_accept_list.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"counts": out["counts"], "problems": problems}, ensure_ascii=False))
    raise SystemExit(2 if problems else 0)


if __name__ == "__main__":
    main()
