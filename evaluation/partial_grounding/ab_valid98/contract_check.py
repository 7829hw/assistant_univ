# -*- coding: utf-8 -*-
"""ab_valid98 모델 실행 전 contract 검사(PLAN.md 2절). 모델을 부르지 않는다. prompt를 고치기 위한 것이 아니다.

    python evaluation/partial_grounding/ab_valid98/contract_check.py --out evaluation/partial_grounding/ab_valid98/contract_check.json

1. P0.2 output_format의 예시 1–6을 고정 parser/composer(mock Tool, --condition-check와 같은 pipeline)에 넣는다.
2. valid98 모든 문항의 정답 grounding(`evaluate_vendor100.gold_grounding`)을 Full 그대로와 Partial(`replay_partial.to_partial`)로
   같은 pipeline에 넣어 결과(outcome, error_code, 채점 범주, 호출)가 같은지 본다. 사용자는 유형별 1문항 정도를 요청했고, 모든
   문항을 돌려 유형별 대표를 보고한다(문항 내용은 보지만 prompt는 고치지 않는다).
"""
import argparse
import collections
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation" / "partial_grounding"))

import evaluate_vendor100 as EV  # noqa: E402
from geoflow import providers  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from replay_partial import to_partial  # noqa: E402
from tests.test_geoflow import ScriptedClient, planner_response  # noqa: E402

GOLD = ROOT / "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml"
P02 = ROOT / "evaluation/partial_grounding/prompts/partial_p0_2.yaml"


def run(question, payload, item=None):
    pipeline = GeoFlowPipeline.create(
        client=ScriptedClient([planner_response(payload)]), tool_executor=EV._executor(),
        aggregation_grounding="flat", clock=lambda: date(2026, 9, 25), condition_check=True,
        execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY), condition_notes=False)
    try:
        observed = EV.run_item(pipeline, question)
    except AssertionError:      # ScriptedClient: 재질의가 일어났다(정답 grounding이면 생기면 안 된다)
        return {"outcome": "repair_requested", "error_code": None, "category": None, "calls": []}
    view = {"outcome": observed["outcome"], "error_code": observed.get("error_code"),
            "calls": [(c["tool"], sorted((k, str(v)) for k, v in c["args"].items())) for c in observed["calls"]]}
    if item is not None:
        view["category"] = EV.score(item, observed)[0]
    return view


def kinds(item):
    out = [item["expected_outcome"] if item["expected_outcome"] != "answered" else "answerable"]
    calls = item["gold"]
    if "scope:" in item["question"]:
        out.append("scope_direct")
    if any(c["tool"] == "get_place_scope" for c in calls):
        out.append("place")
    args = {k: v for c in calls for k, v in c["args"].items()}
    if "dimension" in args:
        out.append("dimension")
    if {"scope_pickup", "scope_dropoff"} & set(args) or "od" in json.dumps(item.get("gold_grounding") or {}):
        out.append("od")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = {"examples": [], "items": []}
    output_format = yaml.safe_load(P02.read_text(encoding="utf-8"))["sections"]["output_format"]
    for question, text in re.findall(r"\n질문:\n([^\n]+)\n\n출력:\n(\{.*?\n\})", output_format, re.S):
        view = run(question, json.loads(text))
        result["examples"].append({"question": question, "outcome": view["outcome"], "error_code": view["error_code"]})
    EV.GOLD_PATH = GOLD
    for item in EV.load_gold(GOLD)["items"]:
        payload = EV.gold_grounding(item)
        if payload is None:
            result["items"].append({"id": item["id"], "kinds": kinds(item), "full": None, "partial": None})
            continue
        partial, _ = to_partial(json.loads(json.dumps(payload)))
        full_view, partial_view = run(item["question"], payload, item), run(item["question"], partial, item)
        result["items"].append({"id": item["id"], "kinds": kinds(item), "expected": item["expected_outcome"],
                                "full": {k: full_view[k] for k in ("outcome", "error_code", "category")},
                                "partial": {k: partial_view[k] for k in ("outcome", "error_code", "category")},
                                "same": full_view == partial_view})
    rows = [r for r in result["items"] if r["full"] is not None]
    result["summary"] = {
        "n": len(result["items"]), "no_gold_grounding": len(result["items"]) - len(rows),
        "same": sum(r["same"] for r in rows),
        "full_categories": dict(collections.Counter(r["full"]["category"] for r in rows)),
        "partial_categories": dict(collections.Counter(r["partial"]["category"] for r in rows)),
        "examples_answered": sum(e["outcome"] == "answered" for e in result["examples"]),
        "representative": {kind: next((r["id"] for r in rows if kind in r["kinds"]), None)
                           for kind in ("answerable", "unsupported", "needs_clarification", "scope_direct",
                                        "place", "dimension", "od")},
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    print("examples", result["examples"])
    for r in rows:
        if not r["same"]:
            print("DIFF", r["id"], r["kinds"], r["full"], r["partial"])


if __name__ == "__main__":
    main()
