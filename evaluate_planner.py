# -*- coding: utf-8 -*-
"""GeoFlow Planner의 concept grounding 품질을 모델별로 측정한다.

예전에는 "질문에 맞는 template을 골랐는가" 하나를 쟀다. 지금 Planner는
template을 고르지 않으므로, 대신 논문의 단계 구분을 따라 나눠서 잰다.

    concept / subtype / role 정확도   grounding 단계
    macro coverage / recall           macro retrieval + composition 단계
    graph validation pass rate        G1~G6
    operator mapping 정확도           factorization 단계
    execution success                 실제 Tool 실행(--execute)

Tool 실행은 기본적으로 하지 않으므로 gazetteer의 NOT_FOUND 같은 잡음을 섞지
않고 semantic parsing 품질만 잴 수 있다.

사용법:
    python evaluate_planner.py --model qwen3:8b --model gemma4:12b
    python evaluate_planner.py --all-models --repeat 3 --execute

정답 라벨은 Query YAML의 expected_concepts / expected_macros /
expected_operators에서 읽는다.
"""

import argparse
import json
import os
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from agent_graph import extract_scopes
from build import build
from geoflow import validator as geoflow_validator
from geoflow.compiler import compile_plan
from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError
from geoflow.grounding import OD_ROLE
from geoflow.executor import STATUS_OK, execute_plan
from geoflow.macros import MacroLibrary
from geoflow.planner import NO_TEMPLATE, GeoFlowPlanner
from geoflow.repair import decide as decide_repair
from geoflow.types import CoreConcept
from ollama_client import (
    THINK_CHOICES,
    OllamaClient,
    chat_options,
    resolve_chat_timeout,
    resolve_think,
)
from query_loader import QueryValidationError, load_queries
from tool_executor import ToolExecutor
from tool_handlers import get_tool_handlers

BASE_DIR = Path(__file__).resolve().parent
RESULT_DIR = BASE_DIR / "evaluation" / "planner_accuracy"
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_OPTIONS = {"temperature": 0}

#: 지원 범위 밖이라 Planner가 거부해야 하는 질의의 정답 라벨.
#: 틀린 계획을 만드는 것보다 거부가 낫다는 설계 주장을 측정한다.
NO_TEMPLATE_LABEL = NO_TEMPLATE

#: 계획을 만들지 않고 물러선 경우의 오류 코드.
#: Planner가 스스로 밝힌 경우와, 합성 단계에서 근거가 모자라 만들지 못한
#: 경우를 모두 포함한다. 둘 다 "틀린 계획을 만들지 않았다"는 같은 결과다.
REFUSAL_CODES = frozenset({
    "UNSUPPORTED_QUESTION",
    "UNSUPPORTED_MEASURE",
    "NO_MEASURE",
    "NO_MACRO",
    "NO_OPERATOR",
    "AMBIGUOUS_PORT",
    "AMBIGUOUS_OPERATOR",
    "UNUSED_CONCEPT",
})


def _now_local():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def _place_name(value):
    if isinstance(value, dict):
        return (value.get("name") or "").strip()
    return str(value or "").strip()


def check_concept_roles(question, grounding):
    """승차/하차 개념이 발화 순서와 뒤바뀌지 않았는지 확인한다.

    논문이 지적한 대표적 실패 모드다. 판정할 근거가 없으면 ``None``.
    """
    by_role = {}
    for concept in grounding.concepts:
        role = concept.attributes.get(OD_ROLE)
        if role in ("pickup", "dropoff"):
            by_role.setdefault(role, concept)
    if len(by_role) < 2:
        return None
    pickup = _place_name(by_role["pickup"].value)
    dropoff = _place_name(by_role["dropoff"].value)
    if not pickup or not dropoff:
        return None
    pickup_at = question.find(pickup)
    dropoff_at = question.find(dropoff)
    if pickup_at < 0 or dropoff_at < 0 or pickup_at == dropoff_at:
        return None
    return pickup_at < dropoff_at


# -- 채점 -------------------------------------------------------------------


