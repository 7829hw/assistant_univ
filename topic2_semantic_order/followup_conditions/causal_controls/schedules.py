"""Build schedules from frozen training records and the exact supervised-token ledger."""
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import (APPROVED, HERE as FOLLOWUP, REV, S, SEEDS, STEPS, TRAIN_SHA,
                    analytical_rates, check_seq, dump, input_records, labels_for, load, local)
from prepare import APPROVED_SHA

ORDER_SEEDS = (*SEEDS, 51001, 51002, 51003)
TRAIN_SEEDS = (43, 51004)
FACTORIAL = ("S0T0", "S1T0", "S0T1", "S1T1")
ARMS = (*FACTORIAL, "placebo", "low_gap", "high_gap")
SCOPES = ("full_response", "json_only")
ASSIGN_SWAPS = 22000
SPACING_SWAPS = 3500
FACTORIAL_LIMITS = {"coarse": (0.035, 0.085), "fine": (0.035, 0.085),
                    "scope_count": (0.025, 0.065), "scope_loss": (0.025, 0.065)}
SPACING_LIMITS = {"total_relative": .01, "coarse": .010, "fine": .018,
                  "scope": .008, "decile_joint": .020}


@dataclass(frozen=True)
class Block:
    question: str
    records: tuple
    scopes: tuple
    inputs: tuple
    losses: tuple
    previous: int
    following: int

    def __len__(self):
        return len(self.records)


def blocks_from(records, ledger):
    questions = defaultdict(list)
    for record in records:
        questions[S.qid(record)].append(record)
    result = []
    for qid, rr in sorted(questions.items()):
        rr.sort(key=S.within_key)
        for start in range(0, len(rr), 4):
            chunk = rr[start:start+4]
            ids = tuple(map(S.rid, chunk))
            index = len(result)
            result.append(Block(qid, ids, tuple(r["metadata"]["loss_scope"] for r in chunk),
                                tuple(ledger[k][0] for k in ids), tuple(ledger[k][1] for k in ids),
                                index-1 if start else -1, index+1 if start+4 < len(rr) else -1))
    return result


def blind_order(blocks, rng):
    """Random priorities are independent of semantic, supervision and token data."""
    for _ in range(128):
        rank = np.argsort(rng.permutation(len(blocks)))
        ready = {i for i, b in enumerate(blocks) if b.previous == -1}
        order = []
        while ready:
            allowed = [i for i in ready if not order or blocks[order[-1]].question != blocks[i].question]
            if not allowed:
                break
            i = min(allowed, key=rank.__getitem__)
            order.append(i)
            ready.remove(i)
            if blocks[i].following != -1:
                ready.add(blocks[i].following)
        if len(order) == len(blocks):
            return order
    raise RuntimeError("Could not generate a group-blind feasible order")


def placebo_labels(blocks, labels, rng):
    chunks = defaultdict(list)
    for block in blocks:
        chunks[block.question].append(block.scopes)
    strata = defaultdict(list)
    for qid, profile in sorted(chunks.items()):
        strata[tuple(profile)].append(qid)
    assigned = {}
    for stratum in strata.values():
        for qid, donor in zip(stratum, rng.permutation(stratum), strict=True):
            assigned[qid] = labels[str(donor)]
    return assigned


def encodings(blocks, labels):
    keys = [sorted({pair[i] for pair in labels.values()}) for i in (0, 1)]
    groups = [{key: i for i, key in enumerate(level)} for level in keys]
    dimension = sum(map(len, keys)) + 4
    sections = dict(coarse=slice(len(keys[0])), fine=slice(len(keys[0]), dimension-4),
                    scope_count=slice(dimension-4, dimension-2), scope_loss=slice(dimension-2, dimension))
    features = np.zeros((len(blocks), 4, dimension), dtype=np.float64)
    for i, b in enumerate(blocks):
        coarse, fine = labels[b.question]
        for k, (scope, loss) in enumerate(zip(b.scopes, b.losses)):
            si = SCOPES.index(scope)
            features[i,k,groups[0][coarse]] = 1
            features[i,k,len(keys[0])+groups[1][fine]] = 1
            features[i,k,dimension-4+si] = 1
            features[i,k,dimension-2+si] = loss
    return features, sections, keys


