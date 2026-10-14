# -*- coding: utf-8 -*-
"""M2 신규 trace 1차 필터·ranking·선택(PLAN.md 2·3절). 모델 호출 없음(tokenizer만 CPU).

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 python sft_dpo_inventory/p0_sft_003_recovery/m2_quality.py
    # -> m2_quality.json(사람 검토 칸은 비어 있음, m2_review.json이 채운다)
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/loop_filter"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_003/data"))
import ranking  # noqa: E402

RAW = ROOT / "training/generated/p0_sft_003_recovery/m2_raw/traces.jsonl"


def main():
    from build_v004_thinking import CAP_SFT_TOTAL, tokenizer
    from apply_filter import is_loop, loop_metrics
    tok = tokenizer()
    rows = [json.loads(x) for x in RAW.read_text(encoding="utf-8").splitlines() if x.strip()]
    v006 = {json.loads(x)["metadata"]["source_record_id"]: json.loads(x) for x in
            (ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl").read_text(encoding="utf-8").splitlines()}
    by_item = collections.defaultdict(list)
    for r in rows:
        by_item[r["item_id"]].append(r)
    items, cats = {}, collections.Counter(r["judge"]["category"] for r in rows)
    for item, rs in sorted(by_item.items()):
        target = json.loads(v006[item]["messages"][2]["content"])
        cands, seen = [], set()
        detail = []
        for r in rs:
            reasons = []
            if r["judge"]["category"] != "EXACT_OR_SEMANTIC_MATCH":
                reasons.append(r["judge"]["category"])
            if not (r["think_closed"] and (r.get("thinking") or "").strip()):
                reasons.append("no_thinking")
            if r["done_reason"] != "stop":
                reasons.append("truncated")
            if r["done_reason"] == "stop" and r["think_closed"] and \
                    tok(r["raw_text"] + tok.eos_token, add_special_tokens=False)["input_ids"] != r["generated_ids"]:
                reasons.append("decision4_tokenization_mismatch")
            m = loop_metrics(r.get("thinking") or "")
            if (is_loop(m) if m else ["empty_thinking"]):
                reasons.append("decision40D_loop")
            if r["prompt_tokens"] + r["generated_tokens"] + 1 > CAP_SFT_TOTAL:
                reasons.append("decision18_over_length")
            if r["raw_sha256"] in seen:
                reasons.append("duplicate_raw")
            seen.add(r["raw_sha256"])
            q = ranking.quality(r.get("thinking") or "", target) if not reasons else None
            detail.append({"trace_id": r["trace_id"], "category": r["judge"]["category"], "excluded": reasons,
                           "quality": q})
            if not reasons:
                cands.append((r, q))
        pick = min(cands, key=lambda x: ranking.rank_key(x[1], x[0]["sample_index"])) if cands else None
        items[item] = {"exact_samples": sum(r["judge"]["category"] == "EXACT_OR_SEMANTIC_MATCH" for r in rs),
                       "candidates": len(cands), "tiers": dict(collections.Counter(q["tier_name"] for _, q in cands)),
                       "selected": pick[0]["trace_id"] if pick else None,
                       "selected_tier": pick[1]["tier_name"] if pick else None, "traces": detail}
    summary = {"calls": len(rows), "categories": dict(cats),
               "items_with_new_exact": sum(v["exact_samples"] > 0 for v in items.values()),
               "items_with_candidate": sum(v["candidates"] > 0 for v in items.values()),
               "selected_tier": dict(collections.Counter(v["selected_tier"] for v in items.values() if v["selected"])),
               "candidate_tier_total": dict(sum((collections.Counter(v["tiers"]) for v in items.values()), collections.Counter())),
               "truncated": sum(r["done_reason"] == "length" for r in rows)}
    (HERE / "m2_quality.json").write_text(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for k, v in items.items():
        print(k, v["exact_samples"], v["candidates"], v["selected"], v["selected_tier"])


if __name__ == "__main__":
    main()