def concept_keys(grounding):
    """grounding 개념을 (concept, subtype, role) 문자열로 편다.

    id는 모델이 정하는 이름이라 정답과 맞출 수 없으므로 의미만 비교한다.
    """
    return [
        f"{item.concept.value}/{item.subtype}:{item.role.value}"
        for item in grounding.concepts
    ]


def _levels(key):
    """채점 단계별로 잘라 낸 key. 상위 단계가 맞으면 하위도 비교한다."""
    types, _, role = key.partition(":")
    concept, _, subtype = types.partition("/")
    return concept, f"{concept}/{subtype}", key


def score_concepts(predicted, expected):
    """concept / subtype / role 각각의 일치 개수를 센다.

    같은 개념이 여러 개인 질문(출발지·도착지)이 있으므로 집합이 아니라
    다중집합으로 비교한다.
    """
    result = {}
    for index, name in enumerate(("concept", "subtype", "role")):
        predicted_counter = Counter(_levels(key)[index] for key in predicted)
        expected_counter = Counter(_levels(key)[index] for key in expected)
        matched = sum((predicted_counter & expected_counter).values())
        result[name] = {
            "matched": matched,
            "expected": sum(expected_counter.values()),
            "predicted": sum(predicted_counter.values()),
        }
    return result


def score_sequence(predicted, expected):
    """macro/operator 목록의 재현율과 완전 일치 여부."""
    predicted_counter = Counter(predicted)
    expected_counter = Counter(expected)
    matched = sum((predicted_counter & expected_counter).values())
    return {
        "matched": matched,
        "expected": sum(expected_counter.values()),
        "predicted": sum(predicted_counter.values()),
        "exact": predicted_counter == expected_counter,
    }


def _empty_score():
    return {"matched": 0, "expected": 0, "predicted": 0}


