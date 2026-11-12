"""Exact CPU token and supervised-label counts using the production renderer and TRL."""
from collections import Counter
from importlib.metadata import version

from common import *


def main():
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer
    from trl.trainer.sft_trainer import DataCollatorForLanguageModeling
    from training.trainer_common import render_records, tokenizer_for
    import train_a11

    records = input_records()
    c = config(source("B", SEEDS[0]))
    train_a11.install_override()
    tokenizer = tokenizer_for(c)
    rows = render_records(tokenizer, records, c, "sft")
    args = SFTConfig(output_dir="/tmp/followup-tokens", use_cpu=True, report_to="none",
                     max_length=c["training"]["max_seq_length"], completion_only_loss=True,
                     assistant_only_loss=False, packing=False)
    # This method uses only the dataset and tokenizer. Do not instantiate a trainer/model.
    prep = SFTTrainer._prepare_dataset(None, Dataset.from_list(rows), tokenizer, args, False, None, "train")
    collator = DataCollatorForLanguageModeling(pad_token_id=tokenizer.pad_token_id, completion_only_loss=True)
    ledger = {}
    for record, row in zip(records, prep, strict=True):
        batch = collator([row])
        # The LM predicts labels[1:] from input_ids[:-1]. Check against TRL's mask.
        n = int(batch["attention_mask"].sum())
        m = int((batch["labels"][0, 1:] != -100).sum())
        if not 0 < m < n or m != sum(row["completion_mask"]) or row["completion_mask"][0] != 0:
            raise ValueError("Unexpected TRL mask")
        ledger[S.rid(record)] = [n, m]
    total = np.array(list(ledger.values())).sum(axis=0)
    if total[0] != 16047305:
        raise ValueError(f"Actual TRL policy token total differs from historical training log: {total}")
    dump(HERE / "provenance/token_ledger.json", {
        "columns": ["input_tokens", "loss_tokens"], "training_sha256": TRAIN_SHA, "revision": REV,
        "provenance": "exact CPU reconstruction with pinned TRL dataset and collator; causal LM shift",
        "packages": {p: version(p) for p in ("trl","transformers","datasets","torch")},
        "input_tokens": int(total[0]), "loss_tokens": int(total[1]), "records": ledger,
    })
    print("tokens:", total)


if __name__ == "__main__":
    main()
