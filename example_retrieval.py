# -*- coding: utf-8 -*-
"""질문–graph 예시 저장소 검증, 검색 index 만들기, 검색 결과 보기.

    python example_retrieval.py verify            # 등록 검증(형식·조합·G1–G5·reference 실행)
    python example_retrieval.py build             # lexical index 다시 만들기
    python example_retrieval.py build --ollama-model MODEL --out PATH   # 임베딩 index
    python example_retrieval.py query "질문" [--top-k 3] [--show-section]
    python example_retrieval.py replay RUN_DIR --out FILE   # 후처리 영향과 모델 출력 영향 분리

lexical index는 임베딩이 아니다(geoflow/retrieval.py). 임베딩 index는 Ollama 서버가 embedding을
지원하고 embedding 모델이 있어야 만들 수 있다.
"""

import argparse
import json
import os
import sys

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from geoflow.examples import load_store, verify_store  # noqa: E402
from geoflow.retrieval import (  # noqa: E402
    LEXICAL_INDEX_PATH, ExampleRetriever, OllamaEmbedder, RetrievalSettings, build_index,
    save_index,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    build = sub.add_parser("build")
    build.add_argument("--ollama-model")
    build.add_argument("--host", default="http://localhost:11434")
    build.add_argument("--out")
    query = sub.add_parser("query")
    query.add_argument("question")
    query.add_argument("--top-k", type=int, default=3)
    query.add_argument("--show-section", action="store_true")
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("run_dir")
    replay_parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "replay":
        return replay(args.run_dir, args.out)

    store = load_store()
    if args.command == "verify":
        failures = verify_store(store)
        print(f"{len(store.examples)} examples, store sha256 {store.sha256}")
        for example_id, problems in failures.items():
            print(f"FAIL {example_id}")
            for problem in problems:
                print(f"  - {problem}")
        return 1 if failures else 0
    if args.command == "build":
        failures = verify_store(store)
        if failures:
            print(f"등록 검증 실패로 index를 만들지 않습니다: {sorted(failures)}", file=sys.stderr)
            return 1
        embedder = OllamaEmbedder(args.ollama_model, args.host) if args.ollama_model else None
        out = args.out or (None if embedder else LEXICAL_INDEX_PATH)
        if out is None:
            parser.error("임베딩 index에는 --out이 필요합니다.")
        index = build_index(store, embedder)
        save_index(index, out)
        print(f"{out}: {index['embedder']['kind']} {index['embedder']['name']} "
              f"store {store.sha256[:12]}")
        return 0
    retriever = ExampleRetriever.load(settings=RetrievalSettings(top_k=args.top_k))
    result = retriever.select(args.question)
    print(json.dumps({key: value for key, value in result.to_dict().items() if key != "index"},
                     ensure_ascii=False, indent=1))
    if args.show_section:
        print(result.section)
    return 0


def _replayed(record, *, selector, condition_check, provider):
    """기록된 LLM 원문을 현재 코드로 다시 돌린다(LLM 호출 없음)."""
    from datetime import date

    from failure_census import ReplayClient
    from geoflow.pipeline import GeoFlowPipeline
    from geoflow.providers import profile_for
    from structured_grounding_eval import _tool_executor

    contents = [call.get("content") or "" for call in record.get("llm_calls") or []]
    run = GeoFlowPipeline.create(
        client=ReplayClient(contents), tool_executor=_tool_executor(provider),
        aggregation_grounding="structured", clock=lambda: date(2026, 9, 25),
        condition_check=condition_check, execution_profile=profile_for(provider),
        example_selector=selector).run(record["question"])
    value = (run.execution or {}).get("final_value")
    return {"outcome": run.outcome, "code": (run.error or {}).get("code"),
            "aggregation": (run.grounding or {}).get("aggregation"),
            "factors": (run.grounding or {}).get("factors"), "final_value": value}


def replay(run_dir, out):
    """같은 LLM 원문에 대한 후처리 영향을 잰다.

    1. 예시 on/off: 같은 원문을 검색 예시가 있는/없는 pipeline으로 돌린다. 예시는 prompt에만
       들어가므로 결과가 같아야 한다. 같다면 arm 사이의 차이는 모두 모델 출력이 달라진 영향이다.
    2. condition_check on/off: 같은 원문에서 조건 보정이 바꾼 것.
    """
    from pathlib import Path

    from structured_grounding_eval import arm_examples, example_selector, parse_arm

    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    provider = meta.get("provider", "mock")
    selectors = {kind: example_selector(kind) for kind in (None, "rx", "fx")}
    rows = []
    for line in open(run_dir / "observations.jsonl", encoding="utf-8"):
        record = json.loads(line)
        if record.get("measurement") != "valid" or not record.get("llm_calls"):
            continue
        _mode, cc = parse_arm(record["arm"])
        kind = arm_examples(record["arm"])
        same_arm = _replayed(record, selector=selectors[kind], condition_check=cc,
                             provider=provider)
        other = _replayed(record, selector=selectors["rx" if kind is None else None],
                          condition_check=cc, provider=provider)
        flipped_cc = _replayed(record, selector=selectors[kind], condition_check=not cc,
                               provider=provider)
        rows.append({
            "id": record["id"], "arm": record["arm"], "repetition": record.get("repetition", 0),
            "recorded_outcome": record.get("outcome"),
            "replay_consistent": same_arm["outcome"] == record.get("outcome"),
            "examples_toggle_same": same_arm == other,
            "condition_check_changes": same_arm != flipped_cc,
            "same_arm": same_arm, "examples_toggled": other, "condition_check_toggled": flipped_cc,
        })
    summary = {
        "observations": len(rows),
        "replay_consistent": sum(row["replay_consistent"] for row in rows),
        "examples_toggle_same": sum(row["examples_toggle_same"] for row in rows),
        "condition_check_changes": {arm: sum(row["condition_check_changes"] for row in rows
                                             if row["arm"] == arm)
                                    for arm in sorted({row["arm"] for row in rows})},
    }
    with open(out, "x", encoding="utf-8") as handle:
        json.dump({"summary": summary, "rows": rows}, handle, ensure_ascii=False, indent=1,
                  default=str)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
