# -*- coding: utf-8 -*-
"""R0 1단계(결정 130 G0): 검토 결정 파일을 원본 검토 시트와 대조하고, 받아들일 목록 전체를 표로 만든다. 모델 호출 없음. 아무것도 기록하지 않는다.

    python3 sft_dpo_inventory/pilot_006_prep/review/r0/r0_plan.py   # -> r0_accept_list.json, r0_accept_list.md

- 결정 파일 sha256 = ``405a217f…``(지시 0절 3)이어야 한다. "요약" 시트의 원본 경로·sha256이 저장소 파일과 같아야 한다.
- 행마다: 원본 시트에 같은 id가 있고, 두 파일에 함께 있는 초안 열(질문, 정답 호출, semantics 요약, 초안 grounding, gold, 수정 전·후 질문 등)이 글자까지 같아야 한다.
  결정 열(``결정(승인/수정/보류/제외)``)·수정 칸·메모·검토자·검토일·Claude 권고 열은 결정 파일에서 새로 채운 칸이라 대조하지 않는다.
- 하나라도 어긋나면 exit 2(지시 5절: 전체를 멈춘다).
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

DECISION_FILE = INV / "pilot_006_prep/review/pilot006_review_decisions_v1.xlsx"
DECISION_SHA = "405a217fcb97710ce5bd5815aaaaaa497fe42e12014472c2cb46b386a915540a"
SHEETS = {"aug300": "aug300", "batch007": "batch007", "batch008": "batch008", "pg_edit_required": "edit_required"}
NEW_COLS = {"결정(승인/수정/보류/제외)", "수정 grounding(JSON)", "수정 질문", "메모", "검토자", "검토일", "Claude 2차 검토 권고", "Claude 근거", "Claude 수정안"}
DECISION_MAP = {"승인": "approve", "수정": "modify", "제외": "exclude", "보류": "hold"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def table(sheet):
    rows = sheet["rows"]
    head = [str(c) if c is not None else "" for c in rows[0]]
    return head, [dict(zip(head, r)) for r in rows[1:] if r and r[0] not in (None, "")]


def main():
    problems = []
    if sha(DECISION_FILE) != DECISION_SHA:
        print("decision file sha256 mismatch", file=sys.stderr)
        raise SystemExit(2)
    wb = read_workbook(DECISION_FILE)
    _, summary = table(wb["요약"])
    originals = {}
    for row in summary:
        group = row["묶음"]
        if group not in SHEETS:
            continue
        path, digest = INV / row["원본 시트(저장소)"], row["원본 sha256"]
        if sha(path) != digest:
            problems.append({"group": group, "problem": "original sheet sha256 mismatch", "path": str(path.relative_to(INV))})
        originals[group] = {"path": str(path.relative_to(INV)), "sha256": digest, "summary": {k: row[k] for k in ("승인", "수정", "제외", "해당 없음", "합계")}}
    out = {"decision_file": {"path": str(DECISION_FILE.relative_to(INV)), "sha256": DECISION_SHA}, "originals": originals, "groups": {}, "rows": []}
    for group, osheet in SHEETS.items():
        dhead, drows = table(wb[group])
        ohead, orows = table(read_workbook(INV / originals[group]["path"])[osheet])
        omap = {r["id"]: r for r in orows}
        shared = [c for c in dhead if c in ohead and c not in NEW_COLS]
        if len(drows) != len(orows):
            problems.append({"group": group, "problem": f"row count {len(drows)} != original {len(orows)}"})
        counts = Counter()
        for r in drows:
            rid = r["id"]
            o = omap.get(rid)
            if o is None:
                problems.append({"group": group, "id": rid, "problem": "id not in original sheet"})
                continue
            diff = [c for c in shared if (r.get(c) or "") != (o.get(c) or "")]
            if diff:
                problems.append({"group": group, "id": rid, "problem": "draft columns differ", "columns": diff})
            raw = (r.get("결정(승인/수정/보류/제외)") or "").strip()
            excluded_e4 = group == "aug300" and "제외" in str(r.get("상태(결정 119)") or "") and raw in ("", "해당 없음")
            decision = "not_applicable(decision 119)" if excluded_e4 else DECISION_MAP.get(raw, f"unknown:{raw}")
            if decision.startswith("unknown"):
                problems.append({"group": group, "id": rid, "problem": f"unknown decision {raw!r}"})
            counts[decision] += 1
            kind = None
            if decision == "modify":
                kind = "grounding" if (r.get("수정 grounding(JSON)") or "").strip() else ("question" if (r.get("수정 질문") or "").strip() else "missing")
                if kind == "missing":
                    problems.append({"group": group, "id": rid, "problem": "modify without corrected grounding or question"})
            out["rows"].append({"group": group, "id": rid, "decision": decision, "modify_kind": kind,
                                "status_e4": r.get("상태(결정 119)") if group == "aug300" else None,
                                "corrected_grounding": r.get("수정 grounding(JSON)") or None, "corrected_question": r.get("수정 질문") or None,
                                "reviewer": r.get("검토자"), "reviewed_on": r.get("검토일"), "memo": r.get("메모")})
        out["groups"][group] = {"rows": len(drows), "shared_draft_columns_checked": shared, "decisions": dict(counts)}
    out["totals"] = dict(Counter(r["decision"] for r in out["rows"]))
    out["problems"] = problems
    (HERE / "r0_accept_list.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    lines = ["# R0 받아들일 목록(결정 130 G0, 기록 전 고정)", "", f"결정 파일 `{out['decision_file']['path']}` sha256 `{DECISION_SHA}`. 대조 문제 {len(problems)}건.", "",
             "| 묶음 | 행 | 승인 | 수정 | 제외 | 해당 없음(결정 119) |", "|---|---:|---:|---:|---:|---:|"]
    for g, v in out["groups"].items():
        d = v["decisions"]
        lines.append(f"| {g} | {v['rows']} | {d.get('approve', 0)} | {d.get('modify', 0)} | {d.get('exclude', 0)} | {d.get('not_applicable(decision 119)', 0)} |")
    lines += ["", "| 묶음 | id | 결정 | 수정 종류 | 결정 119 상태 |", "|---|---|---|---|---|"]
    for r in out["rows"]:
        lines.append(f"| {r['group']} | {r['id']} | {r['decision']} | {r['modify_kind'] or ''} | {r['status_e4'] or ''} |")
    (HERE / "r0_accept_list.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"groups": {g: v["decisions"] for g, v in out["groups"].items()}, "totals": out["totals"], "problems": problems[:20]}, ensure_ascii=False, indent=1))
    raise SystemExit(2 if problems else 0)


if __name__ == "__main__":
    main()
