# -*- coding: utf-8 -*-
"""augmentation_holdout_v1 고정(W6 5). 모델 출력을 만들거나 보기 전에 실행한다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/aug300/freeze_holdout.py

- 조건: ``check_results.json``에서 holdout 문항의 새 강한 겹침이 0이고 holdout 문항이 모두 현재 코드에서 정답 호출과 같은 실행(match)일 때만 쓴다.
- ``holdout_v1.json``: 셋 이름, 53문항 목록(id, 질문, 질문 sha256), 정렬된 질문 ID의 sha256(``"\\n".join(sorted ids)``의 UTF-8),
  질문 텍스트 sha256(정렬된 id 순서로 질문을 ``"\\n"``으로 이은 UTF-8), 평가용 gold 파일과 그 sha256.
- ``augmentation_holdout_v1_gold.yaml``: ``evaluate_vendor100.load_gold`` 형식(평가 셀 J2가 읽는다). 문항 순서는 xlsx 순서.
- 출력이 이미 있으면 멈춘다(고정한 뒤에는 다시 쓰지 않는다).
"""
import hashlib
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from training.data.common import read_jsonl  # noqa: E402

NAME = "augmentation_holdout_v1"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    out, gold_out = HERE / "holdout_v1.json", HERE / f"{NAME}_gold.yaml"
    if out.exists() or gold_out.exists():
        raise SystemExit("holdout already frozen")
    items = [i for i in read_jsonl(HERE / "augmentation_300.jsonl") if i["status"] == "holdout"]
    check = {r["id"]: r for r in json.loads((HERE / "check_results.json").read_text(encoding="utf-8"))["items"]}
    blocked = [i["id"] for i in items if check[i["id"]]["new_strong_overlap"] or check[i["id"]]["code"]["category"] != "match"]
    if len(items) != 53 or blocked:
        raise SystemExit(f"cannot freeze: {len(items)} items, blocked {blocked}")
    ids = sorted(i["id"] for i in items)
    by_id = {i["id"]: i for i in items}
    document = {"set": NAME, "source": "pilot_006_prep/aug300/augmentation_300.jsonl", "note": "freeze_holdout.py가 생성. 손으로 고치지 않는다.",
                "items": [{"id": i["id"], "question": i["question"], "gold_text": i["gold_text"], "gold": i["gold"]} for i in items]}
    gold_text = yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=120)
    gold_out.write_text(gold_text, encoding="utf-8")
    record = {
        "set": NAME, "items": len(ids),
        "sorted_ids_sha256": sha("\n".join(ids)),
        "questions_sha256(sorted id order, newline joined)": sha("\n".join(by_id[i]["question"] for i in ids)),
        "gold_file": gold_out.name, "gold_file_sha256": hashlib.sha256(gold_out.read_bytes()).hexdigest(),
        "source_xlsx_sha256": "2aeaaffb3b2ba4f0b4b47e3ec78f20d4057bf1a8ba6e01335afcb640a599a039",
        "augmentation_300_jsonl_sha256": hashlib.sha256((HERE / "augmentation_300.jsonl").read_bytes()).hexdigest(),
        "check_results_sha256": hashlib.sha256((HERE / "check_results.json").read_bytes()).hexdigest(),
        "rule": "고정 뒤 학습, prompt 예시, 오류 기반 보강 설계에 쓰지 않는다(계획서 v2 6.3절). 모델 출력은 이 커밋 뒤에만 만든다.",
        "by_semantic_type": {},
        "list": [{"id": i, "question": by_id[i]["question"], "question_sha256": sha(by_id[i]["question"]),
                  "family_id": by_id[i]["family_id"], "semantic_type": by_id[i]["semantic_type"]} for i in ids],
    }
    for i in ids:
        t = by_id[i]["semantic_type"]
        record["by_semantic_type"][t] = record["by_semantic_type"].get(t, 0) + 1
    out.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "list"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
