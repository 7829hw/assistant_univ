# -*- coding: utf-8 -*-
"""pilot_010 사후 측정 FREEZE_JP.json(결정 268, PLAN_J_POSTHOC) — 측정 전에 고정할 파일 sha256과 값. 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_010/freeze_jp.py --tools-commit <40자리>
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FILES = ["sft_dpo_inventory/pilot_010/PLAN_J_POSTHOC.md", "sft_dpo_inventory/pilot_010/gpu/scheduler18.py", "sft_dpo_inventory/pilot_010/gpu/make_jobs_jp.py",
         "sft_dpo_inventory/pilot_010/gpu/JP/jobs_jp.json", "sft_dpo_inventory/pilot_010/results/analyze_jp.py", "sft_dpo_inventory/pilot_010/results/analyze_j.py",
         "sft_dpo_inventory/pilot_010/results/validity_j.py", "sft_dpo_inventory/pilot_010/gates/select_s10.py", "sft_dpo_inventory/pilot_010/gates/make_spec_jp.py",
         "sft_dpo_inventory/pilot_010/gates/spec_jp_dev.json", "sft_dpo_inventory/pilot_010/protected_final_v2/run_cell_pf2.py",
         "sft_dpo_inventory/pilot_010/protected_final_v2/vllm_eval_pf2.py", "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py",
         "sft_dpo_inventory/ablation_012/e2/h_final.yaml", "sft_dpo_inventory/pilot_010/gpu/JP/device_check/compare2.json", "sft_dpo_inventory/pilot_010/freeze_jp.py"]
ADAPTERS = {"P9": {s: ("/data/hwkim/sftdpo_work/pilot_009/train_p9/P9-F-%s/checkpoint-1993" % s) for s in ("o43", "o1016", "o7", "o11", "o2027")},
            "V8": {s: ("/data/hwkim/sftdpo_work/pilot_010/train_s10/S-V8-%s/checkpoint-2071" % s) for s in ("o43", "o1016", "o7")},
            "V4": {s: ("/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-%s/checkpoint-1984" % s) for s in ("o101", "o523", "o2029", "o31", "o20271027")}}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools-commit", required=True)
    a = ap.parse_args()
    body = {"decision": 268, "label": "판정 뒤 추가(사후)", "plan": "sft_dpo_inventory/pilot_010/PLAN_J_POSTHOC.md", "tools_commit": a.tools_commit,
            "frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "files": {f: sha(ROOT / f) for f in FILES},
            "adapters_sha256_checked": {arm: {s: sha(Path(p) / "adapter_model.safetensors") for s, p in d.items()} for arm, d in ADAPTERS.items()},
            "pf2": {"gold_sha256": sha("/data/hwkim/sftdpo_work/protected_final_v2/pf2_gold.yaml"), "meta_sha256": sha("/data/hwkim/sftdpo_work/protected_final_v2/pf2_items_meta.json")},
            "gpus": ["GPU-2445b100-70d8-e384-3a24-0249eeefc64d", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555", "GPU-48f798cc-9437-50ac-d604-448bbad7b311"],
            "gpu_not_used": {"GPU-c8f1bae2-de7a-a1c0-a054-8b6ebe5c2c8e": "device check 2 (compare2.json): V4_o101 5/7 calls differ from reference GPU"},
            "deadline": "2026-11-20T09:00:00+09:00"}
    (HERE / "FREEZE_JP.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(body["files"]), "files;", {k: len(v) for k, v in body["adapters_sha256_checked"].items()})


if __name__ == "__main__":
    main()
