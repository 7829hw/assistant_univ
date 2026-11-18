# -*- coding: utf-8 -*-
"""pilot_010 JQ FREEZE_JQ.json(결정 269, PLAN_JQ) — 학습·측정·계산 전에 고정할 파일 sha256과 값. 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_010/freeze_jq.py --commit <작업 고정 커밋 40자리>
"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEEDS = json.loads((HERE / "build/seeds_jq.json").read_text(encoding="utf-8"))["order_seeds"]
P = "sft_dpo_inventory/pilot_010/"
FILES = [P + "PLAN_JQ.md", P + "build/pick_seeds_jq.py", P + "build/seeds_jq.json", P + "build/make_orders_jq.py", P + "build/orders_jq_summary.json",
         P + "build/V8/full/sft_train.jsonl", P + "build/V8/full/manifest.json", P + "build/V8/order_b2_o43.json",
         *[P + f"build/V8/order_b2_o{s}.json" for s in SEEDS], P + "train/configs_s10/S-V8-o43.yaml", P + "train/make_jq_configs.py",
         *[P + f"train/configs_jq/JQ-V8-o{s}.yaml" for s in SEEDS], P + "train/configs_jq/DIFF.md", P + "train/configs_jq/dryrun.log",
         "sft_dpo_inventory/pilot_007/train/train_b7b.py", "sft_dpo_inventory/pilot_007/train_data/order7b.py", P + "gpu/scheduler19.py", P + "gpu/make_jobs_jq.py",
         P + "gpu/JQ/jobs_jq.json", P + "protected_final_v2/run_cell_pf2.py", P + "protected_final_v2/vllm_eval_pf2.py", "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py",
         "sft_dpo_inventory/ablation_011/gpu/serve_a11.sh", "sft_dpo_inventory/pilot_007/results/completeness_B.py", "sft_dpo_inventory/ablation_012/e2/h_final.yaml",
         "evaluate_vendor100.py", P + "results/analyze_j.py", P + "results/analyze_jp.py", P + "results/validity_j.py", P + "freeze_jq.py"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def same_as_19d91001(f):
    a = subprocess.run(["git", "rev-parse", f"19d91001:{f}"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    b = subprocess.run(["git", "rev-parse", f"HEAD:{f}"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return bool(a) and a == b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", required=True)
    a = ap.parse_args()
    exec_files = ["sft_dpo_inventory/pilot_010/protected_final_v2/run_cell_pf2.py", "sft_dpo_inventory/pilot_010/protected_final_v2/vllm_eval_pf2.py",
                  "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py", "sft_dpo_inventory/ablation_011/gpu/serve_a11.sh",
                  "sft_dpo_inventory/pilot_007/results/completeness_B.py", "sft_dpo_inventory/pilot_007/train/train_b7b.py", "evaluate_vendor100.py"]
    body = {"decision": 269, "label": "판정 뒤 추가(사후), PF2·H-final 두 번째 사용", "plan": P + "PLAN_JQ.md", "jobs_commit": a.commit,
            "frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "files": {f: sha(ROOT / f) for f in FILES},
            "exec_files_same_as_tools_commit_19d91001": {f: same_as_19d91001(f) for f in exec_files},
            "values": {"order_seeds": SEEDS, "model_seed": 43, "checkpoint": "checkpoint-2071 (epoch end)", "v8_train_sha256": sha(ROOT / P / "build/V8/full/sft_train.jsonl"),
                       "train_output_root": "/data/hwkim/sftdpo_work/pilot_010/train_jq", "prompt_sha256_prefix": "87048d0c", "semantic_code_fingerprint": "791c4a68", "thinking": "on"},
            "pf2": {"gold_sha256": sha("/data/hwkim/sftdpo_work/protected_final_v2/pf2_gold.yaml"), "meta_sha256": sha("/data/hwkim/sftdpo_work/protected_final_v2/pf2_items_meta.json")},
            "gpus": ["GPU-2445b100-70d8-e384-3a24-0249eeefc64d", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555", "GPU-c8f1bae2-de7a-a1c0-a054-8b6ebe5c2c8e",
                     "GPU-48f798cc-9437-50ac-d604-448bbad7b311"],
            "device_byte_check": "exempt (decision 269)", "deadline": "2026-11-20T21:00:00+09:00"}
    assert all(body["exec_files_same_as_tools_commit_19d91001"].values()), body["exec_files_same_as_tools_commit_19d91001"]
    (HERE / "FREEZE_JQ.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(body["files"]), "files; exec same as 19d91001:", all(body["exec_files_same_as_tools_commit_19d91001"].values()))


if __name__ == "__main__":
    main()
