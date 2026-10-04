# -*- coding: utf-8 -*-
"""운행 상태(taxi_status)로 멈춘 행의 원인 사슬(모델 호출 없음).

    python evaluation/grounding_v10/status_chain.py RUN.json [RUN.json ...]

각 행마다: 최초 모델 출력의 taxi_status·측정값 → 조건 계층 기록(질문의 상태 표현, 모델 값, 조치: 채움·확인·보존·삭제)
→ 최종 오류 코드·상세. 조건 계층 기록은 저장된 첫 계획 원출력을 현재 코드의 ``conditions.reconcile_payload``에 다시
넣어 얻는다. 원인 진단용이며 결과 수치로 세지 않는다.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluate_vendor100 import REFERENCE_DATE  # noqa: E402
from geoflow import conditions  # noqa: E402
from geoflow.errors import PlannerError  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402


def measure(payload):
    for concept in payload.get("concepts") or []:
        if concept.get("role") == "MEASURE":
            return f"{concept.get('concept')}/{concept.get('subtype')}", concept.get("text")
    return None, None


def chain(row):
    text = next((c["content"] for c in row.get("llm_calls") or [] if c["kind"] == "plan" and not c.get("failed")), None)
    payload = parse_planner_json(text)
    out = {"id": row["id"], "question": row["question"],
           "model_taxi_status": (payload.get("factors") or {}).get("taxi_status"),
           "model_measure": measure(payload)}
    try:
        _, audit = conditions.reconcile_payload(payload, row["question"], reference_date=REFERENCE_DATE, raw_text=text)
        record = (audit or {}).get("taxi_status") if isinstance(audit, dict) else None
        if record is None and hasattr(audit, "to_dict"):
            record = audit.to_dict().get("taxi_status")
        out["condition_layer"] = {k: (record or {}).get(k) for k in ("mentions", "llm_value", "value", "action", "basis")}
    except PlannerError as error:
        out["condition_layer"] = {"error": error.code}
    out["final"] = (row.get("outcome"), row.get("error_code"),
                    ((row.get("planner_trace") or {}).get("error_detail") or "")[:80])
    return out


def main():
    for path in sys.argv[1:]:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))["rows"]
        hits = [r for r in rows if r.get("error_code") == "UNCONSUMED_CONDITION"
                and "taxi_status" in ((r.get("planner_trace") or {}).get("error_detail") or "")]
        print(f"== {path}: taxi_status 정지 {len(hits)}")
        for row in hits:
            print(json.dumps(chain(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