def evaluate_model(model, queries, *, host, chat_timeout, repeat, verbose,
                   think=None, num_predict=None, execute=False,
                   tool_executor=None):
    """모델 하나로 전체 Query의 grounding과 합성을 측정한다."""
    client = OllamaClient(
        host,
        model,
        chat_options(OLLAMA_OPTIONS, num_predict),
        chat_timeout=chat_timeout,
        think=think,
    )
    planner = GeoFlowPlanner(client=client)
    system_prompt_chars = len(planner.system_prompt())
    composer = MacroComposer(MacroLibrary.from_directory())
    available_tools = None if tool_executor is None else tool_executor.tool_names

    records = []
    for item in queries:
        expected_concepts = list(item.get("expected_concepts") or [])
        expected_macros = list(item.get("expected_macros") or [])
        expected_operators = list(item.get("expected_operators") or [])
        refusal_expected = NO_TEMPLATE_LABEL in expected_macros
        for attempt in range(1, repeat + 1):
            started_at = time.perf_counter()
            record = {
                "id": item["id"],
                "repeat_index": attempt,
                "status": "OK",
                "error": None,
                "stage": "planner",
                "concepts": [],
                "factors": {},
                "macros": [],
                "operators": [],
                "concept_score": {
                    name: _empty_score()
                    for name in ("concept", "subtype", "role")
                },
                "macro_score": _empty_score(),
                "operator_score": _empty_score(),
                "validated": False,
                "executed": None,
                # 실행 실패가 재계획으로 복구 가능한 종류였는지. 장소 조회
                # 실패는 런타임이 한 번 고쳐 다시 시도하지만, 이 측정은
                # 첫 계획을 그대로 실행하므로 여기서 구분해 둔다.
                "execution_retryable": None,
                "refused": False,
                "role_order_ok": None,
                # 계획 단계 재질의. 파이프라인과 같은 1회 규칙을 따른다.
                "od_qualified_initial": None,
                "repair_kind": None,
                "repair_attempted": False,
                "repair_succeeded": False,
                "repair_error": None,
                "unsupported_relation": False,
                # 지연을 단계별로 나눠 본다. 총합만 보면 한 건의 이상치가
                # 전체 평균을 지배하는 것을 알 수 없다.
                "initial_planner_ms": 0.0,
                "repair_planner_ms": 0.0,
                "planner_calls": 0,
                "output_chars": 0,
                "duration_ms": 0.0,
            }
            try:
                output = planner.plan(item["question"])
                record["initial_planner_ms"] = output.duration_ms
                record["planner_calls"] = 1
                record["output_chars"] = len(output.raw_text)
                grounding = output.grounding
                record["concepts"] = concept_keys(grounding)
                record["factors"] = dict(grounding.factors)
                record["role_order_ok"] = check_concept_roles(
                    item["question"], grounding,
                )
                record["concept_score"] = score_concepts(
                    record["concepts"], expected_concepts,
                )
                record["od_qualified_initial"] = _od_qualified(grounding)

                record["stage"] = "composition"
                plan = _compose_with_repair(
                    composer, planner, item["question"], output, record,
                )
                record["macros"] = list(plan.applied_macros)
                record["operators"] = [
                    item.operator for item in plan.transformations
                ]
                record["macro_score"] = score_sequence(
                    record["macros"], expected_macros,
                )
                record["operator_score"] = score_sequence(
                    record["operators"], expected_operators,
                )

                record["stage"] = "validation"
                report = geoflow_validator.validate(
                    plan, available_tools=available_tools,
                )
                record["validated"] = report.ok
                if not report.ok:
                    record["status"] = "VALIDATION_FAILED"
                    record["error"] = "; ".join(
                        error["message"] for error in report.errors
                    )
                elif execute and tool_executor is not None:
                    record["stage"] = "execution"
                    # 사용자가 발화에 적은 scope는 실행 시점에도 known scope로
                    # 넘겨야 한다. 파이프라인이 하는 것과 같은 처리이며,
                    # 빠뜨리면 provenance gate가 정상 질의를 막는다.
                    result = execute_plan(
                        compile_plan(plan),
                        tool_executor,
                        known_scopes=set(extract_scopes(item["question"])),
                    )
                    record["executed"] = result.status == STATUS_OK
                    if not record["executed"]:
                        record["status"] = result.status
                        error = result.error or {}
                        record["error"] = error.get("detail")
                        record["execution_retryable"] = bool(
                            (error.get("context") or {}).get("retryable")
                        )
                else:
                    record["stage"] = "done"
            except GeoFlowError as error:
                record["status"] = error.code
                record["error"] = error.detail
                if error.code in REFUSAL_CODES:
                    # 지원 범위 밖임을 스스로 인정한 경우도 하나의 판정 결과다.
                    record["refused"] = True
                    record["macros"] = [NO_TEMPLATE_LABEL]
                    record["macro_score"] = score_sequence(
                        record["macros"], expected_macros,
                    )
            except Exception as error:  # noqa: BLE001 - 모델 오류도 기록 대상
                record["status"] = "CLIENT_ERROR"
                record["error"] = f"{type(error).__name__}: {error}"
            record["duration_ms"] = round(
                (time.perf_counter() - started_at) * 1000, 3
            )
            # 종합 판정은 "실행 가능한 올바른 그래프가 나왔는가"만 본다.
            # concept/subtype/role 정확도를 여기에 다시 곱하지 않는 이유는
            # 설계상 질문에 드러나지 않아도 되는 개념이 있기 때문이다.
            # "평균 속도"라는 질문에 passage를 적지 않아도 registry가 유일하게
            # 결정할 수 있으므로 합성은 성공한다. 그것을 틀렸다고 셀 수 없다.
            # grounding 품질은 별도 지표로 따로 본다.
            record["correct"] = bool(
                record["macro_score"].get("exact")
                and record["operator_score"].get("exact")
                and record["validated"]
            )
            if refusal_expected:
                # 라벨이 NONE이면 "실행 가능한 계획이 만들어지지 않는 것"이
                # 정답이다. Planner가 거부했든 합성이 포기했든 같다.
                record["correct"] = not record["validated"]
            record["system_prompt_chars"] = system_prompt_chars
            records.append(record)
            if verbose:
                mark = "O" if record["correct"] else "X"
                shown = " + ".join(record["macros"]) or record["status"]
                print(
                    f"  {mark} {item['id']:<36} "
                    f"{shown[:34]:<36} "
                    f"{record['duration_ms']:7.0f}ms"
                )
    return records


