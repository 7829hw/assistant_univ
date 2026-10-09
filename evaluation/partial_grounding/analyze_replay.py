# -*- coding: utf-8 -*-
"""replay_partial.py 결과를 원인별로 나눈다.

결과가 달라진 문항마다 원래(full) 응답의 구조 필드가 ontology 추론과 어떻게 달랐는지 본다.

- event_mismatch:   EVENT가 측정값에서 정해지는 사건과 다르거나 여럿이다(partial은 composer가 추론).
- role_or_source:   concept·role·source 가운데 추론과 다른 값이 있다(partial은 추론값).
- unknown_subtype:  ontology에 없는 subtype이다(partial은 concept이 비어 거부된다).
- place_measure:    값 없는 장소가 MEASURE다(답이 장소인 질문).
- other:            구조 필드는 추론과 같다(id나 재질의 경로 차이).

    python evaluation/partial_grounding/analyze_replay.py evaluation/partial_grounding/replay_result.json
"""

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from geoflow import operator_mapping  # noqa: E402
from geoflow.grounding import _inferred_fields  # noqa: E402
from geoflow.types import CoreConcept  # noqa: E402

GOOD = {"match", "refused_unsupported"}


def causes(payload):
    concepts = [item for item in payload.get("concepts") or [] if isinstance(item, dict)]
    found = set()
    for item in concepts:
        inferred = _inferred_fields(item)
        if inferred["concept"] is None and item.get("concept") != "EVENT":
            found.add("unknown_subtype")
            continue
        if item.get("subtype") == "place" and item.get("role") == "MEASURE":
            found.add("place_measure")
        for key, want in inferred.items():
            if want is not None and item.get(key) not in (None, "", want):
                found.add("role_or_source")
    measures = [item for item in concepts if item.get("role") == "MEASURE"]
    events = sorted(str(item.get("subtype")) for item in concepts if item.get("concept") == "EVENT")
    if len(measures) == 1:
        try:
            want = operator_mapping.event_subtype_for(CoreConcept(measures[0].get("concept")),
                                                      measures[0].get("subtype"))
        except ValueError:
            want = None
        if want is not None and events not in ([], [want]):
            found.add("event_mismatch")
    return sorted(found) or ["other"]


def direction(row):
    before, after = row["full"]["category"] in GOOD, row["partial"]["category"] in GOOD
    if before == after:
        return "neutral"
    return "improved" if after else "regressed"


def main(path):
    results = json.loads(Path(path).read_text(encoding="utf-8"))
    total = collections.Counter()
    by_cause = collections.Counter()
    examples = collections.defaultdict(list)
    table = []
    for result in results:
        rows = result["rows"]
        summary = result["summary"]
        good = lambda arm: sum(row[arm]["category"] in GOOD for row in rows)  # noqa: E731
        table.append([result["source"], summary["items"], summary["same"],
                      summary["full_categories"].get("match", 0),
                      summary["partial_categories"].get("match", 0),
                      good("full"), good("partial"),
                      summary["full_grounding_ok"], summary["partial_grounding_ok"]])
        for row in rows:
            total["items"] += 1
            if row["same"]:
                total["same"] += 1
                continue
            way = direction(row)
            total[way] += 1
            for cause in causes(row.get("payload") or {}):
                by_cause[(cause, way)] += 1
                if len(examples[(cause, way)]) < 3:
                    examples[(cause, way)].append({
                        "source": result["source"], "id": row["id"], "question": row["question"],
                        "full": [row["full"]["category"], row["full"]["error_code"]],
                        "partial": [row["partial"]["category"], row["partial"]["error_code"]]})
    print("source | items | same | match full→partial | match+refused full→partial | grounding_ok full→partial")
    for name, items, same, mf, mp, gf, gp, of, op in table:
        print(f"{name} | {items} | {same} | {mf}→{mp} | {gf}→{gp} | {of}→{op}")
    print(json.dumps(dict(total), ensure_ascii=False))
    for (cause, way), count in sorted(by_cause.items()):
        print(f"{cause:16s} {way:9s} {count}")
    for key, items in sorted(examples.items()):
        print("--", *key)
        for item in items:
            print("  ", json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
