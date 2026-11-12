"""Temporal and supervision exposure from orders and the exact TRL ledger."""
from collections import Counter, defaultdict
import ast
import csv

from common import *


def write_csv(name, rows):
    if not rows:
        raise ValueError(f"No rows for {name}")
    p = HERE / "tables" / (name + ".csv")
    p.parent.mkdir(exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields, lineterminator=chr(10))
        w.writeheader()
        w.writerows(rows)


def step_rows(seq, labels, scopes, rates, ledger):
    for i, (key, lr) in enumerate(zip(seq, rates, strict=True), 1):
        q = key.split("|", 1)[0]
        c, f = labels[q]
        yield dict(step=i, record=key, question=q, coarse=c, fine=f, scope=scopes[key],
                   lr=lr, input_tokens=ledger[key][0], loss_tokens=ledger[key][1])


def summarize(rows, level):
    by_group = defaultdict(list)
    transitions = Counter()
    for i, r in enumerate(rows):
        by_group[r[level]].append(r)
        if i and rows[i-1][level] != r[level]:
            transitions[(rows[i-1][level], r[level])] += 1
    a, b = [], []
    n = len(rows)
    totals = dict(records=n, input=sum(x["input_tokens"] for x in rows), loss=sum(x["loss_tokens"] for x in rows),
                  lr=sum(x["lr"] for x in rows), lr_input=sum(x["lr"]*x["input_tokens"] for x in rows),
                  lr_loss=sum(x["lr"]*x["loss_tokens"] for x in rows))
    for group, rr in sorted(by_group.items()):
        pos = np.array([r["step"] for r in rr])
        gap = np.diff(pos)
        absent = np.r_[pos[0]-1, gap-1, n-pos[-1]]
        outgoing = {v:k for (u,v),k in transitions.items() if u==group}
        incoming = {u:k for (u,v),k in transitions.items() if v==group}
        full = sum(r["scope"] == "full_response" for r in rr)
        count = len(rr)
        base = dict(level=level, group=group, records=count, questions=len({r["question"] for r in rr}))
        a.append(dict(**base, position_mean=pos.mean(), position_variance=pos.var(), first=pos[0], last=pos[-1],
                      gap_mean=gap.mean() if len(gap) else None, gap_p50=np.median(gap) if len(gap) else None,
                      gap_p90=np.percentile(gap,90) if len(gap) else None, gap_max=gap.max() if len(gap) else None,
                      max_absence=absent.max(), gap_histogram=json.dumps(dict(sorted(Counter(map(int,gap)).items()))),
                      exits=sum(outgoing.values()), entries=sum(incoming.values()),
                      exit_fraction=sum(outgoing.values())/max(1,count-int(pos[-1]==n)),
                      outgoing=json.dumps(outgoing,ensure_ascii=False), incoming=json.dumps(incoming,ensure_ascii=False),
                      full_response_fraction=full/count, json_only_fraction=1-full/count,
                      lr_mean=sum(r["lr"] for r in rr)/count,
                      **{f"decile_{i+1}":int(((pos-1)*10//n==i).sum()) for i in range(10)}))
        vals = dict(records=count, input=sum(r["input_tokens"] for r in rr), loss=sum(r["loss_tokens"] for r in rr),
                    lr=sum(r["lr"] for r in rr), lr_input=sum(r["lr"]*r["input_tokens"] for r in rr),
                    lr_loss=sum(r["lr"]*r["loss_tokens"] for r in rr))
        b.append(dict(**base, **{k:v for k,v in vals.items() if k!="records"},
                      **{f"share_{k}": v/totals[k] for k,v in vals.items()},
                      full_response_loss_tokens=sum(r["loss_tokens"] for r in rr if r["scope"]=="full_response"),
                      json_only_loss_tokens=sum(r["loss_tokens"] for r in rr if r["scope"]=="json_only")))
    return a, b


def window_tv(rows, level, weight, window=128):
    def shares(rr):
        c = Counter()
        for r in rr:
            c[r[level]] += weight(r)
        total = sum(c.values())
        if total <= 0:
            raise ValueError("Zero exposure window")
        return {k: v/total for k,v in c.items()}
    ref = shares(rows)
    tv = []
    for i in range(0, len(rows), window):
        d = shares(rows[i:i+window])
        tv.append(.5 * sum(abs(d.get(k, 0)-v) for k,v in ref.items()))
    return float(np.mean(tv))


def historical_trajectory(arm, seed):
    log = ((source(arm,seed).parents[2] / "gpu" / f"T-A0-o{seed}.log") if arm == "A"
           else T2 / "gpu" / f"T-B-o{seed}.log")
    rows = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.startswith("{'loss':") and "'learning_rate':" in line:
            d = ast.literal_eval(line.split("}", 1)[0] + "}")
            rows.append({k:d[k] for k in ("loss","learning_rate","num_tokens","epoch")})
    ref = analytical_rates("linear")
    if len(rows)!=STEPS or not np.allclose([r["learning_rate"] for r in rows],ref,rtol=0,atol=1e-18):
        raise ValueError(f"Historical logged LR differs: {log}")
    return rows, log


def main():
    records = input_records()
    labels = labels_for(records)
    scopes = {S.rid(r):r["metadata"]["loss_scope"] for r in records}
    ledger = load(HERE / "provenance/token_ledger.json")
    if ledger["training_sha256"] != TRAIN_SHA or set(ledger["records"]) != set(scopes):
        raise ValueError("Token ledger does not cover V4 exactly")
    exposure, supervision, steps, tv, logs = [], [], [], [], {}
    for seed in SEEDS:
        for arm in "AB":
            seq,_ = actual_order(arm, seed, records)
            meta = dict(arm=arm, seed=seed)
            tr, log = historical_trajectory(arm, seed)
            logs[local(log)] = S.sha_file(log)
            rates = [r["learning_rate"] for r in tr]
            rows = list(step_rows(seq, labels, scopes, rates, ledger["records"]))
            for row, t in zip(rows,tr,strict=True):
                row["training_loss"] = t["loss"]
                row["observed_cumulative_tokens"] = t["num_tokens"]
            if not np.array_equal(np.cumsum([r["input_tokens"] for r in rows]), [r["num_tokens"] for r in tr]):
                raise ValueError(f"Per-step token sequence differs from log: {log}")
            steps.extend(dict(**meta, **r) for r in rows)
            for level in ("coarse","fine"):
                a, b = summarize(rows, level)
                exposure.extend(dict(**meta, **r) for r in a)
                supervision.extend(dict(**meta, **r) for r in b)
                weights = dict(record=lambda r:1, input=lambda r:r["input_tokens"], loss=lambda r:r["loss_tokens"],
                               lr=lambda r:r["lr"], lr_loss=lambda r:r["lr"]*r["loss_tokens"])
                tv.append(dict(**meta, level=level, **{k:window_tv(rows,level,w) for k,w in weights.items()}))
    dump(HERE / "provenance/exposure_logs.json", logs)
    for name, rows in (("exposure_by_group",exposure),("effective_supervision",supervision),
                       ("exposure_by_step",steps),("window_tv",tv)):
        write_csv(name,rows)


if __name__ == "__main__":
    main()
