# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273) 측정 전 고정: 계획·변환·등록·실행·분석 파일과 그 의존 파일의 sha256, 모델 digest → ``pilot_010/FREEZE_JV.json``.

    python3 sft_dpo_inventory/pilot_010/jv/freeze_jv.py
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
JV = "sft_dpo_inventory/pilot_010/jv/"
FILES = [
    "sft_dpo_inventory/pilot_010/PLAN_JV.md",
    *[JV + f for f in ("models_jv.py", "convert_jv.py", "compare_types_jv.py", "register_jv.py", "serve_jv.sh", "ollama_eval_jv.py", "run_cell_jv.py",
                       "common_jv.py", "serverlog_jv.py", "render_check_jv.py", "render_split_jv.py", "driver_jv.py")],
    "sft_dpo_inventory/pilot_010/results/analyze_jv.py",
    "sft_dpo_inventory/pilot_010/gpu/JV/render_check.json", "sft_dpo_inventory/pilot_010/gpu/JV/render_split.json",
    # 의존(고치지 않음)
    "evaluate_vendor100.py", "ollama_client.py", "training/merge_adapter.py", "sft_dpo_inventory/pilot_prep_001/gguf_convert.sh",
    "sft_dpo_inventory/pilot_prep_003/ollama/Modelfile.base.thinking", "sft_dpo_inventory/pilot_001/ollama/register_model.py",
    "sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py", "sft_dpo_inventory/thinking_prep_001/hf_thinking.py",
    "sft_dpo_inventory/pilot_007/gpu_data/gpu_lib7.sh", "sft_dpo_inventory/pilot_010/jt/hfinal_subset1000_ids.txt", "sft_dpo_inventory/pilot_010/gpu/JG/adapters_check_main.json",
    "sft_dpo_inventory/pilot_010/results/analyze_ju.py", "sft_dpo_inventory/pilot_010/results/ju_results.json",
    "sft_dpo_inventory/pilot_010/results/analyze_jt.py", "sft_dpo_inventory/pilot_010/results/jt_results.json", "sft_dpo_inventory/pilot_010/results/analyze_jg.py",
    "sft_dpo_inventory/pilot_010/results/analyze_jq.py", "sft_dpo_inventory/pilot_010/results/analyze_j.py", "sft_dpo_inventory/pilot_010/results/analyze_jp.py",
    "sft_dpo_inventory/pilot_010/results/validity_j.py", "sft_dpo_inventory/ablation_012/e2/h_final.yaml", "sft_dpo_inventory/ablation_012/e2/h_dev.yaml",
    "sft_dpo_inventory/conversion_diag/selection_gold.yaml", "sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt",
]


def main():
    reg = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in sorted((HERE / "registration").glob("*.json"))}
    rec = {"decision": 273, "plan": "sft_dpo_inventory/pilot_010/PLAN_JV.md", "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "files": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in FILES},
           "receipts": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((HERE / "receipts").glob("*.json"))},
           "models": {k: {"ollama": v["model"], "digest": v["digest"], "q4_sha256": v["source_gguf"]["sha256"]} for k, v in reg.items()},
           "teacher_q4": {"ollama": "qwen3.8:27b", "digest": "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813", "models_dir": "/data/hwkim/sftdpo_work/pilot_010_ju/models"},
           "ollama": {"version": "0.40.6", "binary": "/data/hwkim/sftdpo_work/pilot_010_ju/ollama-0.40.6/bin/ollama", "models_dir": "/data/hwkim/sftdpo_work/pilot_010_jv/models"},
           "pf2_gold_outside_repo": "/data/hwkim/sftdpo_work/protected_final_v2/pf2_gold.yaml (sha256은 셀 meta·분석 inputs에 적힘)"}
    out = ROOT / "sft_dpo_inventory/pilot_010/FREEZE_JV.json"
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("written", out, len(rec["files"]), len(rec["models"]))


if __name__ == "__main__":
    main()