def _od_qualified(grounding):
    """초기 grounding의 장소에 승하차 구분이 붙어 있었는지.

    장소가 없으면 판정 대상이 아니므로 ``None``.
    """
    locations = [
        concept for concept in grounding.concepts
        if concept.concept == CoreConcept.LOCATION
        and concept.role.value != "MEASURE"
    ]
    if not locations:
        return None
    return all(OD_ROLE in concept.attributes for concept in locations)


def _compose_with_repair(composer, planner, question, output, record):
    """합성이 실패하면 파이프라인과 같은 규칙으로 한 번만 다시 묻는다.

    복구 가능 여부 판정과 허용 범위 검사는 런타임과 같은 코드를 쓴다.
    측정이 실제 동작과 어긋나지 않게 하기 위해서다.
    """
    try:
        return composer.compose(output.grounding)
    except GeoFlowError as error:
        decision = decide_repair(error)
        record["repair_kind"] = decision.kind
        if error.code == "AMBIGUOUS_LOCATION_RELATION" and not (
            decision.repairable
        ):
            record["unsupported_relation"] = True
        if not decision.repairable:
            raise
        record["repair_attempted"] = True
        try:
            repaired = planner.repair_planning_error(
                question, output, error=error, decision=decision,
            )
            record["repair_planner_ms"] = repaired.duration_ms
            record["planner_calls"] += 1
            record["output_chars"] += len(repaired.raw_text)
        except GeoFlowError as repair_error:
            record["repair_error"] = repair_error.code
            raise error from repair_error
        plan = composer.compose(repaired.grounding)
        record["repair_succeeded"] = True
        record["concepts_after_repair"] = concept_keys(repaired.grounding)
        record["factors_after_repair"] = dict(repaired.grounding.factors)
        return plan


