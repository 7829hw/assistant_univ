# -*- coding: utf-8 -*-
"""trip 문항에서 모델이 적은 taxi_status 때문에 멈춘 행(UNCONSUMED_CONDITION taxi_status)을 원인별로 나눈다(모델 호출 없음).

    python evaluation/grounding_v9/status_attribution.py RUN_DIR [RUN_DIR ...]

첫 계획 원출력에서 taxi_status만 뺀 grounding이 정답 grounding과 같은지 본다. 같으면 "운행 상태만 더 적은 것"이고 다른
의미 차이가 없다. 파이프라인 동작이 아니라 원인 분석이며, 이 수치를 정상 답변으로 세지 않는다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluate_vendor100 import grounding_check  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import _gold  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402

for directory in sys.argv[1:]:
    hit = only = 0
    rest = []
    for path in sorted(Path(directory).glob("*.json")):
        set_name = path.stem
        for row in json.loads(path.read_text(encoding="utf-8"))["rows"]:
            if row.get("error_code") != "UNCONSUMED_CONDITION" or "taxi_status" not in (
                    row["planner_trace"].get("error_detail") or ""):
                continue
            hit += 1
            item = _gold(set_name, row)[row["id"]]
            text = next(c["content"] for c in row["llm_calls"] if c["kind"] == "plan" and not c.get("failed"))
            payload = parse_planner_json(text)
            payload.setdefault("factors", {}).pop("taxi_status", None)
            ok, diffs = grounding_check(item, payload)
            if ok:
                only += 1
            else:
                rest.append(f"{set_name}/{row['id']} {diffs}")
    print(f"{directory}: taxi_status 정지 {hit}, 그 조건만 빼면 정답 grounding {only}")
    for line in rest:
        print("   ", line)
