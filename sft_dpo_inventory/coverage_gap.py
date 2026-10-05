# -*- coding: utf-8 -*-
"""thor reviewed gold v003의 coverage와 synthetic negative 종류를 학습 대상 조합의 실제 오류 유형과 비교한다.

    python sft_dpo_inventory/coverage_gap.py      # error_types.py를 먼저 실행해 둔다

- coverage는 v003 dataset_index의 학습 target(JSON)에서 센다. train/valid를 나눈다(valid만 있는 유형은 학습되지 않는다).
- 실제 오류는 error_types.py 산출물(qwen3:8b + T2PC, grounding_v13 136문항)의 최종 grounding 차이 세부값이다.
  차이 세부값은 라벨 값(측정값 이름, od_role, factor 값)만 남기고 질문 문장은 넣지 않는다.
- 오류 차원과 negative type의 대응(DIMENSION_OF_NEGATIVE)은 이 조사에서 정한 분류이며 thor 문서의 정의가 아니다.
"""
import json
from collections import Counter, defaultdict

from _common import CORPORA, GENERATED, thor_json, write_output

import error_types as E

#: negative_type → 오류 차원. 이 조사의 분류다.
DIMENSION_OF_NEGATIVE = {
    "od_role_confusion": "place_od_role", "place_role_confusion": "place_role(SUBCOND/COND)",
    "place_source_confusion": "place_source", "od_dimension_target_confusion": "dimension_target",
    "od_both_to_dropoff_dimension": "dimension_target", "aggregation_stage_swap": "aggregation",
    "bucket_rollup_omission": "aggregation", "answer_dimension_to_value": "aggregation(answer)",
    "undefined_rpm_sum": "aggregation", "factor_omission_taxi_type": "taxi_type",
    "date_factor_relative_confusion": "date", "date_factor_range_omission": "date",
    "fare_revenue_measure_confusion": "measure", "speed_rpm_measure_confusion": "measure",
    "hallucinated_measure_input_value": "measure_value",
    "actual_model_multi_field_grounding_error": "multi(actual)",
    "actual_measure_date_source_grounding_error": "multi(actual)",
}


def sft_coverage(records):
    cov = defaultdict(Counter)
    for record in records:
        payload = json.loads(record["messages"][-1]["content"])
        factors = payload.get("factors") or {}
        if payload.get("unsupported"):
            cov["unsupported"]["explicit_unsupported"] += 1
            continue
        for c in payload.get("concepts") or []:
            if c.get("role") == "MEASURE":
                cov["measure"][c.get("subtype")] += 1
            if c.get("concept") == "LOCATION":
                cov["location"][f"{c.get('subtype')}:{c.get('role')}:{(c.get('attributes') or {}).get('od_role')}"] += 1
        has_od = any((c.get("attributes") or {}).get("od_role") for c in payload.get("concepts") or [])
        cov["od"]["with_od_role" if has_od else "no_od_role"] += 1
        for key in ("dimension", "dimension_target", "taxi_status", "taxi_type", "order", "time", "vicinity"):
            cov[key][str(factors.get(key, "-"))] += 1
        date = factors.get("date")
        cov["date"]["-" if date is None else ("token" if not str(date)[:1].isdigit() else "range/day")] += 1
        agg = "/".join(f"{k}={factors[k]}" for k in ("aggregation", "bucket", "rollup", "answer") if k in factors)
        cov["aggregation_shape"][agg or "-"] += 1
    return {k: dict(sorted(v.items())) for k, v in cov.items()}


def actual_error_details(arm):
    """최종 grounding 차이를 세부 유형으로 나눈다(라벨 값만)."""
    rows, raw = E.R.load_sources(E.ARMS[arm])
    report = json.loads((GENERATED / "error_types_v13_model_name_only.json").read_text(encoding="utf-8"))
    items = report["arms"][arm]["items"]
    detail = defaultdict(lambda: defaultdict(list))
    for key, item in items.items():
        if item["v4"] == "정상 답변":
            continue
        cls = item["report_class"]
        for diff in raw[key].get("grounding_diffs") or []:
            if isinstance(diff, str):
                detail["format_or_plan"][diff].append((key, cls))
                continue
            name, want, got = diff
            if name == "places":
                w = {p[0]: p[2] for p in want}
                g = {p[0]: p[2] for p in got}
                if set(w) == set(g):
                    for place in w:
                        if w[place] != g[place]:
                            detail["place_od_role"][f"{w[place]}->{g[place]}"].append((key, cls))
                else:
                    detail["place_name_or_count"]["names_differ"].append((key, cls))
            elif name == "measure":
                detail["measure"][f"{want[1]}->{got[1]}"].append((key, cls))
            elif name == "factor:aggregation_spec":
                kind = "invented_aggregation" if want is None else ("dropped_aggregation" if got is None else "changed")
                detail["aggregation"][kind].append((key, cls))
            elif name.startswith("factor:"):
                detail[name[7:]][f"{want}->{got}"].append((key, cls))
            else:
                detail[name]["differs"].append((key, cls))
    return {dim: {sub: {"count": len(v), "items": [f"{k} ({c})" for k, c in v]} for sub, v in subs.items()}
            for dim, subs in detail.items()}


def main():
    index = thor_json(f"{CORPORA}/reviewed_gold_v003/dataset_index.json")
    coverage = {"sft_train": sft_coverage(index["sft_train"]), "sft_valid": sft_coverage(index["sft_valid"])}
    negatives = {split: dict(Counter(f"{r['metadata']['negative_category']}:{r['metadata']['negative_type']}"
                                     for r in index[split])) for split in ("dpo_train", "dpo_valid")}
    negative_dims = {split: dict(Counter(DIMENSION_OF_NEGATIVE.get(r["metadata"]["negative_type"], "?")
                                         for r in index[split])) for split in ("dpo_train", "dpo_valid")}
    out = {
        "sft_coverage": coverage,
        "dpo_negative_types": negatives,
        "dpo_negative_dimensions": negative_dims,
        "dimension_of_negative": DIMENSION_OF_NEGATIVE,
        "actual_errors_q8_T2PC": actual_error_details("q8_T2PC"),
        "actual_errors_B": actual_error_details("B"),
    }
    path, digest = write_output("coverage_gap.json", out)
    print(json.dumps({k: v for k, v in out.items() if k != "actual_errors_B"}, ensure_ascii=False, indent=1))
    print(f"\nwrote {path} sha256={digest}")


if __name__ == "__main__":
    main()