def _median(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _ratio(matched, expected):
    return round(matched / expected, 4) if expected else 0.0


def summarize(records):
    total = len(records)
    correct = sum(1 for item in records if item["correct"])
    refused = sum(1 for item in records if item["refused"])
    failed = sum(
        1 for item in records
        if item["status"] not in ("OK", *REFUSAL_CODES)
    )
    roles = [
        item["role_order_ok"] for item in records
        if item["role_order_ok"] is not None
    ]
    executed = [item["executed"] for item in records if item["executed"] is not None]
    retryable = sum(1 for item in records if item["execution_retryable"])

    def level(name):
        matched = sum(item["concept_score"][name]["matched"] for item in records)
        expected = sum(
            item["concept_score"][name]["expected"] for item in records
        )
        return _ratio(matched, expected)

    macro_matched = sum(item["macro_score"]["matched"] for item in records)
    macro_expected = sum(item["macro_score"]["expected"] for item in records)
    operator_matched = sum(item["operator_score"]["matched"] for item in records)
    operator_expected = sum(
        item["operator_score"]["expected"] for item in records
    )
    return {
        "total": total,
        "correct": correct,
        "accuracy": _ratio(correct, total),
        "concept_accuracy": level("concept"),
        "subtype_accuracy": level("subtype"),
        "role_accuracy": level("role"),
        "macro_recall": _ratio(macro_matched, macro_expected),
        "macro_exact": _ratio(
            sum(1 for item in records if item["macro_score"].get("exact")),
            total,
        ),
        "operator_accuracy": _ratio(operator_matched, operator_expected),
        "validation_pass_rate": _ratio(
            sum(1 for item in records if item["validated"]), total,
        ),
        "execution_success_rate": (
            _ratio(sum(1 for item in executed if item), len(executed))
            if executed else None
        ),
        # 장소 조회 실패처럼 런타임이 재계획으로 복구하는 실패.
        # 이 측정은 첫 계획을 그대로 실행하므로 복구를 포함하지 않는다.
        "execution_retryable_failures": retryable,
        "refused": refused,
        "planner_error": failed,
        "repair_attempted": sum(
            1 for item in records if item["repair_attempted"]
        ),
        "repair_succeeded": sum(
            1 for item in records if item["repair_succeeded"]
        ),
        "relation_repair_attempted": sum(
            1 for item in records
            if item["repair_kind"] == "relation_qualifier"
            and item["repair_attempted"]
        ),
        "relation_repair_succeeded": sum(
            1 for item in records
            if item["repair_kind"] == "relation_qualifier"
            and item["repair_succeeded"]
        ),
        "factor_repair_attempted": sum(
            1 for item in records
            if item["repair_kind"] == "factor_completion"
            and item["repair_attempted"]
        ),
        "factor_repair_succeeded": sum(
            1 for item in records
            if item["repair_kind"] == "factor_completion"
            and item["repair_succeeded"]
        ),
        "unsupported_relations": sum(
            1 for item in records if item["unsupported_relation"]
        ),
        "role_order_checked": len(roles),
        "role_order_ok": sum(1 for item in roles if item),
        "mean_duration_ms": round(
            sum(item["duration_ms"] for item in records) / total, 1
        ) if total else 0.0,
        "median_initial_planner_ms": round(_median(
            [item["initial_planner_ms"] for item in records]
        ), 1),
        "mean_initial_planner_ms": round(
            sum(item["initial_planner_ms"] for item in records) / total, 1
        ) if total else 0.0,
        "total_repair_planner_ms": round(
            sum(item["repair_planner_ms"] for item in records), 1
        ),
        "planner_calls": sum(item["planner_calls"] for item in records),
        "mean_output_chars": round(
            sum(item["output_chars"] for item in records) / total, 1
        ) if total else 0.0,
        "system_prompt_chars": (
            records[0].get("system_prompt_chars", 0) if records else 0
        ),
    }


def print_report(results, query_ids):
    ids = list(query_ids)
    models = list(results)
    width = max((len(name) for name in ids), default=10) + 2

    print("\n" + "=" * 78)
    print("Macro 합성 정확도")
    print("=" * 78)
    header = "query".ljust(width) + "".join(
        name[:14].ljust(16) for name in models
    )
    print(header)
    print("-" * len(header))
    for query_id in ids:
        row = query_id.ljust(width)
        for model in models:
            picks = [
                item for item in results[model]["records"]
                if item["id"] == query_id
            ]
            hit = sum(1 for item in picks if item["correct"])
            if picks and hit == len(picks):
                cell = "O"
            elif hit == 0:
                shown = (
                    "+".join(picks[0]["macros"]) or picks[0]["status"]
                ) if picks else "-"
                cell = f"X {str(shown)[:12]}"
            else:
                cell = f"~ {hit}/{len(picks)}"
            row += cell.ljust(16)
        print(row)

    print("-" * len(header))
    print(
        "\n" + "모델".ljust(20) + "종합".ljust(12) + "concept".ljust(10)
        + "subtype".ljust(10) + "role".ljust(10) + "macro".ljust(10)
        + "operator".ljust(10) + "G1~G6".ljust(10) + "평균 지연"
    )
    print("-" * 100)
    for model in models:
        summary = results[model]["summary"]
        print(
            model.ljust(20)
            + f"{summary['correct']}/{summary['total']}".ljust(12)
            + f"{summary['concept_accuracy'] * 100:.0f}%".ljust(10)
            + f"{summary['subtype_accuracy'] * 100:.0f}%".ljust(10)
            + f"{summary['role_accuracy'] * 100:.0f}%".ljust(10)
            + f"{summary['macro_recall'] * 100:.0f}%".ljust(10)
            + f"{summary['operator_accuracy'] * 100:.0f}%".ljust(10)
            + f"{summary['validation_pass_rate'] * 100:.0f}%".ljust(10)
            + f"{summary['mean_duration_ms']:.0f} ms"
        )
    for model in models:
        summary = results[model]["summary"]
        if summary["execution_success_rate"] is not None:
            print(
                f"  {model}: 실행 성공률 "
                f"{summary['execution_success_rate'] * 100:.0f}% "
                f"(재계획으로 복구 가능한 실패 "
                f"{summary['execution_retryable_failures']}건 포함)"
            )


def load_latest_runs():
    """모델별로 가장 최근 실행 결과만 모은다.

    모델마다 지연 특성이 달라 한 번에 측정하기 어려우므로, 따로 실행한
    결과를 하나의 표로 다시 합칠 수 있게 한다.
    """
    latest = {}
    paths = sorted(
        RESULT_DIR.glob("*/planner_accuracy.json"),
        key=lambda item: item.stat().st_mtime,
    )
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for model, value in payload.get("models", {}).items():
            latest[model] = value
    return latest


def installed_models(host):
    client = OllamaClient(host, "", dict(OLLAMA_OPTIONS))
    return [
        item.get("name") or item.get("model")
        for item in client.list_models()
        if item.get("name") or item.get("model")
    ]


def check_labels(queries, library):
    """정답 라벨이 현재 macro library와 어긋나지 않는지 확인한다."""
    unlabeled = [
        item["id"] for item in queries if not item.get("expected_macros")
    ]
    if unlabeled:
        raise SystemExit(
            "expected_macros 라벨이 없는 Query가 있습니다: "
            + ", ".join(unlabeled)
        )
    unknown = sorted({
        name
        for item in queries
        for name in item["expected_macros"]
        if name not in library and name != NO_TEMPLATE_LABEL
    })
    if unknown:
        raise SystemExit(
            f"등록되지 않은 expected_macros입니다: {', '.join(unknown)}"
        )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="GeoFlow Planner concept grounding 정확도 측정",
    )
    parser.add_argument(
        "--model", action="append", help="측정할 모델(여러 번 지정 가능)",
    )
    parser.add_argument(
        "--all-models", action="store_true", help="설치된 모든 모델을 측정",
    )
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--query-file", default=str(BASE_DIR / "stub_query.yaml"))
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--chat-timeout", type=float, default=None)
    parser.add_argument(
        "--model-think",
        choices=THINK_CHOICES,
        default="auto",
        help="모델 thinking 사용 여부(기본: auto=모델 기본값)",
    )
    parser.add_argument(
        "--num-predict",
        type=int,
        default=None,
        help="Planner 응답 1회의 생성 토큰 상한(기본: 모델 기본값)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="합성된 계획을 실제로 실행해 성공률까지 측정",
    )
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help="새로 측정하지 않고 저장된 모델별 최신 결과를 하나의 표로 출력",
    )
    args = parser.parse_args(argv)
    if not args.aggregate and not args.model and not args.all_models:
        parser.error("--model, --all-models 또는 --aggregate가 필요합니다.")
    if args.repeat < 1:
        parser.error("--repeat는 1 이상이어야 합니다.")
    return args


