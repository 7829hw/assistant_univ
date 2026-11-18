# -*- coding: utf-8 -*-
"""pilot_010 JQ(결정 269, PLAN_JQ) 작업 표 ``gpu/JQ/jobs_jq.json``: RR+NM8(V8) 새 순서 seed 4개 학습 + 평가 8작업.

    python3 sft_dpo_inventory/pilot_010/gpu/make_jobs_jq.py --commit <고정 커밋 40자리>

- 학습(prio 1–4, 한 바퀴, GPU마다 하나): ``train_b7b.py --config configs_jq/JQ-V8-o<seed>.yaml``. 실패는 scheduler19가 같은 config로 한 번 다시(``-retry``).
- 평가 셀 명령은 결정 268 사후 측정(``make_jobs_jp.py``)·판정 단계 J와 같은 실행기·인자. 바뀐 것은 모델·라벨·출력 위치뿐.
  - PF2(prio 10–13): ``protected_final_v2/run_cell_pf2.py``, 동시 8, k=4(회차 20261101–04), ``--sealed``, 기준일 2026-10-26, 셀·원문 700 디렉터리, ``no_rerun``.
  - H-final(prio 20–23): ``pilot_006_prep/gpu_data/run_cell6x.py``, 동시 32, k=1(회차 20261101), ``--sealed``, 셀 ``pilot_010/cells/JQ``. scheduler19 기본 다시 돌리기 검사(잘림 > 1%).
- 시작 조건: 학습 작업의 어댑터 파일(``checkpoint-2071/adapter_model.safetensors``). 모든 작업 ``commit`` = 고정 커밋.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
PFD = "/data/hwkim/sftdpo_work/protected_final_v2"
HF_GOLD = "sft_dpo_inventory/ablation_012/e2/h_final.yaml"
TRAIN = "/data/hwkim/sftdpo_work/pilot_010/train_jq"
SEEDS = tuple(json.loads((HERE.parent / "build/seeds_jq.json").read_text(encoding="utf-8"))["order_seeds"])


def pf_cell(model, label, k):
    return {"name": f"{label}_s{k}", "label": label, "k": k,
            "cmd": (f"umask 077 && {PY} {{WT}}/sft_dpo_inventory/pilot_010/protected_final_v2/run_cell_pf2.py --port {{PORT}} --model {model} --label {label} --k {k} "
                    f"--concurrency 8 --grounding-target full --out-dir {PFD}/cells --raw-dir {PFD}/raw --seed-base 20261100 --gold {PFD}/pf2_gold.yaml "
                    f"--all-items --sealed --reference-date 2026-10-26")}


def hf_cell(model, label, k):
    return {"name": f"{label}_s{k}", "label": label, "k": k,
            "cmd": (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} "
                    f"--concurrency 32 --grounding-target full --out-dir {{MAIN}}/sft_dpo_inventory/pilot_010/cells/JQ "
                    f"--raw-dir {{MAIN}}/training/generated/pilot_010/cells_raw_JQ --seed-base 20261100 --gold {HF_GOLD} --all-items --sealed")}


def pf_outputs(cells):
    return [p for c in cells for p in (f"{PFD}/cells/{c['name']}.json", f"{PFD}/cells/{c['name']}.log", f"{PFD}/raw/{c['name']}_raw.jsonl")]


def jobs(commit):
    out = []
    for i, s in enumerate(SEEDS):
        tid, ck, model = f"T-JQ-V8-o{s}", f"{TRAIN}/JQ-V8-o{s}/checkpoint-2071", f"V8_o{s}"
        out.append({"id": tid, "type": "raw", "kind": f"train_jq_V8-o{s}", "server": "train", "est": 205, "prio": 1 + i, "round": 1, "commit": commit, "deps": [],
                    "cmd": [PY, "{WT}/sft_dpo_inventory/pilot_007/train/train_b7b.py", "--config", f"{{WT}}/sft_dpo_inventory/pilot_010/train/configs_jq/JQ-V8-o{s}.yaml"]})
        deps = [f"file:{ck}/adapter_model.safetensors|{tid}"]
        cells = [pf_cell(model, f"pf2_v8_o{s}", k) for k in range(1, 5)]
        out.append({"id": f"PF-V8-o{s}", "type": "raw", "kind": f"pf2_jq_V8-o{s}_k4", "server": f"lora:{model}={ck}", "est": 35, "prio": 10 + i, "commit": commit,
                    "deps": deps, "cells": cells, "no_rerun": True, "outputs": pf_outputs(cells)})
        out.append({"id": f"HF-V8-o{s}", "type": "raw", "kind": f"hfinal_jq_V8-o{s}_k1", "server": f"lora:{model}={ck}", "est": 45, "prio": 20 + i, "commit": commit,
                    "deps": deps, "cells": [hf_cell(model, f"hfinal_v8_o{s}", 1)]})
    return sorted(out, key=lambda j: (j["prio"], j["id"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", required=True)
    a = ap.parse_args()
    if len(a.commit) != 40:
        raise SystemExit("--commit must be a full 40-hex commit")
    p = HERE / "JQ/jobs_jq.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = {"note": f"pilot_010 JQ(결정 269, PLAN_JQ). RR+NM8(V8) 새 seed 4개 학습 + PF2·H-final, 고정 커밋 {a.commit[:8]}. 판정 뒤 추가(사후).", "jobs": jobs(a.commit)}
    p.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps([(j["prio"], j["id"]) for j in body["jobs"]], ensure_ascii=False))


if __name__ == "__main__":
    main()
