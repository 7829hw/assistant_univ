# -*- coding: utf-8 -*-
"""pilot_010 JG FREEZE_JG.json(결정 270, PLAN_JG) — smoke·측정·집계 전에 고정할 파일 sha256과 값. 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_010/freeze_jg.py
"""
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = "sft_dpo_inventory/pilot_010/"
EXEC = [P + "protected_final_v2/run_cell_pf2.py", P + "protected_final_v2/vllm_eval_pf2.py", "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py",
        "sft_dpo_inventory/ablation_011/gpu/serve_a11.sh", "sft_dpo_inventory/pilot_007/results/completeness_B.py", "evaluate_vendor100.py",
        "sft_dpo_inventory/pilot_005/vllm_eval_thinking5.py", "sft_dpo_inventory/serving_vllm/vllm_thinking.py"]
FILES = [P + "PLAN_JG.md", P + "freeze_jg.py", P + "gpu/scheduler20.py", P + "gpu/make_jobs_jg.py", P + "protected_final_v2/run_cell_pf2_g1.py",
         "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x_g1.py", P + "results/smoke_jg.py", P + "results/analyze_jg.py", P + "results/analyze_jq.py",
         P + "results/analyze_j.py", P + "results/analyze_jp.py", P + "results/validity_j.py", "sft_dpo_inventory/ablation_012/e2/h_final.yaml",
         "sft_dpo_inventory/ablation_012/e2/h_dev.yaml", *EXEC]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def same_as_19d91001(f):
    a = subprocess.run(["git", "rev-parse", f"19d91001:{f}"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return bool(a) and a == subprocess.run(["git", "hash-object", str(ROOT / f)], capture_output=True, text=True).stdout.strip()


def main():
    body = {"decision": 270, "label": "판정 뒤 추가(사후), PF2·H-final 세 번째 사용", "plan": P + "PLAN_JG.md",
            "frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "files": {f: sha(ROOT / f) for f in FILES},
            "exec_files_same_as_tools_commit_19d91001": {f: same_as_19d91001(f) for f in EXEC},
            "conditions": {"G0": "temperature 0 (greedy, --greedy; PF2 k=1, H-final k=1)",
                           "G1": "temperature 0.2, top-p 0.95, top-k 20, min-p 0, repetition penalty 1 (PF2 k=4 rounds 20261101-04, H-final k=1 round 20261101)"},
            "smoke": {"set": "sft_dpo_inventory/ablation_012/e2/h_dev.yaml first 300", "cells": ["base", "B2F o43", "V4 o101"],
                      "rule": "any cell: truncated-call pct > 3 or > 2 x same-model sampling reference -> G1, else G0; accuracy/refusal not used"},
            "pf2": {"gold_sha256": sha("/data/hwkim/sftdpo_work/protected_final_v2/pf2_gold.yaml"), "meta_sha256": sha("/data/hwkim/sftdpo_work/protected_final_v2/pf2_items_meta.json")},
            "gpus": ["GPU-2445b100-70d8-e384-3a24-0249eeefc64d", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555", "GPU-c8f1bae2-de7a-a1c0-a054-8b6ebe5c2c8e",
                     "GPU-48f798cc-9437-50ac-d604-448bbad7b311"],
            "device_byte_check": "exempt (decision 270, as decision 269)", "deadline": "2026-11-20T21:00:00+09:00"}
    assert all(body["exec_files_same_as_tools_commit_19d91001"].values()), body["exec_files_same_as_tools_commit_19d91001"]
    (HERE / "FREEZE_JG.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(body["files"]), "files; exec same as 19d91001:", all(body["exec_files_same_as_tools_commit_19d91001"].values()))


if __name__ == "__main__":
    main()
