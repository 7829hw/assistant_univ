# -*- coding: utf-8 -*-
"""batch013 c2 구조 고르기(결정 243 AA3, ``batch010/free_structures10.py``의 사본: 구조 목록만 요금 지표 밖 tool로 바꿈, family·검사 방법은 그대로).
원 설명: batch010 구조 고르기(결정 169 O5): 약점 셋마다 구조를 늘어놓고 family 키를 계산해, 보호 넷(selection_v2·holdout·valid98·aux_test_v1) + selection_v1·
thor 보호 family·확장 family와 겹치지 않고 현재 코드(검증 사슬 + Full 경로)가 답하는 구조만 낸다. 문장은 다루지 않는다. 모델 호출 없음.
``batch009/free_structures.py``와 같은 방법(구조 범위만 넓힘).

    hfvenv/bin/python sft_dpo_inventory/batch013/free_structures13.py   # -> free_structures13.json

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
    """batch013 c2(요금 지표 밖 tool) 구조: 통과량 지표(speed·rpm)·운행 지표(vacant_ratio)·통행 지표(fare)·통과량 건수 × aggregation × 시간대·택시 유형·상태·차원."""
    out = []
    place = "get_place_scope(name=대구)"
    for tool, metric, extra in (("passage_metrics", "speed", ()), ("passage_metrics", "rpm", ()), ("trip_metrics", "fare", ()),
                                ("drive_metrics", "vacant_ratio", ("taxi_type=private",))):
        for agg, tm, ex in itertools.product(AGG, (None, "070000-090000"), (None,) + extra):
            args = [f"metric={metric}", "scope=$resolve.scope", "date=last_month"] + ([f"time={tm}"] if tm else []) + ([ex] if ex else []) + ([f"aggregation={agg}"] if agg else [])
            out.append(("c2m", {"tool": tool, "metric": metric, "agg": agg, "time": tm, "extra": ex}, [place, f"get_{tool}({', '.join(args)})"]))
    for tt, st, dim, order, tm in itertools.product((None, "private"), (None, "occupied", "vacant"), (None, "sigungu", "emd", "h3"), (None, "top", "bottom"),
                                                    (None, "070000-090000")):
        if order and not dim:
            continue
        args = ["scope=$resolve.scope", "date=last_month"] + ([f"time={tm}"] if tm else []) + ([f"taxi_type={tt}"] if tt else []) + ([f"taxi_status={st}"] if st else [])
        args += ([f"dimension={dim}"] if dim else []) + ([f"order={order}", "limit=2"] if order else [])
        out.append(("c2p", {"tool": "passage_count", "taxi_type": tt, "status": st, "dimension": dim, "order": order, "time": tm}, [place, f"get_passage_count({', '.join(args)})"]))
    for end in ("pickup", "dropoff"):
        for dim, dt, order, tm in [(None, None, None, None), (None, None, None, "070000-090000")] + list(itertools.product(("sido", "sigungu", "emd", "h3"), ("pickup", "dropoff", "both"), (None, "top", "bottom"), (None, "070000-090000"))):
            args = [f"scope_{end}=${end}.scope", "date=last_week"] + ([f"time={tm}"] if tm else [])
            if dim:
                args += [f"dimension={dim}", f"dimension_target={dt}"] + ([f"order={order}", "limit=2"] if order else [])
            out.append(("c2t", {"tool": "trip_count", "end": end, "dimension": dim, "dimension_target": dt, "order": order, "time": tm},
                        ["get_place_scope(name=초량동)", f"get_trip_count({', '.join(args)})"]))
    return out


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
        q = "지난주 대구 초량동 소속 택시 건수 주별 월별 아침 7시부터 9시 개인택시 손님 태운 빈 택시"
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
    (HERE / "free_structures13.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    from collections import Counter
    print("structures", len(out), "free", sum(r["free"] for r in out), "free unique family", len({r["family"] for r in out if r["free"]}))
    print(Counter((r["kind"], r["free"]) for r in out))


if __name__ == "__main__":
    main()
