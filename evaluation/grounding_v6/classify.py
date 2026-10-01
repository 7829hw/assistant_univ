# -*- coding: utf-8 -*-
"""factor 수정 재질의 문항을 정답 라벨과 비교해 원인별로 나눈다(모델 호출 없음).

    python evaluation/grounding_v6/classify.py RUN_DIR [RUN_DIR ...]

결과 역할(그룹, 순위 방향, 개수, 답 대상, 구간 안 집계, 구간별 결과의 집계)을 정답 grounding(`gold_grounding`)과
비교한다. 수정 전(재질의 직전 grounding), 모델 수정안을 그대로 적용했을 때(모든 결과 형태 덮어쓰기), 실제 적용 결과를
본다.

- 복구가 새 오류를 만듦: 적용 뒤 틀린 역할이 수정 전과 다르다(맞던 것이 틀어짐, 또는 틀린 값을 다른 틀린 값으로 바꿈)
- 처음부터 있던 오류가 남음: 수정 전 틀린 역할이 적용 뒤에도 그대로(그중 최종이 답변이면 "실행 가능해짐")
- 정당한 복구: 적용 뒤 모든 역할이 맞음
- 정당한 수정이 막힘: 수정안이 거부됐는데, 수정안 그대로면 모든 역할이 맞음
- 막혀서 오류를 피함: 수정안이 거부됐고, 수정안 그대로면 맞던 역할이 틀렸을 것

역할 비교는 계약 수준이다. 장소·측정값·기간 같은 다른 오류는 결과 분류(정상 답변 등)에서 따로 드러난다.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluate_vendor100 import gold_grounding, load_gold, result_class  # noqa: E402
from geoflow.correction_scope import roles  # noqa: E402
from geoflow.factors import RESULT_SHAPE_FACTORS  # noqa: E402

SETS = ("at", "contrast", "dev", "indepv2", "indepv3", "indepv4", "old44")
ROLE_KEYS = ("grouping", "direction", "limit", "answer", "aggregation", "rollup")


def normalized(factors):
    """역할 비교용. 구간이 없으면 aggregation 생략은 Tool 기본값 avg와 같다(업체 채점 기본값)."""
    view = roles(factors or {})
    if not view["grouping"] or view["grouping_field"] == "dimension":
        view["aggregation"] = view["aggregation"] or "avg"
    return {key: view[key] for key in ROLE_KEYS}


def correction_attempt(row):
    for attempt in (row.get("planner_trace") or {}).get("attempts") or []:
        if attempt.get("repair_kind") == "factor_correction" and attempt.get("repair_attempted"):
            return attempt
    return None


def proposal_of(row):
    calls = [call for call in row.get("llm_calls") or [] if call["kind"] != "plan" and not call.get("failed")]
    for call in calls:
        try:
            payload = json.loads(call["content"].strip().strip("`").removeprefix("json"))
        except Exception:  # noqa: BLE001
            continue
        if isinstance(payload, dict):
            return payload
    return None


def classify(row, item):
    attempt = correction_attempt(row)
    if attempt is None:
        return None
    record = attempt.get("correction") or {}
    gold = gold_grounding(item)
    if gold is None or "before" not in record:
        return {"id": row["id"], "kind": "판정 불가", "class": result_class(row)}
    gold_factors = gold.get("factors") or {}
    want = normalized(gold_factors)
    # 정답에 구간도 집계도 없으면 집계는 그 Tool이 받지 않는 조건이다(건수 Tool). 비교하지 않는다.
    keys = ROLE_KEYS if ("aggregation" in gold_factors or "bucket" in gold_factors) else tuple(
        key for key in ROLE_KEYS if key != "aggregation")
    before = normalized(record["before"])
    after = normalized(record.get("after") or record["before"])
    applied = attempt.get("repair_result") == "OK"
    naive = None
    if record.get("proposed") is not None:
        # 수정안을 범위 없이 그대로 적용했다면(결과 형태 전부를 수정안으로 덮어쓰기).
        naive = normalized({k: v for k, v in record["proposed"].items() if v not in (None, "")})
    # 복구가 만든 오류: 맞던 역할이 틀어졌거나, 이미 틀린 역할을 다른 틀린 값으로 바꿨다(g44: avg → sum).
    lost = [key for key in keys if after[key] != want[key] and before[key] != after[key]]
    kept_wrong = [key for key in keys if before[key] != want[key] and after[key] == before[key]]
    if applied:
        if lost:
            kind = "복구가 새 오류를 만듦"
        elif kept_wrong:
            kind = ("처음부터 있던 오류가 남아 실행됨" if row.get("outcome") == "answered"
                    else "처음부터 있던 오류가 남음")
        else:
            kind = "정당한 복구"
    else:
        if naive is not None and all(naive[key] == want[key] for key in keys):
            kind = "정당한 수정이 막힘"
        elif naive is not None and any(before[key] == want[key] and naive[key] != want[key]
                                       for key in keys):
            kind = "막혀서 새 오류를 피함"
        else:
            kind = "막힘(수정안도 틀림)"
    return {"id": row["id"], "kind": kind, "class": result_class(row), "lost": lost,
            "kept_wrong": kept_wrong, "blocked": [b["factor"] for b in record.get("blocked") or []],
            "error": attempt.get("error_code"), "repair_error": (attempt.get("repair_error") or {}).get("code")}


def main():
    for directory in sys.argv[1:]:
        counts, rows_out = Counter(), []
        for set_name in SETS:
            path = Path(directory) / f"{set_name}.json"
            if not path.is_file():
                continue
            result = json.loads(path.read_text(encoding="utf-8"))
            gold = {item["id"]: item for item in load_gold(result["meta"]["gold_file"])["items"]}
            for row in result["rows"]:
                entry = classify(row, gold[row["id"]])
                if entry is None:
                    continue
                entry["set"] = set_name
                entry["request"] = row.get("request_match")
                counts[entry["kind"]] += 1
                rows_out.append(entry)
        print(f"== {directory}  factor 수정 문항 {len(rows_out)}")
        for kind, number in counts.most_common():
            ids = ", ".join(f"{entry['id']}({entry['class']})" for entry in rows_out if entry["kind"] == kind)
            print(f"  {kind}: {number}  {ids}")


if __name__ == "__main__":
    main()
