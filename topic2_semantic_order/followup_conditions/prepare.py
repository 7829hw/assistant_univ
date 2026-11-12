"""Generate and validate all planned configs/orders, with no evaluation input."""
import copy
from collections import Counter

from common import *
from exposure import step_rows, window_tv, write_csv

ARMS = ("C", "D", "F0", "F48")
WEIGHTS = {"F0":0.0,"F48":.48}
OUT = WORK / "topic2_semantic_order/followup_conditions/train"
PATH_KEYS = {"training.output_dir", "profiling.output"}
LR_KEYS = {"training.learning_rate", "training.lr_scheduler_type"}
APPROVED_SHA = load(HERE/"provenance/existing_evidence.json")["training_inputs"][local(APPROVED)]


def cid(arm, seed):
    return f"{arm}-o{seed}"


def configpath(arm,seed):
    return HERE/"configs"/(cid(arm,seed)+".yaml")


def orderpath(arm,seed):
    return HERE/"orders"/arm/f"semantic_order_o{seed}.json"


def flat(c, prefix=""):
    return {p:v for k, x in c.items() for p,v in
            (flat(x, prefix+k+".").items() if isinstance(x,dict) else [(prefix+k,x)])}


def diff_keys(c, ref):
    a,b=flat(c),flat(ref)
    return {k for k in a.keys()|b.keys() if k not in a or k not in b or a[k]!=b[k]}


def data_policy(c):
    refs = dict(train=TRAIN, valid=V4/"sft_valid.jsonl", manifest=V4/"manifest.json")
    hashes = load(HERE/"provenance/existing_evidence.json")["training_inputs"]
    if set(c["data"]) != {*refs,"grounding_target"} or c["data"]["grounding_target"]!="full":
        raise ValueError("Unexpected training data configuration")
    for k, p in refs.items():
        # Check canonical raw path, real path, and original bytes.
        if c["data"][k] != local(p) or p.resolve() != p or S.sha_file(p) != hashes[local(p)]:
            raise ValueError(f"Training {k} input outside pinned V4 allowlist or changed")
    if (V4/"sft_valid.jsonl").stat().st_size or APPROVED.resolve()!=APPROVED or S.sha_file(APPROVED)!=APPROVED_SHA:
        raise ValueError("Training corpus or approval ledger has drifted")
    if c["chat_template_kwargs"] != {"enable_thinking":True} or c["thinking"] != {"loss_scope":"by_source"}:
        raise ValueError("Thinking/mask drift")


def expected_config(arm,seed):
    if arm not in ARMS or seed not in SEEDS:
        raise ValueError("Unregistered arm or seed")
    ref = config(source("A" if arm=="C" else "B",seed))
    c = copy.deepcopy(ref)
    t = c["training"]
    t["output_dir"] = str(OUT/cid(arm,seed))
    c["profiling"]["output"] = str(OUT/(cid(arm,seed)+"_profile.json"))
    allowed = set(PATH_KEYS)
    if arm in ("C","D"):
        t.update(lr_scheduler_type="constant_with_warmup",learning_rate=CONST)
        allowed |= LR_KEYS
    else:
        t["semantic_schedule_file"] = local(orderpath(arm,seed))
        allowed.add("training.semantic_schedule_file")
    if diff_keys(c,ref)!=allowed:
        raise ValueError("Config changed beyond its planned treatment")
    return c, ref


def validate_config(c, arm, seed):
    expected, ref = expected_config(arm,seed)
    if diff_keys(c,expected):
        raise ValueError("Config does not equal its frozen treatment")
    data_policy(c)
    t=c["training"]
    if ([t[k] for k in ("num_train_epochs","per_device_train_batch_size","gradient_accumulation_steps",
                       "warmup_steps","seed","data_seed","optim","warmup_ratio","bf16")] != [1,1,1,1,43,43,"adamw_torch",0,True]
        or c["model"]["revision"]!=REV or c["model"]["name_or_path"]!="Qwen/Qwen3-8B"):
        raise ValueError("Optimizer steps, seeds, precision, or base model differ")
    return sorted(diff_keys(c,ref))


