# -*- coding: utf-8 -*-
"""기록된 census LLM 응답을 현재 코드로 처음부터 다시 판정한다. LLM 호출 없음.

``failure_census.py``는 같은 코드에서의 재생을 전제로 관측 당시의 합성·검증 결과를
그대로 쓰고 실행만 다시 한다. 코드가 바뀌면 그 전제가 깨진다. 이 도구는 기록된
응답(첫 응답과 재질의 응답)만 가져와 grounding → 합성 → 검증 → Tool 인자 → mock 실행
→ 결과 등급을 모두 현재 코드로 다시 계산한다. 결과 등급의 정의는 failure_census의
``outcome_of``를 그대로 쓴다.

두 코드 버전을 비교하려면 같은 run을 각 버전의 작업 트리에서 이 스크립트로 돌린다.

    git worktree add /tmp/base <commit>
    cp geoflow_replay_compare.py /tmp/base/
    (cd /tmp/base && python geoflow_replay_compare.py <run_dir> --out base.json)
    python geoflow_replay_compare.py <run_dir> --out head.json
    python geoflow_replay_compare.py --diff base.json head.json

LLM 출력은 두 쪽에서 같으므로 차이는 LLM 이후 결정적 단계에서만 온다. 평가 셋은
이미 결과를 본 development census이며 새 holdout이 아니다.
"""

import argparse
import inspect
import json
import os
import sys
from collections import Counter

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_planner as E  # noqa: E402
import evaluate_prompt_ab as A  # noqa: E402
import failure_census as C  # noqa: E402
import paraphrase_corpus as P  # noqa: E402
from agent_graph import extract_scopes  # noqa: E402
from geoflow.compiler import compile_plan  # noqa: E402
from geoflow.composer import MacroComposer  # noqa: E402
from geoflow.errors import GeoFlowError  # noqa: E402
from geoflow.executor import STATUS_OK, execute_plan  # noqa: E402
from geoflow.macros import MacroLibrary  # noqa: E402

#: 평가 기준일. 현재 코드의 paraphrase_corpus와 같은 날이다(이전 코드에는 없다).
REFERENCE = getattr(P, "EVALUATION_REFERENCE_DATE", None)
KEPT = ("id", "intent_id", "question", "status", "validated", "macros", "operators",
        "final_tool", "final_tool_args", "expected_tool_args", "arg_mismatches",
        "final_category", "exec_status", "exec_code", "outcome", "correct",
        "factors", "factors_after_repair", "plan_aggregation", "run_outcome",
        "tool_calls", "measure_dates")

#: 결과 종류(현재 코드의 pipeline.outcome과 같은 기준). 이전 코드에는 없으므로 여기서 정한다.
CLARIFICATION_CODES = frozenset({"AMBIGUOUS_INNER_AGGREGATION"})


def _run_outcome(record):
    """answered / needs_clarification / unsupported / failed."""
    if record["exec_status"] == STATUS_OK:
        return "answered"
    code = record["exec_code"] if record["validated"] else record["status"]
    if code in CLARIFICATION_CODES:
        return "needs_clarification"
    try:
        from geoflow.pipeline import UNSUPPORTED_CODES
    except ImportError:
        UNSUPPORTED_CODES = frozenset()
    if code in UNSUPPORTED_CODES or code in E.REFUSAL_CODES:
        return "unsupported"
    return "failed"


def _compile(plan):
    parameters = inspect.signature(compile_plan).parameters
    if "date_policy" in parameters and CONDITION_CHECK:
        # production pipeline과 같다: condition_check 경로는 기간의 실행 의미를 보장한다.
        return compile_plan(plan, reference_date=REFERENCE, date_policy="guaranteed")
    if "reference_date" in parameters:
        return compile_plan(plan, reference_date=REFERENCE)
    return compile_plan(plan)


#: 조건 보존 기능을 켜고 재생할지(현재 코드에만 있다). main에서 정한다.
CONDITION_CHECK = False


