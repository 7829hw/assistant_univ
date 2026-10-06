# -*- coding: utf-8 -*-
"""GPU 2에서 T2PC v003 training config(한도 7552, DPO prompt 7424)의 메모리·step 시간을 잰다. pilot이 아니다.

    CUDA_VISIBLE_DEVICES=2 HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pilot_prep_001/memory_probe.py \
        --work /home/hwkim/sftdpo_work/pilot_prep_001/probe --steps 3

- config: ``training/configs/qwen3_8b_t2pc_v003_{sft,dpo}.yaml`` 그대로(모델·dtype·LoRA·gradient checkpointing·한도·batch).
  실행 때만 바꾸는 것: output_dir·profiling 경로(저장소 밖·이 디렉터리), max_steps, eval·save 끔, learning_rate=0.
  LR 0은 학습이 일어나지 않게 하려는 것이다. AdamW 상태는 그대로 만들어지므로 메모리 측정에는 영향이 없다.
- 데이터: ``reviewed_gold_v003_t2pc``에서 token이 가장 긴 레코드 하나(SFT·DPO 각각). 메모리 측정용 고정물이며 split을 바꾸지 않는다.
- DPO는 config의 SFT adapter 자리(SELECTED_T2PC_V003_SFT_REQUIRED)에 이 측정의 SFT 단계가 만든 LR0 adapter를 넣는다.
- 만든 adapter는 ``--work`` 아래에만 있고, 측정이 끝나면 지운다. 평가에 쓰지 않는다.
- 메모리가 부족하면 설정을 바꾸지 않고 실패(OOM)를 그대로 기록한다.
"""
import argparse
import copy
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from training.annotations.inventory import digest  # noqa: E402
from training.trainer_common import load_config, load_records, render_records, tokenizer_for  # noqa: E402

CONFIGS = {"sft": ROOT / "training/configs/qwen3_8b_t2pc_v003_sft.yaml",
           "dpo": ROOT / "training/configs/qwen3_8b_t2pc_v003_dpo.yaml"}


class GpuSampler:
    """nvidia-smi로 이 프로세스가 보는 GPU(CUDA_VISIBLE_DEVICES=2 → host GPU 2)의 사용 메모리 최댓값을 잰다."""

    def __init__(self, uuid):
        self.uuid, self.peak_mib, self.stop = uuid, 0, threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop.wait(0.5):
            out = subprocess.run(["nvidia-smi", "-i", self.uuid, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True).stdout.strip()
            if out.isdigit():
                self.peak_mib = max(self.peak_mib, int(out))

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=3)


def longest(tokenizer, config, records, stage):
    rows = []
    for split, group in records.items():
        for position, record in enumerate(group):
            rendered = render_records(tokenizer, [record], config, stage)[0]
            prompt = len(tokenizer(rendered["prompt"], add_special_tokens=False)["input_ids"])
            keys = ("completion",) if stage == "sft" else ("chosen", "rejected")
            completion = max(len(tokenizer(record[k][0]["content"] if stage == "dpo" else record["messages"][-1]["content"],
                                           add_special_tokens=False)["input_ids"]) for k in keys)
            rows.append((prompt + completion + 1, split, position, record))
    total, split, position, record = max(rows, key=lambda r: r[0])
    return record, {"split": split, "position": position, "approx_total_tokens": total,
                    "source_record_id": record["metadata"]["source_record_id"], "record_hash": digest(record)}


