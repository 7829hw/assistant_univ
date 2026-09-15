# -*- coding: utf-8 -*-
"""GeoFlow Planner의 template 선택 정확도를 모델별로 측정한다.

Tool을 실행하지 않고 Planner 호출만 반복하므로, gazetteer의 NOT_FOUND 같은
실행 단계 잡음을 섞지 않고 semantic parsing 품질만 잰다.

사용법:
    python evaluate_planner.py --model qwen3:8b --model gemma4:12b
    python evaluate_planner.py --all-models --repeat 3

정답 라벨은 Query YAML의 expected_template에서 읽는다.
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from build import build
from geoflow.errors import GeoFlowError
from geoflow.planner import GeoFlowPlanner
from geoflow.templates import TemplateRegistry
from ollama_client import OllamaClient, resolve_chat_timeout
from query_loader import QueryValidationError, load_queries
from tool_executor import ToolExecutor
from tool_handlers import get_tool_handlers

BASE_DIR = Path(__file__).resolve().parent
RESULT_DIR = BASE_DIR / "evaluation" / "planner_accuracy"
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_OPTIONS = {"temperature": 0}

#: 역할이 뒤바뀌면 안 되는 slot 쌍. 논문이 지적한 대표적 실패 모드다.
ORDERED_SLOT_PAIRS = (("origin", "destination"),)


def _now_local():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def _place_name(value):
    if isinstance(value, dict):
        return (value.get("name") or "").strip()
    return str(value or "").strip()


def check_slot_roles(question, slots):
    """origin/destination이 발화 순서와 뒤바뀌지 않았는지 확인한다.

    판정할 근거가 없으면 ``None``을 반환한다.
    """
    for first, second in ORDERED_SLOT_PAIRS:
        if first not in slots or second not in slots:
            continue
        first_name = _place_name(slots[first])
        second_name = _place_name(slots[second])
        if not first_name or not second_name:
            continue
        first_at = question.find(first_name)
        second_at = question.find(second_name)
        if first_at < 0 or second_at < 0 or first_at == second_at:
            continue
        return first_at < second_at
    return None


def evaluate_model(model, queries, *, host, chat_timeout, repeat, verbose):
    """모델 하나로 전체 Query의 template 선택을 측정한다."""
    client = OllamaClient(
        host, model, dict(OLLAMA_OPTIONS), chat_timeout=chat_timeout,
    )
    planner = GeoFlowPlanner(
        client=client, templates=TemplateRegistry.from_directory(),
    )

    records = []
    for item in queries:
        expected = item.get("expected_template")
        for attempt in range(1, repeat + 1):
            started_at = time.perf_counter()
            record = {
                "id": item["id"],
                "repeat_index": attempt,
                "expected": expected,
                "template": None,
                "slots": {},
                "status": "OK",
                "error": None,
                "role_order_ok": None,
                "duration_ms": 0.0,
            }
            try:
                output = planner.plan(item["question"])
                record["template"] = output.template
                record["slots"] = output.slots
                record["role_order_ok"] = check_slot_roles(
                    item["question"], output.slots,
                )
            except GeoFlowError as error:
                record["status"] = error.code
                record["error"] = error.detail
            except Exception as error:  # noqa: BLE001 - 모델 오류도 기록 대상
                record["status"] = "CLIENT_ERROR"
                record["error"] = f"{type(error).__name__}: {error}"
            record["duration_ms"] = round(
                (time.perf_counter() - started_at) * 1000, 3
            )
            record["correct"] = (
                record["template"] is not None
                and record["template"] == expected
            )
            records.append(record)
            if verbose:
                mark = "O" if record["correct"] else "X"
                print(
                    f"  {mark} {item['id']:<36} "
                    f"{str(record['template'] or record['status']):<28} "
                    f"{record['duration_ms']:7.0f}ms"
                )
    return records


def summarize(records):
    total = len(records)
    correct = sum(1 for item in records if item["correct"])
    failed = sum(1 for item in records if item["status"] != "OK")
    roles = [
        item["role_order_ok"] for item in records
        if item["role_order_ok"] is not None
    ]
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "planner_error": failed,
        "role_order_checked": len(roles),
        "role_order_ok": sum(1 for item in roles if item),
        "mean_duration_ms": round(
            sum(item["duration_ms"] for item in records) / total, 1
        ) if total else 0.0,
    }


def print_report(results, query_ids):
    ids = list(query_ids)
    models = list(results)
    width = max((len(name) for name in ids), default=10) + 2

    print("\n" + "=" * 78)
    print("Template 선택 정확도")
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
            if hit == len(picks):
                cell = "O"
            elif hit == 0:
                shown = picks[0]["template"] or picks[0]["status"]
                cell = f"X {str(shown)[:12]}"
            else:
                cell = f"~ {hit}/{len(picks)}"
            row += cell.ljust(16)
        print(row)

    print("-" * len(header))
    print("\n" + "모델".ljust(20) + "정확도".ljust(14) + "Planner 오류".ljust(14)
          + "역할 순서".ljust(12) + "평균 지연")
    print("-" * 74)
    for model in models:
        summary = results[model]["summary"]
        roles = (
            f"{summary['role_order_ok']}/{summary['role_order_checked']}"
            if summary["role_order_checked"] else "-"
        )
        print(
            model.ljust(20)
            + f"{summary['correct']}/{summary['total']} "
              f"({summary['accuracy'] * 100:.0f}%)".ljust(14)
            + str(summary["planner_error"]).ljust(14)
            + roles.ljust(12)
            + f"{summary['mean_duration_ms']:.0f} ms"
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="GeoFlow Planner template 선택 정확도 측정",
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

    unlabeled = [item["id"] for item in queries if not item.get("expected_template")]
    if unlabeled:
        raise SystemExit(
            "expected_template 라벨이 없는 Query가 있습니다: "
            + ", ".join(unlabeled)
        )

    # 라벨이 현재 template registry와 맞는지 먼저 확인한다.
    registry = TemplateRegistry.from_directory()
    unknown = sorted({
        item["expected_template"] for item in queries
        if item["expected_template"] not in registry
    })
    if unknown:
        raise SystemExit(
            f"등록되지 않은 expected_template입니다: {', '.join(unknown)}"
        )

    # Tool 실행은 하지 않지만 registry ↔ Tool 계약은 여기서도 확인해 둔다.
    tools, _prompt = build()
    ToolExecutor(tools=tools, handlers=get_tool_handlers())

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
        "templates": list(registry.names),
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