def main():
    records = input_records()
    data_policy(config(source("B",SEEDS[0])))
    labels = labels_for(records)
    refs = [INV/ab/"build/orders" for ab in ("ablation_011","ablation_013")]
    scopes = {S.rid(r):r["metadata"]["loss_scope"] for r in records}
    ledger = load(HERE/"provenance/token_ledger.json")["records"]
    result, tv = [], []
    for arm,w in WEIGHTS.items():
        S.build_manifest(TRAIN.relative_to(ROOT), APPROVED.relative_to(ROOT), REL/"orders"/arm,
                         list(SEEDS), refs, fine_weight=w)
    for seed in SEEDS:
        seqs={a:actual_order(a,seed,records)[0] for a in "AB"}
        for a,w in {"B":.24,**WEIGHTS}.items():
            regen = S.build_balanced_order(records,labels,seed,fine_weight=w)
            order = load(orderpath(a,seed)) if a!="B" else None
            expected = seqs["B"] if a=="B" else order["record_sequence"]
            if regen != expected or (order and (S.sha_lines(regen)!=order["record_sequence_sha256"] or
               order["training_sha256"]!=TRAIN_SHA or order["approved_sha256"]!=APPROVED_SHA or
               not order["reference_is_true_o4prime"] or order["fine_weight"]!=w)):
                raise ValueError(f"Same seed did not reproduce {a}/{seed}")
            check_seq(regen,records,within=True)
            seqs[a]=expected
        if len({S.sha_lines(v) for v in seqs.values()}) != len(seqs):
            raise ValueError(f"Unexpected identical granularity arms for {seed}")
        for arm in ("A","B",*ARMS):
            order_arm = {"C":"A","D":"B"}.get(arm,arm)
            seq = seqs[order_arm]
            kind = "constant_with_warmup" if arm in ("C","D") else "linear"
            rates = analytical_rates(kind)
            tr = list(step_rows(seq,labels,scopes,rates,ledger))
            for level in ("coarse","fine"):
                tv.append(dict(arm=arm,seed=seed,level=level,
                               record_tv=window_tv(tr,level,lambda r:1),
                               loss_token_tv=window_tv(tr,level,lambda r:r["loss_tokens"]),
                               lr_loss_token_tv=window_tv(tr,level,lambda r:r["lr"]*r["loss_tokens"])))
            if arm in "AB":
                continue
            p=configpath(arm,seed)
            p.parent.mkdir(exist_ok=True)
            c, _ = expected_config(arm,seed)
            changed=validate_config(c,arm,seed)
            p.write_text(yaml.safe_dump(c,sort_keys=False),encoding="utf-8")
            order_files = actual_order(order_arm,seed,records)[1] if order_arm in "AB" else [orderpath(arm,seed)]
            result.append(dict(arm=arm,order_seed=seed,repeat=1,training_seed=43,steps=STEPS,
                               config=local(p),config_sha256=S.sha_file(p),changed_keys=changed,
                               order_sha256=S.sha_lines(seq),order_files={local(f):S.sha_file(f) for f in order_files},
                               training_sha256=TRAIN_SHA,prompt_sha256=PROMPT,base_revision=REV,lr_kind=kind,
                               nominal_lr_sum=float(rates.sum()),loss_tokens=sum(r["loss_tokens"] for r in tr),
                               input_tokens=sum(r["input_tokens"] for r in tr),optimizer=c["training"]["optim"],
                               lora=c["lora"],loss_scope=c["thinking"]["loss_scope"],phase=1 if seed in SEEDS[:3] else 2))
    dump(HERE/"configs/manifest.json",result)
    write_csv("planned_order_exposure",tv)
    write_csv("planned_step_lrs",[dict(schedule=k,step=i,lr=v) for k in ("linear","constant_with_warmup")
                                  for i,v in enumerate(analytical_rates(k),1)])
    print("Prepared and verified",len(result),"configs;",len(SEEDS)*2,"new order files")


if __name__=="__main__":
    main()
