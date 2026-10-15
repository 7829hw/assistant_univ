# -*- coding: utf-8 -*-
"""Partial Grounding 실현 가능성 재실행(모델 호출 없음).

이식본(pilot_006 준비 W3·W4 5): 원본 ``geoflow/partial-grounding`` 커밋 ``ab9d215``의 ``evaluation/partial_grounding/replay_partial.py``.
바꾼 것: (1) completion은 ``grounding.completion``(trunk ``geoflow/``는 그대로), (2) full arm은 trunk ``GeoFlowPlanner``,
partial arm은 ``grounding.make_pipeline("partial")``(``PartialPlanner``)로 돈다. 원본은 두 arm 모두 completion이 들어간 planner로 돌았다
(완전한 payload에는 멱등이라 full arm 결과가 같아야 한다 — W4 5에서 문항 단위로 비교). (3) ROOT는 저장소 루트(``parents[4]``).

기록된 vendor100 형식 run의 첫 계획 응답을 두 가지로 현재 코드에 다시 넣는다.

- full:    기록 그대로.
- partial: 같은 응답에서 parser가 ontology로 채울 수 있는 필드(id, concept, role, source)와
           EVENT 개념을 지운 것. 모델이 같은 의미 판단(subtype, value, attributes, text,
           factors)을 하고 구조 필드만 생략했다고 가정한 출력이다.

재질의 응답은 기록 그대로 순서대로 돌려준다. 두 arm의 결과(채점 범주, outcome, 오류 코드,
Tool 호출, grounding 일치)를 문항별로 비교한다. partial arm에서는 parser가 id를 새로 붙이므로, 기록된
재질의 응답이 가리키는 원래 id(``concept_id``)를 새 id로 바꿔 넣는다. 실제 실행에서는 재질의 요청문에
새 id가 보이므로 모델이 새 id로 답한다.

    python evaluation/partial_grounding/replay_partial.py --out evaluation/partial_grounding/result.json \
        sft_dpo_inventory/baseline_conditions_001/runs/E.json ...
"""

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import evaluate_vendor100 as V  # noqa: E402
from geoflow import providers  # noqa: E402
from geoflow.errors import GeoFlowError  # noqa: E402
from grounding import make_pipeline  # noqa: E402
from grounding.completion import complete_grounding_payload  # noqa: E402
from geoflow.planner import load_planner_prompt, parse_planner_json  # noqa: E402

#: parser가 채우므로 partial 출력에서 지우는 필드.
STRUCTURAL_KEYS = ("id", "concept", "role", "source")


def to_partial(payload):
    """full payload를 partial로 줄인다. (partial payload, 지운 내역). concepts가 없으면 그대로."""
    concepts = payload.get("concepts") if isinstance(payload, dict) else None
    if not isinstance(concepts, list):
        return payload, None
    kept, dropped, ids = [], {"events": 0, "fields": 0}, []
    for raw in concepts:
        if not isinstance(raw, dict):
            kept.append(raw)
            ids.append(None)
            continue
        if raw.get("concept") == "EVENT":
            dropped["events"] += 1
            continue
        item = {key: value for key, value in raw.items() if key not in STRUCTURAL_KEYS}
        dropped["fields"] += len(raw) - len(item)
        kept.append(item)
        ids.append(raw.get("id"))
    partial = {**payload, "concepts": kept}
    completed = complete_grounding_payload(partial)["concepts"]
    renamed = {old: new.get("id") for old, new in zip(ids, completed)
               if isinstance(old, str) and isinstance(new, dict) and old != new.get("id")}
    return partial, {**dropped, "renamed": renamed}


def _rename_ids(value, renamed):
    """재질의 응답 안의 concept_id를 새 id로 바꾼다."""
    if isinstance(value, dict):
        return {key: (renamed.get(item, item) if key == "concept_id" and isinstance(item, str)
                      else _rename_ids(item, renamed)) for key, item in value.items()}
    if isinstance(value, list):
        return [_rename_ids(item, renamed) for item in value]
    return value


