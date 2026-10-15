# -*- coding: utf-8 -*-
"""300문항 v2 xlsx(`증강_300` 시트)를 저장소 형식으로 바꾼다(W6 1·4). 모델 호출 없음, 승인 아님.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/aug300/build_aug300.py

출력(이 디렉터리):
- ``augmentation_300.jsonl``: 문항마다 execution 층(정답 호출 ``gold``, 원문 ``gold_text``)과 v2 열 전부(``v2`` 사전, 열 이름 그대로),
  수정 셀의 메모(``v2_cell_comments``), 상태 두 가지:
  - ``status_v2``: xlsx `사용 상태(제안)` 그대로
  - ``status``: 결정 106(D1)을 적용한 상태. `보류_vendor100` → `train`, 나머지는 그대로. holdout은 바꾸지 않는다.
- ``aug300_gold.yaml``: ``evaluate_vendor100.load_gold`` 형식(id, question, gold_text, gold). 평가·mock 실행 도구가 읽는다.
질문 ID는 ``aug300-<번호>``다(xlsx `canonical_id`와 같아야 한다).
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from xlsx_read import read_workbook  # noqa: E402

XLSX = HERE.parent / "inputs/질문_증강_300문항_추가_v2.xlsx"
XLSX_SHA = "2aeaaffb3b2ba4f0b4b47e3ec78f20d4057bf1a8ba6e01335afcb640a599a039"
D1_MAP = {"보류_vendor100": "train"}
EXPECTED_D1 = {"train": 220, "holdout": 53, "제외": 5, "축소": 22}


def load_rows():
    data = XLSX.read_bytes()
    if hashlib.sha256(data).hexdigest() != XLSX_SHA:
        raise SystemExit("xlsx sha256 mismatch")
    sheet = read_workbook(XLSX)["증강_300"]
    header = sheet["rows"][0]
    rows = []
    for index, values in enumerate(sheet["rows"][1:], start=2):
        if not values or values[1] is None:
            continue
        values = list(values) + [None] * (len(header) - len(values))
        cells = dict(zip(header, values))
        letters = {}
        for col, name in enumerate(header):
            letter = ""
            n = col + 1
            while n:
                n, r = divmod(n - 1, 26)
                letter = chr(65 + r) + letter
            letters[name] = letter
        comments = {name: sheet["comments"][f"{letters[name]}{index}"] for name in header
                    if f"{letters[name]}{index}" in sheet["comments"]}
        rows.append((index, cells, comments))
    return rows


def main():
    import evaluate_vendor100 as EV

    items, gold_items = [], []
    for row_index, cells, comments in load_rows():
        number = str(cells["질문 ID"]).strip()
        qid = f"aug300-{number}"
        if cells["canonical_id"] != qid:
            raise SystemExit(f"canonical_id mismatch at row {row_index}: {cells['canonical_id']} != {qid}")
        gold_text = cells["정답 Tool"].strip()
        calls = EV.parse_calls(gold_text)
        status_v2 = cells["사용 상태(제안)"]
        items.append({
            "id": qid, "number": number, "question": cells["질문"].strip(), "gold_text": gold_text, "gold": calls,
            "semantic_type": cells["Semantic Type"], "difficulty": cells["난이도"], "family_id": cells["family_id"],
            "risk_tags": [t.strip() for t in (cells["risk_tags"] or "").split(",") if t.strip()],
            "execution_mode": cells["실행 방식"], "status_v2": status_v2, "status": D1_MAP.get(status_v2, status_v2),
            "xlsx_row": row_index, "v2": cells, "v2_cell_comments": comments,
        })
        gold_items.append({"id": qid, "question": cells["질문"].strip(), "gold_text": gold_text, "gold": calls})
    ids = [i["id"] for i in items]
    if len(ids) != 300 or len(set(ids)) != 300:
        raise SystemExit(f"expected 300 unique ids, got {len(ids)}/{len(set(ids))}")
    counts = Counter(i["status"] for i in items)
    with open(HERE / "augmentation_300.jsonl", "w", encoding="utf-8") as out:
        for item in items:
            out.write(json.dumps(item, ensure_ascii=False) + "\n")
    document = {"source": str(XLSX.relative_to(ROOT)), "source_sha256": XLSX_SHA,
                "note": "build_aug300.py가 xlsx `증강_300` 시트에서 생성. 손으로 고치지 않는다. 승인 아님.",
                "items": gold_items}
    (HERE / "aug300_gold.yaml").write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120),
                                           encoding="utf-8")
    summary = {"items": len(items), "status_v2": dict(Counter(i["status_v2"] for i in items)), "status_d1": dict(counts),
               "status_d1_expected": EXPECTED_D1, "status_d1_matches": dict(counts) == EXPECTED_D1,
               "families": len({i["family_id"] for i in items}),
               "edited_rows(with cell comments)": {i["id"]: sorted(i["v2_cell_comments"]) for i in items if i["v2_cell_comments"]}}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0 if summary["status_d1_matches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
