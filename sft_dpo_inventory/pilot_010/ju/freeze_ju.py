# -*- coding: utf-8 -*-
"""pilot_010 JU(결정 272) 측정 전 고정: 계획·실행·분석 파일과 그 의존 파일의 sha256 → ``pilot_010/FREEZE_JU.json``.

    python3 sft_dpo_inventory/pilot_010/ju/freeze_ju.py
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FILES = [
    "sft_dpo_inventory/pilot_010/PLAN_JU.md",
    "sft_dpo_inventory/pilot_010/ju/ollama_eval_ju.py", "sft_dpo_inventory/pilot_010/ju/run_cell_ju.py", "sft_dpo_inventory/pilot_010/ju/serve_ju.sh",
    "sft_dpo_inventory/pilot_010/ju/driver_ju.py", "sft_dpo_inventory/pilot_010/ju/record_setup_ju.py", "sft_dpo_inventory/pilot_010/ju/setup_record.json",
    "sft_dpo_inventory/pilot_010/results/analyze_ju.py",
    # 의존(고치지 않음)
    "evaluate_vendor100.py", "ollama_client.py", "sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py", "sft_dpo_inventory/thinking_prep_001/hf_thinking.py",
    "sft_dpo_inventory/pilot_007/gpu_data/gpu_lib7.sh", "sft_dpo_inventory/pilot_010/jt/hfinal_subset1000_ids.txt",
    "sft_dpo_inventory/pilot_010/results/analyze_jt.py", "sft_dpo_inventory/pilot_010/results/jt_results.json", "sft_dpo_inventory/pilot_010/results/analyze_jg.py",
    "sft_dpo_inventory/pilot_010/results/analyze_jq.py", "sft_dpo_inventory/pilot_010/results/analyze_j.py", "sft_dpo_inventory/pilot_010/results/analyze_jp.py",
    "sft_dpo_inventory/pilot_010/results/validity_j.py", "sft_dpo_inventory/ablation_012/e2/h_final.yaml", "sft_dpo_inventory/ablation_012/e2/h_dev.yaml",
]


def main():
    rec = {"decision": 272, "plan": "sft_dpo_inventory/pilot_010/PLAN_JU.md", "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "files": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in FILES},
           "model": {"ollama": "qwen3.8:27b", "digest": "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813", "ollama_version": "0.40.6",
                     "setup_record": "sft_dpo_inventory/pilot_010/ju/setup_record.json"},
           "pf2_gold_outside_repo": "/data/hwkim/sftdpo_work/protected_final_v2/pf2_gold.yaml (sha256은 셀 meta·분석 inputs에 적힘)"}
    out = ROOT / "sft_dpo_inventory/pilot_010/FREEZE_JU.json"
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("written", out, len(rec["files"]))


if __name__ == "__main__":
    main()
