"""Stage 1 (CPU only): where do the groups of interest sit in the A (true O4') and B (semantic-balanced) record orders, and what is their LR-weighted exposure?

Uses only train data, the approved TRAIN corpus and the frozen order files. No evaluation signal. LR = linear decay 2e-4 -> 0 over 1,984 steps, warmup_steps 1
(configs/*.yaml), one record per optimizer step. Weight per record = metadata.tokens when present, else assistant-message characters (proxy, flagged).
"""
import csv, json, sys, statistics as st
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "topic2_semantic_order"))
import semantic_schedule as SS
OUT = ROOT / "topic2_semantic_order_repro/tables"
SEEDS = [1102, 211102, 2026113, 2026117, 2026131]
BILLING = {"revenue", "active_taxi_count", "active_taxi_ratio", "operating_days"}
N = 1984

recs = SS.read_jsonl(ROOT / "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl")
appr = {str(x["id"]): x for x in SS.read_jsonl(ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl")}
labels = SS.labels_from_approved(recs, list(appr.values()))
by_id = {SS.rid(r): r for r in recs}
slots = SS.training_record_slots(recs)

def sub(r):
    a = appr.get(SS.qid(r)) or {}
    return ((a.get("view") or {}).get("measure") or {}).get("subtype")

def weight(r):
    t = r["metadata"].get("tokens")
    if t:
        return float(t), "tokens"
    return float(len([m for m in r["messages"] if m["role"] == "assistant"][-1]["content"])), "chars"

is_ct = lambda r: r["metadata"].get("contrast_source") == "teacher"
GROUPS = {
    "billing_all": lambda r: sub(r) in BILLING,
    "billing_contrast_teacher": lambda r: is_ct(r) and sub(r) in BILLING,
    "contrast_teacher_all": is_ct,
    "contrast_teacher_nonbilling": lambda r: is_ct(r) and sub(r) not in BILLING,
    "trip_count": lambda r: sub(r) == "trip_count",
    "place_only(scope_name)": lambda r: sub(r) == "place",
    "refusal": lambda r: bool(r["metadata"].get("refusal_source")),
    "fare_measure_direct": lambda r: sub(r) == "fare",
}
wk = {k: Counter() for k in GROUPS}
for r in recs:
    for g, f in GROUPS.items():
        if f(r):
            wk[g][weight(r)[1]] += 1

def seq_for(arm, seed):
    if arm == "B":
        return json.loads((ROOT / f"topic2_semantic_order/orders/semantic_order_o{seed}.json").read_text())["record_sequence"]
    for sub_ in ("ablation_011", "ablation_013"):
        p = ROOT / f"sft_dpo_inventory/{sub_}/build/orders/order_b2_o{seed}.json"
        if p.exists():
            order = json.loads(p.read_text())["order"]
            return [SS.rid(slots[k]) for k in order]
    raise FileNotFoundError(seed)

def lr(step):  # step index 0..N-1 ; linear decay from 2e-4, warmup 1 step
    return 2e-4 * (1 - step / N)

rows = []
for seed in SEEDS:
    for arm in "AB":
        seq = seq_for(arm, seed)
        assert len(seq) == N and set(seq) == set(by_id)
        W = [weight(by_id[k])[0] for k in seq]
        totLR = sum(lr(i) * w for i, w in enumerate(W))
        for g, f in GROUPS.items():
            idx = [i for i, k in enumerate(seq) if f(by_id[k])]
            if not idx:
                continue
            n = len(idx)
            lre = sum(lr(i) * W[i] for i in idx) / totLR
            share = sum(W[i] for i in idx) / sum(W)
            prev_same = sum(1 for i in idx if i > 0 and f(by_id[seq[i - 1]])) / n
            q_runs = 0
            rows.append({"seed": seed, "arm": arm, "group": g, "records": n, "mean_pos_frac": round(st.mean(i / N for i in idx), 4),
                         "last10pct": sum(i >= 0.9 * N for i in idx), "last25pct": sum(i >= 0.75 * N for i in idx), "last50pct": sum(i >= 0.5 * N for i in idx),
                         "token_share": round(share, 4), "lr_weighted_share": round(lre, 4), "lr_over_token_share": round(lre / share, 3),
                         "prev_in_same_group": round(prev_same, 3),
                         "median_gap_to_next_same_group": st.median([b - a for a, b in zip(idx, idx[1:])]) if n > 1 else None})
OUT.mkdir(exist_ok=True)
with (OUT / "stage1_order_exposure.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
(OUT / "stage1_order_exposure_weight_basis.json").write_text(json.dumps({g: dict(c) for g, c in wk.items()}, indent=1))
# transitions: coarse-group neighbour of billing-contrast-teacher records
tr = {}
for arm in "AB":
    c = Counter()
    for seed in SEEDS:
        seq = seq_for(arm, seed)
        for i, k in enumerate(seq):
            if GROUPS["billing_contrast_teacher"](by_id[k]):
                for j in (i - 1, i + 1):
                    if 0 <= j < N:
                        c[labels[SS.qid(by_id[seq[j]])][0] if SS.qid(by_id[seq[j]]) in labels else "?"] += 1
    tot = sum(c.values()); tr[arm] = {k: round(v / tot, 3) for k, v in c.most_common(8)}
(OUT / "stage1_billing_ct_neighbour_coarse.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1))
print(json.dumps(wk, default=dict)[:600]); print(json.dumps(tr, ensure_ascii=False, indent=1)[:1200])

# ---- by loss scope / source / contrast ----
extra = []
for seed in SEEDS:
    for arm in "AB":
        seq = seq_for(arm, seed)
        W = [weight(by_id[k])[0] for k in seq]
        totLR = sum(lr(i) * w for i, w in enumerate(W)); totW = sum(W)
        cats = defaultdict(list)
        for i, k in enumerate(seq):
            m = by_id[k]["metadata"]
            cats[f"scope={m['loss_scope']}"].append(i)
            cats[f"source={m['source']}"].append(i)
            cats[f"contrast_set={m.get('contrast_set')}"].append(i)
            cats[f"ct={is_ct(by_id[k])}&scope={m['loss_scope']}"].append(i)
        for c, idx in cats.items():
            extra.append({"seed": seed, "arm": arm, "category": c, "records": len(idx), "mean_pos_frac": round(st.mean(i / N for i in idx), 4),
                          "token_share": round(sum(W[i] for i in idx) / totW, 4), "lr_weighted_share": round(sum(lr(i) * W[i] for i in idx) / totLR, 4)})
with (OUT / "stage1_order_exposure_by_category.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(extra[0])); w.writeheader(); w.writerows(extra)