def main(argv=None):
    args = parse_args(argv)

    if args.aggregate:
        results = load_latest_runs()
        if not results:
            raise SystemExit(f"저장된 측정 결과가 없습니다: {RESULT_DIR}")
        ids = list(dict.fromkeys(
            record["id"]
            for value in results.values()
            for record in value["records"]
        ))
        print_report(results, ids)
        return results

    chat_timeout = resolve_chat_timeout(args.chat_timeout)

    try:
        queries = load_queries(args.query_file)
    except QueryValidationError as error:
        raise SystemExit(str(error)) from error

    library = MacroLibrary.from_directory()
    check_labels(queries, library)

    # registry ↔ Tool 계약은 Tool을 실행하지 않더라도 여기서 확인해 둔다.
    tools, _prompt = build()
    tool_executor = ToolExecutor(tools=tools, handlers=get_tool_handlers())

    models = args.model or installed_models(args.ollama_host)
    results = {}
    for model in models:
        print(f"\n[{model}] Query {len(queries)}개 × repeat {args.repeat}")
        records = evaluate_model(
            model,
            queries,
            host=args.ollama_host,
            chat_timeout=chat_timeout,
            repeat=args.repeat,
            verbose=not args.quiet,
            think=resolve_think(args.model_think),
            num_predict=args.num_predict,
            execute=args.execute,
            tool_executor=tool_executor,
        )
        results[model] = {
            "records": records,
            "summary": summarize(records),
        }

    print_report(results, [item["id"] for item in queries])

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RESULT_DIR / _now_local().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir()
    payload = {
        "timestamp": _now_local().isoformat(),
        "query_file": str(args.query_file),
        "query_count": len(queries),
        "repeat": args.repeat,
        "executed": args.execute,
        "macros": list(library.names),
        "models": {
            model: {
                "summary": value["summary"],
                "records": value["records"],
            }
            for model, value in results.items()
        },
    }
    (run_dir / "planner_accuracy.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"\n결과 파일: {run_dir}")
    return results


if __name__ == "__main__":
    main()
