# -*- coding: utf-8 -*-
"""flat(H0) vs structured(S1) 집계 grounding을 같은 조건에서 비교한다.

같은 모델·provider·옵션에서 두 grounding 계약만 바꾼다. 관측마다 모델을 내려 이전
요청의 서버 상태를 없애고(``OllamaStateReset``), cold load를 확인하지 못한 관측은
무효로 적는다. 질문마다 두 arm의 순서를 번갈아 바꾼다(짝수 번째 질문 flat 먼저).

실행은 결정적 계층 전체(합성 → 검증 → lowering → mock 실행 → 답변)를 production
pipeline 그대로 탄다. Tool provider는 mock이므로 수치의 정답 여부가 아니라 "질문과
같은 계산을 실행했는가"를 의미 계획·조건·결과 종류로 채점한다. 의미 계획이 맞으면
그 뒤의 계산이 맞다는 것은 결정적 계층 테스트(test_geoflow_aggregation_graph)가 본다.

    python structured_grounding_eval.py run QUESTIONS.yaml --name NAME
    python structured_grounding_eval.py score RUN_DIR

측정 원칙은 evaluation/prompt_ab/variants/structured_grounding_decision_rule.md에
측정 전에 고정했다.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import yaml  # noqa: E402

from evaluate_prompt_ab import (  # noqa: E402
    COLD_LOAD_MIN_MS,
    OllamaStateReset,
    RecordingClient,
)
from evaluation_records import write_analysis, write_new  # noqa: E402
from geoflow import structured_grounding  # noqa: E402
from geoflow.aggregation import UNSPECIFIED  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from ollama_client import OllamaClient, chat_options  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
RESULT_DIR = BASE_DIR / "evaluation" / "structured_grounding"
REFERENCE_DATE = date(2026, 9, 25)
OPTIONS = {"temperature": 0}
ARMS = (structured_grounding.FLAT, structured_grounding.STRUCTURED)
#: arm 이름 = 집계 grounding 계약[+cc]. +cc는 조건 보존 기능(condition_check)을 켠다.
CONDITION_SUFFIX = "+cc"
#: 이 파일의 score()(v1 채점). taxi_type all 정규화를 correction_quality에 넣은 판이다.
#: 새 채점 의미(해석·요청·provider 분리)는 condition_scoring.py(v2)가 맡는다.
LEGACY_SCORER_VERSION = "v1.1"


def parse_arm(arm):
    mode, _, flag = arm.partition("+")
    if mode not in ARMS or flag not in ("", "cc"):
        raise ValueError(f"알 수 없는 arm: {arm}")
    return mode, flag == "cc"


def executed_conditions(run):
    measure = [hop for hop in run.hop_log if hop.get("phase", "tool") == "tool"
               and hop.get("tool") not in ("get_place_scope", "get_scope_name")]
    return {
        "measure_calls": len(measure),
        "dates": sorted({hop["arguments"].get("date") for hop in measure} - {None}),
        "taxi_types": sorted({hop["arguments"].get("taxi_type") for hop in measure} - {None}),
        "place_lookups": [hop["arguments"].get("name") for hop in run.hop_log
                          if hop.get("tool") == "get_place_scope"],
    }


def load_questions(path):
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return document, document["questions"]


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tool_executor():
    from tests.test_geoflow_composition import new_tool_executor
    return new_tool_executor()


# -- 관측 -------------------------------------------------------------------


def observe(item, arm, *, host, model, timeout, reset):
    outcome = reset.reset() if reset is not None else None
    record = {"id": item["id"], "arm": arm, "question": item["question"],
              "reset": None if outcome is None else {
                  "succeeded": outcome.succeeded, "detail": outcome.detail,
                  "duration_ms": outcome.duration_ms}}
    if outcome is not None and not outcome.succeeded:
        return {**record, "measurement": "invalid", "invalid_reason": "reset_failed"}
    client = RecordingClient(OllamaClient(host, model, chat_options(OPTIONS, None),
                                          chat_timeout=timeout))
    mode, condition_check = parse_arm(arm)
    pipeline = GeoFlowPipeline.create(client=client, tool_executor=_tool_executor(),
                                      model=model, aggregation_grounding=mode,
                                      clock=lambda: REFERENCE_DATE,
                                      condition_check=condition_check)
    record["prompt_sha256"] = _sha(pipeline.planner.system_prompt())
    started = time.perf_counter()
    try:
        run = pipeline.run(item["question"])
        record.update(
            outcome=run.outcome, stage=run.stage, error=run.error,
            final_answer=run.final_answer, grounding=run.grounding, plan=run.plan,
            lowering=(run.execution_plan or {}).get("lowering"),
            tool_calls=sum(1 for hop in run.hop_log if hop.get("phase", "tool") == "tool"),
            repair_count=run.repair_count, durations=run.durations,
            condition_audit=run.condition_audit, condition_trace=run.condition_trace,
            verification=run.verification,
            date_semantics=(run.execution_plan or {}).get("date_semantics"),
            executed=executed_conditions(run),
        )
    except Exception as error:  # noqa: BLE001 - 관측 결과로 남긴다
        record.update(outcome="crash", error={"code": "CRASH",
                                              "detail": f"{type(error).__name__}: {error}"})
    record["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    record["llm_calls"] = client.calls
    first = client.calls[0].get("load_duration_ms") if client.calls else None
    if reset is not None and (first is None or first < COLD_LOAD_MIN_MS):
        record.update(measurement="invalid", invalid_reason="cold_load_unverified")
    elif any(call.get("error") and "imeout" in call["error"] for call in client.calls):
        record.update(measurement="invalid", invalid_reason="timeout")
    else:
        record["measurement"] = "valid"
    return record


def run(questions_path, *, name, host, model, timeout, reset_state=True, repeat=1,
        arms=ARMS):
    document, questions = load_questions(questions_path)
    arms = tuple(arms)
    stamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d_%H%M%S")
    out_dir = RESULT_DIR / f"{stamp}_{name}"
    out_dir.mkdir(parents=True, exist_ok=False)
    reset = OllamaStateReset(host, model) if reset_state else None
    prompts = {arm: _sha(GeoFlowPipeline.create(
        client=type("C", (), {"model": model})(), tool_executor=_tool_executor(),
        aggregation_grounding=parse_arm(arm)[0]).planner.system_prompt()) for arm in arms}
    meta = {
        "name": name, "created_at": stamp, "model": model, "host": host,
        "options": OPTIONS, "chat_timeout": timeout, "reference_date": str(REFERENCE_DATE),
        "questions_file": str(questions_path), "questions_sha256": _sha(
            Path(questions_path).read_text(encoding="utf-8")),
        "questions_role": document.get("role"), "prompt_sha256": prompts,
        "arms": list(arms),
        "order": "question i: arms를 i만큼 회전한 순서(2 arm이면 짝수 flat 먼저)",
        "repeat": repeat, "reset_state": reset_state,
        "provider": os.environ.get("ASSISTANT_TOOL_PROVIDER"),
        "tims_contract": "DEFAULT_CONTRACT(geoflow/tims_contract.py)",
        "code_sha256": {path: _sha(Path(BASE_DIR / path).read_text(encoding="utf-8"))
                        for path in ("geoflow/conditions.py", "geoflow/compiler.py",
                                     "geoflow/tims_contract.py", "geoflow/pipeline.py",
                                     "condition_scoring.py")},
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    with open(out_dir / "observations.jsonl", "x", encoding="utf-8") as handle:
        for repetition in range(repeat):
            for index, item in enumerate(questions):
                shift = index % len(arms)
                order = arms[shift:] + arms[:shift]
                for position, arm in enumerate(order):
                    record = observe(item, arm, host=host, model=model, timeout=timeout,
                                     reset=reset)
                    record.update(repetition=repetition, question_index=index,
                                  position=position)
                    handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    handle.flush()
                    print(f"{item['id']} {arm:10} {record.get('outcome')} "
                          f"{(record.get('error') or {}).get('code')} "
                          f"{record['measurement']} {record['elapsed_ms']:.0f}ms", flush=True)
    return out_dir


# -- 채점 -------------------------------------------------------------------


def grounding_plan(grounding):
    """최종 grounding의 집계 의미. v2 라벨과 같은 모양."""
    if not grounding:
        return "NO_GROUNDING"
    spec = grounding.get("aggregation") or {}
    if spec.get("bucket") is None:
        return None if spec.get("inner") is None else {"final": spec["inner"]}
    plan = {"bucket": spec["bucket"], "inner": spec.get("inner") or UNSPECIFIED}
    if spec.get("select"):
        plan["select"] = spec["select"]
    else:
        plan["final"] = spec.get("outer")
    return plan


def grounding_conditions(grounding):
    if not grounding:
        return None
    factors = grounding.get("factors") or {}
    conditions = {key: factors[key] for key in ("date", "taxi_type") if key in factors}
    if conditions.get("taxi_type") == "all":
        conditions.pop("taxi_type")
    places = sorted(
        (item.get("value") or {}).get("name") if isinstance(item.get("value"), dict)
        else item.get("value")
        for item in grounding.get("concepts") or []
        if item.get("concept") == "LOCATION" and item.get("role") != "MEASURE"
        and item.get("value")
    )
    if places:
        conditions["place"] = places
    return conditions


def grounding_od(grounding):
    roles = {}
    for item in (grounding or {}).get("concepts") or []:
        role = (item.get("attributes") or {}).get("od_role")
        value = item.get("value")
        if role and isinstance(value, dict):
            roles[role] = value.get("name")
    return roles


def condition_status(conditions, want):
    """조건마다 ok | missing | added | changed. grounding이 없으면 not_judgeable."""
    if conditions is None:
        return {key: "not_judgeable" for key in ("date", "taxi_type", "place")}
    status = {}
    for key in ("date", "taxi_type", "place"):
        got, wanted = conditions.get(key), want.get(key)
        if got == wanted:
            status[key] = "ok" if wanted is not None else "absent_ok"
        elif wanted is None:
            status[key] = "added"
        elif got is None:
            status[key] = "missing"
        else:
            status[key] = "changed"
    return status


def correction_quality(record, want):
    """조건 보정이 맞았는지. 보정 전 LLM 값과 보정 후 값을 기대 조건과 비교한다."""
    def normal(key, value):
        # 라벨은 taxi_type all(전체 택시)을 조건 없음과 같게 적는다. grounding_conditions와
        # 같은 정규화다. cond_v1_4arms 첫 채점에는 이 정규화가 없었다(판정은 첫 채점 기준).
        return None if key == "taxi_type" and value == "all" else value

    good, bad = 0, 0
    for item in ((record.get("condition_audit") or {}).get("corrections") or []):
        key = item["condition"]
        wanted, before, after = want.get(key), normal(key, item.get("from")), normal(
            key, item.get("to"))
        if before == after:
            continue
        if after == wanted and before != wanted:
            good += 1
        elif before == wanted and after != wanted:
            bad += 1
    return good, bad


def judge(record, expected):
    plan = grounding_plan(record.get("grounding"))
    conditions = grounding_conditions(record.get("grounding"))
    want_conditions = dict(expected.get("conditions") or {})
    want_od = want_conditions.pop("od", None)
    if "place" in want_conditions:
        want_conditions["place"] = sorted(
            want_conditions["place"] if isinstance(want_conditions["place"], list)
            else [want_conditions["place"]])
    missing = [key for key, value in want_conditions.items()
               if (conditions or {}).get(key) != value]
    extra = [key for key in (conditions or {}) if key not in want_conditions]
    plan_ok = plan == expected.get("plan")
    od_ok = want_od is None or grounding_od(record.get("grounding")) == want_od
    conditions_ok = conditions is not None and not missing and not extra and od_ok
    status = condition_status(conditions, want_conditions)
    good_fix, bad_fix = correction_quality(record, want_conditions)
    outcome = record.get("outcome")
    want = expected["outcome"]
    answered = outcome == "answered"
    return {
        "plan": plan, "plan_ok": plan_ok, "conditions": conditions,
        "conditions_ok": conditions_ok, "missing_conditions": missing,
        "extra_conditions": extra, "condition_status": status, "od_ok": od_ok,
        "date_ok": status["date"] in ("ok", "absent_ok"),
        "good_corrections": good_fix, "bad_corrections": bad_fix,
        "correct_answer": answered and want == "answered" and plan_ok and conditions_ok,
        "silent_wrong": answered and not (want == "answered" and plan_ok and conditions_ok),
        "answerable_refused": want == "answered" and not answered,
        "clarification_ok": want == "needs_clarification" and outcome == "needs_clarification",
        "outcome_ok": outcome == want,
        "execution_failure": outcome in ("failed", "crash"),
    }


def score(run_dir):
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    _document, questions = load_questions(meta["questions_file"])
    expected = {item["id"]: item["expected"] for item in questions}
    rows = [json.loads(line) for line in open(run_dir / "observations.jsonl",
                                              encoding="utf-8")]
    judged = []
    for row in rows:
        entry = {"id": row["id"], "arm": row["arm"], "measurement": row["measurement"],
                 "invalid_reason": row.get("invalid_reason"),
                 "outcome": row.get("outcome"), "code": (row.get("error") or {}).get("code"),
                 "tool_calls": row.get("tool_calls"), "elapsed_ms": row.get("elapsed_ms"),
                 "llm_calls": len(row.get("llm_calls") or []),
                 "expected": expected[row["id"]]}
        if row["measurement"] == "valid":
            entry.update(judge(row, expected[row["id"]]))
        judged.append(entry)
    # 한 arm이라도 무효인 질문은 두 arm 모두에서 뺀다(짝 비교).
    invalid_ids = {row["id"] for row in judged if row["measurement"] != "valid"}
    summary = {"invalid_questions": sorted(invalid_ids), "arms": {}}
    for arm in meta.get("arms") or ARMS:
        mine = [row for row in judged if row["arm"] == arm and row["id"] not in invalid_ids]
        n = len(mine)
        answerable = [r for r in mine if r["expected"]["outcome"] == "answered"]
        ambiguous = [r for r in mine if r["expected"]["outcome"] == "needs_clarification"]
        with_conditions = [r for r in mine if r["expected"].get("conditions")]
        summary["arms"][arm] = {
            "observations": n,
            "correct_answer": sum(r["correct_answer"] for r in mine),
            "plan_ok": sum(r["plan_ok"] for r in mine),
            "silent_wrong": sum(r["silent_wrong"] for r in mine),
            "answerable": len(answerable),
            "answerable_refused": sum(r["answerable_refused"] for r in answerable),
            "ambiguous": len(ambiguous),
            "clarification_ok": sum(r["clarification_ok"] for r in ambiguous),
            "with_conditions": len(with_conditions),
            "condition_missing": sum(bool(r["missing_conditions"]) for r in with_conditions),
            "condition_extra": sum(bool(r["extra_conditions"]) for r in mine),
            "execution_failure": sum(r["execution_failure"] for r in mine),
            "outcome_ok": sum(r["outcome_ok"] for r in mine),
            "conditions_ok": sum(r["conditions_ok"] for r in mine),
            "grounding_rejected": sum(r["conditions"] is None for r in mine),
            "condition_status": {
                key: dict(Counter(r["condition_status"][key] for r in mine))
                for key in ("date", "taxi_type", "place")},
            "od_wrong": sum(not r["od_ok"] for r in mine),
            "date_ok": sum(r["date_ok"] for r in mine),
            "good_corrections": sum(r["good_corrections"] for r in mine),
            "bad_corrections": sum(r["bad_corrections"] for r in mine),
            "outcomes": dict(Counter(r["outcome"] for r in mine)),
            "tool_calls_total": sum(r["tool_calls"] or 0 for r in mine),
            "llm_calls_total": sum(r["llm_calls"] for r in mine),
            "elapsed_ms_median": sorted(r["elapsed_ms"] for r in mine)[n // 2] if n else None,
        }
    # 처음 채점한 파일은 측정 기록이다. 이미 있으면 덮어쓰지 않고 analyses/ 아래 새 id로
    # 쓴다(evaluation_records). 예전의 *_rescored 접미사는 두 번째 재채점에서 덮어썼다.
    if not (run_dir / "summary.json").exists():
        write_new(run_dir / "judged.json", judged)
        write_new(run_dir / "summary.json", summary)
    else:
        write_analysis(
            run_dir, analysis_id=f"legacy-{LEGACY_SCORER_VERSION}",
            outputs={"judged.json": judged, "summary.json": summary},
            scorer={"name": "structured_grounding_eval.score",
                    "version": LEGACY_SCORER_VERSION, "source": __file__},
            config={}, inputs=[run_dir / "observations.jsonl", meta["questions_file"]],
        )
    return summary, judged


def replay_score(run_dir, *, condition_check):
    """기록된 LLM 원문을 현재 코드로 다시 돌려 채점한다. LLM 호출 없음.

    재생에서 녹화에 없는 LLM 호출이 필요해지면(재질의 경로가 달라짐) 그 관측은
    ``not_replayable``로 따로 센다.
    """
    from failure_census import ReplayClient

    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    _document, questions = load_questions(meta["questions_file"])
    expected = {item["id"]: item["expected"] for item in questions}
    rows = []
    for line in open(run_dir / "observations.jsonl", encoding="utf-8"):
        record = json.loads(line)
        if record["measurement"] != "valid":
            continue
        arm = record["arm"].split("+")[0]
        client = ReplayClient([c.get("content") or "" for c in record.get("llm_calls") or []])
        pipeline = GeoFlowPipeline.create(client=client, tool_executor=_tool_executor(),
                                          aggregation_grounding=arm,
                                          clock=lambda: REFERENCE_DATE,
                                          condition_check=condition_check)
        run = pipeline.run(record["question"])
        replayed = {"outcome": run.outcome, "grounding": run.grounding,
                    "error": run.error}
        detail = str((run.error or {}).get("detail", ""))
        entry = {"id": record["id"], "arm": record["arm"],
                 "not_replayable": "replay exhausted" in detail,
                 "outcome": run.outcome, "code": (run.error or {}).get("code"),
                 "expected": expected[record["id"]],
                 "corrections": (run.condition_audit or {}).get("corrections"),
                 **judge(replayed, expected[record["id"]])}
        rows.append(entry)
    return rows


def summarize_rows(rows):
    summary = {}
    for arm in sorted({row["arm"] for row in rows}):
        mine = [row for row in rows if row["arm"] == arm and not row["not_replayable"]]
        answerable = [r for r in mine if r["expected"]["outcome"] == "answered"]
        ambiguous = [r for r in mine if r["expected"]["outcome"] == "needs_clarification"]
        summary[arm] = {
            "observations": len(mine),
            "not_replayable": sum(row["not_replayable"] for row in rows if row["arm"] == arm),
            "correct_answer": sum(r["correct_answer"] for r in mine),
            "plan_ok": sum(r["plan_ok"] for r in mine),
            "conditions_ok": sum(r["conditions_ok"] for r in mine),
            "silent_wrong": sum(r["silent_wrong"] for r in mine),
            "answerable_refused": sum(r["answerable_refused"] for r in answerable),
            "clarification_ok": sum(r["clarification_ok"] for r in ambiguous),
            "execution_failure": sum(r["execution_failure"] for r in mine),
            "outcomes": dict(Counter(r["outcome"] for r in mine)),
        }
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("questions")
    run_parser.add_argument("--name", required=True)
    run_parser.add_argument("--model", default="qwen3:8b")
    run_parser.add_argument("--host", default="http://localhost:11434")
    run_parser.add_argument("--timeout", type=float, default=300.0)
    run_parser.add_argument("--repeat", type=int, default=1)
    run_parser.add_argument("--no-reset", action="store_true")
    run_parser.add_argument("--arms", default=",".join(ARMS),
                            help="쉼표로 구분. 예: flat,flat+cc,structured,structured+cc")
    score_parser = sub.add_parser("score")
    score_parser.add_argument("run_dir")
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("run_dir")
    replay_parser.add_argument("--condition-check", choices=("off", "on"), default="off")
    replay_parser.add_argument("--out")
    args = parser.parse_args(argv)
    if args.command == "replay":
        rows = replay_score(args.run_dir, condition_check=args.condition_check == "on")
        summary = summarize_rows(rows)
        if args.out:
            with open(args.out, "x", encoding="utf-8") as handle:
                json.dump({"summary": summary, "rows": rows}, handle, ensure_ascii=False,
                          indent=2, default=str)
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return
    if args.command == "run":
        out = run(args.questions, name=args.name, host=args.host, model=args.model,
                  timeout=args.timeout, reset_state=not args.no_reset, repeat=args.repeat,
                  arms=args.arms.split(","))
        print(out)
        summary, _ = score(out)
    else:
        summary, _ = score(args.run_dir)
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
