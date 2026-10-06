# -*- coding: utf-8 -*-
"""문항을 장소 provider 기준으로 나눈다(결정 11). CPU만 쓰고 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_002/provider/classify_providers.py

- 대상: reviewed corpus v003_t2pc(``sft_train``·``sft_valid``)와 batch004 후보(``candidates_checked.json``의 18개).
  gold(또는 batch004 초안) grounding의 장소를 쓴다. 질문·gold는 고치지 않는다.
- 장소 조회는 pipeline의 RESOLVE_PLACE_SCOPE와 같은 인자다: subtype ``place``인 LOCATION 개념마다
  ``get_place_scope(name, region, include_vicinity)``. ``include_vicinity``는 factors.vicinity를 따른다.
  subtype ``scope``(사용자가 준 scope 값, 예: scope:edge:2607)는 조회하지 않으므로 provider와 무관하다.
- 분류:
  - ``no_lookup``: 조회할 장소가 없음.
  - ``mock``: mock으로 모든 장소가 풀림(reference로도 풀리면 ``mock_and_reference``).
  - ``reference_only``: reference로만 모든 장소가 풀림.
  - ``neither``: 어느 provider로도 모든 장소가 풀리지 않음.
- 평가 provider: ``reference_only``만 reference, 나머지는 mock(결정 11). ``neither``는 보고만 한다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

CORPUS = ROOT / "training/generated/reviewed_gold_v003_t2pc"
BATCH004 = ROOT / "sft_dpo_inventory/batch004/candidates_checked.json"


def lookups(grounding):
    vicinity = bool((grounding.get("factors") or {}).get("vicinity"))
    out = []
    for concept in grounding.get("concepts") or []:
        if concept.get("concept") != "LOCATION":
            continue
        value = concept.get("value")
        if concept.get("subtype") == "place" and isinstance(value, dict):
            out.append({"id": concept.get("id"), "name": value.get("name"), "region": value.get("region") or "",
                        "include_vicinity": vicinity})
        else:
            out.append({"id": concept.get("id"), "literal": value, "subtype": concept.get("subtype")})
    return out


def resolve(place):
    from mock_responses import mock_get_place_scope
    from reference_provider import ReferenceProvider
    args = {"name": place["name"], "region": place["region"], "include_vicinity": place["include_vicinity"]}
    mock = mock_get_place_scope(dict(args))
    ref = ReferenceProvider.place_scope(dict(args))
    ok = lambda r: not (isinstance(r, dict) and r.get("status") == "ERROR")  # noqa: E731
    return {"mock": ok(mock), "reference": ok(ref),
            "mock_error": None if ok(mock) else mock.get("error_code"),
            "reference_error": None if ok(ref) else ref.get("error_code")}


def classify(grounding):
    places = lookups(grounding)
    named = [p for p in places if "name" in p]
    for place in named:
        place.update(resolve(place))
    if not named:
        cls = "no_lookup"
    else:
        mock_all = all(p["mock"] for p in named)
        ref_all = all(p["reference"] for p in named)
        cls = ("mock_and_reference" if mock_all and ref_all else "mock" if mock_all
               else "reference_only" if ref_all else "neither")
    return cls, places


def items():
    for split in ("train", "valid"):
        for line in (CORPUS / f"sft_{split}.jsonl").read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            yield {"source": f"v003_t2pc_{split}", "id": record["metadata"]["source_record_id"],
                   "question": record["messages"][1]["content"],
                   "grounding": json.loads(record["messages"][2]["content"])}
    for cand in json.loads(BATCH004.read_text(encoding="utf-8"))["candidates"]:
        yield {"source": "batch004_candidate", "id": cand["id"], "question": cand["question"],
               "grounding": cand["draft_grounding"]}


def main():
    rows = []
    for item in items():
        cls, places = classify(item["grounding"])
        rows.append({"source": item["source"], "id": item["id"], "question": item["question"], "class": cls,
                     "eval_provider": "reference" if cls == "reference_only" else "mock", "places": places})
    counts = {}
    for row in rows:
        counts.setdefault(row["source"], Counter())[row["class"]] += 1
    out = {"rule": __doc__.split("\n\n")[2].strip(), "counts": {k: dict(v) for k, v in counts.items()}, "rows": rows}
    (HERE / "provider_classification.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                                                      encoding="utf-8")
    lines = ["# 문항별 장소 provider 분류", "",
             "`classify_providers.py`가 만든다. 장소 = subtype place인 LOCATION의 (name, region). "
             "literal scope는 조회하지 않는다.", "",
             "| 출처 | id | 분류 | 평가 provider | 장소(mock / reference) | 질문 |", "|---|---|---|---|---|---|"]
    for row in rows:
        places = "; ".join(
            f"{p['name']}{'(' + p['region'] + ')' if p['region'] else ''} "
            f"{'O' if p['mock'] else 'X'}/{'O' if p['reference'] else 'X'}" if "name" in p
            else f"literal {p['literal']}" for p in row["places"]) or "—"
        lines.append(f"| {row['source']} | {row['id']} | {row['class']} | {row['eval_provider']} | {places} | "
                     f"{row['question'][:60]} |")
    lines += ["", "| 출처 | " + " | ".join(("no_lookup", "mock", "mock_and_reference", "reference_only", "neither")) + " |",
              "|---|---:|---:|---:|---:|---:|"]
    for source, count in counts.items():
        lines.append(f"| {source} | " + " | ".join(str(count.get(k, 0)) for k in (
            "no_lookup", "mock", "mock_and_reference", "reference_only", "neither")) + " |")
    (HERE / "provider_classification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
