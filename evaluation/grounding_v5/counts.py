# -*- coding: utf-8 -*-
"""grounding_v5 집계: 결과 분류, 집계 발명, answer 오용, 재질의 결과·범위 위반, 올바른 첫 grounding의 회귀.

    python evaluation/grounding_v5/counts.py NAME=DIR[:SUFFIX] ...   (DIR/<set><SUFFIX>.json)

- 집계 발명: 정답이 구간 안 집계 미지정(expected_error AMBIGUOUS_INNER_AGGREGATION 또는 why에 "구간 안 집계")인데
  최종 결과가 답변인 문항.
- answer 오용: 정답에 bucket이 없는 문항에서 모델 첫 응답이 answer=bucket을 적은 것. 최종이 정상 답변/정당한 거부면 해결.
- 올바른 첫 grounding 회귀: 첫 응답 grounding이 정답과 같았는데(grounding_ok 기준은 최종이라 쓰지 않는다) 재질의가
  일어났거나 결과가 맞지 않은 문항. 첫 응답이 재질의 없이 끝났으면 재질의 경로의 영향을 받지 않는다.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluate_vendor100 import load_gold, result_class  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402

SETS = ("at", "contrast", "dev", "indepv2", "indepv3", "indepv4", "old44")
OK = ("정상 답변", "정당한 거부")


def inner_missing(item):
    return (item.get("expected_error") == "AMBIGUOUS_INNER_AGGREGATION"
            or "구간 안 집계" in (item.get("why") or "")
            or "AMBIGUOUS_INNER_AGGREGATION" in (item.get("why") or ""))


def gold_has_bucket(item):
    for call in item.get("gold") or []:
        if "bucket" in (call.get("args") or {}):
            return True
    factors = (item.get("gold_grounding") or {}).get("factors") or {}
    # 정답 grounding 없이 "값이 아니라 구간(주·달)을 묻는다"로 라벨한 구간 선택 문항.
    why = item.get("why") or ""
    return "bucket" in factors or "값이 아니라 구간" in why or "어느 달인지" in why


def first_factors(row):
    plans = [call for call in row.get("llm_calls") or [] if call["kind"] == "plan"
             and not call.get("failed")]
    if not plans:
        return None
    try:
        return parse_planner_json(plans[0]["content"]).get("factors") or {}
    except Exception:  # noqa: BLE001
        return None


def summarize(path):
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    gold = {item["id"]: item for item in load_gold(result["meta"]["gold_file"])["items"]}
    out = Counter()
    notes = {"invented": [], "answer_misuse": [], "out_of_scope": [], "repair_unsupported": []}
    for row in result["rows"]:
        item = gold[row["id"]]
        klass = result_class(row)
        out[klass] += 1
        out["items"] += 1
        attempts = (row.get("planner_trace") or {}).get("attempts") or []
        repairs = [call for call in row.get("llm_calls") or [] if call["kind"] != "plan"]
        out["repair_calls"] += len(repairs)
        for attempt in attempts:
            if attempt.get("repair_attempted"):
                kind = attempt.get("repair_kind") or "?"
                out[f"repair:{kind}"] += 1
                if attempt.get("repair_result") == "OK":
                    out[f"repair_ok:{kind}"] += 1
                code = (attempt.get("repair_error") or {}).get("code")
                if code == "REPAIR_OUT_OF_SCOPE":
                    out["repair_out_of_scope"] += 1
                    notes["out_of_scope"].append(row["id"])
                if code == "REPAIR_UNSUPPORTED":
                    out["repair_unsupported"] += 1
                    notes["repair_unsupported"].append(f"{row['id']}:{klass}")
        if inner_missing(item):
            out["inner_missing_items"] += 1
            if row.get("outcome") == "answered":
                out["invented"] += 1
                notes["invented"].append(row["id"])
        factors = first_factors(row)
        if factors is not None and factors.get("answer") == "bucket" and not gold_has_bucket(item):
            out["answer_misuse_first"] += 1
            resolved = klass in OK
            out["answer_misuse_resolved"] += resolved
            notes["answer_misuse"].append(f"{row['id']}:{klass}")
        latency = (row.get("planner_trace") or {}).get("durations", {}).get("total_ms")
        if latency is not None:
            out["latency_ms"] += latency
    return out, notes


def main():
    for spec in sys.argv[1:]:
        name, _, rest = spec.partition("=")
        directory, _, suffix = rest.partition(":")
        total, per_set, all_notes = Counter(), {}, {}
        for set_name in SETS:
            path = Path(directory) / f"{set_name}{suffix}.json"
            if not path.is_file():
                continue
            counts, notes = summarize(path)
            per_set[set_name] = counts
            total.update(counts)
            all_notes[set_name] = notes
        print(f"== {name}")
        for set_name, counts in per_set.items():
            print(f"  {set_name:9s} ok {counts['정상 답변'] + counts['정당한 거부']:3d}/{counts['items']:3d}"
                  f"  정상 {counts['정상 답변']:3d} 정당거부 {counts['정당한 거부']:2d} 오답 {counts['오답']:2d}"
                  f" 부당거부 {counts['부당한 거부']:2d} 실패 {counts['실행 실패']:2d} 재질의 {counts['repair_calls']:2d}")
        keys = ("items", "정상 답변", "정당한 거부", "오답", "부당한 거부", "실행 실패", "미실행",
                "repair_calls", "repair_out_of_scope", "repair_unsupported",
                "inner_missing_items", "invented", "answer_misuse_first", "answer_misuse_resolved")
        print("  total", {key: total[key] for key in keys},
              {key: value for key, value in sorted(total.items()) if key.startswith("repair")},
              "latency_s", round(total["latency_ms"] / 1000))
        for set_name, notes in all_notes.items():
            shown = {key: value for key, value in notes.items() if value}
            if shown:
                print("   ", set_name, shown)


if __name__ == "__main__":
    main()
