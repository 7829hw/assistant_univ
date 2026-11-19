# -*- coding: utf-8 -*-
"""pilot_010 JT(결정 271) 측정 전 고정: 계획·실행·분석 파일과 그 의존 파일의 sha256 → ``pilot_010/FREEZE_JT.json``.

    python3 sft_dpo_inventory/pilot_010/jt/freeze_jt.py
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FILES = [
    "sft_dpo_inventory/pilot_010/PLAN_JT.md",
    "sft_dpo_inventory/pilot_010/jt/vllm_thinking27.py", "sft_dpo_inventory/pilot_010/jt/vllm_eval_jt.py", "sft_dpo_inventory/pilot_010/jt/run_cell_jt.py",
    "sft_dpo_inventory/pilot_010/jt/serve27.sh", "sft_dpo_inventory/pilot_010/jt/driver_jt.py", "sft_dpo_inventory/pilot_010/jt/make_subset_jt.py",
    "sft_dpo_inventory/pilot_010/jt/record_model_jt.py", "sft_dpo_inventory/pilot_010/jt/hfinal_subset1000_ids.txt", "sft_dpo_inventory/pilot_010/jt/hfinal_subset1000.json",
    "sft_dpo_inventory/pilot_010/jt/model_manifest.json", "sft_dpo_inventory/pilot_010/jt/vllm_support.json", "sft_dpo_inventory/pilot_010/jt/render_check.json",
    "sft_dpo_inventory/pilot_010/results/analyze_jt.py",
    # 의존(고치지 않음)
    "sft_dpo_inventory/pilot_010/results/analyze_jg.py", "sft_dpo_inventory/pilot_010/results/analyze_jq.py", "sft_dpo_inventory/pilot_010/results/analyze_j.py",
    "sft_dpo_inventory/pilot_010/results/analyze_jp.py", "sft_dpo_inventory/pilot_010/results/validity_j.py", "sft_dpo_inventory/pilot_007/results/completeness_B.py",
    "sft_dpo_inventory/pilot_010/protected_final_v2/vllm_eval_pf2.py", "sft_dpo_inventory/serving_vllm/vllm_thinking.py", "sft_dpo_inventory/thinking_prep_001/hf_thinking.py",
    "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py", "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x_g1.py", "sft_dpo_inventory/ablation_011/gpu/serve_a11.sh",
    "sft_dpo_inventory/pilot_007/gpu_data/gpu_lib7.sh", "training/trainer_common.py", "evaluate_vendor100.py",
    "sft_dpo_inventory/ablation_012/e2/h_final.yaml", "sft_dpo_inventory/ablation_012/e2/h_dev.yaml", "sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt",
    "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml", "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml",
]


def main():
    rec = {"decision": 271, "plan": "sft_dpo_inventory/pilot_010/PLAN_JT.md", "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "files": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in FILES},
           "model": {"repo": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0", "manifest": "sft_dpo_inventory/pilot_010/jt/model_manifest.json"},
           "pf2_gold_outside_repo": "/data/hwkim/sftdpo_work/protected_final_v2/pf2_gold.yaml (sha256은 셀 meta·분석 inputs에 적힘)"}
    out = ROOT / "sft_dpo_inventory/pilot_010/FREEZE_JT.json"
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("written", out, len(rec["files"]))


if __name__ == "__main__":
    main()
