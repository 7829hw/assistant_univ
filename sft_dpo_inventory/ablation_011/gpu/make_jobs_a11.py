# -*- coding: utf-8 -*-
"""ablation_011 작업 표(결정 261) → ``gpu/jobs_a11.json``. scheduler13이 (prio, id) 순으로 고른다.

- 우선순위: (1) 학습이 끝난 모델의 평가 E-<id>(prio 1; adapter 파일이 생겨야 준비됨) → (2) 학습 T-<id>(순서 seed 블록 단위: 블록 1 = A0·A1·A2·A3 @1102 → 블록 2 @211102
  → 블록 3 @2026113; prio 10–21) → (3) soup 평가 E-soup(prio 30). E2(H-ans·H-ref)와 그 기준 셀은 30k 원천이 없어 빠졌다(결정 261 실행 기록).
- 평가 E1: refusal_dev v2(거부 90 + 대조 30)·valid98·aux, k = 1–4(회차 seed 20261100 + k), 동시 8, grounding_target full —
  pilot_010 ES 작업(``pilot_010/gpu_data/jobs_S2.json``)과 같은 client(``pilot_006_prep/gpu_data/run_cell6x.py``)·sampler·seed·순서(rdev → valid98 → aux, 셋 안 k 순).
- 평가 작업은 ``gpu/ready/A11_TOOLS.json``(분석 도구 smoke·고정 커밋 뒤 만든다)이 있어야 시작한다(PLAN_A11 7절).
- 학습: ``ablation_011/train/train_a11.py --config ablation_011/train/configs/<id>.yaml``, epoch 끝 checkpoint = checkpoint-<레코드 수>.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
MAIN = "/home/hwkim/assistant_univ"
TRAIN = "/data/hwkim/sftdpo_work/ablation_011/train"
SOUP = "/data/hwkim/sftdpo_work/ablation_011/soup/V4-soup3"
SEEDS = (1102, 211102, 2026113)
ARMS = ("A0", "A1", "A2", "A3")
STEPS = {"A0": 1984, "A1": 1984, "A2": 1944, "A3": 1522}
SETS = (("rdevv2", "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"),
        ("valid98", "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml"),
        ("aux", "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"))
SEC_PER_STEP = 5.9  # pilot_010 실측(1,984 step 191–198분)


def cell_cmd(model, label_prefix):
    parts = []
    for st, gold in SETS:
        for k in range(1, 5):
            parts.append(f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port {{PORT}} --model {model} --label {label_prefix}_{st} --k {k} "
                         f"--concurrency 8 --grounding-target full --out-dir {MAIN}/sft_dpo_inventory/ablation_011/cells "
                         f"--raw-dir {MAIN}/training/generated/ablation_011/cells_raw --seed-base 20261100 --gold {gold} --all-items")
    return ["bash", "-c", " && ".join(parts)]


def main():
    jobs = []
    for b, s in enumerate(SEEDS):
        for a, arm in enumerate(ARMS):
            cid = f"{arm}-o{s}"
            ck = f"{TRAIN}/{cid}/checkpoint-{STEPS[arm]}"
            jobs.append({"id": f"T-{cid}", "type": "raw", "kind": f"train_a11_{cid}", "server": "train", "est": round(STEPS[arm] * SEC_PER_STEP / 60), "prio": 10 + 4 * b + a,
                         "deps": [], "cmd": [PY, f"{{WT}}/sft_dpo_inventory/ablation_011/train/train_a11.py", "--config", f"{{WT}}/sft_dpo_inventory/ablation_011/train/configs/{cid}.yaml"],
                         "outputs": []})
            name = f"{arm}_o{s}"
            jobs.append({"id": f"E-{cid}", "type": "raw", "kind": f"cells_a11_{cid}_rdevv2_valid98_aux_k4", "server": f"lora:{name}={ck}", "est": 45, "prio": 1,
                         "deps": [f"file:{ck}/adapter_model.safetensors|T-{cid}", "ready:A11_TOOLS"], "cmd": cell_cmd(name, f"a11_{arm.lower()}_o{s}"), "outputs": []})
    jobs.append({"id": "E-soup", "type": "raw", "kind": "cells_a11_soup_rdevv2_valid98_aux_k4", "server": f"lora64:V4_soup3={SOUP}", "est": 45, "prio": 30,
                 "deps": [f"file:{SOUP}/adapter_model.safetensors", "ready:A11_TOOLS"], "cmd": cell_cmd("V4_soup3", "a11_soup"), "outputs": []})
    (HERE / "jobs_a11.json").write_text(json.dumps({"label": "ablation_011(결정 261)", "jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(jobs), [(j["id"], j["prio"], j["est"]) for j in jobs if j["server"] == "train"])


if __name__ == "__main__":
    main()
