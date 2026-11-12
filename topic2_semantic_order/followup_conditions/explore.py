"""Post-hoc matched signature associations; no significance declarations."""
import csv
from collections import defaultdict

from common import *
from exposure import write_csv


def rows(name):
    with (HERE / "tables" / (name + ".csv")).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rankdata(values):
    a = np.asarray(values)
    order = np.argsort(a, kind="stable")
    _, starts, counts = np.unique(a[order], return_index=True, return_counts=True)
    r = np.empty(len(a))
    r[order] = np.repeat(starts + (counts+1)/2, counts)
    return r


def rank_partial(x,y,controls):
    x,y=map(rankdata,(x,y))
    if controls is not None:
        x=x-controls@np.linalg.lstsq(controls,x,rcond=None)[0]
        y=y-controls@np.linalg.lstsq(controls,y,rcond=None)[0]
    return float(np.corrcoef(x,y)[0,1]) if min(np.std(x),np.std(y))>1e-8 else None


def main():
    exp = {(r["level"],r["group"],r["seed"],r["arm"]):r for r in rows("exposure_by_group")}
    sup = {(r["level"],r["group"],r["seed"],r["arm"]):r for r in rows("effective_supervision")}
    groups = defaultdict(dict)
    for r in rows("group_regression"):
        if r["dataset"]=="CT10K" and r["level"] in ("coarse","fine"):
            groups[r["level"],r["group"],r["seed"]][r["arm"]]=r
    matched, assoc = [], []
    for (lv,g,s),d in groups.items():
        row=dict(level=lv,group=g,seed=int(s),n=int(d["A"]["n"]),base=float(d["A"]["base"]),
                 B_minus_A=float(d["B"]["vs_A"]),B_minus_base=float(d["B"]["vs_base"]))
        if (lv,g,s,"A") in exp:
            a,b=[exp[lv,g,s,arm] for arm in "AB"]
            sa,sb=[sup[lv,g,s,arm] for arm in "AB"]
            row.update(records=int(b["records"]), matched=True,
                       **{f"delta_{k}":float(b[k])-float(a[k]) if a[k] and b[k] else None
                          for k in ("gap_mean","max_absence","last","exit_fraction","lr_mean")},
                       loss_per_record=float(sb["loss"])/float(sb["records"]),
                       delta_share_lr_loss=float(sb["share_lr_loss"])-float(sa["share_lr_loss"]))
        else:
            row.update(matched=False)
        matched.append(row)
    specs = {k:"B_minus_A" for k in ("delta_gap_mean","delta_max_absence","delta_last","delta_exit_fraction",
                                      "delta_lr_mean","delta_share_lr_loss")}
    specs["loss_per_record"]="B_minus_base"
    for lv in ("fine","coarse"):
        for x,y in specs.items():
            rr=[r for r in matched if r["level"]==lv and r["matched"] and r.get(x) is not None]
            if len({r["group"] for r in rr})<4:
                continue
            def estimate(rs):
                zs=sorted({r["seed"] for r in rs})
                cov=np.column_stack([np.ones(len(rs)),*[rankdata([r[k] for r in rs]) for k in ("n","base","records")],
                                     *[[r["seed"]==s for r in rs] for s in zs[1:]]])
                xv,yv=([r[k] for r in rs] for k in (x,y))
                return rank_partial(xv,yv,None),rank_partial(xv,yv,cov)
            raw,adj=estimate(rr)
            loo=[estimate([r for r in rr if r["seed"]!=s])[1] for s in SEEDS]
            vals=[x for x in loo if x is not None]
            assoc.append(dict(level=lv,predictor=x,outcome=y,group_seed_rows=len(rr),groups=len({r["group"] for r in rr}),
                              spearman=raw,partial_rank=adj,leave_seed_min=min(vals) if vals else None,
                              leave_seed_max=max(vals) if vals else None))
    write_csv("signature_join",matched)
    write_csv("exploratory_associations",assoc)


if __name__=="__main__":
    main()
