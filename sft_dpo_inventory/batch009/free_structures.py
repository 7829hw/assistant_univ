# -*- coding: utf-8 -*-
"""batch009 2차 후보용: (od, dimension, dimension_target, order) 구조마다 정답 호출을 만들어 family 키를 계산하고,
보호 넷(+ holdout)·selection_v1·thor 보호 family·확장 family와 겹치지 않고 현재 코드가 답하는 구조만 낸다. 문장은 다루지 않는다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/batch009/free_structures.py   # -> free_structures.json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch004"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300_review"))


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
    blocked = set()
    for name in ("selection_v2", "valid98", "aux_test_v1", "selection_v1"):
        for _, _, pl in tg[name]:
            if pl:
                try:
                    blocked.add(family_key(pl))
                except Exception:  # noqa: BLE001
                    pass
    hold = {i["id"] for i in json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/holdout_v1.json").read_text(encoding="utf-8"))["list"]}
    blocked |= {family_key(EV.derive_grounding(i["gold"])) for i in read_jsonl(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_300.jsonl")
                if i["id"] in hold}
    _, ext_f = extended_fingerprints()
    guard = Protection.current(ROOT / "training/generated/reviewed_gold_v006_t2pc")
    places = {"none": [], "pickup": ["get_place_scope(name=수성구, region=대구)"], "dropoff": ["get_place_scope(name=수성구, region=대구)"],
              "both_one": ["get_place_scope(name=대구)"], "two": ["get_place_scope(name=수성구, region=대구)", "get_place_scope(name=부산)"]}
    args = {"none": "", "pickup": "scope_pickup=$pickup.scope, ", "dropoff": "scope_dropoff=$dropoff.scope, ",
            "both_one": "scope_pickup=$area.scope, scope_dropoff=$area.scope, ", "two": "scope_pickup=$pickup.scope, scope_dropoff=$dropoff.scope, "}
    out = []
    for od in places:
        for dim in ("sido", "sigungu", "emd", "h3"):
            for dt in ("pickup", "dropoff", "both"):
                for order in (None, "top", "bottom"):
                    tail = f", order={order}, limit=2" if order else ""
                    calls_text = places[od] + [f"get_trip_count({args[od]}date=last_week, dimension={dim}, dimension_target={dt}{tail})"]
                    calls = EV.parse_calls("\n".join(calls_text))
                    payload = EV.derive_grounding(calls)
                    fk = family_key(payload)
                    q = "지난주 대구 수성구 부산 건수"
                    pl, _ = add_spans(payload, q)
                    chain = validate_semantics(semantics_from_full(pl), q, calls)
                    thor_f = "protected_semantic_family" in guard.reasons("-", payload, ["-"])
                    out.append({"od": od, "dimension": dim, "dimension_target": dt, "order": order, "family": fk[:12],
                                "blocked_by_four_or_sel1": fk in blocked, "extended_family": bool(ext_f.get(fk)), "thor_family": thor_f,
                                "code_answers": bool(chain["full_answered"] and chain["ok"]),
                                "free": fk not in blocked and not ext_f.get(fk) and not thor_f and bool(chain["full_answered"] and chain["ok"])})
    (HERE / "free_structures.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    free = [o for o in out if o["free"]]
    print(len(out), "free", len(free))
    for o in free:
        print(o["od"], o["dimension"], o["dimension_target"], o["order"])


if __name__ == "__main__":
    main()
