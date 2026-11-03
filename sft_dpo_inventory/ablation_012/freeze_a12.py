# -*- coding: utf-8 -*-
"""ablation_012 측정 전 고정(결정 262, PLAN_A12 6절). ``ablation_011/freeze_a11.py``(그대로)와 같은 방식.

    python3 sft_dpo_inventory/ablation_012/freeze_a12.py plan    # -> FREEZE_A12.json(학습 전)
    python3 sft_dpo_inventory/ablation_012/freeze_a12.py tools   # -> FREEZE_A12_tools.json(분석 도구, 평가 전)
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def files(globs):
    out = {}
    for g in globs:
        hits = sorted(p for p in ROOT.glob(g) if p.is_file())
        if not hits:
            raise SystemExit(f"missing {g}")
        for p in hits:
            out[str(p.relative_to(ROOT))] = sha(p)
    return out


def main():
    which = sys.argv[1]
    A = "sft_dpo_inventory/ablation_012"
    if which == "plan":
        body = {"label": "ablation_012 FREEZE(결정 262) — 학습 전", "note": "진단, 판정 아님",
                "order_seeds": [1102, 211102, 2026113], "model_seed": 43, "draw_seeds": {"A3R-d1": 20261104, "A3R-d2": 20261105}, "split_seed": 20261103,
                "bootstrap": {"reps": 10000, "rng": "numpy.random.default_rng(20261109), 비교마다 새로", "ci": "백분위 95%"},
                "power_sim": {"sims": 400, "boot": 1000, "rng_plan2": 20261110, "rng_plan3": 20261111, "seeds_n": [3, 5, 8],
                              "true_diff_pp": {"accuracy": [0, -2, -3], "over_refusal": [0, 1], "correct_refusal": [0, -5]}},
                "a3_interpretation": "(A3 − A3R) 95% CI가 0을 포함하지 않으면 '요금 대조 고유 효과', 포함하면 '데이터 양 효과와 구별 안 됨'",
                "e1": {"sets": ["refusal_dev v2", "valid98", "aux"], "k": 4, "round_seeds": "20261100 + k", "concurrency": 8},
                "ct10k": {"k": 1, "seed": 20261101, "concurrency": 32, "chunks": "client_test_10000/gpu/chunks/c1-c5"},
                "h_dev": {"k": 1, "seed": 20261101, "base_k": [1, 2], "concurrency": 32},
                "h_final": "봉인 — 측정하지 않음, PLAN_J 판정 전용, 측정은 사용자 지시 뒤",
                "files": files([f"{A}/PLAN_A12.md", f"{A}/build/build12.py", f"{A}/build/mask_audit12.py", f"{A}/build/build_summary.json", f"{A}/build/mask_audit12.json",
                                f"{A}/build/removed_A3R-d*.json", f"{A}/build/A3R-d*/full/*", f"{A}/build/orders/*.json",
                                f"{A}/train/make_a12_configs.py", f"{A}/train/configs/*.yaml", f"{A}/train/configs/DIFF.md",
                                f"{A}/e2/build_e2.py", f"{A}/e2/h_dev.yaml", f"{A}/e2/h_final.yaml", f"{A}/e2/e2_summary.json", f"{A}/e2/pool_rule_check.json",
                                f"{A}/e2/gold_check_h_dev.json", f"{A}/e2/gold_check_h_final_summary.json",
                                f"{A}/gpu/scheduler14.py", f"{A}/gpu/make_jobs_a12.py", f"{A}/gpu/jobs_a12.json",
                                "sft_dpo_inventory/ablation_011/gpu/serve_a11.sh", "sft_dpo_inventory/ablation_011/train/train_a11.py",
                                "sft_dpo_inventory/ablation_011/build/removed_A3.json", "sft_dpo_inventory/ablation_011/build/orders/record_order_A0_o*.json",
                                "sft_dpo_inventory/ablation_011/build/orders/order_b2_o*.json", "sft_dpo_inventory/ablation_011/train/configs/A3-o*.yaml",
                                "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl", "sft_dpo_inventory/client_test_10000/qa_test_10000.yaml",
                                "sft_dpo_inventory/client_test_10000/gpu/chunks/*.txt", "sft_dpo_inventory/pilot_007/results/completeness_B.py",
                                "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py", "sft_dpo_inventory/pilot_005/vllm_eval_thinking5.py"])}
        out = HERE / "FREEZE_A12.json"
    else:
        body = {"label": "ablation_012 FREEZE tools(결정 262) — 평가 전", "note": "진단, 판정 아님",
                "smoke": json.loads((HERE / "analysis/smoke_a12.json").read_text(encoding="utf-8")).get("summary"),
                "amendments_to_plan": json.loads((HERE / "analysis/amendments.json").read_text(encoding="utf-8")),
                "files": files([f"{A}/analysis/*.py", f"{A}/analysis/smoke_a12.json", f"{A}/analysis/amendments.json"])}
        out = HERE / "FREEZE_A12_tools.json"
    body["frozen_at"] = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    out.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out, len(body["files"]))


if __name__ == "__main__":
    main()
