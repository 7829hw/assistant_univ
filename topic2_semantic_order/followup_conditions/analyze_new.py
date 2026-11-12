"""Frozen contrasts for complete follow-up cells. Missing results stay missing."""
import argparse
import os

# Small matrix products run faster with one BLAS thread.
os.environ["OPENBLAS_NUM_THREADS"]="1"
import numpy as np

from common import *
from exposure import write_csv
from regression import A, context, group_row, read_model, run_summary

CONTRASTS={
    "interaction":{"D":1,"C":-1,"B":-1,"A":1},
    "F0_minus_B":{"F0":1,"B":-1},
    "F48_minus_B":{"F48":1,"B":-1},
    **{f"{a}_minus_A":{a:1,"A":-1} for a in ("B","C","D","F0","F48")},
}


def divides(x,n):
    return np.divide(x,n,out=np.full_like(x,np.nan,dtype=float),where=n>0)


def cluster_metrics(grouped, tot, group_regress, M, N, R, c, index):
    """Calculate metrics within each seed, then average selected seeds in a replicate."""
    den=c@N
    acc=divides(np.einsum("bk,skg->bsg",c,grouped),den[:,None,:])
    baseacc=divides(c@M,den)
    overall=divides(c@tot.T,(c@R)[:,None])
    loss=divides(np.einsum("bk,skg->bsg",c,group_regress),(c@M)[:,None,:])
    b=np.arange(len(c))[:,None]
    use=acc[b,index]
    ov=overall[b,index]
    q=np.maximum(1,np.ceil(.1*np.sum(den>0,axis=1)).astype(int))
    low=np.sort(use,axis=2)
    qmask=np.arange(use.shape[2])[None,None,:]<q[:,None,None]
    avg=lambda x:x.mean(axis=1)
    out=dict(overall=avg(ov),overall_seed_sd=ov.std(axis=1,ddof=1),worst=avg(np.nanmin(use,axis=2)),
             bottom_decile=avg(np.where(qmask,low,0).sum(axis=2)/q[:,None]),
             collapse20=avg((use<baseacc[:,None,:]-.20).sum(axis=2)),
             collapse30=avg((use<baseacc[:,None,:]-.30).sum(axis=2)),
             group_seed_var=np.nanmean(use.var(axis=1,ddof=1),axis=1),
             group_accuracy=avg(use), group_regression_rate=avg(loss[b,index]))
    return out


def contrast(tab, by_arm, base, weights, type_sums, reps, rng_seed):
    """One shared seed and template-cluster draw per contrast, across all arms."""
    if not by_arm or any(len(by_arm[a])!=len(SEEDS) for a in weights):
        raise ValueError("All five paired seeds are required for a registered contrast")
    M,_=tab.sums(base)
    mats={}
    for a in weights:
        by=[tab.sums(v) for v in by_arm[a]]
        loss=[tab.sums(base*(1-v))[0] for v in by_arm[a]]
        mats[a]=[np.stack([r[0] for r in by]),np.stack([r[1] for r in by]),np.stack(loss)]
    rng=np.random.default_rng(rng_seed)
    K=tab.K
    ns=len(SEEDS)
    def one(c,ix):
        out={}
        for a,w in weights.items():
            m=cluster_metrics(*mats[a],M,tab.N,tab.itemN,c,ix)
            for name,(den,ts) in type_sums.items():
                acc=divides(c@ts[a].T,(c@den)[:,None])
                m[name]=acc[np.arange(len(c))[:,None],ix].mean(axis=1)
            for k,v in m.items():
                out[k]=out[k]+w*v if k in out else w*v
        return out
    point=one(np.ones((1,K)),np.arange(ns)[None,:])
    results={k:[] for k in point}
    for i in range(0,reps,128):
        n=min(128,reps-i)
        ix=np.empty((n,ns),dtype=int)
        c=np.empty((n,K))
        p=np.full(K,1/K)
        for row in range(n):
            ix[row]=rng.integers(0,ns,ns)
            c[row]=rng.multinomial(K,p)
        for k,v in one(c,ix).items():
            results[k].append(v)
    rows=[]
    for k,p in point.items():
        ds=np.concatenate(results[k],axis=0)
        names=tab.groups if p.ndim==2 else [""]
        for j,g in enumerate(names):
            x=ds[:,j] if g else ds
            x=x[np.isfinite(x)]
            y=float(p[0,j] if g else p[0])
            lo,hi=np.percentile(x,[2.5,97.5]) if len(x) else (None,None)
            wide=np.percentile(x,[100*.05/6,100*(1-.05/6)]) if k=="collapse20" else (None,None)
            rows.append(dict(metric=k,group=g,point=y if np.isfinite(y) else None,ci95_low=lo,ci95_high=hi,
                             family_ci_low=wide[0],family_ci_high=wide[1],nonempty_bootstrap_replicates=len(x)))
    return rows


def checked_cells(job,dataset,validated):
    paths=[]
    for c in job["cells"]:
        if c["dataset"]!=dataset:
            continue
        key=f"{c['label']}_s{c['k']}"
        f=HERE/"cells"/f"{key}.json"
        if not f.is_file() or key not in validated:
            return []
        if S.sha_file(f)!=validated[key]["sha256"]:
            raise ValueError(f"Evaluation result altered after completeness checks: {f}")
        paths.append(local(f))
    return paths


