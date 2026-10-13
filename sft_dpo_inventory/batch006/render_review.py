# -*- coding: utf-8 -*-
"""batch006 검토 표를 AUGMENTATION_REVIEW.md 안의 표시 사이에 다시 쓴다(모델 호출 없음).

    python sft_dpo_inventory/batch006/render_review.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SFT = ROOT / "evaluation/partial_grounding/sft_p0"
BEGIN, END = "<!-- review-table:begin -->", "<!-- review-table:end -->"


def summary(p0):
    f = p0.get("factors") or {}
    if any(c.get("subtype") == "scope" for c in p0.get("concepts") or []):
        scope = [c["value"] for c in p0["concepts"] if c.get("subtype") == "scope"][0]
        return f"scope `{scope}` + 값 없는 답 place"
    places = [f"{c['value']['name']}:{(c.get('attributes') or {}).get('od_role', '-')}" for c in p0["concepts"]
              if c.get("subtype") == "place" and c.get("value")]
    parts = [f"장소 {', '.join(places) or '없음'}", f"dt={f.get('dimension_target')}", f"dim={f.get('dimension')}"]
    if f.get("order"):
        parts.append(f"{f['order']} {f.get('limit')}")
    parts.append(f"date={f.get('date')}")
    return ", ".join(parts)


def main():
    rows = [json.loads(line) for line in (SFT / "augmentation_candidates.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    lines = ["| id | gap | 대조쌍 | 질문 | P0 target 요약 | 자동 검사 | 비고 | 승인 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        status = {"auto_ok": "통과", "excluded_overlap": "제외(겹침)", "contract_fail": "계약 실패"}[r["status"]]
        note = []
        if r.get("mock_note"):
            note.append("mock 데이터 없음")
        if r["excluded_reasons"]:
            kinds = sorted({x.split(":")[0] if not x.startswith("eval:") else "평가셋:" + x.split(":")[1]
                            for x in r["excluded_reasons"]})
            note.append(", ".join(kinds))
        lines.append(f"| {r['id']} | {r['gap']} | {r['pair'] or ''} | {r['question']} | {summary(r['p0_target'])} | "
                     f"{status} | {'; '.join(note)} | 대기 |")
    path = SFT / "AUGMENTATION_REVIEW.md"
    text = path.read_text(encoding="utf-8")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    path.write_text(head + BEGIN + "\n" + "\n".join(lines) + "\n" + END + tail, encoding="utf-8")
    print(len(rows))


if __name__ == "__main__":
    main()
