"""Stage 1: split T1/T5/T3 `wrong_region` into (a) model made no get_place_scope lookup although gold has one, (b) lookup made but different place/args,
(c) other. Existing cells only; item type from gold calls."""
import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); import stage1_failure_types as S
T = S.T

def split(row, gold_calls):
    gp = [c for c in gold_calls if c.get("tool") == "get_place_scope"]
    mp = [c for c in (row.get("calls") or []) if c.get("tool") == "get_place_scope"]
    if gp and not mp:
        return "no_place_lookup"
    if len(mp) != len(gp):
        return "lookup_count_differs"
    gn = sorted(((c.get("args") or {}).get("name"), (c.get("args") or {}).get("region")) for c in gp)
    mn = sorted(((c.get("args") or {}).get("name"), (c.get("args") or {}).get("region")) for c in mp)
    return "same_place" if gn == mn else "different_place"

def main():
    gold = {"CT10K": T.load_gold(T.CT), "H-dev": T.load_gold(T.HDEV)}
    out = []
    for ds in ("CT10K", "H-dev"):
        tmap = {i: T.A13.tsig(g.get("gold")) for i, g in gold[ds].items()}
        for arm in "AB":
            for s in S.SEEDS:
                rows = S.load(S.cells(ds, arm, s))
                per = defaultdict(Counter)
                for i, r in rows.items():
                    if S.classify(r) == "wrong_region":
                        per[tmap[i]][split(r, gold[ds][i]["gold"])] += 1
                for t, c in per.items():
                    out.append({"dataset": ds, "type": t, "arm": arm, "seed": s, **c})
    keys = ["dataset", "type", "arm", "seed", "no_place_lookup", "lookup_count_differs", "different_place", "same_place"]
    with (HERE.parent / "tables/stage1_region_split.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, restval=0); w.writeheader(); w.writerows(out)
main()
