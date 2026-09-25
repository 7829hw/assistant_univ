# -*- coding: utf-8 -*-
"""development 확인: 기록된 H0 관측의 최종 계획에 V0 검증기만 새로 부른다.

grounding은 다시 생성하지 않는다. 기록된 LLM 응답을 재생해 최종 계획을 결정적으로
다시 만들고, 검증을 통과한 계획에만 검증 호출을 한다(모델이 올라간 상태). 목적은
출력 형식·근거 문자열·fallback 비율·지연 확인이다. 이 결과로 prompt를 고치지 않는다.

사용: python semantic_verifier_replay.py --out <json> <run_dir>...
"""

import argparse
import json
import os
import sys
import time
from collections import Counter

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_planner as E
import evaluate_prompt_ab as A
import paraphrase_corpus as P
import semantic_verifier as V
from failure_census import ReplayClient
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary
from geoflow.planner import parse_planner_json
from ollama_client import OllamaClient

#: 알려진 corpus. 관측 id로 item(질문, 기대 인자)을 찾는다.
CORPORA = ("evaluation/paraphrases_aggregation_holdout.yaml",
           "evaluation/paraphrases_local_aggregation_holdout.yaml")


def items_by_id():
    table = {item["id"]: item for item in A.census_items()}
    for path in CORPORA:
        for item in P.load_corpus_items(P.BASE_DIR / path):
            table.setdefault(item["id"], item)
    return table


def replay_rows(run_dir, variant_name=None):
    meta, rows, report = A.load_run(run_dir)
    if not report.clean:
        raise SystemExit(f"무결성 문제: {run_dir}")
    arms = {arm["variant"]: A.recorded_variant(arm) for arm in meta["arms"]}
    for row in rows:
        if row.get("measurement") != A.VALID:
            continue
        if variant_name and row["variant"] != variant_name:
            continue
        yield meta["run_id"], row, arms[row["variant"]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="+", help="run_dir 또는 run_dir:VARIANT")
    parser.add_argument("--out", required=True)
    parser.add_argument("--host", default=A.DEFAULT_HOST)
    parser.add_argument("--model", default=A.DEFAULT_MODEL)
    args = parser.parse_args(argv)
    client = OllamaClient(args.host, args.model, {"temperature": 0}, chat_timeout=300)
    composer = MacroComposer(MacroLibrary.from_directory())
    items = items_by_id()
    out = []
    for spec in args.runs:
        run_dir, _, variant_name = spec.partition(":")
        for run_id, row, variant in replay_rows(run_dir, variant_name or None):
            item = items[row["id"]]
            contents = [call.get("content") or "" for call in row.get("llm_calls") or []]
            planner = A.FixedPromptPlanner(client=ReplayClient(contents), variant=variant)
            plans = A.RecordingComposer(composer)
            again = E.evaluate_once(planner, plans, item)
            entry = {"run": run_id, "id": row["id"], "variant": row["variant"],
                     "validated": row.get("validated"), "strict": row.get("strict_correct"),
                     "replay_consistent": again["status"] == row["status"]}
            if row.get("validated") and plans.last_plan is not None:
                started = time.perf_counter()
                result = V.verify(lambda m: V.message_content(client.chat(m)), item["question"],
                                  plans.last_plan, parse_json=parse_planner_json)
                entry["verifier_ms"] = round((time.perf_counter() - started) * 1000, 1)
                entry["verification"] = result
            out.append(entry)
            print(f"{row['id']:12s} {entry.get('verification', {}).get('outcome', '-')}",
                  flush=True)
    called = [e for e in out if "verification" in e]
    outcomes = Counter(e["verification"]["outcome"] for e in called)
    summary = {
        "observations": len(out), "verifier_calls": len(called),
        "replay_consistent": sum(e["replay_consistent"] for e in out),
        "outcomes": dict(outcomes),
        "fallback_reasons": dict(Counter(e["verification"]["reason"] for e in called
                                         if e["verification"]["outcome"] == V.FALLBACK)),
        "median_ms": sorted(e["verifier_ms"] for e in called)[len(called) // 2] if called else None,
        "by_h0_result": {
            "silent_wrong": dict(Counter(e["verification"]["outcome"] for e in called
                                         if not e["strict"])),
            "strict": dict(Counter(e["verification"]["outcome"] for e in called if e["strict"])),
        },
    }
    with open(args.out, "x", encoding="utf-8") as handle:
        json.dump({"summary": summary, "rows": out}, handle, ensure_ascii=False, indent=2,
                  default=str)
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
