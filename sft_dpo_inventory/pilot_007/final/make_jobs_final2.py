# -*- coding: utf-8 -*-
"""최종 판정 작업 표 2판(PLAN_FINAL_AMEND1): ``make_jobs_final.py``(고정본)의 사본 — 셀 실행기만 ``final/run_cell_final.py``(저장소 밖 gold를 받는 client 사본), 작업 ID PF2-*·L-final2.
원 설명: 최종 판정 작업 표·sampling seed(결정 214·215·216). PLAN_FINAL 고정 전에 커밋한다. scheduler8(GPU 0·1, Ollama GPU = GPU 2는 worker 아님)이 읽는다.

    python3 make_jobs_final2.py   # -> gpu/jobs_final2.json (sampling seed는 final/cell_seeds_final.json 그대로, 다시 쓰지 않음)

- PF-base: vLLM-base(Full prompt, 서버 ``b17408``), PF-cand: 후보 B2-F-o11(LoRA ``B2_F_o11`` = checkpoint-1811, 서버 ``lora:``) — 각각 protected_final_v1 120문항 k=8,
  ``run_cell6x.py``(동시 요청 8, PROTOCOL_v4 3절 sampling, 회차 seed S_k = 20261100 + k), ``--sealed``.
  셀·원문·실행 출력은 모두 ``/home/hwkim/sftdpo_work/protected_final_v1/{cells,raw,logs}``(700) 안에 ``umask 077``(600)로 — 저장소에 남는 작업 로그에는 내용이 없다.
  회차 하나라도 실패하면 작업 실패(실행 조건 위반이면 결과를 보기 전 이유를 기록하고 처음부터 한 번만 다시).
- L-final2: 지연 창(``final/latency_final.py``: base → 후보, 고정 30문항, 한 GPU), 두 셀의 마지막 회차 파일이 생긴 뒤(``file:`` — 셀 작업이 실패하면 건너뜀; 1판의 ``done:``은 실패에도 시작됐다), 다른 GPU가 빌 때까지 최대 25분 기다린 뒤.
  출력은 저장소 ``latency/final/``(protected_final_v1 아님), 원문은 ``training/generated/pilot_007/latency_raw/``(커밋 안 함).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P7 = HERE.parent
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
PFD = "/home/hwkim/sftdpo_work/protected_final_v1"
GOLD = f"{PFD}/pf1_gold.yaml"
CAND = {"name": "B2_F_o11", "ckpt": "/home/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-o11/checkpoint-1811"}
SEED_BASE, K = 20261100, 8


def cell_cmd(label, model):
    runs = " && ".join(
        f"{PY} {{WT}}/sft_dpo_inventory/pilot_007/final/run_cell_final.py --port {{PORT}} --model {model} --label {label} --k {k} --concurrency 8 "
        f"--grounding-target full --out-dir {PFD}/cells --raw-dir {PFD}/raw --seed-base {SEED_BASE} --gold {GOLD} --all-items --sealed "
        f">> {PFD}/logs/{label}.stdout 2>&1" for k in range(1, K + 1))
    return ["bash", "-c", f"umask 077 && mkdir -p {PFD}/cells {PFD}/raw {PFD}/logs && {runs} && echo '{label} k1-{K} done'"]


jobs = [
    {"id": "PF2-base", "type": "raw", "kind": "final_pf_base_k8", "server": "b17408", "est": 60, "prio": 1, "cmd": cell_cmd("pf_base", "base"), "outputs": []},
    {"id": "PF2-cand", "type": "raw", "kind": "final_pf_cand_B2-F-o11_k8", "server": f"lora:{CAND['name']}={CAND['ckpt']}", "est": 60, "prio": 1,
     "cmd": cell_cmd("pf_cand", CAND["name"]), "outputs": []},
]
lat_out = "/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_007/latency/final"
lat_raw = "/home/hwkim/assistant_univ/training/generated/pilot_007/latency_raw"
lat_wait = ("IDX=$(( {PORT} - 8620 )); ME=$(nvidia-smi -i $IDX --query-gpu=uuid --format=csv,noheader); "
            "for i in $(seq 1 100); do [ -z \"$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | grep -v \"$ME\")\" ] && break; sleep 15; done; ")
lat_cmd = lat_wait + (f"mkdir -p {lat_out} {lat_raw} && {PY} {{WT}}/sft_dpo_inventory/pilot_007/final/latency_final.py --port {{PORT}} --gpu-index $(( {{PORT}} - 8620 )) "
                      f"--f-model F --out-dir {lat_out} --raw-dir {lat_raw} --label-prefix latF")
jobs.append({"id": "L-final2", "type": "raw", "kind": "latency_base_cand", "server": f"lora:F={CAND['ckpt']}", "est": 30, "prio": 2,
             "deps": ["notrain", f"file:{PFD}/cells/pf_base_s{K}.json|PF2-base", f"file:{PFD}/cells/pf_cand_s{K}.json|PF2-cand"], "cmd": ["bash", "-c", lat_cmd], "outputs": [f"{lat_out}/latency_summary.json"]})
(P7 / "gpu/jobs_final2.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print([(j["id"], j["server"][:40]) for j in jobs])
