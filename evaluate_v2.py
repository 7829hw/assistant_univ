# -*- coding: utf-8 -*-
"""업체 v2 계약 기준 geoflow 평가 실행기. 평가 전용.

production 설정(flat grounding, condition_check 끔, mock + TIMS legacy, 예시 검색 끔)으로 질문마다
전체 파이프라인(planner → composer → validator → compiler → mock 실행 → 답변)을 돌리고, 결과를
다음으로 나눠 채점한다. 설계와 판정 규칙은 ``evaluation/v2/preregistration_v2.md``에 모델 실행
전에 고정했다.

- 실행 완료: 답을 내야 하는 질문(expected_outcome=answered)에서 답을 냈는가
- 의미 정답: 결과 종류, 측정값, 라벨, 집계 의미, 최종 Tool 인자, 답변 형식이 모두 맞는가
- 거부 정확도: 답하지 말아야 하는 질문에서 기대한 종류(unsupported | needs_clarification)로
  멈췄는가(strict). 답하지 않았는가(lenient)도 따로 센다.

관측마다 모델을 내려 이전 요청의 서버 상태를 없앤다(evaluate_prompt_ab ``isolated_state_v1``와
같은 절차). 기준일은 고정한다(``paraphrase_corpus.EVALUATION_REFERENCE_DATE``).

    python evaluate_v2.py run --model qwen3:8b --sets stub,holdout_v2 --label v2_qwen3_8b
    python evaluate_v2.py analyze evaluation/v2/runs/<run_id>
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import yaml  # noqa: E402

import aggregation_plan as AP  # noqa: E402
import evaluate_planner as E  # noqa: E402
import evaluate_prompt_ab as A  # noqa: E402
import paraphrase_corpus as P  # noqa: E402
from build import build  # noqa: E402
from geoflow import providers, structured_grounding  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from mock_responses import mock_get_place_scope  # noqa: E402
from ollama_client import OllamaClient, resolve_think  # noqa: E402
from query_loader import load_queries  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_handlers import get_tool_handlers  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
V2_DIR = BASE_DIR / "evaluation" / "v2"
RUN_ROOT = V2_DIR / "runs"
REFERENCE_DATE = P.EVALUATION_REFERENCE_DATE
PROTOCOL = "v2_pipeline_isolated_v1"
#: production CLI의 기본값(assistant_cli.py). 평가 중에 바꾸지 않는다.
PIPELINE_CONFIG = {
    "agent_mode": "geoflow",
    "aggregation_grounding": structured_grounding.FLAT,
    "condition_check": False,
    "provider": providers.MOCK,
    "tims_execution": providers.LEGACY,
    "example_retrieval": "off",
    "ollama_options": {"temperature": 0},
    "think": "auto",
}
SETS = {
    "stub": {"queries": "stub_query.yaml", "gold": "evaluation/v2/stub_v2_gold.yaml"},
    "holdout_v2": {"corpus": "evaluation/v2/paraphrases_holdout_v2.yaml",
                   "revisions": "evaluation/v2/label_revisions.yaml"},
}
ANSWERED = "answered"
REFUSALS = ("unsupported", "needs_clarification")


# -- 문항 -------------------------------------------------------------------------


def load_revisions(spec, base=BASE_DIR):
    """사전 등록 라벨의 정책 개정(evaluation/v2/label_revisions.yaml). 없으면 빈 개정."""
    if "revisions" not in spec:
        return {"revision": None, "intents": {}}
    document = yaml.safe_load((base / spec["revisions"]).read_text(encoding="utf-8"))
    if document.get("base") != spec["corpus"]:
        raise ValueError(f"{spec['revisions']}의 base가 {spec['corpus']}가 아니다")
    return document


def load_items(names, base=BASE_DIR, *, revised=True):
    """평가 문항. 모든 문항이 expected_outcome을 갖는다.

    ``revised``이면 사전 등록 라벨에 정책 개정을 적용한다. 사전 등록 값은
    ``expected_outcome_prereg``로 남는다. 개정은 기대 결과만 바꾸고 뜻(집계·인자)은 바꾸지 않는다.
    """
    items = []
    for name in names:
        spec = SETS[name]
        if "corpus" in spec:
            goldens = {intent["intent"]: intent.get("golden")
                       for intent in P.load_corpus(base / spec["corpus"])}
            revisions = load_revisions(spec, base) if revised else {"intents": {}}
            for item in P.load_corpus_items(base / spec["corpus"]):
                golden = goldens[item["intent_id"]]
                factors = golden.get("factors") if isinstance(golden, dict) else None
                revision = revisions["intents"].get(item["intent_id"])
                extra = {"expected_outcome_prereg": item["expected_outcome"]}
                if revision is not None:
                    if revision["prereg"] != item["expected_outcome"]:
                        raise ValueError(f"{item['intent_id']}: 개정의 prereg 값이 사전 등록과 다르다")
                    extra.update(expected_outcome=revision["expected_outcome"],
                                 label_revision=revisions["revision"])
                items.append({**item, "set": name, **extra,
                              "golden_factors": None if factors is None else dict(factors)})
            continue
        gold = yaml.safe_load((base / spec["gold"]).read_text(encoding="utf-8"))["queries"]
        queries = load_queries(base / spec["queries"])
        if set(gold) != {query["id"] for query in queries}:
            raise ValueError(f"{spec['gold']}의 질의가 {spec['queries']}와 다르다")
        for query in queries:
            items.append({
                "id": query["id"], "question": query["question"], "set": name,
                "intent_id": query["id"],
                **{key: list(query.get(key) or []) for key in P.LABEL_KEYS},
                **gold[query["id"]],
            })
    return items


def input_files(names):
    files = []
    for name in names:
        spec = SETS[name]
        if "corpus" in spec:
            files.append(spec["corpus"])
            document = yaml.safe_load((BASE_DIR / spec["corpus"]).read_text(encoding="utf-8"))
            files.extend(document.get("parents") or [])
            if "revisions" in spec:
                files.append(spec["revisions"])
        else:
            files.extend([spec["queries"], spec["gold"]])
    return files


# -- 채점 ------------------------------------------------------------------------


def _scope_of(value):
    """"@place:이름"을 mock gazetteer의 scope로 푼다(지역 없이). 못 풀면 원래 값."""
    if isinstance(value, str) and value.startswith("@place:"):
        result = mock_get_place_scope({"name": value.split(":", 1)[1]})
        if isinstance(result, str):
            return result
    return value


def arg_mismatches(expected, actual, tool):
    """기대 인자와 다른 것. 장소는 scope가 같으면 같다(별칭 대구 = 대구시)."""
    expected = {key: _scope_of(value) for key, value in (expected or {}).items()}
    actual = {key: _scope_of(value) for key, value in (actual or {}).items()}
    return P.tool_arg_mismatches(expected, actual, P.tool_defaults(tool) if tool else {})


#: 값이 조건을 걸지 않는 factor 값. 없는 것과 같다.
_NEUTRAL = {"taxi_type": "all", "taxi_status": "all", "vicinity": False,
            "dimension_target": "both"}


def condition_mismatches(golden_factors, actual_factors):
    """golden grounding과 최종 grounding의 조건(집계 제외) 차이. [key, 기대, 실제] 목록.

    최종 Tool 인자만 보면 장소 조회 단계의 조건(주변 포함)이나 질문에 없는 조건을 놓친다.
    """
    def conditions(factors):
        return {key: value for key, value in (factors or {}).items()
                if key not in AP.FLAT_KEYS and key != AP.PLAN_KEY
                and value is not None and _NEUTRAL.get(key) != value}
    want, got = conditions(golden_factors), conditions(actual_factors)
    return [[key, want.get(key), got.get(key)] for key in sorted(set(want) | set(got))
            if want.get(key) != got.get(key)]


def expected_measure(item):
    for label in item.get("expected_concepts") or []:
        if label.endswith(":MEASURE"):
            return label.split("/", 1)[1].split(":", 1)[0]
    return None


_RAW_ROW = re.compile(r"\b[a-z_]+=\S")


def answer_problems(answer, question):
    """답변 문자열의 형식 문제. 값의 정확성은 보지 않는다(mock 고정값)."""
    problems = []
    if not (answer or "").strip():
        return ["empty"]
    if "{'" in answer or '{"' in answer:
        problems.append("raw_object")
    if _RAW_ROW.search(answer):
        problems.append("raw_row")
    if "None" in answer:
        problems.append("none_value")
    if "%%" in answer:
        problems.append("double_unit")
    for scope in re.findall(r"scope:[A-Za-z0-9_:.-]+", answer):
        if scope not in question:
            problems.append("scope_exposed")
            break
    if not re.search(r"\d", answer) and "결과 없음" not in answer:
        problems.append("no_value")
    return problems


def plan_facts(plan):
    """plan에서 채점에 쓰는 사실. plan이 없으면 None."""
    if plan is None:
        return None
    facts = {"final_measure": None, "labels": None, "aggregation": None,
             "final_tool": None, "final_tool_args": None, "tool_call_error": None}
    node = plan.node(plan.final_node)
    facts["final_measure"] = node.subtype if node is not None else None
    macros, operators = E.corpus_labels(plan)
    facts["labels"] = {"expected_macros": macros, "expected_operators": operators}
    facts["aggregation"] = P.plan_aggregation(plan)
    try:
        facts["final_tool"], facts["final_tool_args"] = P.final_tool_call(plan)
    except Exception as error:  # noqa: BLE001 - 측정 결과로 남긴다
        facts["tool_call_error"] = f"{type(error).__name__}: {error}"
    return facts


def score(item, outcome, facts, run_record):
    """관측 하나의 채점. 범주(category)는 하나, 세부 판정은 checks에 모두 남긴다."""
    expected = item["expected_outcome"]
    checks = {"outcome_ok": outcome == expected}
    if facts is not None:
        want_measure = expected_measure(item)
        checks["measure_ok"] = want_measure is None or facts["final_measure"] == want_measure
        if "NONE" not in (item.get("expected_macros") or []) and item.get("expected_macros"):
            checks["labels_ok"] = facts["labels"] == {
                "expected_macros": item["expected_macros"],
                "expected_operators": item["expected_operators"]}
        semantic = item.get("semantic_aggregation")
        if "semantic_aggregation" in item:
            checks["aggregation_ok"] = facts["aggregation"] == (
                None if semantic is None else P.golden_aggregation({"aggregation": semantic}))
        if facts["final_tool_args"] is not None:
            mismatches = arg_mismatches(item.get("expected_tool_args"),
                                        facts["final_tool_args"], facts["final_tool"])
            if item.get("golden_factors") is not None:
                mismatches += [["condition:" + key, want, got] for key, want, got in
                               condition_mismatches(item["golden_factors"],
                                                    (run_record.get("grounding") or {})
                                                    .get("factors"))]
            checks["arg_mismatches"] = mismatches
            checks["args_ok"] = not mismatches
    if outcome == ANSWERED:
        problems = answer_problems(run_record.get("final_answer"), item["question"])
        checks["answer_problems"] = problems
        checks["answer_ok"] = not problems

    if expected == ANSWERED:
        if outcome == ANSWERED:
            if not checks.get("measure_ok", False) or checks.get("labels_ok") is False:
                category = "grounding_error"
            elif checks.get("aggregation_ok") is False:
                category = "aggregation_error"
            elif not checks.get("args_ok", False):
                category = "wrong_tool_args"
            elif not checks.get("answer_ok", False):
                category = "answer_format_error"
            else:
                category = "correct"
        elif outcome in REFUSALS:
            category = "refused_supported"
        elif run_record.get("stage") in ("planner", "composition", "validation"):
            category = "grounding_failure"
        else:
            category = "execution_failure"
    else:
        if outcome == expected:
            category = "correct"
        elif outcome == ANSWERED:
            category = "answered_instead_of_refusal"
        elif outcome in REFUSALS:
            category = "wrong_refusal_kind"
        else:
            category = "failed_instead_of_refusal"
    return category, checks


# -- 실행 ------------------------------------------------------------------------


def observe(item, *, client, reset, tools, model, restarts=A.MAX_FRESH_RESTARTS):
    """새 모델 상태에서 질문 하나를 끝까지 실행하고 채점한다."""
    discarded = []
    while True:
        state = reset.reset()
        if not state.succeeded:
            return {"id": item["id"], "measurement": A.INVALID, "invalid_reason": "reset_failed",
                    "reset_detail": state.detail, "category": "invalid_measurement"}
        recorder = A.RecordingClient(client)
        executor = ToolExecutor(tools=tools, handlers=get_tool_handlers(providers.MOCK),
                                provider=providers.MOCK)
        pipeline = GeoFlowPipeline.create(
            client=recorder, tool_executor=executor, model=model,
            aggregation_grounding=PIPELINE_CONFIG["aggregation_grounding"],
            condition_check=PIPELINE_CONFIG["condition_check"],
            execution_profile=providers.profile_for(providers.MOCK,
                                                    PIPELINE_CONFIG["tims_execution"]),
            clock=lambda: REFERENCE_DATE,
        )
        composer = A.RecordingComposer(pipeline.composer)
        pipeline.composer = composer
        run = pipeline.run(item["question"])
        retried = A.retried_calls(recorder.calls)
        if not retried or len(discarded) >= restarts:
            break
        discarded.append({"retried_call_indices": retried})
    record = run.to_dict()
    facts = plan_facts(composer.last_plan)
    category, checks = score(item, run.outcome, facts, record)
    first_load = recorder.calls[0].get("load_duration_ms") if recorder.calls else None
    measurement = A.VALID
    invalid_reason = None
    if retried:
        measurement, invalid_reason = A.INVALID, "warm_retry"
    elif first_load is None or first_load < A.COLD_LOAD_MIN_MS:
        measurement, invalid_reason = A.INVALID, "cold_load_unverified"
    return {
        "protocol": PROTOCOL,
        "id": item["id"], "set": item["set"], "intent_id": item.get("intent_id"),
        "question": item["question"], "expected_outcome": item["expected_outcome"],
        "expected_outcome_prereg": item.get("expected_outcome_prereg",
                                            item["expected_outcome"]),
        "label_revision": item.get("label_revision"),
        "capability": item.get("capability"), "restores": item.get("restores"),
        "expected_tool_args": item.get("expected_tool_args"),
        "semantic_aggregation": item.get("semantic_aggregation"),
        "outcome": run.outcome, "stage": record["stage"],
        "error_code": (record.get("error") or {}).get("code"),
        "final_answer": record.get("final_answer"),
        "category": "invalid_measurement" if measurement == A.INVALID else category,
        "scored_category": category, "checks": checks, "plan_facts": facts,
        "measurement": measurement, "invalid_reason": invalid_reason,
        "fresh_restarts": len(discarded), "reset_duration_ms": state.duration_ms,
        "llm_calls": recorder.calls, "cold_load_ms": first_load,
        "tools": [hop["tool"] for hop in run.hop_log],
        "hop_log": run.hop_log, "attempts": record.get("attempts"),
        "repair_count": record.get("repair_count"), "grounding": record.get("grounding"),
        "durations": record.get("durations"),
    }


#: 결과에 영향을 주는 경로. run meta에 커밋과 함께 이 경로의 미커밋 변경을 남긴다.
TRACKED_PATHS = ("geoflow", "prompts", "schemas", "geoflow_macros", "geoflow_examples",
                 "evaluate_v2.py", "evaluate_planner.py", "paraphrase_corpus.py",
                 "aggregation_plan.py", "mock_responses.py", "mock_stub.yaml", "tool_executor.py",
                 "tool_handlers.py", "build.py", "stub_query.yaml", "evaluation/v2")


def git_state():
    def git(*args):
        import subprocess
        return subprocess.run(["git", *args], cwd=BASE_DIR, capture_output=True,
                              text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
            "dirty_paths": git("status", "--porcelain", "--", *TRACKED_PATHS).splitlines()}


def _sha(path):
    return hashlib.sha256((BASE_DIR / path).read_bytes()).hexdigest()


def run_meta(args, names, client, tools, system_prompt):
    version, digest, details = A._server_details(args.host, args.model)
    planner = GeoFlowPipeline.create(client=client, tool_executor=ToolExecutor(
        tools=tools, handlers=get_tool_handlers(providers.MOCK)),
        aggregation_grounding=PIPELINE_CONFIG["aggregation_grounding"]).planner
    prompt = planner.system_prompt()
    return {
        "protocol": PROTOCOL,
        "started_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "command": " ".join(sys.argv),
        "git": git_state(),
        "model": args.model, "ollama_host": args.host, "ollama_version": version,
        "model_digest": digest, "model_details": details,
        "pipeline": PIPELINE_CONFIG, "chat_timeout": args.chat_timeout,
        "reference_date": REFERENCE_DATE.isoformat(),
        "planner_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "vendor_tool_schema_sha256": hashlib.sha256(json.dumps(
            tools, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "vendor_system_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
        "inputs": {path: _sha(path) for path in [*input_files(names), "mock_stub.yaml"]},
        "sets": names, "cold_load_min_ms": A.COLD_LOAD_MIN_MS,
    }


def cmd_run(args):
    names = args.sets.split(",")
    items = load_items(names)
    if args.only:
        wanted = set(args.only.split(","))
        items = [item for item in items if item["id"] in wanted or item.get("intent_id") in wanted]
    if args.limit:
        items = items[:args.limit]
    tools, system_prompt = build()
    client = OllamaClient(args.host, args.model, dict(PIPELINE_CONFIG["ollama_options"]),
                          chat_timeout=args.chat_timeout,
                          think=resolve_think(PIPELINE_CONFIG["think"]))
    # 서버 정보를 먼저 읽는다. 서버에 닿지 않으면 빈 run 디렉터리를 남기지 않는다.
    meta = run_meta(args, names, client, tools, system_prompt)
    run_id = f"{datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d_%H%M%S')}_{args.label}"
    run_dir = Path(args.out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    meta.update(run_id=run_id, item_count=len(items))
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    A.unload_all_models(args.host)
    reset = A.OllamaStateReset(args.host, args.model)
    with (run_dir / "observations.jsonl").open("a", encoding="utf-8") as handle:
        for index, item in enumerate(items, start=1):
            record = observe(item, client=client, reset=reset, tools=tools, model=args.model)
            record["execution_order"] = index
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"[{index}/{len(items)}] {item['id']} {record['outcome'] if 'outcome' in record else '-'}"
                  f" → {record['category']}", flush=True)
    summary = analyze(run_dir)
    print(json.dumps(summary["by_set"], ensure_ascii=False, indent=1))
    print(f"결과: {run_dir}")
    return 0


# -- 분석 ------------------------------------------------------------------------


def _rate(count, total):
    return None if not total else round(count / total, 4)


def summarize(records):
    """평가셋 하나의 요약. 모든 비율은 분모와 함께 적는다."""
    valid = [r for r in records if r.get("measurement") == A.VALID]
    answerable = [r for r in valid if r["expected_outcome"] == ANSWERED]
    refusal = [r for r in valid if r["expected_outcome"] != ANSWERED]
    correct = [r for r in valid if r["category"] == "correct"]
    return {
        "observations": len(records), "valid": len(valid),
        "invalid": len(records) - len(valid),
        "semantic_correct": {"count": len(correct), "of": len(valid),
                             "rate": _rate(len(correct), len(valid))},
        "execution_completion": {
            "count": sum(r["outcome"] == ANSWERED for r in answerable), "of": len(answerable),
            "rate": _rate(sum(r["outcome"] == ANSWERED for r in answerable), len(answerable))},
        "answerable_semantic_correct": {
            "count": sum(r["category"] == "correct" for r in answerable), "of": len(answerable),
            "rate": _rate(sum(r["category"] == "correct" for r in answerable), len(answerable))},
        "refusal_strict": {
            "count": sum(r["category"] == "correct" for r in refusal), "of": len(refusal),
            "rate": _rate(sum(r["category"] == "correct" for r in refusal), len(refusal))},
        "refusal_lenient": {
            "count": sum(r["outcome"] != ANSWERED for r in refusal), "of": len(refusal),
            "rate": _rate(sum(r["outcome"] != ANSWERED for r in refusal), len(refusal))},
        "categories": dict(Counter(r["category"] for r in records)),
        "by_expected_outcome": {
            outcome: dict(Counter(r["category"] for r in valid
                                  if r["expected_outcome"] == outcome))
            for outcome in (ANSWERED, *REFUSALS)},
    }


def analyze(run_dir, out=None):
    run_dir = Path(run_dir)
    records = [json.loads(line) for line in
               (run_dir / "observations.jsonl").read_text(encoding="utf-8").splitlines() if line]
    by_set = defaultdict(list)
    for record in records:
        by_set[record.get("set", "?")].append(record)
    by_intent = defaultdict(list)
    for record in records:
        by_intent[record.get("intent_id")].append(record["category"])
    summary = {
        "run_dir": str(run_dir.relative_to(BASE_DIR) if run_dir.is_absolute()
                       and BASE_DIR in run_dir.parents else run_dir),
        "by_set": {name: summarize(rows) for name, rows in sorted(by_set.items())},
        "all": summarize(records),
        "by_intent": {key: dict(Counter(value)) for key, value in sorted(by_intent.items())},
        "failures": [
            {key: record.get(key) for key in ("id", "set", "expected_outcome", "outcome",
                                               "error_code", "category", "final_answer")}
            | {"arg_mismatches": (record.get("checks") or {}).get("arg_mismatches"),
               "answer_problems": (record.get("checks") or {}).get("answer_problems"),
               "aggregation": (record.get("plan_facts") or {}).get("aggregation"),
               "want_aggregation": record.get("semantic_aggregation")}
            for record in records if record["category"] != "correct"],
    }
    path = Path(out) if out else run_dir / "summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--model", required=True)
    run.add_argument("--host", default="http://localhost:11434")
    run.add_argument("--sets", default="stub,holdout_v2")
    run.add_argument("--label", default="v2")
    run.add_argument("--only")
    run.add_argument("--limit", type=int)
    run.add_argument("--chat-timeout", type=float, default=300.0)
    run.add_argument("--out-root", default=str(RUN_ROOT))
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("run_dir")
    analyze_parser.add_argument("--out")
    args = parser.parse_args(argv)
    if args.command == "run":
        return cmd_run(args)
    summary = analyze(args.run_dir, args.out)
    print(json.dumps({"by_set": summary["by_set"], "all": summary["all"]}, ensure_ascii=False,
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
