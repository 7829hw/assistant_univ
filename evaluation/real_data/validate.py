# -*- coding: utf-8 -*-
"""실제 질문 검증 기록(JSONL, 한 줄에 한 질문) 검사.

    python evaluation/real_data/validate.py RECORDS.jsonl

- record_schema.json(JSON Schema)과 맞는지 본다.
- decision_refs가 decisions.md에 있는 결정 항목인지 본다.
- label_basis에 vendor_decision이 있으면 그 결정 항목을 decision_refs에도 적었는지 본다.
- 같은 record_id가 두 번 나오지 않는지 본다.
형식 검사일 뿐이며 라벨의 의미가 맞는지는 판단하지 않는다.
"""
import json
import re
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent


def known_decisions():
    text = (HERE / "decisions.md").read_text(encoding="utf-8")
    return set(re.findall(r"\b(D[0-9]+) ", text))


def validate_records(records):
    schema = json.loads((HERE / "record_schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    decisions = known_decisions()
    problems, seen = [], set()
    for index, record in enumerate(records, 1):
        where = f"{index}:{record.get('record_id', '?')}"
        for error in validator.iter_errors(record):
            path = "/".join(str(p) for p in error.absolute_path)
            problems.append(f"{where} {path}: {error.message}")
        if record.get("record_id") in seen:
            problems.append(f"{where} record_id 중복")
        seen.add(record.get("record_id"))
        review = record.get("review") or {}
        refs = set(review.get("decision_refs") or [])
        for ref in refs - decisions:
            problems.append(f"{where} decision_refs {ref}: decisions.md에 없음")
        for basis in review.get("label_basis") or []:
            if basis.get("kind") == "vendor_decision" and not refs:
                problems.append(f"{where} label_basis vendor_decision인데 decision_refs가 없음")
    return problems


def main(path):
    records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    problems = validate_records(records)
    for problem in problems:
        print(problem)
    print(f"{len(records)} records, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