def assert_block_sequence(order, blocks):
    if sorted(order)!=list(range(len(blocks))):
        raise ValueError("Repeated or missing block")
    inverse=np.argsort(order)
    for position,index in enumerate(order):
        block=blocks[index]
        if block.previous!=-1 and inverse[block.previous]>=position:
            raise ValueError("Block precedence was violated")
        if position and blocks[order[position-1]].question==block.question:
            raise ValueError("Adjacent blocks from one question")


def slots(order, blocks):
    lengths = np.array([len(blocks[i]) for i in order])
    starts = np.r_[0, np.cumsum(lengths[:-1])]
    return lengths, starts


def totals(order, blocks, features):
    lengths, starts = slots(order,blocks)
    result = np.zeros((10, features.shape[-1]))
    for i, length, start in zip(order, lengths, starts):
        np.add.at(result, np.arange(start,start+length)*10//STEPS, features[i,:length])
    return result


def composition(matrix, sections):
    result = matrix.copy()
    for s in sections.values():
        n = matrix[:,s].sum(axis=1,keepdims=True)
        result[:,s] = np.divide(matrix[:,s], n, out=np.zeros_like(matrix[:,s]), where=n>0)
    return result


def tv(a,b,sections):
    return {key: (float(v.mean()), float(v.max())) for key,s in sections.items()
            for v in [np.abs(a[:,s]-b[:,s]).sum(axis=1)/2]}


def swap_allowed(order, inverse, blocks, left, right):
    x,y = order[left],order[right]
    if blocks[x].question == blocks[y].question:
        return False
    for pos, i in ((left,y),(right,x)):
        b = blocks[i]
        if (b.previous != -1 and inverse[b.previous]>=pos) or (b.following != -1 and inverse[b.following]<=pos):
            return False
        for neighbor in (pos-1,pos+1):
            if 0<=neighbor<len(order):
                adjacent = y if neighbor==left else x if neighbor==right else order[neighbor]
                if b.question==blocks[adjacent].question:
                    return False
    return True


def assign(blind, blocks, labels, semantic, supervision, rng):
    features, sections, _ = encodings(blocks,labels)
    profile = totals(blind, blocks, features)
    epoch_mass = profile.sum(axis=0)
    order = list(blind)
    inverse = np.argsort(order)
    lengths, starts = slots(order,blocks)
    deciles = [(np.arange(start,start+length)*10//STEPS) for start,length in zip(starts,lengths)]
    current = profile.copy()
    target = composition(profile,sections)
    weight = np.ones(features.shape[-1])
    for name,s in sections.items():
        enabled = semantic if name in ("coarse","fine") else supervision
        if enabled:
            target[:,s] = epoch_mass[s]/epoch_mass[s].sum()
        # Matching the untreated factor takes priority over treating a second factor.
        weight[s] = 1 if enabled else 2
    same_length = {k:np.flatnonzero(lengths==k) for k in range(1,5)}
    first_positions = rng.integers(len(order),size=ASSIGN_SWAPS)
    for first in first_positions:
        length = lengths[first]
        second = int(rng.choice(same_length[length]))
        if first==second or not swap_allowed(order,inverse,blocks,first,second):
            continue
        dl,dr = deciles[first],deciles[second]
        if np.array_equal(dl,dr):
            continue
        affected = np.unique(np.r_[dl,dr])
        changed = current[affected].copy()
        diff = features[order[second],:length]-features[order[first],:length]
        np.add.at(changed,np.searchsorted(affected,dl),diff)
        np.add.at(changed,np.searchsorted(affected,dr),-diff)
        before = np.abs(composition(current[affected],sections)-target[affected])
        after = np.abs(composition(changed,sections)-target[affected])
        if ((after-before)*weight).sum() < -1e-12:
            x,y = order[first],order[second]
            order[first],order[second] = y,x
            inverse[x],inverse[y] = second,first
            current[affected] = changed
    return order


def exposures(order, blocks, labels):
    pairs = sorted({(fine,scope) for _,fine in labels.values() for scope in SCOPES})
    groups = sorted({c for c,_ in labels.values()})
    coarse_by_fine = {f:c for c,f in labels.values()}
    fine_code = {key:i for i,key in enumerate(pairs)}
    coarse_code = {key:i for i,key in enumerate(groups)}
    codes, coarse, inputs, losses = [], [], [], []
    for i in order:
        b = blocks[i]
        c,f = labels[b.question]
        codes.extend(fine_code[f,s] for s in b.scopes)
        coarse.extend([coarse_code[c]]*len(b))
        inputs.extend(b.inputs)
        losses.extend(b.losses)
    deciles = np.arange(STEPS)*10//STEPS
    joint = deciles*len(pairs)+np.asarray(codes)
    lr = analytical_rates("linear")
    mass = {}
    for name,weights in (("count",None),("input",inputs),("loss",losses),("lr_loss",lr*losses)):
        vals = np.bincount(joint,weights=weights,minlength=10*len(pairs)).reshape(10,len(pairs))
        mass[name] = vals if name=="lr_loss" else vals.astype(np.int64)
    return mass,pairs,coarse_by_fine,np.asarray(coarse),groups


def spacing_metrics(coarse, groups):
    gaps = {}
    for i, group in enumerate(groups):
        positions = np.flatnonzero(coarse==i)
        if len(positions)>=50:
            gaps[group] = int(np.diff(np.r_[-1,positions,len(coarse)]).max()-1)
    switching = float(np.mean(coarse[1:]!=coarse[:-1]))
    return dict(max_gap_steps=gaps, mean_max_gap_steps=float(np.mean(list(gaps.values()))),
                switch_fraction=switching)


def spacing(order, blocks, labels, high, rng):
    result = list(order)
    lengths, starts = slots(order,blocks)
    inverse = np.argsort(order)
    _,_,_,coarse,groups = exposures(order,blocks,labels)
    initial = coarse.copy()
    buckets = defaultdict(list)
    for slot, (length,start) in enumerate(zip(lengths,starts)):
        d = start*10//STEPS
        if d==(start+length-1)*10//STEPS:
            buckets[d,length].append(slot)
    candidates = [b for b in buckets.values() if len(b)>=2]
    def score(metrics):
        return metrics["mean_max_gap_steps"]/STEPS-metrics["switch_fraction"]/3
    current = score(spacing_metrics(coarse,groups))
    lr = analytical_rates("linear")
    loss = np.concatenate([np.asarray(blocks[i].losses) for i in order])
    total_lr = float(lr@loss)
    # Conservative bound on normalized fine×scope LR half-L1 accumulated over swaps.
    moved_lr = 0.0
    for _ in range(SPACING_SWAPS):
        first,second = rng.choice(candidates[int(rng.integers(len(candidates)))],2,replace=False)
        if not swap_allowed(result,inverse,blocks,first,second):
            continue
        length = lengths[first]
        i,j = starts[first],starts[second]
        a,b = slice(i,i+length),slice(j,j+length)
        if coarse[i]==coarse[j]:
            continue
        # Linear LR gives a scalar difference for equal-length chunks. Swaps
        # never cross a decile, so this also bounds the decile-joint change.
        half_l1 = float(np.abs(lr[a]-lr[b])@(loss[a]+loss[b]))/2
        if (moved_lr+half_l1)/total_lr>.0035:
            continue
        coarse[a],coarse[b] = coarse[b].copy(),coarse[a].copy()
        value = score(spacing_metrics(coarse,groups))
        if (value-current)*(1 if high else -1)>1e-12:
            x,y = result[first],result[second]
            result[first],result[second] = y,x
            inverse[x],inverse[y] = second,first
            loss[a],loss[b] = loss[b].copy(),loss[a].copy()
            moved_lr += half_l1
            current = value
        else:
            coarse[a],coarse[b] = coarse[b].copy(),coarse[a].copy()
    metrics = spacing_metrics(coarse, groups)
    metrics["initial"] = spacing_metrics(initial,groups)
    return result, metrics


def spacing_audit(low, high, blocks, labels):
    lo,pairs,coarse,lp,groups = exposures(low,blocks,labels)
    hi,_,_,hp,_ = exposures(high,blocks,labels)
    reference = lo["lr_loss"].sum()
    delta = hi["lr_loss"]-lo["lr_loss"]
    values = {"decile_joint": np.abs(delta).sum()/(2*reference),
              "total_relative": abs(delta.sum())/reference}
    for name, keys in (("coarse",[coarse[f] for f,s in pairs]), ("fine",[f for f,s in pairs]),
                       ("scope",[s for f,s in pairs])):
        grouped = defaultdict(float)
        for k,d in zip(keys,delta.sum(axis=0)):
            grouped[k] += d
        values[name] = sum(map(abs,grouped.values()))/(2*reference)
    a,b = spacing_metrics(lp,groups),spacing_metrics(hp,groups)
    gap = b["mean_max_gap_steps"]-a["mean_max_gap_steps"]
    switch = a["switch_fraction"]-b["switch_fraction"]
    checks = {key:bool(np.array_equal(lo[key],hi[key])) for key in ("count","input","loss")}
    checks.update({key:bool(values[key]<=limit) for key,limit in SPACING_LIMITS.items()})
    checks.update(gap=gap>=20,switch=switch>=.025)
    return dict(eligible=all(checks.values()), checks=checks, lr_residuals=values,
                gap_delta=gap,switch_drop=switch,low=a,high=b)


def factorial_audit(orders, blocks, labels, assigned):
    features, sections, names = encodings(blocks,labels)
    raw = {a:totals(o,blocks,features) for a,o in orders.items()}
    profiles = {a:composition(v,sections) for a,v in raw.items()}
    corpus = composition(raw["S0T0"].sum(axis=0,keepdims=True),sections)
    balance = {a:tv(p,corpus,sections) for a,p in profiles.items()}
    pairs = [("S0T0","S1T0","semantic"),("S0T1","S1T1","semantic"),
             ("S0T0","S0T1","supervision"),("S1T0","S1T1","supervision")]
    checks = {}
    for a,b,axis in pairs:
        residual = tv(profiles[a],profiles[b],sections)
        treated = ("coarse","fine") if axis=="semantic" else ("scope_count","scope_loss")
        improvement = {k:balance[a][k][0]-balance[b][k][0] for k in treated}
        gates = {f"improve_{k}":v>=(.025 if axis=="semantic" else .015) for k,v in improvement.items()}
        for k,v in residual.items():
            if k not in treated:
                gates[f"match_{k}"] = all(x<=bound for x,bound in zip(v,FACTORIAL_LIMITS[k]))
        checks[f"{a}_vs_{b}"] = dict(eligible=all(gates.values()),gates=gates,
                                     residuals=residual,improvement=improvement)
    pf,ps,_ = encodings(blocks,assigned)
    pb = composition(totals(orders["S0T0"],blocks,pf),ps)
    pp = composition(totals(orders["placebo"],blocks,pf),ps)
    pc = composition(totals(orders["S0T0"],blocks,pf).sum(axis=0,keepdims=True),ps)
    gain = {k:tv(pb,pc,ps)[k][0]-tv(pp,pc,ps)[k][0] for k in ("coarse","fine")}
    changed = sum(len(b) for b in blocks if labels[b.question][1]!=assigned[b.question][1])/STEPS
    residual = tv(profiles["S0T0"],profiles["placebo"],sections)
    eligible = changed>=.5 and min(gain.values())>=.025 and all(
        all(x<=lim for x,lim in zip(residual[k],FACTORIAL_LIMITS[k])) for k in ("scope_count","scope_loss"))
    direct_residual = tv(profiles["S1T0"],profiles["placebo"],sections)
    direct_match = all(all(x<=limit for x,limit in zip(direct_residual[k],FACTORIAL_LIMITS[k]))
                       for k in ("scope_count","scope_loss"))
    return dict(balance=balance,factorial=checks,
                placebo=dict(eligible=eligible,fine_reassigned_fraction=changed,placebo_improvement=gain,residuals=residual,
                             true_vs_placebo_scope_match=direct_match,true_vs_placebo_residuals=direct_residual),
                per_decile_labels=dict(coarse=names[0],fine=names[1],scopes=list(SCOPES)),
                per_decile_counts={a:v.astype(int).tolist() for a,v in raw.items()})


def experiment():
    records = input_records()
    if S.sha_file(APPROVED)!=APPROVED_SHA:
        raise ValueError("Approved train corpus hash mismatch")
    ledger_path = FOLLOWUP/"provenance/token_ledger.json"
    ledger = load(ledger_path)
    record_keys = {S.rid(r) for r in records}
    if (ledger["training_sha256"]!=TRAIN_SHA or ledger["revision"]!=REV
        or set(ledger["records"])!=record_keys or list(map(sum,zip(*ledger["records"].values())))!=[16047305,908705]):
        raise ValueError("Token ledger does not describe the approved corpus")
    return records, blocks_from(records,ledger["records"]),labels_for(records),ledger_path


def main():
    from hashlib import sha256
    prereg = HERE/"PREREGISTRATION.md"
    if sha256(prereg.read_bytes()).hexdigest()!=(HERE/"PREREGISTRATION.sha256").read_text().split()[0]:
        raise ValueError("Protocol changed")
    records,blocks,labels,ledger = experiment()
    manifest = dict(training_sha256=TRAIN_SHA,approved_sha256=APPROVED_SHA,ledger_sha256=S.sha_file(ledger),
                    protocol_sha256=S.sha_file(prereg),block_count=len(blocks),training_seeds=list(TRAIN_SEEDS),audits={},runs=[])
    for seed in ORDER_SEEDS:
        rng = np.random.default_rng(seed)
        blind = blind_order(blocks,rng)
        assigned = placebo_labels(blocks,labels,rng)
        orders = {"S0T0":blind}
        for arm,(sem,sup) in zip(FACTORIAL[1:],[(True,False),(False,True),(True,True)]):
            orders[arm] = assign(blind,blocks,labels,sem,sup,rng)
        orders["placebo"] = assign(blind,blocks,assigned,True,False,rng)
        for arm,high in (("low_gap",False),("high_gap",True)):
            orders[arm],_ = spacing(orders["S1T1"],blocks,labels,high,rng)
        audit = factorial_audit(orders,blocks,labels,assigned)
        audit["spacing"] = spacing_audit(orders["low_gap"],orders["high_gap"],blocks,labels)
        audit["placebo_label_sha256"] = S.sha_lines(f"{q}\t{c}\t{f}" for q,(c,f) in sorted(assigned.items()))
        audit["placebo_labels"] = assigned
        audit["lr_weighted_loss_tokens"]={}
        for arm,order in orders.items():
            mass,_,_,_,_=exposures(order,blocks,labels)
            audit["lr_weighted_loss_tokens"][arm]=dict(total=mass["lr_loss"].sum(),by_decile=mass["lr_loss"].sum(axis=1).tolist())
        for arm,order in orders.items():
            assert_block_sequence(order,blocks)
            seq = [rid for i in order for rid in blocks[i].records]
            check_seq(seq,records,within=True)
            path = HERE/"orders"/arm/f"o{seed}.json"
            dump(path,dict(arm="SEMANTIC_ORDER",treatment=arm,seed=seed,training_sha256=TRAIN_SHA,max_run_limit=4,
                           block_order=order,record_sequence=seq,record_sequence_sha256=S.sha_lines(seq)))
            manifest["runs"].append(dict(arm=arm,order_seed=seed,path=local(path),sha256=S.sha_file(path)))
        audit_path=HERE/f"audits/o{seed}.json"
        dump(audit_path,audit)
        manifest["audits"][local(audit_path)]=S.sha_file(audit_path)
        print(seed, {k:v["eligible"] for k,v in audit["factorial"].items()},
              "placebo",audit["placebo"]["eligible"],"spacing",audit["spacing"]["eligible"],flush=True)
    dump(HERE/"orders/manifest.json",manifest)


if __name__=="__main__":
    main()
