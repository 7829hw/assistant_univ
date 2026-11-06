# -*- coding: utf-8 -*-
"""ablation_013 측정 전 고정(결정 263, PLAN_A13 7절). ``ablation_012/freeze_a12.py``(그대로)와 같은 방식.

    python3 sft_dpo_inventory/ablation_013/freeze_a13.py plan    # -> FREEZE_A13.json(학습 전)
    python3 sft_dpo_inventory/ablation_013/freeze_a13.py tools   # -> FREEZE_A13_tools.json(분석 도구, 평가 전)
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
    A = "sft_dpo_inventory/ablation_013"
    if which == "plan":
        body = {"label": "ablation_013 FREEZE(결정 263) — 학습 전", "note": "진단, 판정 아님",
                "order_seeds_a3t": [1102, 211102, 2026113], "order_seeds_a0_new": [2026117, 2026131], "model_seed": 43, "a3t_draw_seed": 20261106,
                "a3t": {"target_share_pct": 16.15, "tolerance_pp": 2.0, "reached_target": False, "final_share_pct": 29.6, "removed_questions": 55, "removed_records": 198},
                "bootstrap": {"reps": 10000, "rng": "numpy.random.default_rng(20261109), 비교마다 새로", "ci": "백분위 95%"},
                "power_sim_criteria_dev_v1": {"sims": 400, "boot": 1000, "rng": 20261113, "seeds_n": 5,
                                              "true_diff_pp": {"accuracy_hdev": [0, -2, -3, -4], "correct_refusal": [0, -5, -7], "over_refusal": [0, 1, 1.5]}},
                "a3_interpretation": {"A3-A3T": "95% CI가 0을 포함하지 않으면 '근접 대조 비중을 맞춰도 남는 요금 대조 고유 효과', 포함하면 '근접 대조 비중 효과와 구별 안 됨' (구성 차이 병기)",
                                      "A3T-A0_over_refusal": "CI 하한 > 0이면 '요금 외 근접 대조도 과잉 거부를 막음'"},
                "signature_split": "PLAN_A13 5.2 T1–T5 정의",
                "e1": {"sets": ["refusal_dev v2", "valid98", "aux"], "k": 4, "round_seeds": "20261100 + k", "concurrency": 8},
                "h_dev": {"k": 1, "seed": 20261101, "concurrency": 32},
                "j_b014": {"base_self_round_seed": 20261015, "greedy_first": True},
                "h_final": "봉인 — 측정·열람 안 함(그룹 크기 분포만, e2/h_final_group_sizes.json)",
                "files": files([f"{A}/PLAN_A13.md", f"{A}/CRITERIA_DEV_v1.json", f"{A}/e2/h_final_group_sizes.py", f"{A}/e2/h_final_group_sizes.json",
                                f"{A}/build/build13.py", f"{A}/build/mask_audit13.py", f"{A}/build/build_summary.json", f"{A}/build/mask_audit13.json",
                                f"{A}/build/removed_A3T.json", f"{A}/build/loss_tokens_A0.json", f"{A}/build/A3T/full/*", f"{A}/build/orders/*.json",
                                f"{A}/train/make_a13_configs.py", f"{A}/train/configs/*.yaml", f"{A}/train/configs/DIFF.md",
                                f"{A}/gpu/scheduler15.py", f"{A}/gpu/make_jobs_a13.py", f"{A}/gpu/jobs_a13.json", f"{A}/gpu/seeds_a13.json", f"{A}/gpu/check_ready13.sh",
                                "sft_dpo_inventory/ablation_011/gpu/serve_a11.sh", "sft_dpo_inventory/ablation_011/train/train_a11.py",
                                "sft_dpo_inventory/ablation_011/build/orders/record_order_A0_o*.json", "sft_dpo_inventory/ablation_011/build/orders/order_b2_o*.json",
                                "sft_dpo_inventory/ablation_011/train/configs/A3-o*.yaml", "sft_dpo_inventory/ablation_011/train/configs/A0-o1102.yaml",
                                "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl", "sft_dpo_inventory/ablation_012/e2/h_dev.yaml",
                                "sft_dpo_inventory/pilot_007/results/completeness_B.py", "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py",
                                "sft_dpo_inventory/pilot_006_prep/gpu_data/collect6b.py", "sft_dpo_inventory/pilot_008/gpu/collect8.py"])}
        out = HERE / "FREEZE_A13.json"
    else:
        body = {"label": "ablation_013 FREEZE tools(결정 263) — 평가 전", "note": "진단, 판정 아님",
                "smoke": json.loads((HERE / "analysis/smoke_a13.json").read_text(encoding="utf-8")).get("summary"),
                "amendments_to_plan": json.loads((HERE / "analysis/amendments.json").read_text(encoding="utf-8")),
                "files": files([f"{A}/analysis/*.py", f"{A}/analysis/smoke_a13.json", f"{A}/analysis/amendments.json"])}
        out = HERE / "FREEZE_A13_tools.json"
    body["frozen_at"] = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    out.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out, len(body["files"]))


if __name__ == "__main__":
    main()
