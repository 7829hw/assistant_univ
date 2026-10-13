"""reviewed_gold_v006_p0 전체 검사(모델 호출 없음). 출력: v006_verification.json, dataset_stats_v006.json.

    /data/hwkim/path_repeat_001/venv/py/bin/python evaluation/partial_grounding/sft_p0/verify_v006.py

1. 불변식(154건 모두): metadata.target_full(Full canonical gold)을 `build_targets.convert`로 다시 변환해
   - 저장된 assistant(P0 target)와 같은가(변환 결정성),
   - Full·P0가 같은 T2PC 운영 경로에서 같은 실행 결과(parse·outcome·error_code·validation·operators·compile)를 내는가,
   - 의미 서명(EVENT 제외: 측정값·장소·scope·od_role·factors 전부 = dimension·dimension_target·bucket·aggregation·rollup·
     answer·taxi_type·taxi_status·date·time·order·limit)과 평가 비교 정규형이 같은가.
2. 오염: 질문·id·template·family를 보호 원본 전체(`Protection.current`), 확장 지문, 평가셋 4종(vendor100, valid98, sel154,
   aux_test_v1)에 대조한다. 한 장소 od_role=both는 두 장소로 펼친 형태도 대조한다.
   - v005 문항의 기존 겹침은 결정 15·54에서 허용된 예외 목록과 맞춰 본다. 목록 밖의 겹침이 있으면 new_hits로 따로 센다.
   - 신규(batch006) 문항은 어떤 겹침이든 new_hits다(제외 대상).
3. 분포(dataset_stats.stats와 같은 정의): 전체, v005, 신규.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch006"))

import check_candidates as CC  # noqa: E402  (경로 설정과 겹침 도구를 함께 불러온다)
from check_candidates import (BT, Protection, as_record, expand_both, extended_fingerprints, eval_index,  # noqa: E402
                              family_key, question_key, template_key)
from dataset_stats import stats  # noqa: E402

DATA = ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"


def overlap(guard, ext_t, ext_f, evk, rid, q, payload):
    hits = [f"protected:{x}" for x in guard.reasons(q, payload, [rid])]
    tk, fk = template_key(as_record(payload)), family_key(payload)
    if ext_t.get(tk):
        hits.append("extended_template")
    if ext_f.get(fk):
        hits.append("extended_family")
    alt = expand_both(payload)
    alt_keys = (template_key(as_record(alt)), family_key(alt)) if alt else None
    if alt_keys:
        if alt_keys[0] in guard.templates or alt_keys[0] in ext_t:
            hits.append("both_expanded_template")
        if alt_keys[1] in guard.families or alt_keys[1] in ext_f:
            hits.append("both_expanded_family")
    qk = question_key(q)
    for name, k in evk.items():
        kinds = [kind for kind, v in (("question", qk), ("id", rid), ("template", tk), ("family", fk)) if v in k[kind]]
        if alt_keys:
            kinds += [f"both_expanded_{kind}" for kind, v in zip(("template", "family"), alt_keys) if v in k[kind]]
        hits += [f"eval:{name}:{kind}" for kind in kinds]
    return sorted(set(hits))


def main():
    rows = [json.loads(x) for x in DATA.read_text(encoding="utf-8").splitlines() if x.strip()]
    guard = Protection.current(CC.GOLD_DIR)
    ext_t, ext_f = extended_fingerprints()
    evk = eval_index()
    inv = []
    for r in rows:
        m = r["metadata"]
        q = r["messages"][1]["content"]
        stored = json.loads(r["messages"][2]["content"])
        p0, conv = BT.convert(q, m["target_full"])
        hits = overlap(guard, ext_t, ext_f, evk, m["source_record_id"], q, m["target_full"])
        inv.append({"id": m["source_record_id"], "source": m["source"], "question": q,
                    "deterministic": p0 == stored, "auto_pass": conv["auto_pass"], "problems": conv["problems"],
                    "full_exec": conv["full_exec"], "p0_exec": conv["p0_exec"], "overlap": hits,
                    "has_thinking_field": "<think>" in r["messages"][2]["content"]})
    # v005 기존 겹침(결정 15·54 허용분). 질문·id 겹침은 허용된 적이 없다.
    allowed_kinds = ("template", "family")
    for x in inv:
        new = [h for h in x["overlap"] if x["source"] != "v005" or not any(h.endswith(k) for k in allowed_kinds)]
        x["new_hits"] = new
        x["known_exception_hits"] = [h for h in x["overlap"] if h not in new]
    by_src = collections.defaultdict(list)
    for x in inv:
        by_src[x["source"]].append(x)
    summary = {
        "records": len(inv),
        "by_source": {s: len(v) for s, v in by_src.items()},
        "deterministic_conversion": sum(x["deterministic"] for x in inv),
        "invariants_pass": sum(x["auto_pass"] for x in inv),
        "invariant_failures": {x["id"]: x["problems"] for x in inv if not x["auto_pass"]},
        "outcomes_full": dict(collections.Counter(str(x["full_exec"]["outcome"]) for x in inv)),
        "compile_ok_full": sum(bool(x["full_exec"]["compile_ok"]) for x in inv),
        "overlap_any": {s: sum(bool(x["overlap"]) for x in v) for s, v in by_src.items()},
        "new_hits": {x["id"]: x["new_hits"] for x in inv if x["new_hits"]},
        "known_exception_items_v005": {x["id"]: x["known_exception_hits"] for x in inv if x["known_exception_hits"]},
        "known_exception_kinds": dict(collections.Counter(h for x in inv for h in x["known_exception_hits"])),
        "question_or_id_overlap": sum(any(h.endswith((":question", ":id")) or h in ("protected:question", "protected:id")
                                          for h in x["overlap"]) for x in inv),
    }
    out = {"note": "모델 호출 없음. v005 문항의 template·family 겹침은 결정 15·54에서 허용한 기존 예외로 따로 센다.",
           "summary": summary, "items": inv}
    (HERE / "v006_verification.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    targets = {x["id"]: json.loads(r["messages"][2]["content"]) for x, r in zip(inv, rows)}
    new = [x for x in inv if x["source"] != "v005"]
    dstats = {
        "note": "reviewed_gold_v006_p0 최종 분포(P0 target 기준, dataset_stats.stats와 같은 정의).",
        "v006": stats(list(targets.values())),
        "v005": stats([targets[x["id"]] for x in inv if x["source"] == "v005"]),
        "new_batch006": stats([targets[x["id"]] for x in new]),
        "new_by_source": {s: stats([targets[x["id"]] for x in v]) for s, v in by_src.items() if s != "v005"},
    }
    (HERE / "dataset_stats_v006.json").write_text(json.dumps(dstats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for k in ("v006", "v005", "new_batch006"):
        print(k, json.dumps(dstats[k], ensure_ascii=False))


if __name__ == "__main__":
    main()
