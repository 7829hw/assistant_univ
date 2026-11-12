"""Regressions relative to base and A, using the frozen evaluation definitions."""
from collections import Counter
import re
import sys

from common import *
from exposure import write_csv

sys.path.insert(0, str(T2 / "analysis"))
import analyze_t2 as A
import repeat_pair_t2 as P
sys.path.insert(0, str(ROOT / "topic2_semantic_order_repro/analysis"))
import variance_repro as R


def read_model(paths, ids):
    cats, walls, trunc, calls, errors, server_errors = {}, [], 0, 0, 0, 0
    for path in paths:
        for r in load(ROOT / path)["rows"]:
            key = r["id"]
            if key in cats:
                raise ValueError(f"Duplicate evaluation ID in {path}: {key}")
            cats[key] = r["category"]
            if r.get("started_at") and r.get("finished_at"):
                walls.append(A.A12._ts(r["finished_at"]) - A.A12._ts(r["started_at"]))
            for c in r.get("hf_calls") or []:
                calls += 1
                trunc += c.get("finish_reason") == "length"
            exception = ((r.get("planner_trace") or {}).get("exception") or "")
            unhandled = r.get("error_code")=="UNHANDLED_EXCEPTION"
            errors += bool(unhandled or r.get("evaluator_error") or "error" in r["category"])
            server_errors += bool(unhandled and re.match(r"^(URLError|HTTPError|ConnectionError|ConnectionResetError|ConnectionRefusedError|RemoteDisconnected|TimeoutError|socket\.timeout|IncompleteRead)\b",exception))
    if set(cats) != set(ids):
        raise ValueError(f"Evaluation ID coverage mismatch: {paths}")
    return (np.array([cats[k] for k in ids]), dict(latency_p50_s=np.percentile(walls,50) if walls else None,
            latency_p95_s=np.percentile(walls,95) if walls else None, truncated_calls=trunc, calls=calls,
            truncation=trunc/calls if calls else None, evaluator_or_unhandled_rows=errors, server_error_rows=server_errors))


def context(dataset):
    path, threshold = (A.CT, A.MIN_CT) if dataset == "CT10K" else (A.HDEV, A.MIN_HD)
    gold = A.load_gold(path)
    ids = sorted(gold)
    semantic = [A.esig(gold[k].get("gold")) for k in ids]
    clusters = {k:gold[k]["template_group"] for k in ids}
    sigs = {k:A.A13.tsig(gold[k].get("gold")) for k in ids}
    groups = {}
    for name, keys in (("coarse",[s[0] for s in semantic]),("fine",[s[1] for s in semantic]),
                       ("template",list(clusters.values()))):
        n = Counter(keys)
        groups[name] = {g:np.array(keys)==g for g in sorted(n) if n[g]>=threshold}
    groups["type"] = {g:np.array(list(sigs.values()))==g for g in ("T1","T5")}
    return ids, clusters, groups


def behavior(cats, mask):
    x = cats[mask]
    return dict(accuracy=float(np.mean(x=="match")), refusal=float(np.mean(x=="refused_unsupported")),
                silent_wrong=float(np.mean(x=="answered_mismatch")), failed=float(np.mean(x=="failed")))


def group_row(mask, cats, base, aa):
    pred = cats[mask] == "match"
    b = base[mask]
    p = behavior(cats,mask)
    base_acc = b.mean()
    return dict(n=int(mask.sum()), base=base_acc, **p, vs_base=pred.mean()-base_acc,
                vs_A=pred.mean()-(aa[mask]=="match").mean(), collapse20=bool(pred.mean()<base_acc-.2),
                collapse30=bool(pred.mean()<base_acc-.3), base_correct_sft_wrong=b[~pred].sum(),
                base_wrong_sft_correct=(1-b[pred]).sum(), base_correct_sft_correct=b[pred].sum(),
                base_wrong_sft_wrong=(1-b[~pred]).sum())


def run_summary(cats, groups, base):
    fine = [group_row(m,cats,base,cats) for m in groups["fine"].values()]
    acc = sorted(row["accuracy"] for row in fine)
    return dict(**behavior(cats,np.ones(len(cats),dtype=bool)), worst=acc[0],
                bottom_decile=np.mean(acc[:max(1,int(np.ceil(.1*len(acc))))]),
                collapse20=sum(row["collapse20"] for row in fine), collapse30=sum(row["collapse30"] for row in fine),
                **{g:behavior(cats,m)["accuracy"] for g,m in groups["type"].items()})


