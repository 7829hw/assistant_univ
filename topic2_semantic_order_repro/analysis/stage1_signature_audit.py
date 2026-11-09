"""Stage 1: audit the scheduler's train-only signatures (coarse = tool|metric; fine = + agg/time/region/od)."""
import json, sys, csv
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "topic2_semantic_order"))
import semantic_schedule as SS
recs = SS.read_jsonl(ROOT / "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl")
appr = SS.read_jsonl(ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl")
labels = SS.labels_from_approved(recs, appr)
by_q = Counter(SS.qid(r) for r in recs)
coarse = Counter(); fine = Counter(); unk = Counter(); ex = {}
fields = ["tool", "metric", "agg", "t", "reg", "od"]
apprd = {str(a["id"]): a for a in appr}
exec_src = Counter()
for q, (c, f) in labels.items():
    n = by_q[q]
    coarse[c] += n; fine[f] += n
    parts = dict(p.split("=", 1) for p in f.split("|")[2:] if "=" in p) if "|" in f else {}
    tool, metric = (c.split("|") + ["?"])[:2]
    for name, v in (("tool", tool), ("metric", metric), *parts.items()):
        if v in ("unknown", "none", "?"):
            unk[name + "=" + v] += n
    exec_src[bool(apprd.get(q, {}).get("execution"))] += n
    ex.setdefault(c, f)
out = {"records": len(recs), "questions": len(labels), "coarse_groups": len(coarse), "fine_groups": len(fine),
       "coarse_records": dict(coarse.most_common()), "fine_group_size_quantiles": {k: sorted(fine.values())[int(len(fine) * k / 100)] for k in (0, 25, 50, 75, 100) if k < 100} | {"max": max(fine.values())},
       "fine_groups_le5_records": sum(1 for v in fine.values() if v <= 5), "unknown_or_none_records_by_field": dict(unk.most_common()),
       "records_with_approved_execution": exec_src[True], "records_without_execution(fallback to view)": exec_src[False],
       "contains_fare_or_trip_metrics": [k for k in coarse if "fare" in k or "trip_metrics" in k]}
(ROOT / "topic2_semantic_order_repro/tables/stage1_signature_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