def rederive(row, item, composer, executor, variant):
    contents = [call.get("content") or "" for call in row.get("llm_calls") or []]
    planner = A.FixedPromptPlanner(client=C.ReplayClient(contents), variant=variant)
    if CONDITION_CHECK:
        planner.condition_check = True
        planner.clock = lambda: REFERENCE
    plans = A.RecordingComposer(composer)
    record = E.evaluate_once(planner, plans, item)
    record.update(
        intent_id=row["intent_id"], question=item["question"],
        expected_macros=list(item.get("expected_macros") or []),
        expected_tool_args=dict(item.get("expected_tool_args") or {}),
        final_tool=None, final_tool_args=None, arg_mismatches=None,
        exec_status=None, exec_code=None, exec_retryable=None,
        plan_aggregation=None, tool_calls=None,
    )
    plan = plans.last_plan
    if plan is not None and hasattr(P, "plan_aggregation"):
        record["plan_aggregation"] = P.plan_aggregation(plan)
    if plan is not None and record["validated"]:
        try:
            record["final_tool"], record["final_tool_args"] = P.final_tool_call(plan)
        except Exception as error:  # noqa: BLE001 - 판정 결과로 남긴다
            record["tool_call_error"] = f"{type(error).__name__}: {error}"
        try:
            executed = execute_plan(_compile(plan), executor,
                                    known_scopes=set(extract_scopes(item["question"])))
            record["tool_calls"] = sum(1 for entry in executed.trace
                                       if entry.get("phase", "tool") == "tool")
            record["measure_dates"] = sorted({
                str((entry.get("arguments") or {}).get("date"))
                for entry in executed.trace
                if entry.get("phase", "tool") == "tool"
                and entry.get("tool") not in ("get_place_scope", "get_scope_name")})
            error = executed.error or {}
            record.update(exec_status=executed.status, exec_code=error.get("code"),
                          exec_retryable=bool((error.get("context") or {}).get("retryable")))
        except GeoFlowError as error:
            record.update(exec_status="COMPILE_ERROR", exec_code=error.code,
                          exec_retryable=False)
    if record["final_tool_args"] is not None:
        record["arg_mismatches"] = P.tool_arg_mismatches(
            record["expected_tool_args"], record["final_tool_args"],
            P.tool_defaults(record["final_tool"]))
    record["final_category"] = A.final_category(record)
    record["outcome"] = C.outcome_of(record)
    record["run_outcome"] = _run_outcome(record)
    return {key: record.get(key) for key in KEPT}


def run(run_dir):
    from tests.test_geoflow_composition import new_tool_executor

    meta, rows, report = A.load_run(run_dir)
    if not report.clean:
        raise SystemExit("무결성 문제로 재생하지 않는다")
    variants = {arm["variant"]: A.recorded_variant(arm) for arm in meta.get("arms", [])}
    items = {item["id"]: item for item in A.census_items()}
    composer = MacroComposer(MacroLibrary.from_directory())
    executor = new_tool_executor()
    out = []
    for row in rows:
        if row.get("measurement") != A.VALID:
            continue
        variant = variants.get(row["variant"]) or A.build_variant(row["variant"])
        out.append(rederive(row, items[row["id"]], composer, executor, variant))
    return {"run_id": meta["run_id"], "rows": out,
            "outcomes": dict(Counter(row["outcome"] for row in out))}


def diff(base_path, head_path):
    base = {row["id"]: row for row in json.load(open(base_path, encoding="utf-8"))["rows"]}
    head = {row["id"]: row for row in json.load(open(head_path, encoding="utf-8"))["rows"]}
    changed = []
    for key in sorted(base):
        a, b = base[key], head[key]
        if (a["outcome"], a["final_tool_args"]) != (b["outcome"], b["final_tool_args"]):
            changed.append({
                "id": key, "intent_id": a["intent_id"], "question": a["question"],
                "before": {k: a[k] for k in ("outcome", "status", "final_tool_args")},
                "after": {k: b[k] for k in ("outcome", "status", "final_tool_args")},
            })
    transitions = Counter(f"{c['before']['outcome']} -> {c['after']['outcome']}"
                          for c in changed)
    return {
        "observations": len(base),
        "before": dict(Counter(row["outcome"] for row in base.values())),
        "after": dict(Counter(row["outcome"] for row in head.values())),
        "changed": len(changed),
        "transitions": dict(transitions),
        "rows": changed,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", nargs="?")
    parser.add_argument("--out", help="결과 JSON 경로 (새 파일)")
    parser.add_argument("--diff", nargs=2, metavar=("BASE", "HEAD"))
    parser.add_argument("--condition-check", action="store_true")
    args = parser.parse_args(argv)
    global CONDITION_CHECK
    CONDITION_CHECK = args.condition_check
    result = diff(*args.diff) if args.diff else run(args.run_dir)
    if args.out:
        with open(args.out, "x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, default=str)
    view = {key: value for key, value in result.items() if key != "rows"}
    json.dump(view, sys.stdout, ensure_ascii=False, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