def repeat_analysis(ids, groups):
    cells, actions = {}, {}
    for a in "AB":
        for s in R.SEEDS:
            for r in R.RUNS:
                raw = R.load_cell(R.path(a,s,r))
                if set(raw)!=set(ids):
                    raise ValueError("Repeat cell ID coverage mismatch")
                cells[a,s,r]=np.array([raw[i]["category"] for i in ids])
                actions[a,s,r]=np.array([S.canonical([raw[i].get("outcome"),raw[i].get("error_code"),
                    [[x.get("tool"),x.get("args")] for x in raw[i].get("calls") or []]]) for i in ids], dtype=object)
    repeat_summary, pairs, group_variation = [], [], []
    masks = {"overall":np.ones(len(ids),dtype=bool), **groups["type"], **groups["fine"]}
    for g, m in masks.items():
        means, rss, df, distinct = {"A": {}, "B": {}}, 0, 0, []
        for a in "AB":
            for s in R.SEEDS:
                vals = [(cells[a,s,r][m]=="match").mean() for r in R.RUNS]
                means[a][s]=np.mean(vals)
                distinct.append(dict(arm=a,seed=s,group=g, n=int(m.sum()), accuracy_r1=vals[0],
                                     accuracy_r2=vals[1],accuracy_r3=vals[2],sd=np.std(vals,ddof=1)))
                rss += sum((v-np.mean(vals))**2 for v in vals)
                df += len(vals)-1
                for x,y in ((1,2),(1,3),(2,3)):
                    u,v=cells[a,s,x][m],cells[a,s,y][m]
                    pairs.append(dict(arm=a,seed=s,group=g,r1=x,r2=y,n=int(m.sum()),
                                      delta_accuracy=(v=="match").mean()-(u=="match").mean(),
                                      correctness_discordance=np.mean((u=="match")!=(v=="match")),
                                      category_discordance=np.mean(u!=v),
                                      action_signature_discordance=np.mean(actions[a,s,x][m]!=actions[a,s,y][m])))
        group_variation.extend(distinct)
        y = {a:{s:[d[f"accuracy_r{r}"] for r in R.RUNS] for d in distinct if d["arm"]==a for s in [d["seed"]]} for a in "AB"}
        repeat_summary.append(dict(group=g,n=int(m.sum()),within_cell_sd=np.sqrt(rss/df),within_df=df,
                                   repeated_B_minus_A=np.mean([means["B"][s]-means["A"][s] for s in R.SEEDS]),
                                   original_B_minus_A=np.mean([y["B"][s][0]-y["A"][s][0] for s in R.SEEDS]),
                                   **{f"var_{k}":v for k,v in R.anova(y)["var_components_raw"].items()}))
    write_csv("repeat_discordance",pairs)
    write_csv("repeat_group_runs",group_variation)
    write_csv("repeat_summary",repeat_summary)
    one = {k:P.load(p) for k,p in P.paths.items()}
    dump(HERE/"tables/original_repeat_pair.json",{f"{a}_vs_{b}":P.pair(one[a],one[b])
         for a,b in (("A","A_r2"),("B","B_r2"),("A","B"),("A_r2","B_r2"))})


def main():
    group_rows, runs, seed_var = [], [], []
    for dataset in ("CT10K","H-dev"):
        ids, _, groups = context(dataset)
        baserefs = A.ct_base_paths() if dataset == "CT10K" else [[f"{A.C12}/hdev_base_s{k}.json"] for k in (1,2)]
        base = np.mean([read_model(p,ids)[0]=="match" for p in baserefs],axis=0)
        for s in A.SEEDS:
            models = {a:read_model(A.ct_paths(a,s) if dataset=="CT10K" else [A.hd_path(a,s)],ids) for a in "AB"}
            for a, (cats,extra) in models.items():
                meta = dict(dataset=dataset,arm=a,seed=int(s[1:]))
                runs.append(dict(**meta, **run_summary(cats,groups,base),**extra))
                for level, masks in groups.items():
                    for group, mask in masks.items():
                        group_rows.append(dict(**meta,level=level,group=group,**group_row(mask,cats,base,models["A"][0])))
        for a in "AB":
            for level,masks in groups.items():
                for g in masks:
                    rs = [x for x in group_rows if x["dataset"]==dataset and x["arm"]==a and x["level"]==level and x["group"]==g]
                    acc = [r["accuracy"] for r in rs]
                    seed_var.append(dict(dataset=dataset,arm=a,level=level,group=g,n=rs[0]["n"],mean=np.mean(acc),
                                         across_seed_sd=np.std(acc,ddof=1),accuracy_min=min(acc),accuracy_max=max(acc)))
        if dataset=="H-dev":
            repeat_analysis(ids,groups)
    write_csv("group_regression",group_rows)
    write_csv("evaluation_per_run",runs)
    write_csv("group_seed_variation",seed_var)


if __name__=="__main__":
    main()