def _partial_calls(calls):
    """첫 계획 응답만 partial로 바꾼 호출 기록."""
    calls = [dict(call) for call in calls]
    if not calls or calls[0].get("kind", "plan") != "plan" or calls[0].get("failed"):
        return calls, None
    try:
        payload = parse_planner_json(calls[0]["content"])
    except GeoFlowError:
        return calls, None
    partial, dropped = to_partial(payload)
    if dropped is None:
        return calls, None
    calls[0]["content"] = json.dumps(partial, ensure_ascii=False)
    for call in calls[1:]:
        if call.get("failed") or not dropped["renamed"]:
            continue
        try:
            repair = parse_planner_json(call["content"])
        except GeoFlowError:
            continue
        call["content"] = json.dumps(_rename_ids(repair, dropped["renamed"]), ensure_ascii=False)
    return calls, {"payload": payload, "partial": partial, "dropped": dropped}


def _run(row, calls, meta, target="full"):
    client = V._SequenceClient(calls, meta.get("model"))
    # 기록된 응답을 돌려주므로 prompt는 결과에 영향이 없다. 원본과 같게 두 arm 모두 기본 prompt를 둔다.
    pipeline = make_pipeline(
        target, planner_prompt=load_planner_prompt(),
        client=V._RecordingClient(client), tool_executor=V._executor(),
        clock=lambda: V.REFERENCE_DATE,
        condition_check=(meta.get("pipeline") or {}).get("condition_check", True),
        condition_notes=False,
        execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY))
    try:
        observed = V.run_item(pipeline, row["question"])
    except Exception as error:  # noqa: BLE001 - 평가 대상 코드의 미처리 예외도 결과로 남긴다
        observed = V._crashed(error)
    return observed, client.needs_live


def _view(gold, observed, needs_live):
    category, _ = V.score(gold, observed)
    grounding_ok, diffs = V.grounding_check(gold, observed["grounding"])
    return {"category": category, "outcome": observed["outcome"],
            "error_code": observed["error_code"],
            "calls": [[call.get("tool"), call.get("args")] for call in observed.get("calls") or []],
            "grounding_ok": grounding_ok, "grounding_diffs": diffs, "needs_live": needs_live}


def replay(path):
    source = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = source["meta"]
    gold_file = meta.get("gold_file")
    gold = {item["id"]: item for item in V.load_gold(ROOT / gold_file if gold_file else None)["items"]}
    rows = []
    for row in source["rows"]:
        if row["id"] not in gold or not row.get("llm_calls"):
            continue
        full = _view(gold[row["id"]], *_run(row, row["llm_calls"], meta))
        calls, change = _partial_calls(row["llm_calls"])
        if change is None:
            partial, same = full, True
        else:
            partial = _view(gold[row["id"]], *_run(row, calls, meta, "partial"))
            same = {key: full[key] for key in ("category", "outcome", "error_code", "calls")} == \
                   {key: partial[key] for key in ("category", "outcome", "error_code", "calls")}
        rows.append({"id": row["id"], "question": row["question"], "converted": change is not None,
                     "same": same, "full": full, "partial": partial,
                     **({"payload": change["payload"], "partial_payload": change["partial"]}
                        if change is not None and not same else {})})
    return {"source": str(path), "model": meta.get("model"), "rows": rows}


def summarize(result):
    rows = result["rows"]
    count = collections.Counter
    return {
        "items": len(rows),
        "converted": sum(row["converted"] for row in rows),
        "same": sum(row["same"] for row in rows),
        "full_categories": dict(count(row["full"]["category"] for row in rows)),
        "partial_categories": dict(count(row["partial"]["category"] for row in rows)),
        "full_grounding_ok": sum(bool(row["full"]["grounding_ok"]) for row in rows),
        "partial_grounding_ok": sum(bool(row["partial"]["grounding_ok"]) for row in rows),
        "transitions": dict(count(f'{row["full"]["category"]}->{row["partial"]["category"]}'
                                  for row in rows if not row["same"])),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="+")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    results = []
    for path in args.sources:
        result = replay(path)
        result["summary"] = summarize(result)
        print(path, json.dumps(result["summary"], ensure_ascii=False), flush=True)
        results.append(result)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
