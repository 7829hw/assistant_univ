# -*- coding: utf-8 -*-
"""thinking training config(``qwen3_8b_t2pc_thinking_{sft,dpo}.yaml``)의 메모리·step 시간 확인. pilot이 아니다.
이번 측정은 사용자 지시로 CUDA 3(host GPU 3)에서 했다(``gpu_runs.log``).

    CUDA_VISIBLE_DEVICES=3 HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/thinking_prep_001/memory_probe_thinking.py \
        --work /home/hwkim/sftdpo_work/thinking_prep_001/probe --steps 3

``pilot_prep_001/memory_probe.py``를 그대로 쓰고, config 경로와 결과 위치만 바꾼다(가장 긴 레코드, LR 0, 3 step,
eval·save 끔, adapter는 저장소 밖에 두었다가 지움). 메모리가 부족하면 설정을 바꾸지 않고 실패를 기록한다.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("memory_probe", ROOT / "sft_dpo_inventory/pilot_prep_001/memory_probe.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
M.HERE = HERE
M.CONFIGS = {"sft": ROOT / "training/configs/qwen3_8b_t2pc_thinking_sft.yaml",
             "dpo": ROOT / "training/configs/qwen3_8b_t2pc_thinking_dpo.yaml"}

_load_config = M.load_config


def _probe_config(path, stage):
    """SFT config의 loss_scope 자리표시자를 이 측정에서만 full_response로 바꾼다(메모리는 json_only와 같은 전체 길이)."""
    config = _load_config(path, stage)
    if config.get("thinking", {}).get("loss_scope") not in ("full_response", "json_only"):
        config["thinking"] = {"loss_scope": "full_response"}
        config.setdefault("_probe_runtime_overrides", []).append("thinking.loss_scope=full_response")
    return config


M.load_config = _probe_config

if __name__ == "__main__":
    sys.exit(M.main())
