# -*- coding: utf-8 -*-
"""학습 기록에서 checkpoint별 학습 값을 뽑는다(pilot_005, pilot_004 train_summary.py와 같은 계산이고 변형 이름을 받는다). 모델 호출 없음.

    python sft_dpo_inventory/pilot_005/train_summary5.py VARIANT STAGE CHECKPOINT_DIR...

- 입력: ``train_logs/<variant>_log_history.json``(trainer log), ``train_logs/<variant>_profile.json``(step 시간), ``train_logs/<variant>_nvidia_smi.txt``
  (0.5초 간격 memory.used, MiB).
- checkpoint마다: 그 step의 loss, 그 step까지 마지막 50 step 평균 loss, 그 step까지 평균 step 시간, adapter 파일 sha256.
  peak 메모리는 학습 전체의 nvidia-smi 최댓값이다(시각이 없어 checkpoint별로 나누지 않는다).
- 출력: ``train_logs/<variant>_summary.json``(label ``<variant>_step<N>`` → 값).
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    variant, stage, cks = sys.argv[1], sys.argv[2], sys.argv[3:]
    logs = HERE / "train_logs"
    hist = [h for h in json.loads((logs / f"{variant}_log_history.json").read_text(encoding="utf-8")) if "loss" in h]
    prof = json.loads((logs / f"{variant}_profile.json").read_text(encoding="utf-8"))
    steps = prof.get("step_seconds") or []
    mem = [int(x) for x in (logs / f"{variant}_nvidia_smi.txt").read_text().split() if x.isdigit()]
    out = {"variant": variant, "stage": stage, "total_seconds": prof.get("total_seconds"), "optimizer_steps": prof.get("optimizer_steps"),
           "seconds_per_step": prof.get("seconds_per_step"), "peak_memory_used_mib(nvidia-smi, whole run)": max(mem) if mem else None,
           "checkpoints": {}}
    for ck in cks:
        n = int(ck.rsplit("-", 1)[1])
        upto = [h for h in hist if h["step"] <= n]
        adapter = Path(ck) / ("policy" if stage == "dpo" and (Path(ck) / "policy").exists() else "") / "adapter_model.safetensors"
        out["checkpoints"][f"{variant}_step{n}"] = {
            "path": ck, "step": n, "epoch": upto[-1].get("epoch") if upto else None,
            "loss_at_step": upto[-1]["loss"] if upto else None,
            "loss_mean_last50": round(sum(h["loss"] for h in upto[-50:]) / len(upto[-50:]), 6) if upto else None,
            "seconds_per_step_upto": round(sum(steps[:n]) / len(steps[:n]), 3) if steps[:n] else None,
            "adapter_file": str(adapter), "adapter_sha256": sha(adapter) if adapter.exists() else None}
    (logs / f"{variant}_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