def run_stage(stage, work, steps, sft_adapter, uuid):
    import torch
    from training.profiling import RunProfile
    config = load_config(CONFIGS[stage], stage)
    original = copy.deepcopy(config)
    records, manifest = load_records(config, stage)
    tokenizer = tokenizer_for(config)
    record, selection = longest(tokenizer, config, records, stage)
    output = work / stage
    config["training"].update(output_dir=str(output), max_steps=steps, eval_strategy="no", save_strategy="no",
                              logging_steps=1, learning_rate=0.0)
    config["profiling"] = {"enabled": True, "output": str(HERE / "memory" / f"{stage}_profile.json")}
    if stage == "dpo":
        config["model"]["adapter_path"] = str(sft_adapter)
    changed = sorted(f"{section}.{key}" for section in config for key in (config[section] if isinstance(config[section], dict) else {})
                     if not isinstance(original.get(section), dict) or original[section].get(key) != config[section][key])
    module = __import__(f"training.train_{stage}", fromlist=["train"])
    saved = {}

    def capture(trainer, tok, cfg, dataset_manifest, saved_stage):
        encoded = trainer.train_dataset[0]
        saved["trl_lengths"] = ({"input_ids": len(encoded["input_ids"])} if stage == "sft" else
                                {k: len(encoded[f"{k}_input_ids"]) for k in ("prompt", "chosen", "rejected")})
        saved["global_step"] = trainer.state.global_step
        if stage == "sft":
            from training.trainer_common import save_run
            save_run(trainer, tok, cfg, dataset_manifest, saved_stage)   # DPO 측정용 LR0 adapter(저장소 밖, 측정 뒤 삭제)
            (output / "PROBE_ONLY.json").write_text(json.dumps({"never_use": True, "learning_rate": 0}))

    result = {"stage": stage, "config_file": str(CONFIGS[stage].relative_to(ROOT)), "runtime_overrides": changed,
              "selection": selection, "status": None, "OOM": False}
    profile = RunProfile(config, stage)
    error = None
    torch.cuda.reset_peak_memory_stats()
    with GpuSampler(uuid) as sampler:
        try:
            with patch.object(module, "save_run", capture):
                module.train(SimpleNamespace(resume_from_checkpoint=None), config,
                             {"train": [record], "valid": []}, manifest, profile)
            result["status"] = "PASS"
        except BaseException as exc:  # noqa: BLE001 - OOM 등 실패를 그대로 기록한다
            error = exc
            result.update(status="FAIL", error=f"{type(exc).__name__}: {str(exc)[:500]}",
                          OOM=isinstance(exc, torch.cuda.OutOfMemoryError))
        finally:
            profile.finish(error)
    report = json.loads((HERE / "memory" / f"{stage}_profile.json").read_text())
    result.update(trl_lengths=saved.get("trl_lengths"), global_step=saved.get("global_step"),
                  torch_max_memory_allocated_gib=round(torch.cuda.max_memory_allocated() / 2**30, 2),
                  torch_max_memory_reserved_gib=round(torch.cuda.max_memory_reserved() / 2**30, 2),
                  nvidia_smi_peak_mib=sampler.peak_mib, step_seconds=report.get("step_seconds"),
                  seconds_per_step=report.get("seconds_per_step"), model_load_seconds=report.get("model_load_seconds"),
                  policy_tokens_per_second=report.get("policy_tokens_per_second"))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True)
    parser.add_argument("--steps", type=int, default=3)
    args = parser.parse_args()
    import torch
    work = Path(args.work).resolve()
    if ROOT in work.parents:
        raise SystemExit("--work는 저장소 밖이어야 한다")
    if work.exists():
        raise SystemExit("--work가 이미 있다")
    work.mkdir(parents=True)
    device = torch.cuda.get_device_properties(0)
    uuid = f"GPU-{device.uuid}"
    results = {"device": {"name": device.name, "uuid": uuid, "total_gib": round(device.total_memory / 2**30, 2)},
               "steps": args.steps, "stages": {}}
    (HERE / "memory").mkdir(exist_ok=True)
    try:
        results["stages"]["sft"] = run_stage("sft", work, args.steps, None, uuid)
        torch.cuda.empty_cache()
        if results["stages"]["sft"]["status"] == "PASS":
            results["stages"]["dpo"] = run_stage("dpo", work, args.steps, work / "sft", uuid)
        else:
            results["stages"]["dpo"] = {"status": "NOT_RUN", "reason": "SFT 측정이 실패해 DPO용 SFT adapter가 없다"}
    finally:
        shutil.rmtree(work)
        results["temporary_adapters_deleted"] = not work.exists()
    (HERE / "memory" / "memory_probe.json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n",
                                                       encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
