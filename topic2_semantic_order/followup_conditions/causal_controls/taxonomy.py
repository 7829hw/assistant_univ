"""Score overlapping errors from frozen scorer evidence without model calls."""
import argparse
from collections import Counter, defaultdict
import csv

from schedules import HERE
from common import ROOT, load, local, S
from regression import A

ERRORS = ("tool_selection", "grounding", "argument", "aggregation", "refusal", "silent_wrong",
          "truncation", "execution_failure", "unclassified_error")
REFUSAL = {"refused_unsupported", "refused_clarification", "wrong_refusal_reason",
           "wrong_refusal_kind", "answered_instead_of_refusal"}
AGGREGATION_KEYS = {"aggregation", "rollup", "bucket"}


def classify(row):
    category = row["category"]
    checks = row.get("checks") or {}
    flags = set()
    if checks.get("tool_ok") is False or checks.get("single_analysis_call") is False:
        flags.add("tool_selection")
    if (row.get("grounding_ok") is False or row.get("grounding_diffs")
        or any(checks.get(key) is False for key in ("place_lookups_ok", "place_lookup_count_ok"))):
        flags.add("grounding")
    keys = {m[0] for m in checks.get("arg_mismatches") or []}
    if keys or checks.get("args_ok") is False:
        flags.add("argument")
    if keys & AGGREGATION_KEYS:
        flags.add("aggregation")
    if category in REFUSAL:
        flags.add("refusal")
    if category == "answered_mismatch":
        flags.add("silent_wrong")
    if category == "failed":
        flags.add("execution_failure")
    if any(call.get("finish_reason") == "length" for call in row.get("hf_calls") or []):
        flags.add("truncation")
    if category not in ("match","expected_refusal") and not flags:
        flags.add("unclassified_error")
    return flags


def write_csv(path, rows):
    if not rows:
        raise ValueError("Refusing to write an empty table")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def recorded_cells(historical_only=False):
    for arm in "AB":
        for seed in A.SEEDS:
            yield from (("historical",arm,seed[1:],dataset,p)
                        for dataset,paths in (("CT10K",A.ct_paths(arm,seed)),("H-dev",[A.hd_path(arm,seed)]),
                                              ("E1",[p for group in A.e1_cells(arm,seed).values() for p in group]))
                        for p in paths)
    if historical_only:
        return
    f=HERE.parent/"gpu/execution/eval_provenance.jsonl"
    if not f.exists():
        return
    labels={f"{c['label']}_s{c['k']}":(j["arm"],str(j["order_seed"]),c["dataset"])
            for phase in (1,2) for j in load(HERE.parent/f"gpu/jobs_phase{phase}.json")["jobs"] for c in j["cells"]}
    for receipt in S.read_jsonl(f):
        cell = receipt["cell"]
        source = HERE.parent/"cells"/f"{cell}.json"
        if S.sha_file(source)!=receipt["sha256"]:
            raise ValueError(f"Stored evaluation hash mismatch: {cell}")
        arm,seed,dataset=labels[cell]
        yield "followup",arm,seed,dataset,local(source)


def summarize_cells(cells):
    counts=defaultdict(Counter)
    provenance=[]
    maps={}
    seen=set()
    for study,arm,seed,dataset,path in cells:
        source=ROOT/path
        if source in seen:
            raise ValueError(f"Duplicate evaluation source: {path}")
        seen.add(source)
        doc=load(source)
        meta=doc["meta"]
        expected=meta.get("item_order")
        ids=[r["id"] for r in doc["rows"]]
        if len(ids)!=len(set(ids)) or (expected is not None and ids!=expected):
            raise ValueError(f"Invalid item coverage: {path}")
        gold_path=meta["gold_file"]
        allowed={A.CT,A.HDEV,*A.CORE.SETS.values()}
        if gold_path not in allowed:
            raise ValueError(f"Evaluation source outside the development allowlist: {gold_path}")
        if gold_path not in maps:
            maps[gold_path]={i:(A.A13.tsig(r.get("gold")),*A.esig(r.get("gold"))) for i,r in A.load_gold(gold_path).items()}
        tmap=maps[gold_path]
        provenance.append(dict(study=study,arm=arm,order_seed=seed,dataset=dataset,source=path,
                               sha256=S.sha_file(source),n=len(ids)))
        for r in doc["rows"]:
            flags=classify(r)
            key=tuple(sorted(flags))
            typ,coarse,fine=tmap[r["id"]]
            for group in ("ALL",f"type:{typ}",f"coarse:{coarse}",f"fine:{fine}"):
                tally=counts[study,arm,seed,dataset,group]
                tally["items"]+=1
                tally["scorer_correct"]+=r["category"] in ("match","expected_refusal")
                tally["any_flag"]+=bool(flags)
                tally.update(flags)
                tally[key]+=1
    rows=[]
    overlaps=[]
    for (study,arm,seed,dataset,group), c in sorted(counts.items()):
        shared=dict(study=study,arm=arm,order_seed=seed,dataset=dataset,group=group,items=c["items"])
        rows.append(dict(**shared,scorer_correct=c["scorer_correct"],any_flag=c["any_flag"],
                         **{tag:c[tag] for tag in ERRORS}))
        for flags, n in sorted((k,v) for k,v in c.items() if isinstance(k,tuple)):
            overlaps.append(dict(**shared,flags="|".join(flags),count=n))
    return rows,overlaps,provenance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-only",action="store_true")
    parser.add_argument("--snapshot-from",type=str,help="Reuse the exact paths and hashes in a prior taxonomy sources CSV")
    args=parser.parse_args()
    cells=list(recorded_cells(args.historical_only)) if not args.snapshot_from else []
    if args.snapshot_from:
        allowed={row[-1] for row in recorded_cells(args.historical_only)}
        with open(args.snapshot_from,encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if row["source"] not in allowed or S.sha_file(ROOT/row["source"])!=row["sha256"]:
                    raise ValueError(f"Snapshot input changed: {row['source']}")
                cells.append(tuple(row[k] for k in ("study","arm","order_seed","dataset","source")))
    rows,overlaps,provenance=summarize_cells(cells)
    suffix="_historical" if args.historical_only else "_snapshot"
    for stem,data in (("taxonomy",rows),("taxonomy_overlap",overlaps),("taxonomy_sources",provenance)):
        write_csv(HERE/"tables"/f"{stem}{suffix}.csv",data)
    print(f"Classified {sum(r['n'] for r in provenance)} scored rows from {len(provenance)} cells")


if __name__=="__main__":
    main()
