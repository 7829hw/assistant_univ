# -*- coding: utf-8 -*-
"""pilot_010 FREEZE_J.json(결정 267, PLAN_J) — 학습 전에 고정할 파일의 sha256과 값. 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_010/freeze_j.py   # -> pilot_010/FREEZE_J.json
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INV = ROOT / "sft_dpo_inventory"
SEEDS = (101, 523, 2029, 31, 20271027)
FILES = [
    "sft_dpo_inventory/pilot_010/PLAN_J.md",
    "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl",
    "sft_dpo_inventory/pilot_010/build/V4/full/sft_valid.jsonl",
    "sft_dpo_inventory/pilot_010/build/V4/full/manifest.json",
    "sft_dpo_inventory/pilot_010/build/make_orders_j.py",
    "sft_dpo_inventory/pilot_010/build/orders_j_summary.json",
    *[f"sft_dpo_inventory/pilot_010/build/V4/order_b2_o{s}.json" for s in SEEDS],
    "sft_dpo_inventory/pilot_010/train/make_j_configs.py",
    *[f"sft_dpo_inventory/pilot_010/train/configs_j/J-V4-o{s}.yaml" for s in SEEDS],
    "sft_dpo_inventory/pilot_010/train/configs_j/dryrun.log",
    "sft_dpo_inventory/pilot_007/train/train_b7b.py",
    "sft_dpo_inventory/pilot_007/train_data/order7b.py",
    "sft_dpo_inventory/pilot_010/gpu/scheduler17.py",
    "sft_dpo_inventory/pilot_010/gpu/make_jobs_j.py",
    "sft_dpo_inventory/pilot_010/gpu/J/jobs_j.json",
    "sft_dpo_inventory/ablation_012/e2/h_final.yaml",
    "sft_dpo_inventory/pilot_010/protected_final_v2/MANIFEST_PF2_J.json",
    "sft_dpo_inventory/pilot_010/protected_final_v2/check_pf2_j.py",
    "sft_dpo_inventory/pilot_007/adapters_B2.json",
    "sft_dpo_inventory/pilot_010/freeze_j.py",
]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    b2 = json.loads((INV / "pilot_007/adapters_B2.json").read_text(encoding="utf-8"))["adapters"]
    body = {
        "decision": 267, "plan": "sft_dpo_inventory/pilot_010/PLAN_J.md", "frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "files": {f: sha(ROOT / f) for f in FILES},
        "values": {
            "v4_train_sha256": "3575c7f06c2ee7baaf59233b01c926504589ec2fbf3136f255a45599ced10e3f",
            "v4_question_list_sha256": "d559b3e1acca8c8dbd3592d3e0c2302e1890b88801f5df5d160a35938ef54b98",
            "order_seeds": {"round1": [101, 523, 2029], "round2": [31, 20271027]}, "model_seed": 43, "checkpoint": "checkpoint-1984 (epoch end)",
            "prompt_sha256_prefix": "87048d0c", "semantic_code_fingerprint": "791c4a68", "thinking": "on", "train_output_root": "/data/hwkim/sftdpo_work/pilot_010/train_j",
            "b2f_adapters": {k: {"checkpoint": "checkpoint-1811", "adapter_sha256": v["checkpoint-1811"]["adapter_sha256"]} for k, v in b2.items() if k.startswith("B2-F-")},
            "base": {"model": "Qwen/Qwen3-8B", "revision": "b968826d9c46dd6066d109eabc6255188de91218"},
            "pf2": {"xlsx_sha256": "c7174e710d56adfee4b055c1655836b49c84ae0df97c2732acf5a5e2b5631557", "items": 150, "refusal": 50, "answerable": 100, "contrast": 25,
                    "excluded_rows": [], "reference_date": "2026-10-26", "k_adapter": 4, "k_base": 8, "concurrency": 8, "rerun": "none"},
            "h_final": {"sha256": "bbc4265071be36f99630bfcc00fa832950c07a131e2007ba63a0274aa0697ddb", "items": 3000, "k": 1, "round_seed": 20261101,
                        "base_round_seeds": [20261101, 20261102], "concurrency": 32, "reference_date": "2026-09-25", "rerun": "PLAN_S 5절 (> 1% truncated calls, same seed once)"},
            "seed_base": 20261100, "protocol": "PROTOCOL_v5: vLLM 0.30.0 BF16, flashinfer, LoRA unmerged, max_model_len 17408, T 0.6 / top_p 0.95 / top_k 20 / min_p 0 / max_tokens 8192",
            "bootstrap": {"reps": 10000, "rng": "numpy.random.default_rng(20261109) per comparison", "method": "U1 hierarchical: items shared across arms, seeds per arm; base items only",
                          "ci": "percentile 2.5/97.5"},
            "criteria": {"C1": "P1 (V4 - B2F) lower > 0; no (c) -> undecidable", "C2": "P1 (V4 - base) lower >= -15pp",
                         "C3": "P2 answerable100 (V4 - B2F) upper <= +3pp; no (c) -> V4 - base",
                         "C4": "H-final V4 seed mean >= base(mean of 2 rounds) + 5pp and lowest seed >= base"},
            "time_rule": {"report_deadline": "2026-11-20T12:00:00+09:00", "round2_not_after": "2026-11-20T05:00:00+09:00", "new_job_deadline": "2026-11-20T09:00:00+09:00"},
            "gpus": ["GPU-2445b100-70d8-e384-3a24-0249eeefc64d", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555", "GPU-48f798cc-9437-50ac-d604-448bbad7b311"],
            "ollama_gpu": "GPU-48f798cc-9437-50ac-d604-448bbad7b311",
        },
        "later": "평가 도구·분석 스크립트는 측정 전에 FREEZE_J_tools.json으로 고정한다(PLAN_J 머리말).",
    }
    (HERE / "FREEZE_J.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(body["files"]), "files frozen")


if __name__ == "__main__":
    main()
