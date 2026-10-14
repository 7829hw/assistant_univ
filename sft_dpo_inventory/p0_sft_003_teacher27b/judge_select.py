# -*- coding: utf-8 -*-
"""G5 판정·필터·ranking(IMPORT_AND_TEACHER_PLAN.md). 모델 호출 없음(tokenizer만 CPU).

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 python sft_dpo_inventory/p0_sft_003_teacher27b/judge_select.py
    # -> generation/judge.json, generation/selected_candidates.jsonl(사람 검토 전)

- 판정: collect_p0_traces_hf.judge. 후보는 EXACT_OR_SEMANTIC_MATCH만.
- 필터: thinking 있음·done_reason stop, 결정 40-D 루프 아님, 결정 18 길이, 학습 원문 문자열 왕복 바이트 일치, 중복 원문 아님.
  - 학습 원문: `<think>\\n{thinking}\\n</think>\\n\\n{content}`(training.data.thinking.normalize_trace와 같은 꼴).
  - 길이: prompt token(같은 문항 p0_v006_hf trace의 prompt_tokens, P0 messages 동일) + 원문 + eos token + 1 ≤ CAP_SFT_TOTAL.
- ranking: quality_gate_v1.rank_key. 문항당 1개.
"""
import collections
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "evaluation/partial_grounding/sft_p0"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/loop_filter"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_003/data"))

RAW = ROOT / "training/generated/p0_sft_003_teacher27b/raw/traces.jsonl"
GATE_SHA = "f57e2d3e1045fcf7cb00cfd577b5b8850281158bee52c6d3bd3787bd828bf392"


