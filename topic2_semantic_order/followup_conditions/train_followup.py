"""Audited wrapper around the frozen A11/semantic training paths."""
import argparse
import os

from common import *
from prepare import configpath, validate_config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--tokenizer-check",action="store_true")
    a=parser.parse_args()
    path=a.config.resolve()
    arm,seed=path.stem.split("-o")
    seed=int(seed)
    if path!=configpath(arm,seed) or Path.cwd()!=ROOT:
        raise ValueError("Use the registered config from the same repo root")
    frozen=next(r for r in load(HERE/"configs/manifest.json") if r["arm"]==arm and r["order_seed"]==seed)
    if S.sha_file(path)!=frozen["config_sha256"]:
        raise ValueError("Config hash drift")
    validate_config(config(path),arm,seed)
    import train_a11
    import train_semantic
    import train_b7b as B
    from training.trainer_common import cli
    from trl import SFTTrainer
    train_a11.install_override()
    mode=["--dry-run"] if a.dry_run else ["--tokenizer-check"] if a.tokenizer_check else []
    args,c,records,m=cli("sft",["--config",str(path),*mode])
    order_files=frozen["order_files"]
    if any(S.sha_file(ROOT/p)!=h for p,h in order_files.items()):
        raise ValueError("Order artifact changed")
    if arm=="C":
        train_a11.apply_order_a11(c,records)
    else:
        train_semantic.apply_semantic_order(c,records)
    seq=[S.rid(r) for r in records["train"]]
    check_seq(seq,records["train"],within=arm!="C")
    if S.sha_lines(seq)!=frozen["order_sha256"] or m["prompt_hash"]!=PROMPT:
        raise ValueError("Applied order or prompt does not match pinned provenance")
    class Dummy:
        train_dataset=list(range(STEPS))
    smp=SFTTrainer._get_train_sampler(Dummy())
    if type(smp).__name__!="SequentialSampler" or list(smp)!=list(range(STEPS)):
        raise ValueError("Actual TRL trainer would not sample sequentially")
    rates=hf_rates(c)
    if not np.allclose(rates,analytical_rates(frozen["lr_kind"]),rtol=0,atol=1e-18):
        raise ValueError("HF scheduler differs from the frozen LR schedule")
    print(json.dumps(dict(followup=dict(**frozen, trainer_sampler=type(smp).__name__,optimizer_steps_total=len(rates),
                                       checked_lr_sum=float(rates.sum()),first_lr=float(rates[0]),last_lr=float(rates[-1])))),flush=True)
    if mode:
        return
    import torch
    if (torch.cuda.device_count()!=1 or os.environ.get("FOLLOWUP_RUN_COMMIT") is None or
        Path(c["training"]["output_dir"]).exists()):
        raise RuntimeError("Use the approved pinned launcher on one GPU and a fresh output directory")
    from training.profiling import RunProfile
    from training.train_sft import train
    profile=RunProfile(c,"sft")
    error=None
    try:
        train(args,c,records,m,profile,callbacks=[B.SaveAt()])
    except BaseException as exc:
        error=exc
        raise
    finally:
        profile.finish(error)


if __name__=="__main__":
    main()
