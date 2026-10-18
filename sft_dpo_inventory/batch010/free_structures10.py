# -*- coding: utf-8 -*-
"""batch010 구조 고르기(결정 169 O5): 약점 셋마다 구조를 늘어놓고 family 키를 계산해, 보호 넷(selection_v2·holdout·valid98·aux_test_v1) + selection_v1·
thor 보호 family·확장 family와 겹치지 않고 현재 코드(검증 사슬 + Full 경로)가 답하는 구조만 낸다. 문장은 다루지 않는다. 모델 호출 없음.
``batch009/free_structures.py``와 같은 방법(구조 범위만 넓힘).

    hfvenv/bin/python sft_dpo_inventory/batch010/free_structures10.py   # -> free_structures10.json

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
    out = []
    place = "get_place_scope(name=대구)"
    for agg in AGG:
        a = f", aggregation={agg}" if agg else ""
        out.append(("s1", {"tool": "trip_metrics", "metric": "fare", "agg": agg}, [place, f"get_trip_metrics(metric=fare, scope=$resolve.scope, date=last_month{a})"]))
        out.append(("s1", {"tool": "drive_metrics", "metric": "vacant_ratio", "agg": agg}, [place, f"get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=last_month{a})"]))
    for m in ("revenue", "active_taxi_count", "active_taxi_ratio", "operating_days"):
        for agg, (bucket, rollup), (dim, order) in itertools.product(AGG, [(None, None)] + [(b, r) for b in ("week", "month") for r in AGG[1:]],
                                                                     [(None, None)] + [(d, o) for d in ("sigungu", "emd", "dayofweek") for o in (None, "top", "bottom")]):
            if bucket and dim:
                continue
            args = [f"metric={m}", "scope=$resolve.scope", "date=this_year"]
            args += [f"aggregation={agg}"] if agg else []
            args += [f"bucket={bucket}", f"rollup={rollup}"] if bucket else []
            args += [f"dimension={dim}"] + ([f"order={order}", "limit=2"] if order else []) if dim else []
            kind = "s3" if bucket or dim == "dayofweek" else "s1"
            out.append((kind, {"tool": "billing", "metric": m, "agg": agg, "bucket": bucket, "rollup": rollup, "dimension": dim, "order": order},
                        [place, f"get_billing_metrics({', '.join(args)})"]))
            if kind == "s3":  # bucket ↔ dimension 대조는 소속 아닌 장소에서도 같은 family
                pass
    # s3d: bucket ↔ dimension 대조용 dimension판. 현재 코드는 billing dimension과 장소(scope)를 같이 받지 않는다(PARAM_VALUE_FORBIDS_INPUT) → 장소 없이.
    for m in ("revenue", "active_taxi_count", "active_taxi_ratio", "operating_days"):
        for agg, dim, order in itertools.product(AGG, ("dayofweek", "sigungu", "emd", "sido"), (None, "top", "bottom")):
            args = [f"metric={m}", "date=this_year"] + ([f"aggregation={agg}"] if agg else []) + [f"dimension={dim}"] + ([f"order={order}", "limit=2"] if order else [])
            out.append(("s3d", {"tool": "billing", "metric": m, "agg": agg, "bucket": None, "rollup": None, "dimension": dim, "order": order},
                        [f"get_billing_metrics({', '.join(args)})"]))
    for end in ("pickup", "dropoff"):
        for dim, dt, order in [(None, None, None)] + list(itertools.product(("sido", "sigungu", "emd", "h3"), ("pickup", "dropoff", "both"), (None, "top", "bottom"))):
            args = [f"scope_{end}=${end}.scope", "date=last_week"]
            if dim:
                args += [f"dimension={dim}", f"dimension_target={dt}"] + ([f"order={order}", "limit=2"] if order else [])
            out.append(("s2", {"end": end, "dimension": dim, "dimension_target": dt, "order": order},
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
        q = "지난주 대구 초량동 소속 택시 건수 주별 월별"
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
    (HERE / "free_structures10.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    from collections import Counter
    print("structures", len(out), "free", sum(r["free"] for r in out), "free unique family", len({r["family"] for r in out if r["free"]}))
    print(Counter((r["kind"], r["free"]) for r in out))


if __name__ == "__main__":
    main()