def main():
    if hashlib.sha256((HERE / "quality_gate_v1.py").read_bytes()).hexdigest() != GATE_SHA:
        raise SystemExit("quality_gate_v1 sha256 불일치")
    import quality_gate_v1 as G
    import collect_p0_traces_hf as C
    from build_v004_thinking import CAP_SFT_TOTAL, tokenizer
    from apply_filter import is_loop, loop_metrics
    tok = tokenizer()
    rows = [json.loads(x) for x in RAW.read_text(encoding="utf-8").splitlines() if x.strip()]
    v006 = {json.loads(x)["metadata"]["source_record_id"]: json.loads(x) for x in
            (ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl").read_text(encoding="utf-8").splitlines()}
    prompt_tokens = {}
    for x in (ROOT / "training/generated/thinking_traces/p0_v006_hf/traces.jsonl").read_text(encoding="utf-8").splitlines():
        t = json.loads(x)
        prompt_tokens.setdefault(t["item_id"], t["prompt_tokens"])
    planner, _ = C.p0_planner()
    by_item = collections.defaultdict(list)
    for r in rows:
        by_item[r["item_id"]].append(r)
    items, selected = {}, []
    cats = collections.Counter()
    for item, rs in by_item.items():
        rec = v006[item]
        if planner.messages(rs[0]["question"]) != rec["messages"][:2]:
            raise SystemExit(f"{item}: 질문이 v006 P0 messages와 다르다")
        target_p0 = json.loads(rec["messages"][2]["content"])
        target_full = rec["metadata"]["target_full"]
        seen, detail, cands = set(), [], []
        for r in sorted(rs, key=lambda r: r["sample_index"]):
            thinking, content = r["thinking"], r["content"]
            j, _ = C.judge(r["question"], content, bool(thinking.strip()), target_p0, target_full)
            cats[j["category"]] += 1
            text = "<think>\n" + thinking + "\n</think>\n\n" + content
            ids = tok(text, add_special_tokens=False)["input_ids"]
            roundtrip = tok.decode(ids, skip_special_tokens=False) == text
            gen = len(tok(text + tok.eos_token, add_special_tokens=False)["input_ids"])
            total = prompt_tokens[item] + gen + 1
            m = loop_metrics(thinking)
            loop = is_loop(m) if m else ["empty_thinking"]
            sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            reasons = []
            if j["category"] != "EXACT_OR_SEMANTIC_MATCH":
                reasons.append(j["category"])
            if not thinking.strip():
                reasons.append("no_thinking")
            if r["done_reason"] != "stop":
                reasons.append("not_stop")
            if loop:
                reasons.append("decision40D_loop")
            if total > CAP_SFT_TOTAL:
                reasons.append("decision18_over_length")
            if not roundtrip:
                reasons.append("string_roundtrip_mismatch")
            if sha in seen:
                reasons.append("duplicate_raw")
            seen.add(sha)
            fl = G.flags(thinking, content)
            d = {"trace_id": r["trace_id"], "kind": r["kind"], "sample_index": r["sample_index"], "seed": r["seed"],
                 "category": j["category"], "judge": j, "done_reason": r["done_reason"], "thinking_chars": len(thinking),
                 "total_tokens": total, "loop": loop, "roundtrip": roundtrip, "raw_sha256": sha,
                 "excluded": reasons, "quality_gate_v1_flags": fl,
                 "rank_key": list(G.rank_key(thinking, content, r["kind"], r["sample_index"]))}
            detail.append(d)
            if not reasons:
                cands.append((d, r, text))
        pick = min(cands, key=lambda c: c[0]["rank_key"]) if cands else None
        items[item] = {"item_index": rs[0]["item_index"], "calls": len(rs),
                       "exact": sum(d["category"] == "EXACT_OR_SEMANTIC_MATCH" for d in detail),
                       "greedy_exact": any(d["category"] == "EXACT_OR_SEMANTIC_MATCH" and d["kind"] == "greedy" for d in detail),
                       "sample_exact": sum(d["category"] == "EXACT_OR_SEMANTIC_MATCH" and d["kind"] == "sample" for d in detail),
                       "candidates": len(cands), "selected": pick[0]["trace_id"] if pick else None,
                       "selected_flags": pick[0]["quality_gate_v1_flags"] if pick else None, "traces": detail}
        if pick:
            d, r, text = pick
            selected.append({"item_id": item, "item_index": r["item_index"], "trace_id": r["trace_id"], "kind": r["kind"],
                             "sample_index": r["sample_index"], "seed": r["seed"], "options": r["options"],
                             "teacher_model": r["teacher_model"], "teacher_digest": r["teacher_digest"],
                             "ollama_version": r["ollama_version"], "generation_batch": r["generation_batch"],
                             "prompt_sha256": r["prompt_sha256"], "question": r["question"],
                             "thinking": r["thinking"], "content": r["content"], "raw_text": text, "raw_sha256": d["raw_sha256"],
                             "total_tokens": d["total_tokens"], "quality_gate_v1_flags": d["quality_gate_v1_flags"],
                             "rank_key": d["rank_key"]})
    selected.sort(key=lambda s: s["item_index"])
    summary = {"calls": len(rows), "categories": dict(cats),
               "greedy_exact": sum(v["greedy_exact"] for v in items.values()),
               "sample_exact": sum(v["sample_exact"] for v in items.values()),
               "items_with_exact": sum(v["exact"] > 0 for v in items.values()),
               "items_with_candidate": sum(v["candidates"] > 0 for v in items.values()),
               "selected": len(selected), "selected_flagged": sum(bool(s["quality_gate_v1_flags"]) for s in selected),
               "selected_flag_counts": dict(collections.Counter(f for s in selected for f in s["quality_gate_v1_flags"])),
               "exclusion_counts": dict(collections.Counter(x for v in items.values() for d in v["traces"] for x in d["excluded"])),
               "not_stop": sum(r["done_reason"] != "stop" for r in rows),
               "quality_gate_sha256": GATE_SHA, "raw_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest()}
    out = HERE / "generation"
    out.mkdir(exist_ok=True)
    (out / "judge.json").write_text(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(out / "selected_candidates.jsonl", "w", encoding="utf-8") as f:
        for s in selected:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for k, v in sorted(items.items(), key=lambda kv: kv[1]["item_index"]):
        print(v["item_index"], k, "exact", v["exact"], "cand", v["candidates"], v["selected"], v["selected_flags"])


if __name__ == "__main__":
    main()