def for_dataset(dataset, jobs, reps, validated):
    ids, clusters, groups = context(dataset)
    paths=A.ct_base_paths() if dataset=="CT10K" else [[f"{A.C12}/hdev_base_s{k}.json"] for k in (1,2)]
    base=np.mean([read_model(p,ids)[0]=="match" for p in paths],axis=0)
    allcats, per_run, by_group = {}, [], []
    for arm in ("A","B","C","D","F0","F48"):
        for seed in SEEDS:
            s=f"o{seed}"
            if arm in "AB":
                paths=A.ct_paths(arm,s) if dataset=="CT10K" else [A.hd_path(arm,s)]
            else:
                j=jobs[arm,seed]
                paths=checked_cells(j,dataset,validated)
            if not paths or not A.exists(paths):
                continue
            cats, extra=read_model(paths,ids)
            allcats[arm,seed]=cats
            summary=run_summary(cats,groups,base)
            per_run.append(dict(dataset=dataset,arm=arm,seed=seed,**summary,**extra,base_accuracy=base.mean(),
                                accuracy_vs_base=summary["accuracy"]-base.mean(),
                                accuracy_vs_A=summary["accuracy"]-(allcats["A",seed]=="match").mean()))
            for level,masks in groups.items():
                for group,mask in masks.items():
                    by_group.append(dict(dataset=dataset,arm=arm,seed=seed,level=level,group=group,
                                    **group_row(mask,cats,base,allcats["A",seed])))
    complete={a for a,_ in allcats if all((a,s) in allcats for s in SEEDS)}
    if not complete:
        return [],per_run,by_group,[]
    by_arm={a:[allcats[a,s]=="match" for s in SEEDS] for a in complete}
    gold=A.load_gold(A.CT if dataset=="CT10K" else A.HDEV)
    rows=[]
    eligible=[(name,w) for name,w in CONTRASTS.items() if set(w)<=complete]
    for level,ix in (("fine",1),("coarse",0)):
        gs={k:A.esig(gold[k].get("gold"))[ix] for k in ids}
        tab=A.Tab(ids,gs,clusters,A.MIN_CT if dataset=="CT10K" else A.MIN_HD)
        ty={t:(tab.sums(m)[1],{a:np.stack([tab.sums(m*v)[1] for v in vs]) for a,vs in by_arm.items()})
            for t,m in groups["type"].items()}
        for name,w in eligible:
            for r in contrast(tab,by_arm,base,w,ty,reps,A.RNG_SEED):
                primary=dataset=="CT10K" and level=="fine" and name in list(CONTRASTS)[:3] and r["metric"]=="collapse20"
                if not primary:
                    r.update(family_ci_low=None,family_ci_high=None)
                r["status"]=("SUPPORTED" if r["family_ci_low"]*r["family_ci_high"]>0 else "INCONCLUSIVE") if primary else "EXPLORATORY"
                rows.append(dict(dataset=dataset,level=level,contrast=name,primary=primary,**r))
    return rows,per_run,by_group,sorted(complete)


def e1(jobs,validated):
    import robust_scoring
    robust_scoring.patch()
    import evaluate_vendor100 as EV
    gold={st:{i["id"]:i for i in EV.load_gold(ROOT/p)["items"]} for st,p in A.CORE.SETS.items()}
    vals, by_run = {}, []
    for (arm,seed),j in {**{(a,s):None for a in "AB" for s in SEEDS},**jobs}.items():
        s=f"o{seed}"
        if j and not checked_cells(j,"E1",validated):
            continue
        paths=A.e1_cells(arm,s) if not j else {
            st:[local(HERE/"cells"/f"{c['label']}_s{c['k']}.json") for c in j["cells"]
                if c["dataset"]=="E1" and c["gold"]==g] for st,g in A.CORE.SETS.items()}
        if all(len(v)==4 and A.exists(v) for v in paths.values()):
            vectors=A.A12.e1_vectors(A.CORE.load_model(paths,dict(A.CORE.SETS),gold,False))
            vals.setdefault(arm,{})[s]=vectors
            by_run.append(dict(arm=arm,seed=seed,**{k:float(np.mean(v)) for k,v in vectors.items()}))
    comparisons={a:A.A12.compare(v,vals["A"],A.SEEDS,list(A.CORE.ITEM_VEC))
                 for a,v in vals.items() if a!="A" and len(v)==5 and len(vals.get("A",{}))==5}
    return comparisons,by_run


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reps",type=int,default=A.REPS)
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    if not args.out and args.reps!=A.REPS:
        p.error("Reduced replicate count requires a separate smoke output")
    jobs={(j["arm"],j["order_seed"]):j for phase in (1,2) for j in load(HERE/f"gpu/jobs_phase{phase}.json")["jobs"]}
    receipt=HERE/"gpu/execution/eval_provenance.jsonl"
    validated={r["cell"]:r for r in S.read_jsonl(receipt)} if receipt.is_file() else {}
    status, tables, runs, groups = {}, [], [], []
    for dataset in ("CT10K","H-dev"):
        res,rr,gr,complete=for_dataset(dataset,jobs,args.reps,validated)
        status[dataset]={"all_five_seeds":complete,"missing_complete_arms":sorted({"C","D","F0","F48"}-set(complete))}
        tables.extend(res); runs.extend(rr); groups.extend(gr)
    er, erun=e1(jobs,validated)
    if args.out:
        dump(args.out,dict(status=status,contrasts=tables,runs=runs,e1=er,reps=args.reps,smoke=args.reps!=A.REPS))
    else:
        dump(HERE/"tables/followup_analysis.json",dict(status=status,e1_vs_A=er,reps=args.reps))
        for n,d in (("registered_contrasts",tables),("followup_evaluation_per_run",runs),
                    ("followup_group_results",groups),("followup_e1_per_run",erun)):
            write_csv(n,d)
    print(status)


if __name__=="__main__":
    main()
