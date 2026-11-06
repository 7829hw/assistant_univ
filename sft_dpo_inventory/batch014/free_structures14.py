# -*- coding: utf-8 -*-
"""batch014 구조 고르기(결정 263 D5, ``batch013/free_structures13.py``의 사본: 구조 목록만 CONTRAST_PLAN_DRAFT T1–T5 서명으로 바꿈, family·검사 방법은 그대로).
문장은 다루지 않는다. 모델 호출 없음. 평가 셋 문항 원문은 읽지 않는다(보호 넷 family 키만 계산).

    runtime/envs/hf/bin/python sft_dpo_inventory/batch014/free_structures14.py   # -> free_structures14.json

- tm(T1·T2, 참고로 POI 주변도): get_trip_metrics(fare) × 장소(없음·시도 대구·시군구 수성구·POI 주변 동대구역) × aggregation(없음·avg·med·min·max·sum) × 날짜(하루·기간·주·주말).
- tb(T3): get_billing_metrics(revenue·active_taxi_count·active_taxi_ratio) × 장소(시도 대구·없음) × 날짜(하루·월) × aggregation × dimension(없음, 장소 없을 때 sido·dayofweek) × order.
- tc(T4): get_trip_count × 끝(없음·출발·도착; 장소 없음·POI 동대구역) × 하루 × 시간대(없음·07–09시).
- to(T5): get_trip_count(OD 상위 N) × 끝(없음·출발·도착·둘 다) × dimension 4 × dimension_target 3 × order 2, limit 3.
family 키는 장소·날짜·taxi_type·status·limit을 보지 않는다(``pilot_006_prep/analysis/family_key.md``).

이하 batch013 원 설명.
원 설명: batch010 구조 고르기(결정 169 O5): 약점 셋마다 구조를 늘어놓고 family 키를 계산해, 보호 넷(selection_v2·holdout·valid98·aux_test_v1) + selection_v1·
thor 보호 family·확장 family와 겹치지 않고 현재 코드(검증 사슬 + Full 경로)가 답하는 구조만 낸다. 문장은 다루지 않는다. 모델 호출 없음.
``batch009/free_structures.py``와 같은 방법(구조 범위만 넓힘).

    hfvenv/bin/python sft_dpo_inventory/batch013/free_structures13.py   # -> free_structures14.json

- s1 "<지역> 소속 택시"(장소 하나, od 없음): get_trip_metrics(fare)·get_drive_metrics(vacant_ratio)·get_billing_metrics(revenue·active_taxi_count·active_taxi_ratio·
  operating_days) × aggregation(없음·5) × [billing만] bucket/rollup·dimension(+order).
- s2 "…으로 들어온·…에서 나간"(실차 건수, 장소가 한 끝만 제한): get_trip_count(scope_pickup | scope_dropoff) × dimension(없음·4) × dimension_target × order.
- s3 bucket(주별·월별 먼저 집계)과 bucket ↔ dimension 대조(s3d: 장소 없는 dimension판 — 현재 코드가 billing dimension + scope를 거부): get_billing_metrics 측정 4 × bucket 2 × rollup 5 × aggregation(없음·5), 그리고 같은 측정의 dimension(dayofweek·지역)판.
family 키는 장소·날짜·taxi_type·status·limit을 보지 않는다(``pilot_006_prep/analysis/family_key.md``).
"""
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "sft_dpo_inventory/batch004", ROOT / "sft_dpo_inventory/pilot_006_prep/aug300", ROOT / "sft_dpo_inventory/pilot_006_prep/aug300_review"):
    sys.path.insert(0, str(p))
AGG = (None, "avg", "sum", "max", "min", "med")


