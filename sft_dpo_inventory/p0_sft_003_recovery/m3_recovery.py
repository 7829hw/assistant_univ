# -*- coding: utf-8 -*-
"""M3 재검사(PLAN.md 1절). 새 생성 없음, tokenizer만 CPU.

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 python sft_dpo_inventory/p0_sft_003_recovery/m3_recovery.py
    # -> m3_recovery.json
"""
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

M3 = ["b004-19", "b005-19", "b006-10", "b006-11"]


def main():
    from build_v004_thinking import CAP_SFT_TOTAL, tokenizer
    from apply_filter import is_loop, loop_metrics
    tok = tokenizer()
    eos = tok.convert_tokens_to_ids("<|im_end|>")
    traces = [json.loads(x) for x in (ROOT / "training/generated/thinking_traces/p0_v006_hf/traces.jsonl").read_text(encoding="utf-8").splitlines()]
    v006 = {json.loads(x)["metadata"]["source_record_id"]: json.loads(x) for x in
            (ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl").read_text(encoding="utf-8").splitlines()}
    out = {}
    for item in M3:
        target = json.loads(v006[item]["messages"][2]["content"])
        rows = [t for t in traces if t["item_id"] == item and t["judge"]["category"] == "EXACT_OR_SEMANTIC_MATCH"]
        recs, seen = [], set()
        for t in rows:
            ids = t["generated_ids"]
            retok = tok(t["raw_text"] + tok.eos_token, add_special_tokens=False)["input_ids"]
            redecoded = tok.decode(tok(t["raw_text"], add_special_tokens=False)["input_ids"], skip_special_tokens=False)
            first = next((i for i, (a, b) in enumerate(zip(ids, retok)) if a != b), None if len(ids) == len(retok) else min(len(ids), len(retok)))
            m = loop_metrics(t.get("thinking") or "")
            loop = is_loop(m) if m else ["empty_thinking"]
            total = t["prompt_tokens"] + t["generated_tokens"] + 1
            reasons = []
            if retok != ids:
                reasons.append("decision4_tokenization_mismatch")
            if loop:
                reasons.append("decision40D_loop")
            if total > CAP_SFT_TOTAL:
                reasons.append("decision18_over_length")
            checks = {"stop": t["done_reason"] == "stop", "think_closed": bool(t["think_closed"]),
                      "thinking_nonempty": bool((t.get("thinking") or "").strip()), "final_nonempty": bool(t["content"].strip()),
                      "ends_with_eos": bool(ids) and ids[-1] == eos,
                      "string_roundtrip_exact": redecoded == t["raw_text"],
                      "no_loop": not loop, "within_length": total <= CAP_SFT_TOTAL, "exact_match": True}
            recoverable = all(checks.values())
            ctx = None
            if first is not None:
                ctx = {"position": first, "generated": tok.convert_ids_to_tokens(ids[max(0, first - 2):first + 3]),
                       "retokenized": tok.convert_ids_to_tokens(retok[max(0, first - 2):first + 3]),
                       "len_generated": len(ids), "len_retokenized": len(retok)}
            q = ranking.quality(t.get("thinking") or "", target)
            dup = t["raw_sha256"] in seen
            seen.add(t["raw_sha256"])
            recs.append({"trace_id": t["trace_id"], "kind": t["kind"], "sample_index": t["sample_index"], "duplicate_raw": dup,
                         "filter_reasons": reasons, "checks": checks, "mismatch": ctx,
                         "verdict": "RECOVERABLE" if recoverable and not dup else "NOT_RECOVERABLE", "quality": q})
        cands = [r for r in recs if r["verdict"] == "RECOVERABLE"]
        pick = min(cands, key=lambda r: ranking.rank_key(r["quality"], r["sample_index"])) if cands else None
        out[item] = {"correct_traces": len(rows), "traces": recs, "recoverable": len(cands),
                     "selected_for_review": pick["trace_id"] if pick else None}
    summary = {k: {"correct": v["correct_traces"], "recoverable": v["recoverable"], "selected": v["selected_for_review"]} for k, v in out.items()}
    (HERE / "m3_recovery.json").write_text(json.dumps({"summary": summary, "items": out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for k, v in out.items():
        for r in v["traces"]:
            print(k, r["trace_id"], r["filter_reasons"], r["verdict"], r["mismatch"], r["quality"]["tier_name"], r["quality"]["wrong_mentions"])


if __name__ == "__main__":
    main()
