# -*- coding: utf-8 -*-
"""결정 9(reference log-prob 미리 계산)의 메모리 효과를 thinking_prep_001 측정과 같은 레코드로 잰다. 학습이 아니다.

    CUDA_VISIBLE_DEVICES=3 HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pipeline_pilot_001/memory_probe_precompute.py \
        --work /home/hwkim/sftdpo_work/pipeline_pilot_001/probe_precompute --steps 3

- ``thinking_prep_001/memory_probe_thinking.py``(→ ``pilot_prep_001/memory_probe.py``)를 그대로 쓴다. 같은 config·데이터
  (thinking_v003_t2pc_train, 가장 긴 레코드), LR 0, 3 step이다. DPO의 ``reference.strategy``만 이 측정에서 ``precompute``로
  바꾼다(``_probe_runtime_overrides``에 남김). 비교 대상은 ``thinking_prep_001/memory/memory_probe.json``(shared_adapter)이다.
- 결과는 ``memory_compare/``에 쓴다. thinking_prep_001 결과는 고치지 않는다. 임시 adapter는 저장소 밖에 두었다가 지운다.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location(
    "memory_probe_thinking", ROOT / "sft_dpo_inventory/thinking_prep_001/memory_probe_thinking.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
M = T.M
M.HERE = HERE / "memory_compare"
M.HERE.mkdir(exist_ok=True)

_thinking_config = M.load_config


def _precompute_config(path, stage):
    config = _thinking_config(path, stage)
    if stage == "dpo":
        config["reference"] = {**config.get("reference", {}), "strategy": "precompute"}
        config["training"]["precompute_ref_log_probs"] = True
        config.setdefault("_probe_runtime_overrides", []).extend(
            ["reference.strategy=precompute", "training.precompute_ref_log_probs=true"])
    return config


M.load_config = _precompute_config

if __name__ == "__main__":
    sys.exit(M.main())
