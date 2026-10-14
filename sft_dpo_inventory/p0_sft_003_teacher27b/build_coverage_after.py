# -*- coding: utf-8 -*-
"""G6 reasoning coverage 갱신(IMPORT_AND_TEACHER_PLAN.md G6). 모델 호출 없음. -> generation/coverage_after.json

- covered = R70 ∪ M3 회수 ∪ M2 회수(p0_sft_003_recovery) ∪ 27B 승인(generation/approved_traces.jsonl), unique item.
- feature는 p0_sft_003_prep/coverage_analysis.feats와 같은 정의(p0_sft_003_recovery/build_coverage.py와 같은 flag).
- 31문항 대상별: target / 정답 후보 있음 / 사람 승인.
- 8B vs 27B reasoning 특성(참고): thinking 길이, Wait·Hmm 수, quality_gate_v1 flag. 승인 여부를 바꾸지 않는다.
"""
import collections
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("ca", ROOT / "sft_dpo_inventory/p0_sft_003_prep/coverage_analysis.py")
CA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CA)
GEN = HERE / "generation"

FLAGS = {
    "dt_pickup": lambda t: t["ft"].get("dimension_target") == "pickup",
    "dt_dropoff": lambda t: t["ft"].get("dimension_target") == "dropoff",
    "dt_both": lambda t: t["ft"].get("dimension_target") == "both",
    "dt_none": lambda t: t["ft"].get("dimension_target") is None,
    "od_ne_dt": lambda t: bool(t["ft"].get("od_ne_dt")),
    "gap_a": lambda t: t["source"] == "augment_dt_event", "gap_b": lambda t: t["source"] == "augment_od_vs_dt",
    "h3": lambda t: t["ft"].get("dimension") == "h3", "sido": lambda t: t["ft"].get("dimension") == "sido",
    "sigungu": lambda t: t["ft"].get("dimension") == "sigungu", "emd": lambda t: t["ft"].get("dimension") == "emd",
    "bucket": lambda t: t["ft"].get("bucket") is not None, "order": lambda t: t["ft"].get("order") is not None,
    "aggregation": lambda t: t["ft"].get("aggregation") is not None}


def split_think(text):
    m = re.match(r"<think>\n(.*)\n</think>\n\n(.*)", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


def style(rows):
    import quality_gate_v1 as G
    th = [len(t) for t, _ in rows]
    hedges = [len(re.findall(r"\b(Wait|Hmm)\b", t)) for t, _ in rows]
    flagged = [bool(G.flags(t, c)) for t, c in rows]
    return {"n": len(rows), "thinking_chars_median": statistics.median(th) if th else None,
            "thinking_chars_mean": round(statistics.mean(th), 1) if th else None,
            "wait_hmm_per_trace_mean": round(statistics.mean(hedges), 2) if hedges else None,
            "traces_with_wait_hmm": sum(h > 0 for h in hedges), "quality_gate_v1_flagged": sum(flagged)}


def main():
    v006 = CA.train_set(CA.read_jsonl(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"))
    by_id = {t["id"]: t for t in v006}
    r70_rows = CA.read_jsonl(ROOT / "training/generated/p0_sft_002/r70/sft_train.jsonl")
    r70 = {r["metadata"]["source_record_id"] for r in r70_rows}
    rec = CA.read_jsonl(ROOT / "sft_dpo_inventory/p0_sft_003_recovery/recovered_traces.jsonl")
    m3 = {r["item_id"] for r in rec if r["recovery"] == "M3"}
    m2 = {r["item_id"] for r in rec if r["recovery"] == "M2"}
    appr = CA.read_jsonl(GEN / "approved_traces.jsonl")
    t27 = {r["item_id"] for r in appr}
    before = r70 | m3 | m2
    if len(before) != 83 or before & t27 or len(t27) != len(appr):
        raise SystemExit(f"중복 또는 기준 불일치: before {len(before)}, overlap {sorted(before & t27)}")
    after = before | t27
    judge = json.loads((GEN / "judge.json").read_text(encoding="utf-8"))["items"]
    man = json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_recovery/teacher27b_manifest.json").read_text(encoding="utf-8"))["items"]
    targets = [x["item_id"] for x in man]

    table = {}
    for name, fn in FLAGS.items():
        ts = [t for t in v006 if fn(t)]
        n = len(ts)
        table[name] = {"v006": n, "before_27b": sum(t["id"] in before for t in ts), "after_27b": sum(t["id"] in after for t in ts),
                       "before_ratio": round(sum(t["id"] in before for t in ts) / n, 3) if n else None,
                       "after_ratio": round(sum(t["id"] in after for t in ts) / n, 3) if n else None}
    recovery = {}
    for name, fn in FLAGS.items():
        ts = [i for i in targets if fn(by_id[i])]
        recovery[name] = {"target": len(ts), "correct_candidate": sum(judge[i]["candidates"] > 0 for i in ts),
                          "human_approved": sum(i in t27 for i in ts)}
    prep = json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_prep/missing_reasoning_manifest.json").read_text(encoding="utf-8"))["items"]
    remaining = [x for x in prep if x["item_id"] not in after]
    cls = collections.Counter()
    for x in prep:
        if x["item_id"] in before:
            continue
        if x["item_id"] in targets:
            cls["M1 P1/P2 — 27B recovered" if x["item_id"] in t27 else "M1 P1/P2 — 27B failed"] += 1
        elif x["m_class"] == "M1":
            cls[f"M1 P{x['priority']} untouched"] += 1
        else:
            cls[f"{x['m_class']} failed(8B 회수 실패)"] += 1
    failed27 = [{"item_id": i, "item_index": judge[i]["item_index"], "categories": dict(collections.Counter(d["category"] for d in judge[i]["traces"])),
                 "features": [n for n, fn in FLAGS.items() if fn(by_id[i])], "source": by_id[i]["source"]} for i in targets if i not in t27]

    r70_style = [split_think(r["messages"][2]["content"]) for r in r70_rows]
    rec_style = [((r.get("thinking") or ""), r.get("content") or "") for r in rec]
    doc = {
        "covered_items": len(after), "of": len(v006), "ratio": round(len(after) / len(v006), 3),
        "before": {"covered": len(before), "ratio": round(len(before) / len(v006), 3)},
        "by_source": {"HF Qwen3-8B R70": len(r70), "HF Qwen3-8B M2 회수": len(m2), "M3 기존 trace 회수": len(m3),
                      "Ollama qwen3.8:27b teacher": len(t27)},
        "duplicate_ids": 0,
        "feature_coverage": table, "teacher27b_recovery_by_feature": recovery,
        "teacher27b_failed_items": failed27,
        "remaining_missing": {"count": len(remaining), "classes": dict(cls),
                              "m_class": dict(collections.Counter(x["m_class"] for x in remaining)),
                              "ids": sorted(x["item_id"] for x in remaining)},
        "reasoning_style_reference": {"hf8b_r70": style(r70_style), "hf8b_recovered_m2_m3": style(rec_style),
                                      "ollama27b_approved": style([(a["thinking"], a["content"]) for a in appr])},
        "frozen_dataset": None, "training_runs": 0}
    (GEN / "coverage_after.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("covered_items", "ratio", "before", "by_source", "remaining_missing")}, ensure_ascii=False, indent=1))
    for k, v in table.items():
        print(k, v, recovery[k])
    print(json.dumps(failed27, ensure_ascii=False))
    print(json.dumps(doc["reasoning_style_reference"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
