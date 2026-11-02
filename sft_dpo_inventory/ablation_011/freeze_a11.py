# -*- coding: utf-8 -*-
"""ablation_011 측정 전 고정(결정 261, PLAN_A11 7절). 파일 sha256과 정한 값을 FREEZE_A11.json(학습 전) 또는 FREEZE_A11_tools.json(분석 도구, 평가 전)에 쓴다.

    python3 sft_dpo_inventory/ablation_011/freeze_a11.py plan    # -> FREEZE_A11.json
    python3 sft_dpo_inventory/ablation_011/freeze_a11.py tools   # -> FREEZE_A11_tools.json
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
        hits = sorted(ROOT.glob(g))
        if not hits:
            raise SystemExit(f"missing {g}")
        for p in hits:
            out[str(p.relative_to(ROOT))] = sha(p)
    return out


def main():
    which = sys.argv[1]
    A = "sft_dpo_inventory/ablation_011"
    if which == "plan":
        body = {"label": "ablation_011 FREEZE(결정 261) — 학습 전", "note": "진단, 판정 아님",
                "order_seeds": [1102, 211102, 2026113], "model_seed": 43, "bootstrap": {"reps": 10000, "rng": "numpy.random.default_rng(20261109), 비교마다 새로", "ci": "백분위 95%"},
                "e1": {"sets": ["refusal_dev v2", "valid98", "aux"], "k": 4, "round_seeds": "20261100 + k", "concurrency": 8, "reference_date": "2026-09-25"},
                "e2": "없음 — 30k 원천 llm-finetuning-30000.jsonl 없음(결정 261 실행 기록)",
                "files": files([f"{A}/PLAN_A11.md", f"{A}/build/build11.py", f"{A}/build/mask_audit11.py", f"{A}/build/build_summary.json", f"{A}/build/mask_audit11.json",
                                f"{A}/build/removed_A2.json", f"{A}/build/removed_A3.json", f"{A}/build/A*/full/*", f"{A}/build/orders/*.json",
                                f"{A}/train/train_a11.py", f"{A}/train/make_a11_configs.py", f"{A}/train/configs/*.yaml", f"{A}/train/configs/DIFF.md",
                                f"{A}/gpu/scheduler13.py", f"{A}/gpu/serve_a11.sh", f"{A}/gpu/make_jobs_a11.py", f"{A}/gpu/jobs_a11.json",
                                "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl", "sft_dpo_inventory/pilot_010/build/V4/full/manifest.json",
                                "sft_dpo_inventory/pilot_007/train_data/train_b7b.py", "sft_dpo_inventory/pilot_007/train_data/order7b.py", "sft_dpo_inventory/pilot_007/train_data/order7.py",
                                "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py", "sft_dpo_inventory/pilot_005/vllm_eval_thinking5.py", "training/data/thinking.py"])}
        out = HERE / "FREEZE_A11.json"
    else:
        body = {"label": "ablation_011 FREEZE tools(결정 261) — 평가 전", "note": "진단, 판정 아님",
                "files": files([f"{A}/analysis/*.py", f"{A}/analysis/smoke_*.json", f"{A}/soup/soup11.py"])}
        out = HERE / "FREEZE_A11_tools.json"
    body["frozen_at"] = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    out.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out, len(body["files"]))


if __name__ == "__main__":
    main()
