# -*- coding: utf-8 -*-
"""ablation_011 학습 wrapper(결정 261). ``pilot_007/train_data/train_b7b.py``(그대로 둠)의 lr 계획·저장 지점(25·50·75·100%)·profile을 그대로 불러 쓰고,
순서와 A1 손실 범위 표시만 더한다. 기존 학습 코드(``training/``)는 고치지 않는다.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/train/train_a11.py --config <A config> [--dry-run | --tokenizer-check]

1. 순서: config ``training.shared_slot_order_seed``·``shared_slot_order_file``(A0의 O4' 순서, ``build/orders/order_b2_o<seed>.json``)과
   ``training.a11_record_order_file``(``build/orders/record_order_<arm>_o<seed>.json``).
   - 순서 파일 seed = config seed, 파일 순열이 ``default_rng(seed).permutation``(정렬한 slot)으로 다시 만들어지는지(train_b7b와 같은 검사).
   - 레코드 순서 파일의 A0 열 sha256·A0 순서 sha256이 순서 파일과 맞는지, arm 열 = A0 열에서 이 arm에 있는 레코드만 남긴 것인지, arm 열의 레코드 집합 = 학습 파일 레코드 집합인지.
   - A0 데이터(V4 파일)일 때는 ``order7b.order_records``(train_b7b가 쓰는 순서)와 A0 열이 같은지도 확인한다.
   - 레코드를 그 열 순서로 놓고 ``order7.install_sequential_sampler()``로 trainer 쪽 섞기를 끈다.
2. 손실 범위(A1): ``metadata.a11_loss_scope_override == "json_only"``인 레코드만 ``training.data.thinking.sft_loss_scope``가 ``json_only``를 돌려준다
   (config ``thinking.loss_scope: by_source``는 그대로; 표시 없는 레코드는 원래 함수 결과 그대로). 표시는 ``loss_scope: full_response``·``source: teacher``인
   근접 대조 teacher 레코드에만 허용한다.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_007/train_data"))

OVERRIDE = "a11_loss_scope_override"


def install_override():
    """thinking.sft_loss_scope를 표시 레코드만 json_only로 돌려주는 함수로 바꾼다(같은 모듈 전역 이름을 바꿔 render_thinking이 이것을 부른다)."""
    from training.data import thinking as TH
    orig = TH.sft_loss_scope
    if getattr(orig, "_a11", False):
        return orig

    def sft_loss_scope(record, config):
        scope = orig(record, config)
        mark = (record.get("metadata") or {}).get(OVERRIDE)
        if mark is None:
            return scope
        m = record["metadata"]
        if mark != "json_only" or scope != "full_response" or m.get("source") != "teacher" or m.get("contrast_source") != "teacher":
            raise ValueError(f"a11 override only for contrast teacher full_response records: {m.get('source_record_id')} {m.get('trace_id')}")
        return "json_only"
    sft_loss_scope._a11 = True
    TH.sft_loss_scope = sft_loss_scope
    return sft_loss_scope


def rkey(r):
    m = r["metadata"]
    return f"{m['source_record_id']}|{m['trace_id']}"


def apply_order_a11(config, records):
    import numpy as np
    import order7
    import order7b
    t = config["training"]
    seed = t.pop("shared_slot_order_seed", None)
    of = t.pop("shared_slot_order_file", None)
    rf = t.pop("a11_record_order_file", None)
    if seed is None or of is None or rf is None:
        raise ValueError("a11 needs shared_slot_order_seed, shared_slot_order_file, a11_record_order_file")
    want = json.loads(Path(of).read_text(encoding="utf-8"))
    ro = json.loads(Path(rf).read_text(encoding="utf-8"))
    keys = sorted(want["order"])
    regen = [keys[i] for i in np.random.default_rng(int(seed)).permutation(len(keys))]
    sha = lambda xs: hashlib.sha256("\n".join(xs).encode()).hexdigest()  # noqa: E731
    recs = records["train"]
    by_key = {rkey(r): r for r in recs}
    a0 = ro["a0_record_sequence"]
    seq = ro["record_sequence"]
    present = set(by_key)
    checks = {"order_seed": want["seed"] == int(seed) == ro["seed"], "order_regen": regen == want["order"], "order_sha": sha(want["order"]) == want["order_sha256"] == ro["a0_order_sha256"],
              "a0_seq_sha": sha(a0) == ro["a0_record_sequence_sha256"], "arm_seq_sha": sha(seq) == ro["record_sequence_sha256"],
              "arm_is_filtered_a0": [k for k in a0 if k in present] == seq, "keys_unique": len(by_key) == len(recs), "same_set": set(seq) == present and len(seq) == len(recs)}
    if len(recs) == len(a0):  # A0·A1(같은 레코드): train_b7b의 O4' 순서와 같은지
        checks["a0_equals_order7b"] = [rkey(r) for r in order7b.order_records(recs, want["order"])] == a0
    if not all(checks.values()):
        raise ValueError(f"a11 record order check failed: {checks}")
    records["train"] = [by_key[k] for k in seq]
    from transformers import Trainer
    sampler_fn = order7.install_sequential_sampler()
    info = {"shared_slot_order_seed": int(seed), "arm": ro["arm"], "records": len(seq), "order_sha256": want["order_sha256"], "record_sequence_sha256": ro["record_sequence_sha256"],
            "checks": checks, "trainer_sampler": "SequentialSampler" if Trainer._get_train_sampler is sampler_fn else "UNKNOWN",
            "run_stats": order7b.run_stats([order7b.qid(r) for r in records["train"]]),
            "loss_scope_override_records": sum(1 for r in records["train"] if (r.get("metadata") or {}).get(OVERRIDE))}
    print(json.dumps({"a11_order": info}), flush=True)
    return info


def main(argv=None):
    install_override()
    import train_b7b as B
    from training.trainer_common import cli
    args, config, records, manifest = cli("sft", argv)
    apply_order_a11(config, records)
    if args.dry_run:
        print(json.dumps({"lr_plan": B.lr_plan(len(records["train"]), config)}), flush=True)
        return
    if args.tokenizer_check:
        return
    from training.profiling import RunProfile
    from training.train_sft import train
    profile = RunProfile(config, "sft")
    error = None
    try:
        train(args, config, records, manifest, profile, callbacks=[B.SaveAt()])
    except BaseException as exc:
        error = exc
        raise
    finally:
        profile.finish(error)


if __name__ == "__main__":
    main()
