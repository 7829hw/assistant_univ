# -*- coding: utf-8 -*-
"""OD 문항의 최초 grounding·최종 grounding·최종 결과를 나란히 본다(모델 호출 없음).

    python evaluation/grounding_v8/od_view.py RUN.json [RUN2.json]

- 최초: 첫 계획 응답의 장소 od_role과 dimension_target(정규화 전 원출력)
- 최종: 실행된 get_trip_count 인자(scope_pickup/scope_dropoff 유무, dimension_target)
- 정답: 정답 호출의 같은 항목
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluate_vendor100 import load_gold, result_class  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402


def ends(args):
    return ("P" if "scope_pickup" in args else "") + ("D" if "scope_dropoff" in args else "") or "-"


def gold_view(item):
    for call in item.get("gold") or []:
        if call.get("tool") == "get_trip_count":
            args = call.get("args") or {}
            return ends(args), args.get("dimension_target") if "dimension" in args else None
    return None


def first_view(row):
    plans = [c for c in row.get("llm_calls") or [] if c["kind"] == "plan" and not c.get("failed")]
    try:
        payload = parse_planner_json(plans[0]["content"])
    except Exception:  # noqa: BLE001
        return None
    roles = sorted((c.get("attributes") or {}).get("od_role") or c.get("od_role") or "·"
                   for c in payload.get("concepts") or [] if c.get("concept") == "LOCATION")
    factors = payload.get("factors") or {}
    return "/".join(roles), factors.get("dimension_target") if "dimension" in factors else None


def final_view(row):
    for call in row.get("calls") or []:
        if call["tool"] == "get_trip_count":
            args = call["args"]
            return ends(args), args.get("dimension_target") if "dimension" in args else None
    return None


def main():
    for path in sys.argv[1:]:
        result = json.loads(Path(path).read_text(encoding="utf-8"))
        gold = {item["id"]: item for item in load_gold(result["meta"]["gold_file"])["items"]}
        counts = Counter()
        print(f"== {path}")
        for row in result["rows"]:
            want = gold_view(gold[row["id"]])
            if want is None:
                continue
            got = final_view(row)
            first = first_view(row)
            klass = result_class(row)
            counts[klass] += 1
            counts["final_od_ok"] += got == want
            print(f"  {row['id']:5s} {klass:6s} want {want}  final {got}  first(roles, target) {first}"
                  f"  {row.get('error_code') or ''}")
        print("  ", dict(counts))


if __name__ == "__main__":
    main()