def structures():
    """batch014 T1–T5 서명 구조."""
    out = []
    locs = {"none": [], "sido": ["get_place_scope(name=대구)"], "sigungu": ["get_place_scope(name=수성구, region=대구)"],
            "poi_vicinity": ["get_place_scope(name=동대구역, include_vicinity=true)"]}
    for loc, agg, date in itertools.product(("none", "sido", "sigungu", "poi_vicinity"), AGG, ("20261020", "20261001-20261015", "last_week", "weekend")):
        args = ["metric=fare"] + (["scope=$resolve.scope"] if loc != "none" else []) + [f"date={date}"] + ([f"aggregation={agg}"] if agg else [])
        out.append(("tm", {"tool": "trip_metrics", "metric": "fare", "loc": loc, "agg": agg, "date": date}, locs[loc] + [f"get_trip_metrics({', '.join(args)})"]))
    for metric, loc, date, agg, dim, order in itertools.product(("revenue", "active_taxi_count", "active_taxi_ratio"), ("sido", "none"), ("20261020", "last_month"), AGG,
                                                                 (None, "sido", "dayofweek"), (None, "top")):
        if (dim and loc != "none") or (order and not dim):
            continue
        args = [f"metric={metric}"] + (["scope=$resolve.scope"] if loc != "none" else []) + [f"date={date}"] + ([f"aggregation={agg}"] if agg else [])
        args += ([f"dimension={dim}"] if dim else []) + ([f"order={order}", "limit=3"] if order else [])
        out.append(("tb", {"tool": "billing_metrics", "metric": metric, "loc": loc, "date": date, "agg": agg, "dimension": dim, "order": order},
                    locs[loc] + [f"get_billing_metrics({', '.join(args)})"]))
    for end, place, tm in itertools.product((None, "pickup", "dropoff"), ("none", "poi"), (None, "070000-090000")):
        if (end is None) != (place == "none"):
            continue
        pcall = ["get_place_scope(name=동대구역, include_vicinity=true)"] if place == "poi" else []
        args = ([f"scope_{end}=${end}.scope"] if end else []) + ["date=20261020"] + ([f"time={tm}"] if tm else [])
        out.append(("tc", {"tool": "trip_count", "end": end, "place": place, "time": tm}, pcall + [f"get_trip_count({', '.join(args)})"]))
    for ends, dim, dt, order in itertools.product(("none", "pickup", "dropoff", "both"), ("sido", "sigungu", "emd", "h3"), ("pickup", "dropoff", "both"), ("top", "bottom")):
        pc = {"none": [], "pickup": ["get_place_scope(name=대구)"], "dropoff": ["get_place_scope(name=대구)"],
              "both": ["get_place_scope(name=수성구, region=대구)", "get_place_scope(name=부산)"]}[ends]
        sc = {"none": [], "pickup": ["scope_pickup=$pickup.scope"], "dropoff": ["scope_dropoff=$dropoff.scope"], "both": ["scope_pickup=$pickup.scope", "scope_dropoff=$dropoff.scope"]}[ends]
        args = sc + ["date=last_week", f"dimension={dim}", f"dimension_target={dt}", f"order={order}", "limit=3"]
        out.append(("to", {"tool": "trip_count", "ends": ends, "dimension": dim, "dimension_target": dt, "order": order}, pc + [f"get_trip_count({', '.join(args)})"]))
    return out


def qtext(spec):
    """구조마다 날짜 표현 하나만 든 자리표 문장(add_spans·검증 사슬용; 실제 문항 아님)."""
    d = {"20261020": "2026년 10월 20일", "20261001-20261015": "2026년 10월 1일부터 15일까지", "last_week": "지난주", "weekend": "주말", "last_month": "지난달"}
    date = d.get(spec.get("date"), "지난주")
    if spec.get("kind_hint") == "tc" or spec.get("place") is not None:
        date = "2026년 10월 20일"
    return (f"{date} 대구 수성구 부산 동대구역 근처 택시 요금 평균 중간값 최솟값 최댓값 합계 수입 활성 택시 대수 비율 시도별 요일별 건수 "
            "아침 7시부터 9시 출발 도착 상위 하위 3곳 읍면동 시군구 H3")


def main():
    import check_aug300 as W6
    import evaluate_vendor100 as EV
    from build_candidates import extended_fingerprints
    from draft_semantics import add_spans
    from grounding.canonical import semantics_from_full
    from grounding.validation import validate_semantics
    from training.annotations.inventory import Protection, family_key
    from training.data.common import read_jsonl
    tg = W6.load_targets(None)
    blocked = {}
    for name in ("selection_v2", "valid98", "aux_test_v1", "selection_v1"):
        for _, _, pl in tg[name]:
            if pl:
                try:
                    blocked.setdefault(family_key(pl), set()).add(name)
                except Exception:  # noqa: BLE001
                    pass
    hold = {i["id"] for i in json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/holdout_v1.json").read_text(encoding="utf-8"))["list"]}
    for i in read_jsonl(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_300.jsonl"):
        if i["id"] in hold:
            blocked.setdefault(family_key(EV.derive_grounding(i["gold"])), set()).add("holdout")
    _, ext_f = extended_fingerprints()
    guard = Protection.current(ROOT / "training/generated/reviewed_gold_v006_t2pc")
    out, seen = [], {}
    for kind, spec, calls_text in structures():
        calls = EV.parse_calls("\n".join(calls_text))
        payload = EV.derive_grounding(calls)
        fk = family_key(payload)
        q = qtext(spec)
        pl, _ = add_spans(payload, q)
        try:
            chain = validate_semantics(semantics_from_full(pl), q, calls)
            answers = bool(chain["full_answered"] and chain["ok"])
            code = None if answers else (chain.get("mock_full") or {}).get("error_code") or (chain.get("full") or {}).get("error_code")
        except Exception as error:  # noqa: BLE001
            answers, code = False, f"{type(error).__name__}"
        thor_f = "protected_semantic_family" in guard.reasons("-", payload, ["-"])
        row = {"kind": kind, **spec, "family": fk[:12], "blocked_by": sorted(blocked.get(fk, [])), "extended_family": bool(ext_f.get(fk)), "thor_family": thor_f,
               "code_answers": answers, "code_error": code, "calls": calls_text}
        row["free"] = not row["blocked_by"] and not row["extended_family"] and not thor_f and answers
        row["dup_family_of"] = seen.get(fk)
        seen.setdefault(fk, len(out))
        out.append(row)
    (HERE / "free_structures14.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    from collections import Counter
    print("structures", len(out), "free", sum(r["free"] for r in out), "free unique family", len({r["family"] for r in out if r["free"]}))
    print(Counter((r["kind"], r["free"]) for r in out))


if __name__ == "__main__":
    main()
